// FileUpload.jsx — Drag-and-drop / click file uploader

import { useCallback, useState } from "react";
import { uploadFile } from "../api";

export default function FileUpload({ onUploadSuccess }) {
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

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
