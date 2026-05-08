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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center p-6">
      <div className="w-full max-w-xl">

        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-700 text-white text-3xl mb-4 shadow-lg select-none">
            ◈
          </div>
          <h1 className="text-3xl font-bold text-slate-800">
            Ontology Triple Grader
          </h1>
          <p className="mt-2 text-slate-500 text-sm">
            Choose how to start: upload a file or manually add sentences and triples.
          </p>
        </div>

        {/* Start options */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
          <button
            onClick={() => setStartMode("file")}
            className={[
              "rounded-xl border px-4 py-3 text-left transition-all",
              startMode === "file"
                ? "border-blue-500 bg-blue-50 shadow-sm"
                : "border-slate-200 bg-white hover:border-blue-300",
            ].join(" ")}
          >
            <p className="text-sm font-semibold text-slate-800">Option 1: Upload File</p>
            <p className="text-xs text-slate-500 mt-1">Parse CSV/Excel, then review and clean.</p>
          </button>
          <button
            onClick={() => setStartMode("manual")}
            className={[
              "rounded-xl border px-4 py-3 text-left transition-all",
              startMode === "manual"
                ? "border-emerald-500 bg-emerald-50 shadow-sm"
                : "border-slate-200 bg-white hover:border-emerald-300",
            ].join(" ")}
          >
            <p className="text-sm font-semibold text-slate-800">Option 2: Manual Entry</p>
            <p className="text-xs text-slate-500 mt-1">Start from scratch and add sentences/triples manually.</p>
          </button>
        </div>

        {startMode === "file" ? (
          <div className="mb-4 text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-xl p-3 leading-relaxed">
            <p className="font-semibold text-slate-600 mb-1">Expected file format</p>
            <p>• Col 1–3: Subject · Predicate · Object (one triple per row)</p>
            <p>• Col 8: Natural-language sentence (may span multiple rows per group)</p>
            <p>• Groups are separated by blank rows or ======= divider lines</p>
          </div>
        ) : (
          <div className="mb-4 text-xs text-slate-500 bg-emerald-50 border border-emerald-200 rounded-xl p-3 leading-relaxed">
            <p className="font-semibold text-emerald-800 mb-1">Manual mode tips</p>
            <p>• Add sentences in any order, including inserting above or below existing ones.</p>
            <p>• Add one or many triples per sentence before starting grading.</p>
            <p>• Choose a filename and format below; after saving, everyone collaborates on this same shared file.</p>
            <p>• You can still return and upload a file at any time.</p>
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
              "flex flex-col items-center justify-center w-full h-56 border-2 border-dashed rounded-2xl cursor-pointer transition-all",
              dragging
                ? "border-blue-500 bg-blue-50 scale-[1.01]"
                : "border-slate-300 bg-white hover:border-blue-400 hover:bg-blue-50/40",
            ].join(" ")}
          >
            {loading ? (
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-slate-500">Parsing file…</span>
              </div>
            ) : (
              <>
                <div className="text-5xl mb-3 select-none">📂</div>
                <p className="text-sm font-semibold text-slate-600">
                  Drag &amp; drop your file here
                </p>
                <p className="text-xs text-slate-400 mt-1">or click to browse</p>
                <p className="text-xs text-slate-400 mt-3 bg-slate-100 px-3 py-1 rounded-full">
                  CSV · XLSX · XLS
                </p>
              </>
            )}
            <input
              id="file-input"
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={onInputChange}
              disabled={loading}
            />
          </label>
        ) : (
          <div className="w-full rounded-2xl border border-emerald-200 bg-white p-6 text-center shadow-sm">
            <div className="text-4xl mb-2 select-none">✍</div>
            <p className="text-base font-semibold text-slate-800">Manual Sentence and Triple Builder</p>
            <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
              Open the manual page to add sentences and triples in your preferred order, then continue to grading.
            </p>
            <div className="mt-4 grid grid-cols-1 sm:grid-cols-[1fr_180px] gap-2 text-left max-w-lg mx-auto">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">
                  File name
                </label>
                <input
                  type="text"
                  value={manualFilename}
                  onChange={(e) => setManualFilename(e.target.value)}
                  placeholder="e.g., software_ethics_round1"
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-300"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">
                  Format
                </label>
                <select
                  value={manualFormat}
                  onChange={(e) => setManualFormat(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-300"
                >
                  {MANUAL_FORMAT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Will be saved as: <span className="font-semibold text-slate-700">{buildManualSourceFilename(manualFilename, manualFormat)}</span>
            </p>
            <button
              onClick={() => {
                setError("");
                onStartManual?.({
                  sourceFilename: buildManualSourceFilename(manualFilename, manualFormat),
                  sourceFormat: manualFormat,
                });
              }}
              className="mt-4 px-4 py-2 rounded-xl text-sm font-semibold bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
            >
              Start Manual Entry →
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
            ⚠ {error}
          </div>
        )}

        {/* ── Recent Sessions ── */}
        {sessions.length > 0 && (
          <div className="mt-6">
            <div className="flex items-center justify-between mb-2 gap-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Recent Sessions
              </p>
              <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-lg p-0.5 shadow-sm">
                <button
                  onClick={() => setSessionFilter("all")}
                  className={[
                    "px-2 py-1 text-[11px] font-semibold rounded-md transition-colors",
                    sessionFilter === "all"
                      ? "bg-slate-700 text-white"
                      : "text-slate-600 hover:bg-slate-100",
                  ].join(" ")}
                >
                  All
                </button>
                <button
                  onClick={() => setSessionFilter("mine")}
                  className={[
                    "px-2 py-1 text-[11px] font-semibold rounded-md transition-colors",
                    sessionFilter === "mine"
                      ? "bg-green-700 text-white"
                      : "text-slate-600 hover:bg-slate-100",
                  ].join(" ")}
                >
                  My files
                </button>
                <button
                  onClick={() => setSessionFilter("others")}
                  className={[
                    "px-2 py-1 text-[11px] font-semibold rounded-md transition-colors",
                    sessionFilter === "others"
                      ? "bg-amber-600 text-white"
                      : "text-slate-600 hover:bg-slate-100",
                  ].join(" ")}
                >
                  Other users
                </button>
              </div>
            </div>
            <div className="space-y-2">
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
                  <div key={group.sourceKey} className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                    <button
                      onClick={() => toggleSourceGroup(group.sourceKey)}
                      className="w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-slate-800 truncate">
                            {group.sourceFilename}
                          </p>
                          <p className="text-xs text-slate-500 mt-0.5">
                            {group.totalSessions} shared session{group.totalSessions === 1 ? "" : "s"}
                            {headerDate && <> &bull; Latest {headerDate}</>}
                          </p>
                        </div>
                        <span className="text-xs font-semibold text-slate-600">
                          {isCollapsed ? "Show" : "Hide"}
                        </span>
                      </div>
                    </button>

                    {!isCollapsed && (
                      <div className="border-t border-slate-100 bg-slate-50/60 p-2 space-y-2">
                        {group.sessions.map((s) => {
                          const dateStr = s.uploaded_at
                            ? new Date(s.uploaded_at + "Z").toLocaleString([], {
                                month: "short", day: "numeric",
                                hour: "2-digit", minute: "2-digit",
                              })
                            : "";
                          const isLoading = resuming === s.session_id;
                          const sessionType = s.is_owner ? "My file" : "Shared file";
                          const sessionTypeClass = s.is_owner
                            ? "bg-emerald-100 text-emerald-700 border-emerald-200"
                            : "bg-blue-100 text-blue-700 border-blue-200";
                          const ownerName = s.owner_name || "Unknown";
                          const hasWorkedOnSession = !s.is_owner && (
                            Boolean(s.my_has_activity) ||
                            Number(s.my_total_actions || 0) > 0 ||
                            Number(s.my_graded_triples || 0) > 0
                          );
                          const roleHint = s.is_owner
                            ? "You own this file. You can suggest, vote, and approve suggestions, but you do not grade."
                            : hasWorkedOnSession
                              ? "You can continue grading, commenting, and suggesting edits. The owner handles approvals."
                              : "You can grade, suggest edits, and vote. The owner handles approvals.";
                          const actionLabel = isLoading
                            ? "Loading…"
                            : s.is_owner
                              ? "▶ Open"
                              : hasWorkedOnSession
                                ? "▶ Continue"
                                : "▶ Open";
                          const avgBadge = s.total_unique_graders > 0
                            ? `${s.total_unique_graders} grader${s.total_unique_graders === 1 ? "" : "s"} • Avg ${s.session_average_grade != null ? Number(s.session_average_grade).toFixed(2) : "—"}/10`
                            : null;
                          const isDeleting = deleting === s.session_id;
                          const isRecentUpload = recentUploadSessionId === s.session_id;
                          const deleteLabel = isDeleting ? "Deleting…" : "Delete File";

                          return (
                            <div
                              key={s.session_id}
                              className={[
                                "flex items-center justify-between bg-white border rounded-lg px-3 py-2.5 transition-all",
                                isRecentUpload
                                  ? "border-emerald-300 ring-2 ring-emerald-200 bg-emerald-50/40"
                                  : "border-slate-200 hover:border-blue-300 hover:bg-blue-50/30",
                              ].join(" ")}
                            >
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className={`text-[10px] font-semibold border px-2 py-0.5 rounded-full ${sessionTypeClass}`}>
                                    {sessionType}
                                  </span>
                                  <span className="inline-flex items-center gap-1 rounded-md border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-indigo-700 font-semibold text-[10px]">
                                    <span className="text-[11px]">{ownerName}</span>
                                  </span>
                                  {isRecentUpload && s.is_owner && (
                                    <span className="inline-flex items-center rounded-md border border-emerald-200 bg-emerald-100 px-1.5 py-0.5 text-emerald-800 font-semibold text-[10px]">
                                      Just uploaded
                                    </span>
                                  )}
                                </div>
                                <p className="text-xs text-slate-500 mt-1">
                                  {s.total_sentences} sentences
                                  {dateStr && <> &bull; {dateStr}</>}
                                </p>
                                <p className="text-[11px] text-slate-500 mt-1">
                                  {roleHint}
                                </p>
                                {avgBadge && (
                                  <p className="text-[11px] text-emerald-700 mt-1 font-semibold">
                                    {avgBadge}
                                  </p>
                                )}
                              </div>
                              <div className="ml-3 shrink-0 flex items-center gap-2">
                                {s.is_owner && (
                                  <button
                                    onClick={() => handleDelete(s)}
                                    disabled={!!resuming || !!deleting}
                                    className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 active:scale-95 transition-all disabled:opacity-50 whitespace-nowrap"
                                  >
                                    {deleteLabel}
                                  </button>
                                )}
                                <button
                                  onClick={() => handleResume(s)}
                                  disabled={!!resuming || !!deleting}
                                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-700 text-white hover:bg-blue-800 active:scale-95 transition-all disabled:opacity-50 whitespace-nowrap"
                                >
                                  {actionLabel}
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
                <div className="text-xs text-slate-500 bg-white border border-slate-200 rounded-xl px-3 py-2">
                  No sessions in this filter.
                </div>
              )}
            </div>
            {resumeError && (
              <p className="mt-2 text-xs text-red-600">⚠ {resumeError}</p>
            )}
            {deleteError && (
              <p className="mt-2 text-xs text-red-600">⚠ {deleteError}</p>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
