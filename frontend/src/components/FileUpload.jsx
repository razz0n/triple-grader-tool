import { useCallback, useEffect, useMemo, useState } from "react";
import { uploadFile, listSessions, loadSession, deleteSession } from "../api";
import { motion, AnimatePresence } from "framer-motion";
import { useDialog } from "./CustomDialog";
import {
  UploadCloud,
  FileSpreadsheet,
  FileCode,
  FileText,
  Edit,
  Info,
  Trash2,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Folder,
  Calendar,
  User,
  GraduationCap,
  Clock,
  CheckCircle,
  AlertCircle
} from "lucide-react";

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
  const { showAlert, showConfirm } = useDialog();
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [startMode, setStartMode] = useState("file");
  const [manualFilename, setManualFilename] = useState("manual-entry");
  const [manualFormat, setManualFormat] = useState("csv");

  const [sessions, setSessions] = useState([]);
  const [resuming, setResuming] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [resumeError, setResumeError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [sessionFilter, setSessionFilter] = useState("all");
  const [collapsedSourceGroups, setCollapsedSourceGroups] = useState({});
  const [recentFocusAppliedFor, setRecentFocusAppliedFor] = useState(null);

  // Fetch saved sessions on mount and poll every 30 seconds
  useEffect(() => {
    const fetchSessions = () => {
      listSessions()
        .then((list) => {
          const sorted = [...list].sort((a, b) =>
            b.uploaded_at.localeCompare(a.uploaded_at)
          );
          setSessions(sorted);
        })
        .catch(() => { });
    };

    fetchSessions();
    const interval = setInterval(fetchSessions, 30000);
    return () => clearInterval(interval);
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

    console.log('[FileUpload] handleResume called for session:', sessionId);
    setResumeError("");
    setResuming(sessionId);
    try {
      const session = await loadSession(sessionId);
      console.log('[FileUpload] loadSession succeeded:', session?.session_id, 'sentences:', session?.sentences?.length);
      onLoadSession(session);
    } catch (e) {
      const errMsg = e?.response?.data?.detail || e?.message || "Failed to load session.";
      console.error('[FileUpload] loadSession error:', e);
      setResumeError(errMsg);
      showAlert(`Error loading session: ${errMsg}`, "Failed to Load Session");
    } finally {
      setResuming(null);
    }
  };

  const handleDelete = async (sessionMeta) => {
    const sessionId = sessionMeta?.session_id;
    if (!sessionId || !sessionMeta?.is_owner) return;

    const ok = await showConfirm("Delete this shared file? This cannot be undone.", "Delete Shared File", "Delete", "Cancel");
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
          if (Array.isArray(payload)) {
            const firstItem = payload[0];
            const isFlatTriples = firstItem && typeof firstItem === "object" && ("subject" in firstItem) && ("predicate" in firstItem) && ("object" in firstItem);
            
            if (isFlatTriples) {
              const groupedSentences = [];
              const sentenceIndex = {};
              
              payload.forEach((item, idx) => {
                if (!item || typeof item !== "object") return;
                const sText = String(
                  item.sentence || item.text || item.sentence_text || item.sentence_candidate || ""
                ).trim() || `Untitled Sentence ${idx + 1}`;
                
                const tripleObj = {
                  id: String(item.id || `tpl-${idx}-${Date.now()}`),
                  subject: String(item.subject || "").trim(),
                  predicate: String(item.predicate || "").trim(),
                  object: String(item.object || "").trim(),
                };
                
                if (sText in sentenceIndex) {
                  const targetIdx = sentenceIndex[sText];
                  groupedSentences[targetIdx].triples.push(tripleObj);
                } else {
                  const newSent = {
                    text: sText,
                    triples: [tripleObj]
                  };
                  sentenceIndex[sText] = groupedSentences.length;
                  groupedSentences.push(newSent);
                }
              });
              
              payload = { sentences: groupedSentences };
            } else {
              const isGroup = payload.length > 0 && payload[0] && typeof payload[0] === "object" && ("versions" in payload[0]);
              if (isGroup) {
                payload = { sentence_groups: payload };
              } else {
                payload = { sentences: payload };
              }
            }
          }
          _validateJsonUpload(payload);
        }
        const data = await uploadFile(file);
        onUploadSuccess(data);
      } catch (e) {
        const msg = e?.response?.data?.detail || e.message || "Upload failed.";
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

  const filteredSessions = sessions.filter((s) => {
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
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="max-w-2xl mx-auto px-4 py-8 sm:py-12"
    >
      <div className="w-full">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-600 to-indigo-500 text-white shadow-lg shadow-indigo-500/20 mb-4 select-none">
            <UploadCloud size={28} className="animate-pulse" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-800 dark:text-white bg-gradient-to-r from-slate-900 to-slate-700 dark:from-white dark:to-slate-300 bg-clip-text text-transparent">
            Ontology Triple Grader
          </h1>
          <p className="mt-2 text-slate-500 dark:text-slate-400 text-xs sm:text-sm max-w-md mx-auto leading-relaxed">
            Collaboratively review, grade, and refine semantic triples with automated file processing or a fresh manual builder session.
          </p>
        </div>

        {/* Mode Select Buttons */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
          <button
            onClick={() => setStartMode("file")}
            className={`flex items-center gap-4 rounded-xl border p-4 text-left transition-all duration-200 cursor-pointer ${startMode === "file"
                ? "border-indigo-600 bg-indigo-50/20 dark:bg-indigo-950/20 shadow-sm ring-2 ring-indigo-500/10"
                : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-indigo-400"
              }`}
          >
            <div
              className={`p-2 rounded-xl transition-colors duration-200 ${startMode === "file" ? "bg-indigo-600 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500"
                }`}
            >
              <UploadCloud size={18} />
            </div>
            <div>
              <p className="text-xs font-bold text-slate-700 dark:text-slate-200 uppercase tracking-wide">
                Option 1: Upload File
              </p>
              <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
                CSV, Excel, or JSON formats
              </p>
            </div>
          </button>

          <button
            onClick={() => setStartMode("manual")}
            className={`flex items-center gap-4 rounded-xl border p-4 text-left transition-all duration-200 cursor-pointer ${startMode === "manual"
                ? "border-indigo-600 bg-indigo-50/20 dark:bg-indigo-950/20 shadow-sm ring-2 ring-indigo-500/10"
                : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-indigo-400"
              }`}
          >
            <div
              className={`p-2 rounded-xl transition-colors duration-200 ${startMode === "manual" ? "bg-indigo-600 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500"
                }`}
            >
              <Edit size={18} />
            </div>
            <div>
              <p className="text-xs font-bold text-slate-700 dark:text-slate-200 uppercase tracking-wide">
                Option 2: Manual Builder
              </p>
              <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
                Start fresh and write manually
              </p>
            </div>
          </button>
        </div>

        {/* Informative Tips Panel */}
        <div className="mb-6 p-4 bg-slate-100/50 dark:bg-slate-900/50 border border-slate-200/50 dark:border-slate-800/50 rounded-xl leading-normal text-xs text-slate-600 dark:text-slate-300">
          <div className="flex items-center gap-2 mb-2 font-bold text-slate-700 dark:text-slate-200">
            <Info size={16} className="text-indigo-500" />
            {startMode === "file" ? "Expected Upload Format" : "Manual Builder Mode Overview"}
          </div>
          {startMode === "file" ? (
            <ul className="space-y-1 pl-5 list-disc text-slate-500 dark:text-slate-400 text-[11px]">
              <li>
                Columns 1-3: <span className="font-semibold text-slate-700 dark:text-slate-300">Subject, Predicate, Object</span> (one triple per row)
              </li>
              <li>
                Column 8: <span className="font-semibold text-slate-700 dark:text-slate-300">Sentence Text</span> (grouped automatically for matching sentences)
              </li>
              <li>
                Grouping: Add <span className="font-mono bg-slate-200 dark:bg-slate-800 px-1 py-0.5 rounded border border-slate-300 dark:border-slate-700">blank lines</span> or <span className="font-mono bg-slate-200 dark:bg-slate-800 px-1 py-0.5 rounded border border-slate-300 dark:border-slate-700">=======</span> dividers in your spreadsheet.
              </li>
            </ul>
          ) : (
            <ul className="space-y-1 pl-5 list-disc text-slate-500 dark:text-slate-400 text-[11px]">
              <li>Create sentences manually, then construct custom triples under them dynamically.</li>
              <li>Collaborators can access shared sessions, grading values, and suggesting revisions.</li>
              <li>Switch back to upload mode at any point to load spreadsheet batches.</li>
            </ul>
          )}
        </div>

        {/* Upload Action / Form Card */}
        <AnimatePresence mode="wait">
          {startMode === "file" ? (
            <motion.label
              key="file-uploader"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.2 }}
              htmlFor="file-input"
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={`group flex flex-col items-center justify-center w-full h-56 border-2 border-dashed rounded-2xl cursor-pointer transition-all duration-200 bg-white dark:bg-slate-900 ${dragging
                  ? "border-indigo-600 bg-indigo-50/20 dark:bg-indigo-950/20 shadow-md"
                  : "border-slate-200 dark:border-slate-800 hover:border-indigo-500 hover:bg-slate-50/50 dark:hover:bg-slate-900/50"
                }`}
            >
              {loading ? (
                <div className="flex flex-col items-center gap-3">
                  <div className="w-10 h-10 border-4 border-indigo-200 dark:border-indigo-900 border-t-indigo-600 rounded-full animate-spin" />
                  <span className="text-xs font-semibold text-slate-600 dark:text-slate-300">
                    Parsing file and structuring triples...
                  </span>
                </div>
              ) : (
                <>
                  <div className="p-3.5 rounded-full bg-slate-50 dark:bg-slate-800 text-slate-400 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors mb-3">
                    <UploadCloud size={32} />
                  </div>
                  <p className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wide">
                    Drag &amp; drop file here
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    or <span className="text-indigo-600 dark:text-indigo-400 font-bold underline">browse files</span>
                  </p>
                  <div className="flex items-center gap-2 mt-4 text-[9px] font-bold text-slate-400 dark:text-slate-500 tracking-wider uppercase">
                    <span className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-800">CSV</span>
                    <span>·</span>
                    <span className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-800">XLSX</span>
                    <span>·</span>
                    <span className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-800">JSON</span>
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
            </motion.label>
          ) : (
            <motion.div
              key="manual-builder-form"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.2 }}
              className="w-full rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-sm"
            >
              <div className="flex items-start gap-4 mb-4">
                <div className="p-3 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 shrink-0">
                  <Edit size={24} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">
                    Create Manual Session
                  </h3>
                  <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5 leading-relaxed">
                    Set a target filename prefix below. You will be redirected to the custom ontology builder workspace.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-[1fr_160px] gap-3 text-left mb-4">
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-1">
                    File Name Prefix
                  </label>
                  <input
                    type="text"
                    value={manualFilename}
                    onChange={(e) => setManualFilename(e.target.value)}
                    placeholder="e.g., software_ethics_round1"
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 text-xs bg-slate-50/50 dark:bg-slate-950/50 text-slate-700 dark:text-slate-350 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-1">
                    Save Format
                  </label>
                  <select
                    value={manualFormat}
                    onChange={(e) => setManualFormat(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 text-xs bg-slate-50/50 dark:bg-slate-950/50 text-slate-700 dark:text-slate-350 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 focus:outline-none"
                  >
                    {MANUAL_FORMAT_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-t border-slate-100 dark:border-slate-800/80 pt-4 gap-3">
                <p className="text-[10px] text-slate-450 dark:text-slate-500">
                  Target output: <span className="font-semibold text-slate-650 dark:text-slate-300">{buildManualSourceFilename(manualFilename, manualFormat)}</span>
                </p>
                <button
                  onClick={() => {
                    setError("");
                    onStartManual?.({
                      sourceFilename: buildManualSourceFilename(manualFilename, manualFormat),
                      sourceFormat: manualFormat,
                    });
                  }}
                  className="px-4 py-2 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-all duration-200 active:scale-95 cursor-pointer flex items-center justify-center gap-1.5"
                >
                  Start Builder
                  <ExternalLink size={14} />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error Notification */}
        {error && (
          <div className="mt-4 p-3.5 bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/30 rounded-xl text-xs text-rose-800 dark:text-rose-350 flex items-start gap-2.5">
            <AlertCircle size={16} className="text-rose-600 dark:text-rose-450 shrink-0 mt-0.5" />
            <p className="font-medium leading-normal">{error}</p>
          </div>
        )}

        {/* Recent Sessions list */}
        {sessions.length > 0 && (
          <div className="mt-8">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <h2 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Clock size={15} />
                Recent Graded Sessions
              </h2>

              <div className="flex items-center gap-1 bg-slate-100/80 dark:bg-slate-800/80 p-0.5 rounded-lg border border-slate-200/50 dark:border-slate-800/40">
                {["all", "mine", "others"].map((filterOpt) => (
                  <button
                    key={filterOpt}
                    onClick={() => setSessionFilter(filterOpt)}
                    className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition-all duration-200 cursor-pointer ${sessionFilter === filterOpt
                        ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-white shadow-sm"
                        : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                      }`}
                  >
                    {filterOpt === "all" ? "All" : filterOpt === "mine" ? "My Files" : "Others"}
                  </button>
                ))}
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
                const isGroupRecent = group.latestUploadedAt && (Date.now() - new Date(group.latestUploadedAt + "Z").getTime() < 24 * 60 * 60 * 1000);

                return (
                  <div
                    key={group.sourceKey}
                    className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden hover:border-slate-350 dark:hover:border-slate-700 transition-all duration-250"
                  >
                    <button
                      onClick={() => toggleSourceGroup(group.sourceKey)}
                      className="w-full text-left px-4.5 py-3.5 hover:bg-slate-50/50 dark:hover:bg-slate-900/50 transition-colors flex items-center justify-between gap-4 cursor-pointer"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-450 dark:text-slate-500 shrink-0">
                          <Folder size={18} />
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs sm:text-sm font-bold text-slate-800 dark:text-white truncate flex items-center gap-1.5 flex-wrap">
                            <span>{group.sourceFilename}</span>
                            {isGroupRecent && (
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[8px] font-bold uppercase bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-450 border border-emerald-100 dark:border-emerald-900/30 select-none shrink-0">
                                <span className="w-1 h-1 rounded-full bg-emerald-500 animate-ping" />
                                New File
                              </span>
                            )}
                          </p>
                          <div className="flex items-center gap-2 text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
                            <span>
                              {group.totalSessions} session{group.totalSessions === 1 ? "" : "s"}
                            </span>
                            {headerDate && (
                              <>
                                <span>•</span>
                                <span className="flex items-center gap-1 font-medium">
                                  <Calendar size={11} />
                                  {headerDate}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="p-1 rounded bg-slate-50 dark:bg-slate-800 text-slate-450 border border-slate-100 dark:border-slate-800">
                        {isCollapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
                      </div>
                    </button>

                    {!isCollapsed && (
                      <div className="border-t border-slate-100 dark:border-slate-800/80 bg-slate-50/20 dark:bg-slate-950/20 p-3 space-y-2.5">
                        {group.sessions.map((s) => {
                          const dateStr = s.uploaded_at
                            ? new Date(s.uploaded_at + "Z").toLocaleString([], {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                            : "";
                          const isLoading = resuming === s.session_id;
                          const isDeleting = deleting === s.session_id;
                          const isRecentUpload = recentUploadSessionId === s.session_id;

                          const sessionTypeClass = s.is_owner
                            ? "bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-450 border-emerald-100 dark:border-emerald-900/30"
                            : "bg-indigo-50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 border-indigo-200 dark:border-indigo-900/30";

                          const ownerName = s.owner_name || "Unknown";
                          const avatarLetter = ownerName.trim().charAt(0).toUpperCase() || "U";
                          const hasWorkedOnSession =
                            !s.is_owner &&
                            (Boolean(s.my_has_activity) ||
                              Number(s.my_total_actions || 0) > 0 ||
                              Number(s.my_graded_triples || 0) > 0);

                          const roleHint = s.is_owner
                            ? "Owner: Manage triples and approve/reject suggestions."
                            : hasWorkedOnSession
                              ? "Collaborator: Resuming in-progress sheet."
                              : "Collaborator: Open to join grading activity.";

                          const actionLabel = isLoading ? "Loading..." : s.is_owner ? "Open Session" : "Join Session";
                          const deleteLabel = isDeleting ? "Deleting..." : "Delete";

                          const avgBadge =
                            s.total_unique_graders > 0
                              ? `${s.total_unique_graders} grader${s.total_unique_graders === 1 ? "" : "s"
                              } · Avg ${s.session_average_grade != null ? Number(s.session_average_grade).toFixed(2) : "—"
                              }/10`
                              : null;

                          const isRecent = s.uploaded_at && (Date.now() - new Date(s.uploaded_at + "Z").getTime() < 24 * 60 * 60 * 1000);

                          return (
                            <div
                              key={s.session_id}
                              className={`flex flex-col sm:flex-row sm:items-center justify-between bg-white dark:bg-slate-900 border rounded-xl p-3.5 transition-all duration-200 gap-3 ${isRecentUpload
                                  ? "border-emerald-500/40 ring-4 ring-emerald-500/5 bg-emerald-50/10 dark:bg-emerald-950/10"
                                  : "border-slate-200/80 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700"
                                }`}
                            >
                              <div className="min-w-0 flex-1 space-y-1.5">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className={`text-[9px] font-bold border px-2 py-0.5 rounded-full uppercase tracking-wider ${sessionTypeClass}`}>
                                    {s.is_owner ? "Owner" : "Collaborator"}
                                  </span>
                                  {isRecent && (
                                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[8px] font-bold uppercase bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-450 border border-emerald-100 dark:border-emerald-900/30 select-none shrink-0">
                                      <span className="w-1 h-1 rounded-full bg-emerald-500 animate-ping" />
                                      New
                                    </span>
                                  )}
                                  <span className="inline-flex items-center gap-1.5 rounded-md border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 px-2 py-0.5 text-slate-500 dark:text-slate-400 font-semibold text-[10px]">
                                    <span className="w-3.5 h-3.5 rounded-full bg-slate-200 dark:bg-slate-800 text-[8px] font-bold flex items-center justify-center text-slate-750 dark:text-slate-350 uppercase shrink-0">
                                      {avatarLetter}
                                    </span>
                                    {ownerName}
                                  </span>
                                </div>
                                <div className="text-[10px] text-slate-450 dark:text-slate-500 flex items-center gap-2 flex-wrap">
                                  <span className="flex items-center gap-1 font-semibold text-slate-600 dark:text-slate-400">
                                    <FileText size={12} />
                                    {s.total_sentences} sentence{s.total_sentences === 1 ? "" : "s"}
                                  </span>
                                  {dateStr && (
                                    <>
                                      <span>•</span>
                                      <span>{dateStr}</span>
                                    </>
                                  )}
                                </div>
                                <p className="text-[10px] text-slate-400 dark:text-slate-500 leading-normal flex items-start gap-1">
                                  <Info size={11} className="shrink-0 mt-0.5 text-slate-300 dark:text-slate-650" />
                                  {roleHint}
                                </p>
                                {avgBadge && (
                                  <p className="text-[10px] text-emerald-600 dark:text-emerald-450 font-bold flex items-center gap-1">
                                    <GraduationCap size={12} className="shrink-0 text-emerald-500" />
                                    {avgBadge}
                                  </p>
                                )}
                              </div>
                              <div className="shrink-0 flex items-center gap-2 sm:self-center mt-1 sm:mt-0 justify-end">
                                {s.is_owner && (
                                  <button
                                    onClick={() => handleDelete(s)}
                                    disabled={!!resuming || !!deleting}
                                    className="p-2 rounded-lg text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/20 active:scale-95 transition-all disabled:opacity-50 cursor-pointer border border-slate-100 dark:border-slate-800 hover:border-rose-200 dark:hover:border-rose-900"
                                    title="Delete session"
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                )}
                                <button
                                  onClick={() => handleResume(s)}
                                  disabled={!!resuming || !!deleting}
                                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm active:scale-95 transition-all disabled:opacity-55 whitespace-nowrap cursor-pointer flex items-center gap-1"
                                >
                                  {actionLabel}
                                  <ExternalLink size={12} />
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
                <div className="text-center py-6 text-xs text-slate-400 dark:text-slate-600 bg-slate-50/50 dark:bg-slate-900/30 border border-slate-200/50 dark:border-slate-800/40 rounded-2xl">
                  No sessions found in this view.
                </div>
              )}
            </div>
            {resumeError && (
              <p className="mt-2 text-xs font-semibold text-rose-600 flex items-center gap-1">
                <AlertCircle size={14} /> {resumeError}
              </p>
            )}
            {deleteError && (
              <p className="mt-2 text-xs font-semibold text-rose-600 flex items-center gap-1">
                <AlertCircle size={14} /> {deleteError}
              </p>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}
