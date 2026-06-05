// FileUpload.jsx — Drag-and-drop / click file uploader

import { useCallback, useEffect, useMemo, useState } from "react";
import { uploadFile, listSessions, loadSession, deleteSession } from "../api";

const MANUAL_FORMAT_OPTIONS = [
  { value: "csv", label: "CSV (.csv)" },
  { value: "xlsx", label: "Excel (.xlsx)" },
  { value: "json", label: "JSON (.json)" },
  { value: "txt", label: "Text (.txt)" },
];

function buildManualSourceFilename(baseName, format) {
  const cleanFormat = String(format || "csv").toLowerCase().replace(/^\.+/, "") || "csv";
  const normalizedBase = String(baseName || "")
    .trim()
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, "")
    .replace(/\.+$/, "")
    .replace(/\s+/g, " ");

  const withoutExt = normalizedBase.replace(/\.[a-z0-9]+$/i, "").trim();
  const safeBase = withoutExt || "manual-entry";
  return `${safeBase}.${cleanFormat}`;
}

function _isJsonFile(file) {
  return typeof file?.name === "string" && file.name.toLowerCase().endsWith(".json");
}

function _extractSentenceText(item) {
  if (!item || typeof item !== "object") return "";
  return String(
    item.text || item.sentence_text || item.sentence || item.sentence_candidate || ""
  ).trim();
}

function _validateJsonUpload(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Uploaded JSON must be an object at the top level.");
  }

  const validateTriple = (triple, path) => {
    if (!triple || typeof triple !== "object" || Array.isArray(triple)) {
      throw new Error(`${path} must be an object.`);
    }
    const subject = String(triple.subject || "").trim();
    const predicate = String(triple.predicate || "").trim();
    const object = String(triple.object || "").trim();
    if (!subject || !predicate || !object) {
      throw new Error(`${path} must include non-empty subject, predicate, and object.`);
    }
  };

  const validateVersion = (version, path) => {
    if (!version || typeof version !== "object" || Array.isArray(version)) {
      throw new Error(`${path} must be an object.`);
    }
    if (!Array.isArray(version.triples) || version.triples.length === 0) {
      throw new Error(`${path} must contain at least one triple.`);
    }
    version.triples.forEach((triple, ti) => {
      validateTriple(triple, `${path}, triple #${ti + 1}`);
    });
  };

  if (Array.isArray(payload.sentence_groups)) {
    if (payload.sentence_groups.length === 0) {
      throw new Error("Uploaded JSON must contain at least one sentence group.");
    }
    payload.sentence_groups.forEach((group, gi) => {
      if (!group || typeof group !== "object" || Array.isArray(group)) {
        throw new Error(`Sentence group #${gi + 1} must be an object.`);
      }
      const sentenceText = _extractSentenceText(group);
      if (!sentenceText) {
        throw new Error(`Sentence group #${gi + 1} is missing required sentence text.`);
      }
      if (!Array.isArray(group.versions) || group.versions.length === 0) {
        throw new Error(`Sentence group #${gi + 1} must contain at least one version.`);
      }
      group.versions.forEach((version, vi) => {
        validateVersion(version, `Sentence group #${gi + 1}, version #${vi + 1}`);
      });
    });
    return;
  }

  if (!Array.isArray(payload.sentences) || payload.sentences.length === 0) {
    throw new Error("Uploaded JSON must contain a non-empty 'sentences' array.");
  }

  payload.sentences.forEach((sentence, si) => {
    if (!sentence || typeof sentence !== "object" || Array.isArray(sentence)) {
      throw new Error(`Sentence #${si + 1} must be an object.`);
    }
    const sentenceText = _extractSentenceText(sentence);
    if (!sentenceText) {
      throw new Error(`Sentence #${si + 1} is missing required sentence text.`);
    }
    if (!Array.isArray(sentence.triples) || sentence.triples.length === 0) {
      throw new Error(`Sentence #${si + 1} must contain at least one triple.`);
    }
    sentence.triples.forEach((triple, ti) => {
      validateTriple(triple, `Sentence #${si + 1}, triple #${ti + 1}`);
    });
  });
}

export default function FileUpload({ onUploadSuccess, onLoadSession, onStartManual, recentUploadSessionId }) {
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const [startMode, setStartMode] = useState("file");
  const [manualFilename, setManualFilename] = useState("manual-entry");
  const [manualFormat, setManualFormat] = useState("csv");

  const [sessions, setSessions]       = useState([]);
  const [resuming, setResuming]       = useState(null); // session_id being loaded
  const [deleting, setDeleting]       = useState(null); // session_id being deleted
  const [resumeError, setResumeError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [sessionFilter, setSessionFilter] = useState("all");
  const [collapsedSourceGroups, setCollapsedSourceGroups] = useState({});
  const [recentFocusAppliedFor, setRecentFocusAppliedFor] = useState(null);

  // Fetch saved sessions on mount
  useEffect(() => {
    listSessions()
      .then((list) => {
        // Sort newest first by uploaded_at
        const sorted = [...list].sort((a, b) =>
          b.uploaded_at.localeCompare(a.uploaded_at)
        );
        setSessions(sorted);
      })
      .catch(() => {}); // silently ignore if backend not ready
  }, []);

  useEffect(() => {
    if (!recentUploadSessionId) {
      setRecentFocusAppliedFor(null);
      return;
    }
    if (recentFocusAppliedFor === recentUploadSessionId) return;

    const recentSession = sessions.find((s) => s.session_id === recentUploadSessionId);
    if (!recentSession) return;

    setSessionFilter("mine");
    const sourceKey = recentSession.source_filename || "Unknown file";
    setCollapsedSourceGroups((prev) => ({
      ...prev,
      [sourceKey]: false,
    }));
    setRecentFocusAppliedFor(recentUploadSessionId);
  }, [recentUploadSessionId, recentFocusAppliedFor, sessions]);

  const handleResume = async (sessionMeta) => {
    const sessionId = sessionMeta?.session_id;

    if (!sessionId) return;

    setResumeError("");
    setResuming(sessionId);
    try {
      const session = await loadSession(sessionId);
      onLoadSession(session);
    } catch (e) {
      setResumeError(e?.response?.data?.detail || "Failed to load session.");
    } finally {
      setResuming(null);
    }
  };

  const handleDelete = async (sessionMeta) => {
    const sessionId = sessionMeta?.session_id;
    if (!sessionId || !sessionMeta?.is_owner) return;

    const ok = window.confirm("Delete this shared file? This cannot be undone.");
    if (!ok) return;

    setDeleteError("");
    setDeleting(sessionId);
    try {
      const result = await deleteSession(sessionId);
      const deletedIds = new Set(
        Array.isArray(result?.deleted_session_ids) && result.deleted_session_ids.length > 0
          ? result.deleted_session_ids
          : [sessionId]
      );
      setSessions((prev) => prev.filter((s) => !deletedIds.has(s.session_id)));
    } catch (e) {
      setDeleteError(e?.response?.data?.detail || "Failed to delete file.");
    } finally {
      setDeleting(null);
    }
  };

  const processFile = useCallback(
    async (file) => {
      if (!file) return;
      setError("");
      setLoading(true);
      try {
        if (_isJsonFile(file)) {
          const text = await file.text();
          let payload;
          try {
            payload = JSON.parse(text);
          } catch (err) {
            throw new Error("Uploaded JSON is not valid JSON.");
          }
          _validateJsonUpload(payload);
        }
        const data = await uploadFile(file);
        onUploadSuccess(data);
      } catch (e) {
        const msg =
          e?.response?.data?.detail || e.message || "Upload failed.";
        setError(typeof msg === "string" ? msg : JSON.stringify(msg));
      } finally {
        setLoading(false);
      }
    },
    [onUploadSuccess]
  );

  const onInputChange = (e) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  };

  const filteredSessions = sessions
    .filter((s) => {
      if (sessionFilter === "mine") return !!s.is_owner;
      if (sessionFilter === "others") return !s.is_owner;
      return true;
    });

  const groupedSessions = useMemo(() => {
    const grouped = new Map();
    filteredSessions.forEach((session) => {
      const sourceKey = session.source_filename || "Unknown file";
      if (!grouped.has(sourceKey)) {
        grouped.set(sourceKey, []);
      }
      grouped.get(sourceKey).push(session);
    });

    return [...grouped.entries()]
      .map(([sourceKey, sourceSessions]) => {
        const sortedSessions = [...sourceSessions].sort((a, b) =>
          (b.uploaded_at || "").localeCompare(a.uploaded_at || "")
        );
        const latestUploadedAt = sortedSessions[0]?.uploaded_at || "";

        return {
          sourceKey,
          sourceFilename: sourceKey,
          sessions: sortedSessions,
          latestUploadedAt,
          totalSessions: sortedSessions.length,
        };
      })
      .sort((a, b) => (b.latestUploadedAt || "").localeCompare(a.latestUploadedAt || ""))
      .slice(0, 5);
  }, [filteredSessions]);

  const toggleSourceGroup = (sourceKey) => {
    setCollapsedSourceGroups((prev) => ({
      ...prev,
      [sourceKey]: !prev[sourceKey],
    }));
  };

  return (
    <div className="max-w-xl mx-auto px-4 py-8 sm:py-12">
      <div className="w-full">

        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-indigo-600 to-blue-500 text-white text-3xl mb-4 shadow-xl shadow-indigo-100 select-none">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-.778.099-1.533.284-2.253" />
            </svg>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900 bg-gradient-to-r from-slate-900 via-indigo-950 to-blue-900 bg-clip-text text-transparent">
            Ontology Triple Grader
          </h1>
          <p className="mt-3 text-slate-500 text-sm max-w-md mx-auto leading-relaxed">
            Collaboratively review, grade, and refine natural language semantic triples with automated file processing or manual builder.
          </p>
        </div>

        {/* Start options switcher */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
          <button
            onClick={() => setStartMode("file")}
            className={[
              "relative group rounded-2xl border p-5 text-left transition-all duration-300 cursor-pointer overflow-hidden",
              startMode === "file"
                ? "border-indigo-500 bg-indigo-50/35 shadow-md shadow-indigo-100/30 ring-2 ring-indigo-500/10"
                : "border-slate-200 bg-white hover:border-indigo-300 hover:shadow-sm hover:translate-y-[-1px]",
            ].join(" ")}
          >
            <div className="flex items-center gap-3.5">
              <div className={`p-2.5 rounded-xl transition-colors duration-300 ${startMode === "file" ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 group-hover:bg-indigo-50 group-hover:text-indigo-600'}`}>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-bold text-slate-800">Option 1: Upload File</p>
                <p className="text-xs text-slate-500 mt-1 leading-normal">
                  CSV, Excel, or JSON formats
                </p>
              </div>
            </div>
          </button>
          
          <button
            onClick={() => setStartMode("manual")}
            className={[
              "relative group rounded-2xl border p-5 text-left transition-all duration-300 cursor-pointer overflow-hidden",
              startMode === "manual"
                ? "border-emerald-500 bg-emerald-50/35 shadow-md shadow-emerald-100/30 ring-2 ring-emerald-500/10"
                : "border-slate-200 bg-white hover:border-emerald-300 hover:shadow-sm hover:translate-y-[-1px]",
            ].join(" ")}
          >
            <div className="flex items-center gap-3.5">
              <div className={`p-2.5 rounded-xl transition-colors duration-300 ${startMode === "manual" ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-600 group-hover:bg-emerald-50 group-hover:text-emerald-600'}`}>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-bold text-slate-800">Option 2: Manual Builder</p>
                <p className="text-xs text-slate-500 mt-1 leading-normal">
                  Start fresh &amp; add manually
                </p>
              </div>
            </div>
          </button>
        </div>

        {startMode === "file" ? (
          <div className="mb-6 text-xs text-slate-600 bg-white border border-slate-200/80 rounded-2xl p-4 shadow-sm leading-relaxed">
            <div className="flex items-center gap-2 mb-2 font-semibold text-slate-700">
              <svg className="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 111.063.852l-.708 2.836a.75.75 0 001.063.852l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
              </svg>
              Expected File Format
            </div>
            <ul className="space-y-1.5 pl-6 list-disc text-slate-500">
              <li>Columns 1-3: <span className="font-medium text-slate-700">Subject, Predicate, Object</span> (one triple per row)</li>
              <li>Column 8: <span className="font-medium text-slate-700">Natural-Language Sentence</span> (can span multiple rows for grouped triples)</li>
              <li>Separators: Group sentences by inserting <span className="font-mono text-slate-600 bg-slate-100 px-1 py-0.5 rounded border border-slate-200">blank rows</span> or <span className="font-mono text-slate-600 bg-slate-100 px-1 py-0.5 rounded border border-slate-200">=======</span> dividers</li>
            </ul>
          </div>
        ) : (
          <div className="mb-6 text-xs text-slate-600 bg-white border border-slate-200/80 rounded-2xl p-4 shadow-sm leading-relaxed">
            <div className="flex items-center gap-2 mb-2 font-semibold text-emerald-800">
              <svg className="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
              </svg>
              Manual Mode Tips
            </div>
            <ul className="space-y-1.5 pl-6 list-disc text-slate-500">
              <li>Structure: Create custom sentences and insert triples in any order (above or below).</li>
              <li>Collaboration: Saved sessions are stored in the database, letting other graders vote and suggest edits.</li>
              <li>Flexibility: You can switch back to file upload mode at any point to load batches.</li>
            </ul>
          </div>
        )}

        {startMode === "file" ? (
          <label
            htmlFor="file-input"
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={[
              "group flex flex-col items-center justify-center w-full h-60 border-2 border-dashed rounded-2xl cursor-pointer transition-all duration-300 relative overflow-hidden bg-white",
              dragging
                ? "border-indigo-500 bg-indigo-50/40 scale-[1.01] shadow-lg shadow-indigo-100/50"
                : "border-slate-300 hover:border-indigo-500 hover:shadow-md hover:shadow-slate-100/70",
            ].join(" ")}
          >
            {loading ? (
              <div className="flex flex-col items-center gap-3">
                <div className="relative w-12 h-12">
                  <div className="absolute inset-0 border-4 border-indigo-200 rounded-full" />
                  <div className="absolute inset-0 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin" />
                </div>
                <span className="text-sm font-semibold text-slate-600">Parsing file and building triples…</span>
                <span className="text-xs text-slate-400">Please don't close this tab</span>
              </div>
            ) : (
              <>
                <div className="p-4 rounded-full bg-slate-50 text-slate-500 group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-colors duration-300 mb-3">
                  <svg className="w-10 h-10 transition-transform duration-300 group-hover:scale-110" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
                  </svg>
                </div>
                <p className="text-sm font-bold text-slate-700">
                  Drag &amp; drop your file here
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  or <span className="text-indigo-600 font-semibold underline group-hover:text-indigo-700">click to browse</span> your folders
                </p>
                
                <div className="flex items-center gap-2 mt-4 text-[10px] font-semibold text-slate-500 tracking-wider uppercase">
                  <span className="px-2 py-0.5 bg-slate-100 rounded-md border border-slate-200">CSV</span>
                  <span>·</span>
                  <span className="px-2 py-0.5 bg-slate-100 rounded-md border border-slate-200">XLSX</span>
                  <span>·</span>
                  <span className="px-2 py-0.5 bg-slate-100 rounded-md border border-slate-200">XLS</span>
                  <span>·</span>
                  <span className="px-2 py-0.5 bg-slate-100 rounded-md border border-slate-200">JSON</span>
                </div>
              </>
            )}
            <input
              id="file-input"
              type="file"
              accept=".csv,.xlsx,.xls,.json"
              className="hidden"
              onChange={onInputChange}
              disabled={loading}
            />
          </label>
        ) : (
          <div className="w-full rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="inline-flex p-3 rounded-full bg-emerald-50 text-emerald-600 mb-3">
              <svg className="w-8 h-8" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M11.42 15.17L17.25 21A2.67 2.67 0 1120.25 18l-5.83-5.83m-3 0a2.92 2.92 0 114.17 4.17m-4.17-4.17L10 14h-2V8h6v2l1.42 1.42M12 3a9 9 0 100 18 9 9 0 000-18z" />
              </svg>
            </div>
            <p className="text-base font-bold text-slate-800">Create Manual Grading Session</p>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto leading-relaxed">
              Design a custom ontology grading worksheet from scratch by creating sentences and triples.
            </p>
            
            <div className="mt-5 grid grid-cols-1 sm:grid-cols-[1fr_180px] gap-3 text-left max-w-lg mx-auto">
              <div>
                <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wide mb-1">
                  File Name
                </label>
                <input
                  type="text"
                  value={manualFilename}
                  onChange={(e) => setManualFilename(e.target.value)}
                  placeholder="e.g., software_ethics_round1"
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 text-sm text-slate-700 bg-slate-50/50 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-wide mb-1">
                  Format
                </label>
                <select
                  value={manualFormat}
                  onChange={(e) => setManualFormat(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 text-sm text-slate-700 bg-slate-50/50 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                >
                  {MANUAL_FORMAT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            
            <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4 max-w-lg mx-auto">
              <p className="text-xs text-slate-500">
                Target path: <span className="font-semibold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">{buildManualSourceFilename(manualFilename, manualFormat)}</span>
              </p>
              <button
                onClick={() => {
                  setError("");
                  onStartManual?.({
                    sourceFilename: buildManualSourceFilename(manualFilename, manualFormat),
                    sourceFormat: manualFormat,
                  });
                }}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm shadow-emerald-100 hover:shadow-md hover:scale-[1.01] active:scale-95 transition-all duration-200 cursor-pointer"
              >
                Start Builder
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
              </button>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-2xl text-xs text-red-700 flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0 text-red-600" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            <span className="font-semibold">{error}</span>
          </div>
        )}

        {/* ── Recent Sessions ── */}
        {sessions.length > 0 && (
          <div className="mt-8">
            <div className="flex items-center justify-between mb-3 gap-2">
              <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
                </svg>
                Recent Sessions
              </h2>
              <div className="flex items-center gap-1 bg-slate-100 rounded-xl p-1 shadow-inner border border-slate-200/50">
                <button
                  onClick={() => setSessionFilter("all")}
                  className={[
                    "px-3 py-1 text-xs font-bold rounded-lg transition-all duration-200 cursor-pointer",
                    sessionFilter === "all"
                      ? "bg-white text-slate-800 shadow-sm"
                      : "text-slate-500 hover:text-slate-800 hover:bg-white/50",
                  ].join(" ")}
                >
                  All
                </button>
                <button
                  onClick={() => setSessionFilter("mine")}
                  className={[
                    "px-3 py-1 text-xs font-bold rounded-lg transition-all duration-200 cursor-pointer",
                    sessionFilter === "mine"
                      ? "bg-emerald-600 text-white shadow-sm shadow-emerald-100"
                      : "text-slate-500 hover:text-slate-800 hover:bg-white/50",
                  ].join(" ")}
                >
                  My Files
                </button>
                <button
                  onClick={() => setSessionFilter("others")}
                  className={[
                    "px-3 py-1 text-xs font-bold rounded-lg transition-all duration-200 cursor-pointer",
                    sessionFilter === "others"
                      ? "bg-indigo-600 text-white shadow-sm shadow-indigo-100"
                      : "text-slate-500 hover:text-slate-800 hover:bg-white/50",
                  ].join(" ")}
                >
                  Other Users
                </button>
              </div>
            </div>
            
            <div className="space-y-3">
              {groupedSessions.map((group) => {
                const headerDate = group.latestUploadedAt
                  ? new Date(group.latestUploadedAt + "Z").toLocaleString([], {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "";
                const isCollapsed = !!collapsedSourceGroups[group.sourceKey];

                return (
                  <div key={group.sourceKey} className="bg-white border border-slate-200/80 rounded-2xl shadow-sm overflow-hidden hover:border-slate-300 transition-all duration-200">
                    <button
                      onClick={() => toggleSourceGroup(group.sourceKey)}
                      className="w-full text-left px-5 py-4 hover:bg-slate-50/50 transition-colors duration-200 flex items-center justify-between gap-4 cursor-pointer"
                    >
                      <div className="flex items-center gap-3.5 min-w-0">
                        <div className="p-2.5 rounded-xl bg-slate-100 text-slate-500 shrink-0">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                          </svg>
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-bold text-slate-800 truncate">
                            {group.sourceFilename}
                          </p>
                          <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
                            <span>{group.totalSessions} active session{group.totalSessions === 1 ? "" : "s"}</span>
                            {headerDate && (
                              <>
                                <span>•</span>
                                <span className="flex items-center gap-1">
                                  <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                                  </svg>
                                  {headerDate}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="p-1.5 rounded-lg bg-slate-50 text-slate-400 shrink-0 border border-slate-100">
                        <svg 
                          className={`w-4 h-4 transition-transform duration-300 ${isCollapsed ? '' : 'rotate-180'}`} 
                          fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                        </svg>
                      </div>
                    </button>

                    {!isCollapsed && (
                      <div className="border-t border-slate-100 bg-slate-50/40 p-3.5 space-y-2.5">
                        {group.sessions.map((s) => {
                          const dateStr = s.uploaded_at
                            ? new Date(s.uploaded_at + "Z").toLocaleString([], {
                                month: "short", day: "numeric",
                                hour: "2-digit", minute: "2-digit",
                              })
                            : "";
                          const isLoading = resuming === s.session_id;
                          const sessionType = s.is_owner ? "My File" : "Shared File";
                          const sessionTypeClass = s.is_owner
                            ? "bg-emerald-50 text-emerald-700 border-emerald-100"
                            : "bg-blue-50 text-blue-700 border-blue-200";
                          const ownerName = s.owner_name || "Unknown";
                          const avatarLetter = ownerName.trim().charAt(0).toUpperCase() || "U";
                          const hasWorkedOnSession = !s.is_owner && (
                            Boolean(s.my_has_activity) ||
                            Number(s.my_total_actions || 0) > 0 ||
                            Number(s.my_graded_triples || 0) > 0
                          );
                          const roleHint = s.is_owner
                            ? "Owner: Approve suggestions & manage structure."
                            : hasWorkedOnSession
                              ? "Collaborator: In progress grading sheet."
                              : "Collaborator: Open to start grading.";
                          const actionLabel = isLoading
                            ? "Loading…"
                            : s.is_owner
                              ? "Open File"
                              : hasWorkedOnSession
                                ? "Continue"
                                : "Open File";
                          const avgBadge = s.total_unique_graders > 0
                            ? `${s.total_unique_graders} grader${s.total_unique_graders === 1 ? "" : "s"} · Avg ${s.session_average_grade != null ? Number(s.session_average_grade).toFixed(2) : "—"}/10`
                            : null;
                          const isDeleting = deleting === s.session_id;
                          const isRecentUpload = recentUploadSessionId === s.session_id;
                          const deleteLabel = isDeleting ? "Deleting" : "Delete";

                          return (
                            <div
                              key={s.session_id}
                              className={[
                                "flex flex-col sm:flex-row sm:items-center justify-between bg-white border rounded-2xl p-4 transition-all duration-300 gap-3",
                                isRecentUpload
                                  ? "border-emerald-300 ring-4 ring-emerald-500/10 bg-emerald-50/30"
                                  : "border-slate-200/80 hover:border-indigo-300 hover:shadow-sm hover:shadow-indigo-50/30",
                              ].join(" ")}
                            >
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className={`text-[10px] font-bold border px-2 py-0.5 rounded-full uppercase tracking-wider ${sessionTypeClass}`}>
                                    {sessionType}
                                  </span>
                                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-100 bg-slate-50 px-2 py-0.5 text-slate-600 font-bold text-[10px]">
                                    <span className="w-4 h-4 rounded-full bg-slate-300 text-[9px] font-bold flex items-center justify-center text-slate-700 uppercase shrink-0">
                                      {avatarLetter}
                                    </span>
                                    {ownerName}
                                  </span>
                                  {isRecentUpload && s.is_owner && (
                                    <span className="inline-flex items-center rounded-lg border border-emerald-200 bg-emerald-100/80 px-2 py-0.5 text-emerald-800 font-bold text-[10px] uppercase tracking-wide">
                                      Just uploaded
                                    </span>
                                  )}
                                </div>
                                <p className="text-xs text-slate-400 mt-2 flex items-center gap-1">
                                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                  </svg>
                                  {s.total_sentences} sentence{s.total_sentences === 1 ? "" : "s"}
                                  {dateStr && <> &bull; {dateStr}</>}
                                </p>
                                <p className="text-[11px] text-slate-500 mt-1.5 leading-normal flex items-start gap-1">
                                  <svg className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
                                  </svg>
                                  {roleHint}
                                </p>
                                {avgBadge && (
                                  <p className="text-[11px] text-emerald-700 mt-2 font-bold flex items-center gap-1">
                                    <svg className="w-3.5 h-3.5 shrink-0 text-emerald-600" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0110 21a3.745 3.745 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.746 3.746 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.746 3.746 0 011.043 3.296A3.745 3.745 0 0121 12z" />
                                    </svg>
                                    {avgBadge}
                                  </p>
                                )}
                              </div>
                              <div className="shrink-0 flex items-center gap-2 sm:self-center mt-1 sm:mt-0 justify-end">
                                {s.is_owner && (
                                  <button
                                    onClick={() => handleDelete(s)}
                                    disabled={!!resuming || !!deleting}
                                    className="px-3.5 py-2 rounded-xl text-xs font-bold border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 hover:border-red-300 hover:text-red-800 active:scale-95 transition-all duration-200 disabled:opacity-50 whitespace-nowrap cursor-pointer inline-flex items-center gap-1"
                                  >
                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                    </svg>
                                    {deleteLabel}
                                  </button>
                                )}
                                <button
                                  onClick={() => handleResume(s)}
                                  disabled={!!resuming || !!deleting}
                                  className="px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-700 hover:to-blue-700 text-white shadow-sm hover:shadow active:scale-95 transition-all duration-200 disabled:opacity-50 whitespace-nowrap cursor-pointer inline-flex items-center gap-1.5"
                                >
                                  {actionLabel}
                                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                                  </svg>
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
              {groupedSessions.length === 0 && (
                <div className="text-xs text-slate-500 bg-white border border-slate-200/80 rounded-2xl px-4 py-3 text-center shadow-sm">
                  No sessions found in this category.
                </div>
              )}
            </div>
            {resumeError && (
              <p className="mt-2.5 text-xs font-semibold text-red-600 flex items-center gap-1">⚠ {resumeError}</p>
            )}
            {deleteError && (
              <p className="mt-2.5 text-xs font-semibold text-red-600 flex items-center gap-1">⚠ {deleteError}</p>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
