import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Edit3,
  AlertCircle,
  CheckCircle2,
  ArrowRight,
  Plus,
  Trash2,
  X,
  Copy,
  ChevronRight,
  Check,
  User
} from "lucide-react";

export default function TripleCard({
  triple,
  grade,
  author,
  gradesByUser = {},
  currentUserId,
  readOnly = false,
  canSuggest = true,
  canApprove = false,
  onChange,
  onAddTripleComment,
  onDeleteTripleComment,
  onMarkForRemoval,
  onAddTripleAdjacent,
  onRemoveSuggestedTriple,
  onApproveSuggestedTriple,
  onSaveSuggestedTriple,
  onSetTripleEditing,
  onApproveDeletion,
  index,
}) {
  const { subject, predicate, object } = triple;

  const [sub, setSub] = useState(subject || "");
  const [pred, setPred] = useState(predicate || "");
  const [obj, setObj] = useState(object || "");

  useEffect(() => {
    setSub(subject || "");
    setPred(predicate || "");
    setObj(object || "");
  }, [subject, predicate, object]);

  const isNewPending = triple?.is_new_suggestion && triple?.status !== "approved";
  const isNewApproved = triple?.is_new_suggestion && triple?.status === "approved";

  const handleSaveClick = () => {
    if (!sub.trim() || !pred.trim() || !obj.trim()) {
      alert("All fields (Subject, Predicate, Object) are required.");
      return;
    }
    onSaveSuggestedTriple?.(triple.id, {
      subject: sub.trim(),
      predicate: pred.trim(),
      object: obj.trim(),
    });
  };

  const handleCancelClick = () => {
    if (!triple.subject && !triple.predicate && !triple.object) {
      onRemoveSuggestedTriple?.(triple.id);
    } else {
      onSetTripleEditing?.(triple.id, false);
    }
  };

  const allGrades = Object.values(gradesByUser || {})
    .map((entry) => {
      const value = Number(entry?.grade);
      if (!Number.isFinite(value)) return null;
      return {
        userId: String(entry?.user_id || ""),
        userName: String(entry?.user_name || "Unknown"),
        grade: value,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.userName.localeCompare(b.userName));

  const emitTripleCopy = (field) => {
    window.dispatchEvent(
      new CustomEvent("triple-copy", {
        detail: { tripleId: triple.id, field },
      })
    );
  };

  if (isNewPending && triple.is_editing) {
    return (
      <div className="border-l-4 border-l-amber-500 dark:border-l-amber-600 p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-4 shadow-sm">
        <div className="text-xs font-bold text-amber-700 dark:text-amber-400 flex items-center gap-1.5 uppercase tracking-wider">
          <Edit3 size={14} />
          <span>Edit Suggested Triple</span>
        </div>
        <div className="grid grid-cols-1 gap-2.5">
          <div>
            <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-1 block">Subject</label>
            <input
              type="text"
              value={sub}
              onChange={(e) => setSub(e.target.value)}
              placeholder="Subject"
              className="w-full border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-xs bg-slate-50/50 dark:bg-slate-950 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white"
            />
          </div>
          <div>
            <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-1 block">Predicate</label>
            <input
              type="text"
              value={pred}
              onChange={(e) => setPred(e.target.value)}
              placeholder="Predicate"
              className="w-full border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-xs bg-slate-50/50 dark:bg-slate-950 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white"
            />
          </div>
          <div>
            <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-1 block">Object</label>
            <input
              type="text"
              value={obj}
              onChange={(e) => setObj(e.target.value)}
              placeholder="Object"
              className="w-full border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-xs bg-slate-50/50 dark:bg-slate-950 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white"
            />
          </div>
        </div>
        <div className="flex gap-2 justify-end pt-1">
          <button
            onClick={handleCancelClick}
            className="px-3.5 py-2 rounded-xl text-xs font-bold bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={handleSaveClick}
            className="px-3.5 py-2 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-colors cursor-pointer"
          >
            Save Changes
          </button>
        </div>
      </div>
    );
  }

  const borderLeftColor = triple?.marked_for_removal
    ? "border-l-rose-500 dark:border-l-rose-600 bg-rose-50/40 dark:bg-rose-950/20"
    : isNewPending
    ? "border-l-amber-500 dark:border-l-amber-600 bg-amber-50/40 dark:bg-amber-950/20 border-dashed"
    : isNewApproved
    ? "border-l-emerald-500 dark:border-l-emerald-600 bg-emerald-50/40 dark:bg-emerald-950/20"
    : "border-l-indigo-600 dark:border-l-indigo-500 bg-slate-50/80 dark:bg-slate-900/50";

  return (
    <div className={`border border-slate-200/80 dark:border-slate-800 rounded-2xl border-l-4 p-5 transition-all duration-200 hover:shadow-sm ${borderLeftColor}`}>
      {index !== undefined && (
        <div className="flex items-center justify-between mb-3.5 text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider select-none">
          <span>Triple #{index + 1}</span>
        </div>
      )}
      
      {/* Removal Request alert */}
      {triple?.marked_for_removal && (
        <>
          {/* Owner view */}
          {canApprove && (
            <div className="mb-3 px-3 py-2.5 bg-rose-50 dark:bg-rose-950/35 border border-rose-200 dark:border-rose-900/40 rounded-xl text-xs font-semibold text-rose-800 dark:text-rose-400 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <span className="flex items-start gap-2">
                <AlertCircle size={16} className="text-rose-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Request deletion by {triple.marked_for_removal_by_name || "Grader"}:</span> {triple.removal_reason || "Requested removal."}
                </div>
              </span>
              <div className="flex items-center gap-2 justify-end self-end sm:self-center shrink-0">
                <button
                  type="button"
                  onClick={() => onApproveDeletion?.(triple.id)}
                  className="px-2.5 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-[10px] rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1 active:scale-95 shadow-sm"
                >
                  <Trash2 size={11} /> Approve Deletion
                </button>
                <button
                  type="button"
                  onClick={() => onMarkForRemoval?.(triple.id, false)}
                  className="px-2.5 py-1.5 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 text-[10px] rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1 active:scale-95"
                >
                  <X size={11} /> Cancel Request
                </button>
              </div>
            </div>
          )}
          {/* Requester view (Grader who requested it) */}
          {!canApprove && triple.marked_for_removal_by === currentUserId && (
            <div className="mb-3 px-3 py-2.5 bg-rose-50 dark:bg-rose-950/35 border border-rose-200 dark:border-rose-900/40 rounded-xl text-xs font-semibold text-rose-800 dark:text-rose-400 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <span className="flex items-start gap-2">
                <AlertCircle size={16} className="text-rose-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">You requested deletion:</span> {triple.removal_reason || "Requested removal."}
                </div>
              </span>
              <div className="flex items-center gap-2 justify-end self-end sm:self-center shrink-0">
                <button
                  type="button"
                  onClick={() => onMarkForRemoval?.(triple.id, false)}
                  className="px-2.5 py-1.5 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 text-[10px] rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1 active:scale-95"
                >
                  <X size={11} /> Cancel Request
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Suggested Pending Alert */}
      {isNewPending && (
        <div className="mb-3 px-3.5 py-2.5 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/40 rounded-xl text-xs font-semibold text-amber-800 dark:text-amber-400 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <span className="flex items-center gap-1.5">
            <AlertCircle size={16} className="text-amber-600 shrink-0" />
            Suggested Triple (Pending Owner Approval) &bull; By {triple.suggested_by || "Grader"}
          </span>
          <div className="flex items-center gap-2 justify-end self-end sm:self-center">
            {canApprove && (
              <button
                type="button"
                onClick={() => onApproveSuggestedTriple?.(triple.id)}
                className="px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-[10px] rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1 active:scale-95"
              >
                <Check size={11} /> Approve
              </button>
            )}
            {!readOnly && (
              <>
                <button
                  type="button"
                  onClick={() => onSetTripleEditing?.(triple.id, true)}
                  className="px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-[10px] rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1 active:scale-95"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => onRemoveSuggestedTriple?.(triple.id)}
                  className="px-2.5 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-[10px] rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1 active:scale-95"
                >
                  <Trash2 size={11} /> Remove
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Suggested Approved Alert */}
      {isNewApproved && (
        <div className="mb-3 px-3.5 py-2.5 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/30 rounded-xl text-xs font-semibold text-emerald-800 dark:text-emerald-400 flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 size={16} className="text-emerald-600" />
            Approved Suggestion &bull; Added by {triple.suggested_by || "Grader"}
          </span>
          {!readOnly && (
            <button
              type="button"
              onClick={() => onRemoveSuggestedTriple?.(triple.id)}
              className="px-2.5 py-1.5 bg-rose-600 hover:bg-rose-700 text-white text-[10px] rounded-lg font-bold transition-all cursor-pointer flex items-center gap-1 active:scale-95"
            >
              <Trash2 size={11} /> Remove
            </button>
          )}
        </div>
      )}

      {/* Subject → Predicate → Object Badge Controls */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button
          type="button"
          onClick={() => emitTripleCopy("subject")}
          disabled={!canSuggest}
          className={`inline-flex items-center px-3.5 py-1.5 rounded-xl text-xs font-bold border transition-all ${
            canSuggest
              ? "bg-indigo-50 border-indigo-100 text-indigo-700 dark:bg-indigo-950/40 dark:border-indigo-900/50 dark:text-indigo-300 hover:bg-indigo-100/80 dark:hover:bg-indigo-900/70 cursor-pointer"
              : "bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-600 border-slate-200 dark:border-slate-800 cursor-not-allowed"
          }`}
          title="Copy subject to suggestion box"
        >
          {subject}
        </button>
        <ChevronRight size={14} className="text-slate-400" />
        
        <button
          type="button"
          onClick={() => emitTripleCopy("predicate")}
          disabled={!canSuggest}
          className={`inline-flex items-center px-3.5 py-1.5 rounded-xl text-xs font-bold border transition-all ${
            canSuggest
              ? "bg-emerald-50 border-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:border-emerald-900/50 dark:text-emerald-300 hover:bg-emerald-100/80 dark:hover:bg-emerald-900/70 cursor-pointer"
              : "bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-600 border-slate-200 dark:border-slate-800 cursor-not-allowed"
          }`}
          title="Copy predicate to suggestion box"
        >
          {predicate}
        </button>
        <ChevronRight size={14} className="text-slate-400" />

        <button
          type="button"
          onClick={() => emitTripleCopy("object")}
          disabled={!canSuggest}
          className={`inline-flex items-center px-3.5 py-1.5 rounded-xl text-xs font-bold border transition-all ${
            canSuggest
              ? "bg-purple-50 border-purple-100 text-purple-700 dark:bg-purple-950/40 dark:border-purple-900/50 dark:text-purple-300 hover:bg-purple-100/80 dark:hover:bg-purple-900/70 cursor-pointer"
              : "bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-600 border-slate-200 dark:border-slate-800 cursor-not-allowed"
          }`}
          title="Copy object to suggestion box"
        >
          {object}
        </button>

        {canSuggest && (
          <div className="ml-auto flex items-center gap-1.5 pt-2 lg:pt-0">
            <button
              type="button"
              onClick={() => onAddTripleAdjacent?.(triple.id, "above")}
              className="px-2.5 py-1.5 border border-slate-200 dark:border-slate-800 hover:border-slate-300 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100/80 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 text-[10px] rounded-lg font-bold transition-all cursor-pointer"
              title="Insert a new empty triple above this"
            >
              + Add Above
            </button>
            <button
              type="button"
              onClick={() => onAddTripleAdjacent?.(triple.id, "below")}
              className="px-2.5 py-1.5 border border-slate-200 dark:border-slate-800 hover:border-slate-300 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100/80 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 text-[10px] rounded-lg font-bold transition-all cursor-pointer"
              title="Insert a new empty triple below this"
            >
              + Add Below
            </button>
            <button
              type="button"
              onClick={() =>
                window.dispatchEvent(
                  new CustomEvent("triple-copy", {
                    detail: { tripleId: triple.id, action: "new" },
                  })
                )
              }
              className="px-2.5 py-1.5 border border-indigo-200 dark:border-indigo-900/50 bg-indigo-50/40 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 text-[10px] rounded-lg font-bold transition-all hover:bg-indigo-100/50 cursor-pointer"
              title="Create a new suggestion thread"
            >
              + New Suggestion
            </button>
          </div>
        )}
      </div>

      {/* Triple Quality Grades */}
      {!isNewPending && (
        <div className="space-y-3.5 border-t border-slate-100 dark:border-slate-800/80 pt-4">
          <div className="flex items-center gap-3.5 flex-wrap">
            <span className="text-[11px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider w-24 shrink-0">
              Quality Grade
            </span>

            <div className="flex items-center gap-1 flex-wrap">
              {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                <button
                  key={n}
                  onClick={() => onChange(grade === n ? null : n)}
                  disabled={readOnly}
                  className={`grade-button w-6 h-6 rounded-full text-xs font-bold border transition-all cursor-pointer flex items-center justify-center ${
                    grade === n
                      ? "bg-indigo-600 border-indigo-600 text-white scale-110 shadow-sm"
                      : "bg-white dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-950/30"
                  } ${readOnly ? "opacity-60 cursor-not-allowed" : ""}`}
                >
                  {n}
                </button>
              ))}
            </div>

            {grade !== null && grade !== undefined ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-250 dark:border-emerald-900/40 px-2 py-0.5 rounded-full">
                <Check size={11} className="shrink-0" />
                <span>Scored: {grade}/10</span>
              </span>
            ) : !readOnly ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-rose-700 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/40 px-2 py-0.5 rounded-full animate-pulse">
                <AlertCircle size={11} className="shrink-0" />
                <span>Ungraded</span>
              </span>
            ) : null}
          </div>

          {/* Grader list output */}
          {allGrades.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pl-0 md:pl-[6.5rem]">
              {allGrades.map((entry) => {
                const isMine = currentUserId && entry.userId === currentUserId;
                return (
                  <span
                    key={`${entry.userId}-${entry.grade}`}
                    className={`inline-flex items-center gap-1.5 text-[10px] font-semibold border px-2.5 py-1 rounded-full ${
                      isMine
                        ? "bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-400 border-indigo-250 dark:border-indigo-900"
                        : "bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-400 border-amber-250 dark:border-amber-900"
                    }`}
                  >
                    <User size={10} />
                    <span>{entry.userName}</span>
                    {isMine && <span className="text-[9px] opacity-75">(you)</span>}
                    <span className="opacity-40">&bull;</span>
                    <span className="font-bold">{entry.grade}/10</span>
                  </span>
                );
              })}
            </div>
          )}

          {!allGrades.length && author && (
            <div className="pl-0 md:pl-[6.5rem]">
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-900/50 px-2.5 py-1 rounded-full">
                <User size={10} />
                <span>Original by {author}</span>
              </span>
            </div>
          )}
        </div>
      )}

      {/* Mark for removal action */}
      {canSuggest && !isNewPending && (
        (!triple?.marked_for_removal || triple?.marked_for_removal_by === currentUserId) && (
          <div className="mt-3.5 pt-3.5 border-t border-slate-100 dark:border-slate-800/80 flex justify-start">
            <button
              type="button"
              onClick={() => onMarkForRemoval?.(triple.id, !triple?.marked_for_removal)}
              className={`inline-flex items-center gap-1 text-[10px] px-2.5 py-1.5 rounded-lg font-bold border transition-colors cursor-pointer ${
                triple?.marked_for_removal
                  ? "bg-rose-50 dark:bg-rose-950/20 text-rose-700 border-rose-300 hover:bg-rose-100 dark:hover:bg-rose-900/30"
                  : "bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-950/20 dark:hover:text-rose-400 border-slate-200 dark:border-slate-700 hover:border-rose-250 dark:hover:bg-rose-900"
              }`}
              title={triple?.marked_for_removal ? "Cancel deletion request" : "Request deletion of this triple"}
            >
              {triple?.marked_for_removal ? (
                <>
                  <X size={11} /> Cancel Deletion Request
                </>
              ) : (
                <>
                  <AlertCircle size={11} /> Request Deletion
                </>
              )}
            </button>
          </div>
        )
      )}
    </div>
  );
}
