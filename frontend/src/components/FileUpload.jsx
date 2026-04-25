// FileUpload.jsx — Drag-and-drop / click file uploader

import { useCallback, useEffect, useState } from "react";
import { uploadFile, listSessions, loadSession } from "../api";

export default function FileUpload({ onUploadSuccess, onLoadSession }) {
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  const [sessions, setSessions]       = useState([]);
  const [resuming, setResuming]       = useState(null); // session_id being loaded
  const [resumeError, setResumeError] = useState("");

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

  const handleResume = async (sessionId) => {
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
            Upload a CSV or Excel file containing sentences and their triples
            to begin grading.
          </p>
        </div>

        {/* Drop zone */}
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

        {/* Error */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
            ⚠ {error}
          </div>
        )}

        {/* ── Recent Sessions ── */}
        {sessions.length > 0 && (
          <div className="mt-6">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
              Recent Sessions
            </p>
            <div className="space-y-2">
              {sessions.slice(0, 5).map((s) => {
                const dateStr = s.uploaded_at
                  ? new Date(s.uploaded_at + "Z").toLocaleString([], {
                      month: "short", day: "numeric",
                      hour: "2-digit", minute: "2-digit",
                    })
                  : "";
                const isLoading = resuming === s.session_id;
                return (
                  <div
                    key={s.session_id}
                    className="flex items-center justify-between bg-white border border-slate-200 rounded-xl px-4 py-3 shadow-sm hover:border-blue-300 hover:bg-blue-50/30 transition-all"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-slate-700 truncate">
                        {s.source_filename}
                      </p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {s.total_sentences} sentences
                        {s.owner_name && <> &bull; Owner: {s.owner_name}</>}
                        {dateStr && <> &bull; {dateStr}</>}
                      </p>
                    </div>
                    <button
                      onClick={() => handleResume(s.session_id)}
                      disabled={!!resuming}
                      className="ml-3 shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-700 text-white hover:bg-blue-800 active:scale-95 transition-all disabled:opacity-50 whitespace-nowrap"
                    >
                      {isLoading ? "Loading…" : "▶ Resume"}
                    </button>
                  </div>
                );
              })}
            </div>
            {resumeError && (
              <p className="mt-2 text-xs text-red-600">⚠ {resumeError}</p>
            )}
          </div>
        )}

        {/* Format hint */}
        <div className="mt-6 bg-white border border-slate-200 rounded-2xl p-4 text-xs text-slate-500 space-y-1.5 shadow-sm">
          <p className="font-semibold text-slate-600 text-sm mb-2">
            Expected file format
          </p>
          <p>
            •{" "}
            <span className="font-medium text-slate-700">Col 1–3:</span>{" "}
            Subject · Predicate · Object (one triple per row)
          </p>
          <p>
            •{" "}
            <span className="font-medium text-slate-700">Col 8:</span>{" "}
            Natural-language sentence (may span multiple rows per group)
          </p>
          <p>
            • Groups are separated by blank rows or ======= divider lines
          </p>
        </div>
      </div>
    </div>
  );
}
