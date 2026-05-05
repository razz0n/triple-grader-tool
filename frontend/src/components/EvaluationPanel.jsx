// EvaluationPanel.jsx — OpenIE evaluation UI

import { useState, useEffect } from "react";
import { runEvaluation, downloadEvaluation, loadSession } from "../api";

function fmt2(n) {
  return n == null ? "—" : (n * 100).toFixed(1) + "%";
}

function MetricCard({ label, p, r, f1 }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 flex flex-col gap-2 min-w-40">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <div className="grid grid-cols-3 gap-1 mt-1">
        <div className="flex flex-col items-center">
          <span className="text-lg font-bold text-blue-700">{fmt2(p)}</span>
          <span className="text-xs text-slate-400">Prec.</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-lg font-bold text-green-700">{fmt2(r)}</span>
          <span className="text-xs text-slate-400">Recall</span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-lg font-bold text-purple-700">{fmt2(f1)}</span>
          <span className="text-xs text-slate-400">F1</span>
        </div>
      </div>
    </div>
  );
}

export default function EvaluationPanel({ sessionId, sourceFilename, onBack }) {
  const [matchMode, setMatchMode] = useState("soft");
  const [goldSource, setGoldSource] = useState("graded_only");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dlError, setDlError] = useState("");
  const [downloading, setDownloading] = useState(null); // "json"|"csv"|null

  // On mount: load existing evaluation from session if present
  useEffect(() => {
    if (!sessionId) return;
    loadSession(sessionId)
      .then((session) => {
        if (session?.evaluation) {
          setResult(session.evaluation);
          setMatchMode(session.evaluation.match_mode || "soft");
          setGoldSource(session.evaluation.gold_source || "graded_only");
        }
      })
      .catch(() => {});
  }, [sessionId]);

  const handleRun = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await runEvaluation(sessionId, matchMode, goldSource);
      setResult(data);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Evaluation failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (fmt) => {
    setDlError("");
    setDownloading(fmt);
    try {
      await downloadEvaluation(sessionId, fmt);
    } catch (e) {
      setDlError(e?.message || "Download failed.");
    } finally {
      setDownloading(null);
    }
  };

  const perSentence = result?.per_sentence ?? [];
  const macro = result?.macro;
  const micro = result?.micro;
  const effectiveGoldSource = result?.gold_source || goldSource;
  const showNoGradedGoldWarning =
    !!result && effectiveGoldSource === "graded_only" && (micro?.n_gold ?? 0) === 0;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">

      {/* Top bar */}
      <div className="bg-white/95 backdrop-blur border-b border-slate-200 shadow-sm fixed top-0 left-0 right-0 z-30">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-3">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <div className="text-blue-700 text-xl font-bold select-none shrink-0">◈</div>
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-700 leading-tight">OpenIE Evaluation</div>
              <div className="text-xs text-slate-400 truncate max-w-48">{sourceFilename}</div>
            </div>
          </div>

          {/* Match mode selector */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-xs text-slate-500 font-medium">Match:</span>
            {["soft", "exact"].map((m) => (
              <button
                key={m}
                onClick={() => setMatchMode(m)}
                className={[
                  "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all",
                  matchMode === m
                    ? "bg-blue-700 text-white border-blue-700 shadow-sm"
                    : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50",
                ].join(" ")}
              >
                {m.charAt(0).toUpperCase() + m.slice(1)}
              </button>
            ))}
          </div>

          {/* Gold source selector */}
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-xs text-slate-500 font-medium">Gold:</span>
            {[
              { value: "graded_only", label: "Graded" },
              { value: "all", label: "All" },
            ].map((opt) => (
              <button
                key={opt.value}
                onClick={() => setGoldSource(opt.value)}
                className={[
                  "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all",
                  goldSource === opt.value
                    ? "bg-emerald-700 text-white border-emerald-700 shadow-sm"
                    : "bg-white text-slate-600 border-slate-300 hover:bg-slate-50",
                ].join(" ")}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Run button */}
          <button
            onClick={handleRun}
            disabled={loading || !sessionId}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-purple-700 text-white hover:bg-purple-800 active:scale-95 transition-all disabled:opacity-50 shadow-sm whitespace-nowrap shrink-0"
          >
            {loading ? "Running…" : "🔬 Run Evaluation"}
          </button>

          {/* Download buttons */}
          {result && (
            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={() => handleDownload("json")}
                disabled={!!downloading}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-300 text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-all whitespace-nowrap"
              >
                {downloading === "json" ? "…" : "⬇ JSON"}
              </button>
              <button
                onClick={() => handleDownload("csv")}
                disabled={!!downloading}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold border border-slate-300 text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-all whitespace-nowrap"
              >
                {downloading === "csv" ? "…" : "⬇ CSV"}
              </button>
            </div>
          )}

          {/* Back */}
          <button
            onClick={onBack}
            className="text-xs text-slate-500 hover:text-blue-700 transition-colors px-2 py-1 rounded-lg hover:bg-blue-50 shrink-0 whitespace-nowrap flex items-center gap-1"
          >
            ← Back
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-5xl mx-auto px-4 pb-8 pt-24 space-y-6">

        {/* Errors */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {dlError && (
          <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
            Download error: {dlError}
          </div>
        )}

        {/* Graded-only warning */}
        {showNoGradedGoldWarning && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800 flex items-start gap-3">
            <div className="shrink-0 mt-0.5">⚠️</div>
            <div className="flex-1">
              <p className="font-semibold">No triple quality grades found for graded-only gold.</p>
              <p className="text-xs mt-1">
                I can only use triples with a non-empty quality score in this mode. Switch Gold to All,
                or grade triples first, save, and run evaluation again.
              </p>
            </div>
            <button
              onClick={() => setGoldSource("all")}
              className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold border border-amber-300 text-amber-800 hover:bg-amber-100 transition-colors"
            >
              Switch Gold to All
            </button>
          </div>
        )}

        {/* Empty state */}
        {!result && !loading && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-10 flex flex-col items-center gap-4 text-center">
            <span className="text-4xl">🔬</span>
            <p className="text-slate-700 font-semibold">No evaluation yet</p>
            <p className="text-sm text-slate-400 max-w-sm">
              Choose a match mode and gold source, then click <strong>Run Evaluation</strong> to compare OpenIE-extracted triples against your selected gold standard.
            </p>
            <p className="text-xs text-slate-400 mt-1">
              <strong>Soft</strong> match uses Jaccard ≥ 0.5. <strong>Exact</strong> match requires normalised string equality.
            </p>
          </div>
        )}

        {/* Loading spinner */}
        {loading && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-10 flex flex-col items-center gap-3 text-center">
            <div className="w-8 h-8 border-4 border-purple-200 border-t-purple-700 rounded-full animate-spin" />
            <p className="text-sm text-slate-500">Running stanza NLP pipeline…</p>
            <p className="text-xs text-slate-400">This may take 20–60 seconds on first run while models load.</p>
          </div>
        )}

        {/* Results */}
        {result && !loading && (
          <>
            {/* Summary banner */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm px-5 py-3 flex items-center gap-3 flex-wrap text-xs text-slate-500">
              <span>Session: <span className="font-mono text-slate-700">{result.session_id}</span></span>
              <span className="text-slate-300">|</span>
              <span>Source: <span className="font-semibold text-slate-700">{result.source_filename}</span></span>
              <span className="text-slate-300">|</span>
              <span>Mode: <span className={`font-semibold ${result.match_mode === "exact" ? "text-orange-600" : "text-blue-600"}`}>{result.match_mode}</span></span>
              <span className="text-slate-300">|</span>
              <span>
                Gold: <span className="font-semibold text-emerald-700">{result.gold_source === "all" ? "all triples" : "graded only"}</span>
              </span>
              {result.evaluated_at && (
                <>
                  <span className="text-slate-300">|</span>
                  <span>Evaluated: <span className="text-slate-600">{new Date(result.evaluated_at).toLocaleString()}</span></span>
                </>
              )}
            </div>

            {/* Macro / Micro summary cards */}
            <div className="flex gap-4 flex-wrap">
              {macro && (
                <MetricCard label="Macro Average" p={macro.precision} r={macro.recall} f1={macro.f1} />
              )}
              {micro && (
                <MetricCard label="Micro Average" p={micro.precision} r={micro.recall} f1={micro.f1} />
              )}
            </div>

            {/* Per-sentence table */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-100">
                <h2 className="text-sm font-semibold text-slate-700">Per-Sentence Results</h2>
                <p className="text-xs text-slate-400 mt-0.5">{perSentence.length} sentences</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-2 text-left font-semibold">#</th>
                      <th className="px-4 py-2 text-left font-semibold">Sentence</th>
                      <th className="px-4 py-2 text-center font-semibold">Gold</th>
                      <th className="px-4 py-2 text-center font-semibold">Pred</th>
                      <th className="px-4 py-2 text-center font-semibold">TP</th>
                      <th className="px-4 py-2 text-center font-semibold">Prec.</th>
                      <th className="px-4 py-2 text-center font-semibold">Recall</th>
                      <th className="px-4 py-2 text-center font-semibold">F1</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {perSentence.map((row, i) => {
                      const f1Val = row.f1 ?? 0;
                      const f1Color =
                        f1Val >= 0.7 ? "text-green-700 font-semibold" :
                        f1Val >= 0.4 ? "text-amber-600 font-semibold" :
                        "text-red-600 font-semibold";
                      return (
                        <tr key={row.sentence_id ?? i} className="hover:bg-slate-50 transition-colors">
                          <td className="px-4 py-2 text-xs text-slate-400 tabular-nums">{row.sentence_id}</td>
                          <td className="px-4 py-2 text-slate-700 max-w-xs">
                            <span className="line-clamp-2 text-xs leading-relaxed" title={row.sentence_text}>
                              {row.sentence_text}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-center text-xs text-slate-600 tabular-nums">{row.n_gold ?? 0}</td>
                          <td className="px-4 py-2 text-center text-xs text-slate-600 tabular-nums">{row.n_pred ?? 0}</td>
                          <td className="px-4 py-2 text-center text-xs text-blue-700 font-semibold tabular-nums">{row.true_positives ?? 0}</td>
                          <td className="px-4 py-2 text-center text-xs text-slate-600 tabular-nums">{fmt2(row.precision)}</td>
                          <td className="px-4 py-2 text-center text-xs text-slate-600 tabular-nums">{fmt2(row.recall)}</td>
                          <td className={`px-4 py-2 text-center text-xs tabular-nums ${f1Color}`}>{fmt2(row.f1)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Predicted triples detail (collapsible per sentence) */}
            {perSentence.some((r) => r.pred_triples?.length > 0) && (
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-5 py-3 border-b border-slate-100">
                  <h2 className="text-sm font-semibold text-slate-700">Extracted Triples Detail</h2>
                  <p className="text-xs text-slate-400 mt-0.5">OpenIE triples extracted per sentence</p>
                </div>
                <div className="divide-y divide-slate-100">
                  {perSentence.filter((r) => r.pred_triples?.length > 0).map((row, i) => (
                    <details key={row.sentence_id ?? i} className="group px-5 py-3">
                      <summary className="cursor-pointer text-xs text-slate-600 flex items-center gap-2 list-none select-none">
                        <span className="text-slate-400 group-open:rotate-90 transition-transform inline-block">▶</span>
                        <span className="font-mono text-slate-400">S{row.sentence_id}</span>
                        <span className="text-slate-500 truncate max-w-xs" title={row.sentence_text}>{row.sentence_text}</span>
                        <span className="ml-auto shrink-0 text-slate-400">{row.pred_triples.length} triple{row.pred_triples.length !== 1 ? "s" : ""}</span>
                      </summary>
                      <div className="mt-3 ml-5 space-y-1.5">
                        {row.pred_triples.map((t, j) => (
                          <div key={j} className="flex items-baseline gap-1.5 text-xs text-slate-600 bg-slate-50 rounded-lg px-3 py-1.5">
                            <span className="font-semibold text-blue-700 shrink-0">{t.subject}</span>
                            <span className="text-slate-400 shrink-0">→</span>
                            <span className="font-medium text-purple-700 shrink-0">{t.predicate}</span>
                            <span className="text-slate-400 shrink-0">→</span>
                            <span className="font-semibold text-green-700">{t.object}</span>
                          </div>
                        ))}
                      </div>
                    </details>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
