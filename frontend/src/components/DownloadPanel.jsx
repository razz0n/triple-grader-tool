// DownloadPanel.jsx — Format selector and download trigger

import { useState } from "react";
import { downloadSession } from "../api";

const FORMATS = [
  { value: "json",  label: "JSON",  icon: "{}" },
  { value: "csv",   label: "CSV",   icon: "⊞" },
  { value: "excel", label: "Excel", icon: "📊" },
  { value: "pdf",   label: "PDF",   icon: "📄" },
  { value: "word",  label: "Word",  icon: "📝" },
];

export default function DownloadPanel({ sessionId, disabled }) {
  const [selected, setSelected] = useState("pdf");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  const handleDownload = async () => {
    setError("");
    setLoading(true);
    try {
      await downloadSession(sessionId, selected);
    } catch (e) {
      setError(
        e?.message ||
          e?.response?.data?.detail ||
          "Download failed. Make sure the session is saved first."
      );
    } finally {
      setLoading(false);
    }
  };

  const selectedLabel = FORMATS.find((f) => f.value === selected)?.label ?? "";

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-2xl p-5">
      <h3 className="text-sm font-semibold text-slate-600 mb-3 uppercase tracking-wide">
        Download Graded Report
      </h3>

      {/* Format picker */}
      <div className="flex flex-wrap gap-2 mb-4">
        {FORMATS.map((f) => (
          <button
            key={f.value}
            onClick={() => setSelected(f.value)}
            className={[
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border transition-all",
              selected === f.value
                ? "bg-blue-700 text-white border-blue-700 shadow-sm"
                : "bg-white text-slate-600 border-slate-300 hover:border-blue-400 hover:text-blue-700",
            ].join(" ")}
          >
            <span>{f.icon}</span>
            {f.label}
          </button>
        ))}
      </div>

      {/* Download button */}
      <button
        onClick={handleDownload}
        disabled={disabled || loading || !sessionId}
        className="w-full py-2.5 px-4 rounded-xl font-semibold text-sm bg-green-600 text-white hover:bg-green-700 active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
      >
        {loading ? "Preparing download…" : `Download as ${selectedLabel}`}
      </button>

      {!sessionId && (
        <p className="mt-2 text-xs text-amber-600">
          Save the session first to enable downloads.
        </p>
      )}

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}
