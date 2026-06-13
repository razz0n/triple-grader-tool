import { useState, useEffect } from "react";
import { runEvaluation, previewEvaluation, downloadEvaluation, loadSession } from "../api";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  Activity,
  CheckCircle,
  XCircle,
  FileText,
  Download,
  BarChart3,
  RefreshCw,
  AlertCircle,
  Check,
  Zap,
  BookOpen,
  PieChart,
  HelpCircle,
  Loader2,
  Calendar
} from "lucide-react";

function fmt2(n) {
  return n == null ? "—" : (n * 100).toFixed(1) + "%";
}

function MetricCard({ label, p, r, f1, accent = "blue" }) {
  const colors = {
    blue: {
      p: "text-indigo-650 dark:text-indigo-400",
      r: "text-emerald-600 dark:text-emerald-400",
      f1: "text-purple-600 dark:text-purple-400",
      bg: "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800",
    },
    amber: {
      p: "text-amber-600 dark:text-amber-400",
      r: "text-teal-600 dark:text-teal-400",
      f1: "text-rose-600 dark:text-rose-450",
      bg: "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800",
    },
  };
  const c = colors[accent] || colors.blue;
  return (
    <motion.div
      whileHover={{ y: -2 }}
      className={`rounded-2xl border p-5 flex flex-col gap-2 min-w-[200px] flex-1 shadow-sm ${c.bg}`}
    >
      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
        {label}
      </p>
      <div className="grid grid-cols-3 gap-2 mt-1.5 divide-x divide-slate-100 dark:divide-slate-800">
        <div className="flex flex-col items-center">
          <span className={`text-base sm:text-lg font-extrabold tabular-nums ${c.p}`}>{fmt2(p)}</span>
          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wide mt-0.5">Prec.</span>
        </div>
        <div className="flex flex-col items-center pl-2">
          <span className={`text-base sm:text-lg font-extrabold tabular-nums ${c.r}`}>{fmt2(r)}</span>
          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wide mt-0.5">Recall</span>
        </div>
        <div className="flex flex-col items-center pl-2">
          <span className={`text-base sm:text-lg font-extrabold tabular-nums ${c.f1}`}>{fmt2(f1)}</span>
          <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wide mt-0.5">F1</span>
        </div>
      </div>
    </motion.div>
  );
}

function StatusBadge({ ok, label }) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-lg border uppercase tracking-wider ${
        ok
          ? "bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-450 border-emerald-200 dark:border-emerald-900/30"
          : "bg-rose-50 dark:bg-rose-950/20 text-rose-700 dark:text-rose-455 border-rose-200 dark:border-rose-900/30"
      }`}
    >
      {ok ? <CheckCircle size={10} /> : <XCircle size={10} />}
      <span>{label}</span>
    </span>
  );
}

function PerSentenceTable({ perSentence, title, subtitle }) {
  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800/80">
        <h2 className="text-sm font-bold text-slate-850 dark:text-slate-200">{title}</h2>
        <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{subtitle}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs text-left">
          <thead className="bg-slate-50 dark:bg-slate-950 text-[10px] font-bold uppercase tracking-wider text-slate-450 dark:text-slate-500 border-b border-slate-100 dark:border-slate-800">
            <tr>
              <th className="px-4.5 py-3 w-12 text-center">#</th>
              <th className="px-4.5 py-3">Sentence Text</th>
              <th className="px-4.5 py-3 text-center">Gold</th>
              <th className="px-4.5 py-3 text-center">Pred</th>
              <th className="px-4.5 py-3 text-center">TP</th>
              <th className="px-4.5 py-3 text-center">Prec.</th>
              <th className="px-4.5 py-3 text-center">Recall</th>
              <th className="px-4.5 py-3 text-center">F1 Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
            {perSentence.map((row, i) => {
              const f1Val = row.f1 ?? 0;
              const f1Color =
                f1Val >= 0.7
                  ? "text-emerald-600 dark:text-emerald-400 font-extrabold"
                  : f1Val >= 0.4
                  ? "text-amber-600 dark:text-amber-450 font-extrabold"
                  : f1Val > 0
                  ? "text-rose-600 dark:text-rose-455 font-extrabold"
                  : "text-slate-400 dark:text-slate-500";
              const hasData = (row.n_gold ?? 0) > 0 || (row.n_pred ?? 0) > 0;
              return (
                <tr
                  key={row.sentence_id ?? i}
                  className={`hover:bg-slate-50/50 dark:hover:bg-slate-950/40 transition-colors ${
                    !hasData ? "opacity-45" : ""
                  }`}
                >
                  <td className="px-4.5 py-3 text-center text-slate-400 dark:text-slate-500 font-mono tabular-nums">
                    {row.sentence_id}
                  </td>
                  <td className="px-4.5 py-3 text-slate-700 dark:text-slate-300 max-w-sm">
                    <span className="line-clamp-2 leading-relaxed" title={row.sentence_text}>
                      {row.sentence_text || <span className="italic text-slate-350 dark:text-slate-600">No text content</span>}
                    </span>
                  </td>
                  <td className="px-4.5 py-3 text-center text-slate-650 dark:text-slate-400 tabular-nums">
                    {row.n_gold ?? 0}
                  </td>
                  <td className="px-4.5 py-3 text-center text-slate-650 dark:text-slate-400 tabular-nums">
                    {row.n_pred ?? 0}
                  </td>
                  <td className="px-4.5 py-3 text-center text-indigo-600 dark:text-indigo-400 font-bold tabular-nums">
                    {row.true_positives ?? 0}
                  </td>
                  <td className="px-4.5 py-3 text-center text-slate-650 dark:text-slate-400 tabular-nums">
                    {fmt2(row.precision)}
                  </td>
                  <td className="px-4.5 py-3 text-center text-slate-650 dark:text-slate-400 tabular-nums">
                    {fmt2(row.recall)}
                  </td>
                  <td className={`px-4.5 py-3 text-center tabular-nums ${f1Color}`}>{fmt2(row.f1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TriplesDetail({ perSentence, title }) {
  const withTriples = perSentence.filter((r) => (r.pred_triples?.length > 0) || (r.gold_triples?.length > 0));
  if (!withTriples.length) return null;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800/80">
        <h2 className="text-sm font-bold text-slate-850 dark:text-slate-200">{title}</h2>
        <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
          Detailed comparison of gold and predicted triples per sentence
        </p>
      </div>
      <div className="divide-y divide-slate-100 dark:divide-slate-800/80">
        {withTriples.map((row, i) => (
          <details key={row.sentence_id ?? i} className="group px-5 py-3.5">
            <summary className="cursor-pointer text-xs text-slate-600 dark:text-slate-350 flex items-center gap-2 list-none select-none">
              <span className="text-slate-400 group-open:rotate-90 transition-transform inline-block">▶</span>
              <span className="font-mono text-slate-400 dark:text-slate-500">S{row.sentence_id}</span>
              <span className="text-slate-600 dark:text-slate-300 truncate max-w-sm font-semibold" title={row.sentence_text}>
                {row.sentence_text}
              </span>
              <span className="ml-auto shrink-0 text-slate-400 dark:text-slate-500 text-[10px] font-bold uppercase tracking-wider bg-slate-50 dark:bg-slate-950 px-2 py-0.5 rounded border border-slate-150 dark:border-slate-850">
                {row.gold_triples?.length ?? 0} Gold &bull; {row.pred_triples?.length ?? 0} Pred
              </span>
            </summary>
            <div className="mt-4 ml-5 grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Gold triples */}
              {row.gold_triples?.length > 0 ? (
                <div className="space-y-2">
                  <p className="text-[10px] font-bold text-emerald-700 dark:text-emerald-450 uppercase tracking-wider">
                    Gold Triples ({row.gold_triples.length})
                  </p>
                  <div className="space-y-1.5">
                    {row.gold_triples.map((t, j) => (
                      <div
                        key={j}
                        className="flex items-center gap-1.5 text-xs text-slate-700 dark:text-slate-300 bg-emerald-50/45 dark:bg-emerald-950/20 border border-emerald-100/60 dark:border-emerald-900/35 rounded-xl px-3 py-2"
                      >
                        <span className="font-bold text-emerald-800 dark:text-emerald-400">{t.subject}</span>
                        <span className="text-slate-400">&rarr;</span>
                        <span className="font-bold text-emerald-600 dark:text-emerald-450">{t.predicate}</span>
                        <span className="text-slate-400">&rarr;</span>
                        <span className="font-bold text-emerald-800 dark:text-emerald-400">{t.object}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-[10px] font-bold text-slate-450 uppercase tracking-wider">Gold Triples (0)</p>
                  <p className="text-xs text-slate-400 italic">No gold triples graded.</p>
                </div>
              )}

              {/* Predicted triples */}
              {row.pred_triples?.length > 0 ? (
                <div className="space-y-2">
                  <p className="text-[10px] font-bold text-indigo-700 dark:text-indigo-400 uppercase tracking-wider">
                    Predicted Triples ({row.pred_triples.length})
                  </p>
                  <div className="space-y-1.5">
                    {row.pred_triples.map((t, j) => (
                      <div
                        key={j}
                        className="flex items-center gap-1.5 text-xs text-slate-700 dark:text-slate-300 bg-indigo-50/45 dark:bg-indigo-950/20 border border-indigo-100/60 dark:border-indigo-900/35 rounded-xl px-3 py-2"
                      >
                        <span className="font-bold text-indigo-800 dark:text-indigo-400">{t.subject}</span>
                        <span className="text-slate-400">&rarr;</span>
                        <span className="font-bold text-purple-700 dark:text-purple-400">{t.predicate}</span>
                        <span className="text-slate-400">&rarr;</span>
                        <span className="font-bold text-emerald-700 dark:text-emerald-450">{t.object}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-[10px] font-bold text-slate-450 uppercase tracking-wider font-semibold">Predicted Triples (0)</p>
                  <p className="text-xs text-slate-400 italic">No triples predicted by Stanza.</p>
                </div>
              )}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}

function EvaluationSection({ evalData, accent, triplesTitle }) {
  if (!evalData) return null;
  const perSentence = evalData.per_sentence ?? [];
  const macro = evalData.macro;
  const micro = evalData.micro;

  return (
    <div className="space-y-5">
      {evalData.description && (
        <div className="text-[11px] text-slate-500 dark:text-slate-400 bg-slate-100/50 dark:bg-slate-900/50 px-4 py-2 border border-slate-200/50 dark:border-slate-800/80 rounded-xl leading-relaxed">
          {evalData.description} &bull; Exact-match filter threshold: <span className="font-bold">{evalData.threshold}</span>
        </div>
      )}

      {/* Metric Summaries */}
      <div className="flex gap-4 flex-wrap">
        {macro && <MetricCard label="Macro Averages" p={macro.precision} r={macro.recall} f1={macro.f1} accent={accent} />}
        {micro && <MetricCard label="Micro Averages" p={micro.precision} r={micro.recall} f1={micro.f1} accent={accent} />}
      </div>

      {/* Per Sentence details */}
      <PerSentenceTable
        perSentence={perSentence}
        title="Graded Sentences Evaluation Details"
        subtitle={`${perSentence.length} sentences total`}
      />

      {/* Triples compare detail */}
      <TriplesDetail perSentence={perSentence} title={triplesTitle} />
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
  const [downloading, setDownloading] = useState(null);

  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [step, setStep] = useState("review");
  const [activeTab, setActiveTab] = useState("openie");

  useEffect(() => {
    if (!sessionId) return;
    loadSession(sessionId)
      .then((session) => {
        if (session?.evaluation) {
          setResult(session.evaluation);
          setMatchMode(session.evaluation.match_mode || "soft");
          setGoldSource(session.evaluation.gold_source || "graded_only");
          setStep("results");
        }
      })
      .catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || step !== "review") return;
    setPreviewLoading(true);
    previewEvaluation(sessionId, goldSource)
      .then(setPreview)
      .catch(() => {})
      .finally(() => setPreviewLoading(false));
  }, [sessionId, goldSource, step]);

  const handleRun = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await runEvaluation(sessionId, matchMode, goldSource);
      setResult(data);
      setStep("results");
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || "Evaluation execution failed.");
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

  const handleBackToReview = () => {
    setStep("review");
  };

  const effectiveGoldSource = result?.gold_source || goldSource;
  const showNoGradedGoldWarning =
    !!result && effectiveGoldSource === "graded_only" && (result?.micro?.n_gold ?? 0) === 0;

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 transition-colors duration-300">
      {/* Sticky header bar */}
      <div className="bg-white/95 dark:bg-slate-900/95 backdrop-blur border-b border-slate-200 dark:border-slate-800 px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between sticky top-0 z-30 shadow-sm gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950 text-indigo-650 dark:text-indigo-400 flex items-center justify-center shrink-0">
            <Activity size={20} />
          </div>
          <div>
            <h1 className="text-base sm:text-lg font-bold text-slate-800 dark:text-white leading-tight">
              OpenIE NLP Evaluation
            </h1>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5 truncate max-w-xs sm:max-w-md">
              {sourceFilename}
            </p>
          </div>
        </div>

        {/* Toggle options bar */}
        <div className="flex items-center gap-3 flex-wrap justify-end">
          <div className="flex items-center gap-1.5 shrink-0 bg-slate-100/80 dark:bg-slate-855 p-0.5 rounded-lg border border-slate-200/50 dark:border-slate-800/40">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-1.5 select-none">Match:</span>
            {["soft", "exact"].map((m) => (
              <button
                key={m}
                onClick={() => setMatchMode(m)}
                className={`px-2 py-1 text-[10px] font-bold rounded transition-all cursor-pointer ${
                  matchMode === m
                    ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-white shadow-sm"
                    : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                {m.charAt(0).toUpperCase() + m.slice(1)}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5 shrink-0 bg-slate-100/80 dark:bg-slate-855 p-0.5 rounded-lg border border-slate-200/50 dark:border-slate-800/40">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-1.5 select-none">Gold:</span>
            {[
              { value: "graded_only", label: "Graded" },
              { value: "all", label: "All" },
            ].map((opt) => (
              <button
                key={opt.value}
                onClick={() => setGoldSource(opt.value)}
                className={`px-2 py-1 text-[10px] font-bold rounded transition-all cursor-pointer ${
                  goldSource === opt.value
                    ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-white shadow-sm"
                    : "text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {result && step === "results" && (
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                onClick={() => handleDownload("json")}
                disabled={!!downloading}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-[10px] font-bold text-slate-600 dark:text-slate-300 transition-colors disabled:opacity-50 cursor-pointer"
              >
                <Download size={11} /> JSON
              </button>
              <button
                onClick={() => handleDownload("csv")}
                disabled={!!downloading}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-[10px] font-bold text-slate-600 dark:text-slate-300 transition-colors disabled:opacity-50 cursor-pointer"
              >
                <Download size={11} /> CSV
              </button>
            </div>
          )}

          <button
            onClick={onBack}
            className="inline-flex items-center gap-1 text-xs font-bold text-slate-500 dark:text-slate-350 hover:text-indigo-600 dark:hover:text-indigo-400 border border-slate-200 dark:border-slate-800 hover:border-slate-300 rounded-xl px-3.5 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer transition-all"
          >
            <ArrowLeft size={13} /> Back
          </button>
        </div>
      </div>

      {/* Workspace Body */}
      <div className="max-w-5xl mx-auto px-6 py-6 space-y-5">
        {/* Errors list */}
        {error && (
          <div className="p-3.5 bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/30 rounded-xl text-xs text-rose-800 dark:text-rose-350 flex items-start gap-2.5">
            <AlertCircle size={16} className="text-rose-650 shrink-0 mt-0.5" />
            <span className="font-semibold leading-normal">{error}</span>
          </div>
        )}
        {dlError && (
          <div className="p-3.5 bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/30 rounded-xl text-xs text-rose-800 dark:text-rose-350 flex items-start gap-2.5">
            <AlertCircle size={16} className="text-rose-650 shrink-0 mt-0.5" />
            <span className="font-semibold leading-normal">Download failed: {dlError}</span>
          </div>
        )}

        {/* Warning gold-graded alert */}
        {showNoGradedGoldWarning && (
          <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/30 rounded-xl p-4 text-xs text-amber-805 dark:text-amber-400 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <AlertCircle size={18} className="text-amber-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">No triple quality scores found for Graded-Only Gold.</p>
                <p className="text-[11px] text-slate-450 mt-0.5">
                  Change Gold source to "All", or complete grading triples first and re-run.
                </p>
              </div>
            </div>
            <button
              onClick={() => setGoldSource("all")}
              className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-bold transition-all text-[11px] cursor-pointer"
            >
              Switch Gold to All
            </button>
          </div>
        )}

        {/* Loading Spinner Screen */}
        {loading && (
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-12 text-center flex flex-col items-center justify-center gap-4">
            <Loader2 className="w-10 h-10 text-indigo-650 dark:text-indigo-400 animate-spin" />
            <p className="text-sm font-bold text-slate-700 dark:text-slate-350">Stanza NLP pipeline in progress...</p>
            <p className="text-xs text-slate-400 dark:text-slate-500 max-w-sm leading-normal">
              Running relation extraction match checks. First execution might take 30-60 seconds to cache language modules.
            </p>
          </div>
        )}

        {/* ═══════════════ REVIEW STEP ═══════════════ */}
        {step === "review" && !loading && (
          <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
            <div className="px-5 py-4.5 border-b border-slate-100 dark:border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                  <BookOpen size={16} className="text-indigo-600 dark:text-indigo-400" />
                  <span>Evaluation Data Review</span>
                </h2>
                <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                  Validate sentence content and gold triple counts prior to running NLP comparative evaluation.
                </p>
              </div>
              <button
                onClick={handleRun}
                disabled={loading || !sessionId}
                className="inline-flex items-center gap-1.5 px-4.5 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-bold rounded-xl transition-all shadow-sm active:scale-95 cursor-pointer"
              >
                <RefreshCw size={13} className="animate-spin-slow" /> Run Evaluation
              </button>
            </div>

            {previewLoading && (
              <div className="py-12 flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 text-indigo-600 animate-spin" />
                <span className="text-xs text-slate-500 dark:text-slate-400 font-semibold">Generating worksheet statistics...</span>
              </div>
            )}

            {preview && !previewLoading && (
              <>
                {/* Stats board */}
                <div className="px-5 py-4 bg-slate-50/50 dark:bg-slate-950/20 border-b border-slate-100 dark:border-slate-800/85 grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="flex flex-col">
                    <span className="text-xl sm:text-2xl font-extrabold text-indigo-650 dark:text-indigo-400 tabular-nums">
                      {preview.total_sentences}
                    </span>
                    <span className="text-[10px] font-bold text-slate-450 dark:text-slate-550 uppercase tracking-wider mt-0.5">Total Sentences</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xl sm:text-2xl font-extrabold text-emerald-600 dark:text-emerald-405 tabular-nums">
                      {preview.sentences_with_text}
                    </span>
                    <span className="text-[10px] font-bold text-slate-455 dark:text-slate-550 uppercase tracking-wider mt-0.5">With Text Content</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xl sm:text-2xl font-extrabold text-purple-650 dark:text-purple-400 tabular-nums">
                      {preview.sentences_with_gold}
                    </span>
                    <span className="text-[10px] font-bold text-slate-455 dark:text-slate-550 uppercase tracking-wider mt-0.5">With Gold Triples</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-xl sm:text-2xl font-extrabold text-amber-600 dark:text-amber-400 tabular-nums">
                      {preview.total_gold_triples}
                    </span>
                    <span className="text-[10px] font-bold text-slate-455 dark:text-slate-550 uppercase tracking-wider mt-0.5">Total Gold Triples</span>
                  </div>
                </div>

                {/* Sentences table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-50 dark:bg-slate-950 text-[10px] font-bold uppercase tracking-wider text-slate-450 dark:text-slate-500 border-b border-slate-100 dark:border-slate-800">
                      <tr>
                        <th className="px-4.5 py-3 w-12 text-center">#</th>
                        <th className="px-4.5 py-3">Sentence Text</th>
                        <th className="px-4.5 py-3 text-center">Total Triples</th>
                        <th className="px-4.5 py-3 text-center">Graded</th>
                        <th className="px-4.5 py-3 text-center">Gold Used</th>
                        <th className="px-4.5 py-3 text-center">Evaluation Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                      {preview.sentences.map((s, i) => (
                        <tr key={s.sentence_id ?? i} className="hover:bg-slate-50/50 dark:hover:bg-slate-950/40 transition-colors">
                          <td className="px-4.5 py-3 text-center text-slate-400 dark:text-slate-500 font-mono tabular-nums">
                            {s.sentence_id}
                          </td>
                          <td className="px-4.5 py-3 text-slate-700 dark:text-slate-300 max-w-sm">
                            <span className="line-clamp-2 leading-relaxed" title={s.text}>
                              {s.text || <span className="italic text-slate-350 dark:text-slate-600">No text content</span>}
                            </span>
                          </td>
                          <td className="px-4.5 py-3 text-center text-slate-650 dark:text-slate-400 tabular-nums">
                            {s.total_triples}
                          </td>
                          <td className="px-4.5 py-3 text-center text-slate-650 dark:text-slate-400 tabular-nums">
                            {s.graded_triples}
                          </td>
                          <td className="px-4.5 py-3 text-center text-indigo-600 dark:text-indigo-400 font-bold tabular-nums">
                            {s.gold_triples_used}
                          </td>
                          <td className="px-4.5 py-3 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              <StatusBadge ok={s.has_text} label="Text" />
                              <StatusBadge ok={s.gold_triples_used > 0} label="Gold" />
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {/* ═══════════════ RESULTS STEP ═══════════════ */}
        {step === "results" && result && !loading && (
          <>
            {/* Metadata bar */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl px-5 py-3.5 flex items-center gap-4 flex-wrap text-xs text-slate-500 dark:text-slate-450 shadow-sm leading-relaxed">
              <span className="flex items-center gap-1 text-[11px]">
                <Calendar size={13} className="text-slate-400" />
                <span>Session: <span className="font-mono text-slate-700 dark:text-slate-300 font-semibold">{result.session_id.slice(0, 8)}...</span></span>
              </span>
              <span className="text-slate-300 dark:text-slate-800">|</span>
              <span>File: <span className="font-semibold text-slate-700 dark:text-slate-300">{result.source_filename}</span></span>
              <span className="text-slate-300 dark:text-slate-800">|</span>
              <span>Mode: <span className={`font-bold uppercase tracking-wide text-[10px] ${result.match_mode === "exact" ? "text-amber-600" : "text-indigo-600 dark:text-indigo-400"}`}>{result.match_mode}</span></span>
              <span className="text-slate-300 dark:text-slate-800">|</span>
              <span>Gold Target: <span className="font-semibold text-emerald-700 dark:text-emerald-450">{result.gold_source === "all" ? "All Triples" : "Graded Only"}</span></span>
              <span className="text-slate-300 dark:text-slate-800">|</span>
              <span>Sentences: <span className="font-semibold text-slate-700 dark:text-slate-300">{result.total_sentences}</span></span>
              <button
                onClick={handleBackToReview}
                className="sm:ml-auto text-xs text-indigo-600 dark:text-indigo-400 hover:underline font-bold cursor-pointer"
              >
                &larr; Back to review configuration
              </button>
            </div>

            {/* Evaluation Type Tabs */}
            <div className="flex gap-2 p-1 bg-slate-100 dark:bg-slate-900 rounded-2xl border border-slate-200/60 dark:border-slate-800">
              <button
                onClick={() => setActiveTab("openie")}
                className={`flex-1 py-3 rounded-xl text-xs sm:text-sm font-bold transition-all cursor-pointer flex items-center justify-center gap-2 ${
                  activeTab === "openie"
                    ? "bg-white dark:bg-slate-800 text-indigo-650 dark:text-indigo-400 shadow-sm"
                    : "text-slate-500 hover:text-slate-750 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                <Zap size={16} /> OpenIE Soft/Exact Matching
              </button>
              <button
                onClick={() => setActiveTab("standard")}
                className={`flex-1 py-3 rounded-xl text-xs sm:text-sm font-bold transition-all cursor-pointer flex items-center justify-center gap-2 ${
                  activeTab === "standard"
                    ? "bg-white dark:bg-slate-800 text-indigo-650 dark:text-indigo-400 shadow-sm"
                    : "text-slate-500 hover:text-slate-750 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                <PieChart size={16} /> Normal (Standard) Evaluation
              </button>
            </div>

            {/* Results boards */}
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 5 }}
                transition={{ duration: 0.15 }}
              >
                {activeTab === "openie" ? (
                  <EvaluationSection
                    evalData={
                      result.openie_evaluation || {
                        per_sentence: result.per_sentence,
                        macro: result.macro,
                        micro: result.micro,
                      }
                    }
                    accent="blue"
                    triplesTitle="OpenIE Extracted Triples details comparison"
                  />
                ) : (
                  <EvaluationSection
                    evalData={
                      result.standard_evaluation || {
                        per_sentence: result.per_sentence,
                        macro: result.macro,
                        micro: result.micro,
                      }
                    }
                    accent="amber"
                    triplesTitle="Standard Evaluation Triples details comparison"
                  />
                )}
              </motion.div>
            </AnimatePresence>

            {/* Re-run execution block at bottom */}
            <div className="flex justify-center pt-4 border-t border-slate-100 dark:border-slate-900">
              <button
                onClick={handleRun}
                disabled={loading}
                className="inline-flex items-center gap-1.5 px-6 py-3 bg-indigo-600 hover:bg-indigo-755 text-white text-xs font-bold rounded-xl shadow-md transition-all active:scale-95 cursor-pointer"
              >
                <RefreshCw size={13} /> Re-run NLP Analysis
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
