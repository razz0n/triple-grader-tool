// GradingForm.jsx — Main grading interface: one sentence at a time

import { useState, useMemo, useRef, useEffect } from "react";
import TripleCard from "./TripleCard";
import TripleSuggestions from "./TripleSuggestions";
import { saveSession, downloadSession, getAuthToken, addSuggestion, voteOnSuggestion, deleteSuggestion } from "../api";

const IDLE_AUTOSAVE_MS = 10 * 60 * 1000;

export default function GradingForm({ uploadData, onReset, currentUser }) {
  const {
    session_id: initialSessionId,
    source_filename,
    sentences: initialSentences,
    uploaded_at,
    resumed,
  } = uploadData;

  // Deep-clone sentences into local mutable state
  const [sentences, setSentences] = useState(() =>
    initialSentences.map((s) => ({
      ...s,
      suggestion: s.suggestion || "",
      triples: s.triples.map((t) => ({ 
        ...t, 
        grade: t.grade ?? null,
        completeness: t.completeness ?? null,
        relation: t.relation ?? 10,
        author: t.author || null,
        suggestions: t.suggestions || [],
      })),
    }))
  );

  const [currentIdx, setCurrentIdx]       = useState(0);
  // When resuming a saved session, the session is already saved on the server
  const [savedSessionId, setSavedSessionId] = useState(resumed ? initialSessionId : null);
  const [savedAt, setSavedAt]             = useState(resumed ? new Date() : null);
  const [saving, setSaving]               = useState(false);
  const [saveMsg, setSaveMsg]             = useState("");
  const [saveError, setSaveError]         = useState("");

  const [dlFmt, setDlFmt]           = useState("pdf");
  const [dlOpen, setDlOpen]         = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [dlError, setDlError]       = useState("");
  const dlRef                       = useRef(null);
  const idleTimerRef                = useRef(null);
  const hasUnsavedChangesRef        = useRef(false);
  const savingRef                   = useRef(false);
  const latestPayloadRef            = useRef(null);

  // Close download dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dlRef.current && !dlRef.current.contains(e.target)) setDlOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const total   = sentences.length;
  const current = sentences[currentIdx];

  // Compute live sentence grade for the current sentence
  const sentenceGrade = useMemo(() => {
    const grades = current.triples
      .map((t) => t.grade)
      .filter((g) => g !== null && g !== undefined);
    if (grades.length === 0) return null;
    if (grades.length < current.triples.length) return "partial";
    return (grades.reduce((a, b) => a + b, 0) / grades.length).toFixed(1);
  }, [current]);

  // Overall grading progress across ALL sentences
  const gradingProgress = useMemo(() => {
    let graded = 0;
    let totalT = 0;
    sentences.forEach((s) => {
      totalT += s.triples.length;
      graded += s.triples.filter(
        (t) => t.grade !== null && t.grade !== undefined
      ).length;
    });
    return {
      graded,
      total: totalT,
      pct: totalT > 0 ? Math.round((graded / totalT) * 100) : 0,
    };
  }, [sentences]);

  const handleGradeChange = (tripleId, grade) => {
    hasUnsavedChangesRef.current = true;
    setSentences((prev) =>
      prev.map((s, i) =>
        i !== currentIdx
          ? s
          : {
              ...s,
              triples: s.triples.map((t) =>
                t.id === tripleId ? { ...t, grade } : t
              ),
            }
      )
    );
  };

  const handleCompletenessChange = (tripleId, completeness) => {
    hasUnsavedChangesRef.current = true;
    setSentences((prev) =>
      prev.map((s, i) =>
        i !== currentIdx
          ? s
          : {
              ...s,
              triples: s.triples.map((t) =>
                t.id === tripleId ? { ...t, completeness } : t
              ),
            }
      )
    );
  };

  const handleRelationChange = (tripleId, relation) => {
    hasUnsavedChangesRef.current = true;
    setSentences((prev) =>
      prev.map((s, i) =>
        i !== currentIdx
          ? s
          : {
              ...s,
              triples: s.triples.map((t) =>
                t.id === tripleId ? { ...t, relation } : t
              ),
            }
      )
    );
  };

  const handleSuggestionChange = (value) => {
    hasUnsavedChangesRef.current = true;
    setSentences((prev) =>
      prev.map((s, i) => (i === currentIdx ? { ...s, suggestion: value } : s))
    );
  };

  const handleAddSuggestion = async (tripleId, suggestionData) => {
    // Ensure session is saved before adding suggestion
    if (!savedSessionId) {
      await handleSave();
    }
    try {
      const sessionId = savedSessionId || initialSessionId;
      await addSuggestion(
        sessionId,
        current.id,
        tripleId,
        suggestionData.subject,
        suggestionData.predicate,
        suggestionData.object,
        suggestionData.reason
      );
      
      // Update local state with the new suggestion
      setSentences((prev) =>
        prev.map((s, i) =>
          i !== currentIdx
            ? s
            : {
                ...s,
                triples: s.triples.map((t) =>
                  t.id === tripleId
                    ? {
                        ...t,
                        suggestions: [
                          ...(t.suggestions || []),
                          {
                            id: Math.random().toString(36).substr(2, 9),
                            author: currentUser?.name || "user",
                            subject: suggestionData.subject,
                            predicate: suggestionData.predicate,
                            object: suggestionData.object,
                            reason: suggestionData.reason || "",
                            created_at: new Date().toISOString(),
                            votes: {},
                          },
                        ],
                      }
                    : t
                ),
              }
        )
      );
      hasUnsavedChangesRef.current = true;
    } catch (err) {
      console.error("Error adding suggestion:", err);
      throw err;
    }
  };

  const handleVoteSuggestion = async (tripleId, suggestionId, vote) => {
    // Ensure session is saved before voting
    if (!savedSessionId) {
      await handleSave();
    }
    try {
      const sessionId = savedSessionId || initialSessionId;
      await voteOnSuggestion(
        sessionId,
        current.id,
        tripleId,
        suggestionId,
        vote
      );
      
      // Update local state with the vote
      setSentences((prev) =>
        prev.map((s, i) =>
          i !== currentIdx
            ? s
            : {
                ...s,
                triples: s.triples.map((t) =>
                  t.id === tripleId
                    ? {
                        ...t,
                        suggestions: t.suggestions.map((sug) =>
                          sug.id === suggestionId
                            ? {
                                ...sug,
                                votes: {
                                  ...sug.votes,
                                  [currentUser?.name || "user"]: vote,
                                },
                              }
                            : sug
                        ),
                      }
                    : t
                ),
              }
        )
      );
      hasUnsavedChangesRef.current = true;
    } catch (err) {
      console.error("Error voting on suggestion:", err);
      throw err;
    }
  };

  const handleDeleteSuggestion = async (tripleId, suggestionId) => {
    // Ensure session is saved before deleting
    if (!savedSessionId) {
      await handleSave();
    }
    try {
      const sessionId = savedSessionId || initialSessionId;
      await deleteSuggestion(
        sessionId,
        current.id,
        tripleId,
        suggestionId
      );
      
      // Update local state by removing the suggestion
      setSentences((prev) =>
        prev.map((s, i) =>
          i !== currentIdx
            ? s
            : {
                ...s,
                triples: s.triples.map((t) =>
                  t.id === tripleId
                    ? {
                        ...t,
                        suggestions: t.suggestions.filter((sug) => sug.id !== suggestionId),
                      }
                    : t
                ),
              }
        )
      );
      hasUnsavedChangesRef.current = true;
    } catch (err) {
      console.error("Error deleting suggestion:", err);
      throw err;
    }
  };

  const buildPayload = () => ({
    session_id:      savedSessionId || initialSessionId,
    source_filename: source_filename,
    uploaded_at:     uploaded_at,
    sentences: sentences.map((s) => {
      const grades = s.triples
        .map((t) => t.grade)
        .filter((g) => g != null);
      const avg =
        grades.length === s.triples.length && grades.length > 0
          ? parseFloat(
              (grades.reduce((a, b) => a + b, 0) / grades.length).toFixed(2)
            )
          : null;
      return { ...s, sentence_grade: avg };
    }),
  });

  useEffect(() => {
    latestPayloadRef.current = buildPayload();
  }, [savedSessionId, initialSessionId, source_filename, uploaded_at, sentences]);

  useEffect(() => {
    savingRef.current = saving;
  }, [saving]);

  useEffect(() => {
    const autosaveIfIdle = async () => {
      if (savingRef.current || !hasUnsavedChangesRef.current) return;

      savingRef.current = true;
      setSaving(true);
      setSaveError("");
      try {
        const result = await saveSession(latestPayloadRef.current);
        setSavedSessionId(result.session_id);
        setSavedAt(new Date());
        setSaveMsg("Autosaved after 10 minutes idle.");
        setTimeout(() => setSaveMsg(""), 3500);
        hasUnsavedChangesRef.current = false;
      } catch (e) {
        setSaveError(
          e?.response?.data?.detail || "Autosave failed. Is the backend running?"
        );
      } finally {
        savingRef.current = false;
        setSaving(false);
      }
    };

    const resetIdleTimer = () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      idleTimerRef.current = setTimeout(() => {
        void autosaveIfIdle();
      }, IDLE_AUTOSAVE_MS);
    };

    const events = ["mousedown", "mousemove", "keydown", "scroll", "touchstart"];
    events.forEach((evt) => window.addEventListener(evt, resetIdleTimer, { passive: true }));
    resetIdleTimer();

    return () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      events.forEach((evt) => window.removeEventListener(evt, resetIdleTimer));
    };
  }, []);

  const handleSave = async () => {
    savingRef.current = true;
    setSaving(true);
    setSaveMsg("");
    setSaveError("");
    try {
      const result = await saveSession(buildPayload());
      setSavedSessionId(result.session_id);
      setSavedAt(new Date());
      setSaveMsg("Session saved successfully!");
      setTimeout(() => setSaveMsg(""), 3500);
      hasUnsavedChangesRef.current = false;
    } catch (e) {
      setSaveError(
        e?.response?.data?.detail || "Save failed. Is the backend running?"
      );
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  const DL_FORMATS = [
    { value: "pdf",   label: "PDF",   icon: "📄" },
    { value: "word",  label: "Word",  icon: "📝" },
    { value: "excel", label: "Excel", icon: "📊" },
    { value: "csv",   label: "CSV",   icon: "⊞" },
    { value: "json",  label: "JSON",  icon: "{}" },
  ];

  const handleDownload = async (fmt) => {
    const target = fmt || dlFmt;
    setDlOpen(false);
    setDlError("");
    if (!savedSessionId) {
      setDlError("Save the session first.");
      return;
    }
    setDownloading(true);
    try {
      await downloadSession(savedSessionId, target);
    } catch (e) {
      setDlError(e?.message || "Download failed.");
    } finally {
      setDownloading(false);
    }
  };

  const gradeColor =
    sentenceGrade === null
      ? "text-slate-400"
      : sentenceGrade === "partial"
      ? "text-amber-600"
      : parseFloat(sentenceGrade) >= 7
      ? "text-green-700"
      : parseFloat(sentenceGrade) >= 4
      ? "text-amber-600"
      : "text-red-600";

  const previewHref = useMemo(() => {
    if (!savedSessionId) return undefined;
    const token = getAuthToken();
    if (!token) return `/api/preview/${savedSessionId}`;
    return `/api/preview/${savedSessionId}?token=${encodeURIComponent(token)}`;
  }, [savedSessionId]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">

      {/* ── Top bar ────────────────────────────────────────────────────── */}
      <div className="bg-white border-b border-slate-200 shadow-sm sticky top-0 z-20">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">

          {/* Logo + filename */}
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <div className="text-blue-700 text-xl font-bold select-none shrink-0">◈</div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-700 leading-tight">Ontology Triple Grader</div>
              <div className="text-xs text-slate-400 truncate max-w-48">{source_filename}</div>
            </div>
          </div>

          {/* Progress bar — hidden on small screens */}
          <div className="hidden lg:flex items-center gap-2 shrink-0">
            <span className="text-xs text-slate-500">
              {gradingProgress.graded}/{gradingProgress.total}
            </span>
            <div className="w-28 bg-slate-200 rounded-full h-2 overflow-hidden">
              <div className="bg-blue-600 h-2 rounded-full transition-all" style={{ width: `${gradingProgress.pct}%` }} />
            </div>
            <span className="text-xs font-semibold text-blue-700">{gradingProgress.pct}%</span>
          </div>

          {/* ── Save button + last-saved stamp ── */}
          <div className="flex items-center gap-2 shrink-0">
            {savedAt && (
              <div className="hidden sm:flex flex-col items-end">
                <span className="text-xs text-slate-400 leading-tight">Last saved</span>
                <span className="text-xs font-medium text-slate-500 leading-tight tabular-nums">
                  {savedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                </span>
              </div>
            )}
            <div className="flex flex-col items-end">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-700 text-white hover:bg-blue-800 active:scale-95 transition-all disabled:opacity-50 shadow-sm whitespace-nowrap"
              >
                {saving ? "Saving…" : "💾 Save"}
              </button>
              {saveError && <span className="text-xs text-red-500 mt-0.5 max-w-28 text-right leading-tight">{saveError}</span>}
            </div>
          </div>

          {/* ── Download split button ── */}
          <div className="relative shrink-0" ref={dlRef}>
            <div className="flex rounded-lg overflow-hidden shadow-sm border border-green-600">
              {/* Main: download in selected format */}
              <button
                onClick={() => handleDownload()}
                disabled={downloading || !savedSessionId}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold bg-green-600 text-white hover:bg-green-700 active:scale-95 transition-all disabled:opacity-40 whitespace-nowrap"
              >
                {downloading
                  ? "…"
                  : "⬇ Download"}
              </button>
              {/* Chevron: open format picker */}
              <button
                onClick={() => setDlOpen((o) => !o)}
                disabled={downloading}
                className="px-2 py-1.5 text-xs font-bold bg-green-600 text-white hover:bg-green-700 border-l border-green-500 transition-all disabled:opacity-40"
                aria-label="Choose download format"
              >
                {dlOpen ? "▲" : "▼"}
              </button>
            </div>

            {/* Dropdown */}
            {dlOpen && (
              <div className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-36 z-50">
                {DL_FORMATS.map((f) => (
                  <button
                    key={f.value}
                    onClick={() => { setDlFmt(f.value); setDlOpen(false); }}
                    className={[
                      "w-full text-left flex items-center gap-2 px-4 py-2 text-sm transition-colors",
                      f.value === dlFmt
                        ? "bg-green-50 text-green-700 font-semibold"
                        : "text-slate-700 hover:bg-slate-50",
                    ].join(" ")}
                  >
                    <span>{f.icon}</span>
                    {f.label}
                    {f.value === dlFmt && <span className="ml-auto text-green-500 text-xs">✔</span>}
                  </button>
                ))}
              </div>
            )}

            {dlError && (
              <p className="absolute right-0 top-full mt-8 text-xs text-red-500 whitespace-nowrap bg-white border border-red-200 rounded-lg px-2 py-1 shadow">
                {dlError}
              </p>
            )}
          </div>

          {/* ── View Online ── */}
          <a
            href={previewHref}
            target="_blank"
            rel="noopener noreferrer"
            onClick={!savedSessionId ? (e) => e.preventDefault() : undefined}
            className={[
              "flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all shrink-0 whitespace-nowrap",
              savedSessionId
                ? "border-slate-300 text-slate-600 hover:border-blue-400 hover:text-blue-700 hover:bg-blue-50"
                : "border-slate-200 text-slate-300 cursor-not-allowed",
            ].join(" ")}
            title={savedSessionId ? "Preview graded report in a new tab" : "Save the session first"}
          >
            👁 View
          </a>

          {/* New File */}
          <button
            onClick={onReset}
            className="text-xs text-slate-500 hover:text-red-600 transition-colors px-2 py-1 rounded-lg hover:bg-red-50 shrink-0 whitespace-nowrap"
          >
            ✕ New File
          </button>
        </div>

        {/* Inline status bar on small screens */}
        {!savedSessionId && (
          <div className="lg:hidden px-4 pb-2">
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-slate-200 rounded-full h-1.5 overflow-hidden">
                <div className="bg-blue-600 h-1.5 rounded-full transition-all" style={{ width: `${gradingProgress.pct}%` }} />
              </div>
              <span className="text-xs text-blue-700 font-semibold">{gradingProgress.pct}%</span>
            </div>
          </div>
        )}
      </div>

      {/* ── Main content ───────────────────────────────────────────────── */}
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">

        {/* Sentence card */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="bg-blue-700 text-white text-xs font-bold px-3 py-1 rounded-full">
                {currentIdx + 1} / {total}
              </span>
              <span className="text-sm text-slate-500 font-medium">Sentence</span>
            </div>

            {/* Grade badge */}
            <div className={`text-right ${gradeColor}`}>
              {sentenceGrade === null ? (
                <span className="text-xs italic text-slate-400">
                  No triples graded
                </span>
              ) : sentenceGrade === "partial" ? (
                <span className="text-xs font-semibold">Grading incomplete</span>
              ) : (
                <div className="flex flex-col items-end">
                  <span className="text-2xl font-bold leading-none">
                    {sentenceGrade}
                  </span>
                  <span className="text-xs">/ 10 avg</span>
                </div>
              )}
            </div>
          </div>

          {/* Sentence text */}
          <blockquote className="text-base text-slate-800 font-medium leading-relaxed border-l-4 border-blue-300 pl-4 bg-blue-50/40 py-2 pr-2 rounded-r-xl">
            {current.text}
          </blockquote>

          {/* Navigation arrows */}
          <div className="flex items-center justify-between mt-5">
            <button
              onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
              disabled={currentIdx === 0}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              ← Previous
            </button>

            {/* Dot navigator */}
            <div className="hidden sm:flex gap-1 flex-wrap justify-center max-w-xs">
              {sentences.map((s, i) => {
                const allGraded = s.triples.every((t) => t.grade !== null);
                const anyGraded = s.triples.some((t) => t.grade !== null);
                return (
                  <button
                    key={s.id}
                    onClick={() => setCurrentIdx(i)}
                    title={`Sentence ${i + 1}`}
                    className={[
                      "w-3 h-3 rounded-full transition-all",
                      i === currentIdx
                        ? "bg-blue-700 scale-125"
                        : allGraded
                        ? "bg-green-500"
                        : anyGraded
                        ? "bg-amber-400"
                        : "bg-slate-300 hover:bg-slate-400",
                    ].join(" ")}
                  />
                );
              })}
            </div>

            <button
              onClick={() =>
                setCurrentIdx((i) => Math.min(total - 1, i + 1))
              }
              disabled={currentIdx === total - 1}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              Next →
            </button>
          </div>
        </div>

        {/* Triples */}
        <div>
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
            Triples ({current.triples.length})
          </h2>
          <div className="space-y-3">
            {current.triples.map((triple) => (
              <div key={triple.id}>
                <TripleCard
                  triple={triple}
                  grade={triple.grade}
                  completeness={triple.completeness}
                  relation={triple.relation}
                  author={triple.author}
                  onChange={(grade) => handleGradeChange(triple.id, grade)}
                  onCompletenessChange={(completeness) => handleCompletenessChange(triple.id, completeness)}
                  onRelationChange={(relation) => handleRelationChange(triple.id, relation)}
                />
                <TripleSuggestions
                  triple={triple}
                  currentUser={currentUser}
                  onAddSuggestion={(data) => handleAddSuggestion(triple.id, data)}
                  onVoteSuggestion={(suggestionId, vote) => handleVoteSuggestion(triple.id, suggestionId, vote)}
                  onDeleteSuggestion={(suggestionId) => handleDeleteSuggestion(triple.id, suggestionId)}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Suggestion */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
          <label className="block text-sm font-semibold text-slate-600 mb-2">
            Suggestion / Comment for this Sentence
          </label>
          <textarea
            value={current.suggestion}
            onChange={(e) => handleSuggestionChange(e.target.value)}
            rows={3}
            placeholder="Add any suggestions or notes about the quality, accuracy or completeness of the triples for this sentence…"
            className="w-full text-sm text-slate-700 border border-slate-200 rounded-xl p-3 resize-none focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-400 placeholder:text-slate-300"
          />
        </div>

        <div className="h-8" />
      </div>
    </div>
  );
}
