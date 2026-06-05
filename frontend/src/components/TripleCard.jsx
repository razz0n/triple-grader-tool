import { useState, useEffect } from "react";

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
      <div className="border-l-4 border-l-amber-500 p-5 bg-white space-y-3">
        <div className="text-xs font-semibold text-amber-700 flex items-center gap-1">
          <span>✏️</span> Edit Suggested Triple
        </div>
        <div className="space-y-2">
          <input
            type="text"
            value={sub}
            onChange={(e) => setSub(e.target.value)}
            placeholder="Subject"
            className="w-full border border-slate-300 rounded px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
          />
          <input
            type="text"
            value={pred}
            onChange={(e) => setPred(e.target.value)}
            placeholder="Predicate"
            className="w-full border border-slate-300 rounded px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <input
            type="text"
            value={obj}
            onChange={(e) => setObj(e.target.value)}
            placeholder="Object"
            className="w-full border border-slate-300 rounded px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-teal-300"
          />
        </div>
        <div className="flex gap-2 justify-end">
          <button
            onClick={handleCancelClick}
            className="px-3 py-1 text-xs bg-white border border-slate-300 rounded text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSaveClick}
            className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors font-medium"
          >
            Save
          </button>
        </div>
      </div>
    );
  }

  const cardBg = triple?.marked_for_removal
    ? "bg-red-50 border-l-red-500"
    : isNewPending
    ? "bg-amber-50/20 border-l-amber-500 border-dashed"
    : isNewApproved
    ? "bg-emerald-50/10 border-l-emerald-500"
    : "bg-white border-l-blue-500";

  return (
    <div className={`border-l-4 p-5 transition-shadow ${cardBg}`}>
      {/* Removal status badge */}
      {triple?.marked_for_removal && (
        <div className="mb-3 px-3 py-1.5 bg-red-100 border border-red-300 rounded-lg text-xs font-semibold text-red-700">
          ⚠ Marked for removal: {triple.removal_reason || "Not needed"}
        </div>
      )}

      {/* Suggested triple status badge */}
      {isNewPending && (
        <div className="mb-3 px-3 py-1.5 bg-amber-100 border border-amber-300 rounded-lg text-xs font-semibold text-amber-800 flex items-center justify-between gap-2">
          <span>💡 Suggested Triple (Pending Owner Approval) — Added by {triple.suggested_by || "User"}</span>
          <div className="flex items-center gap-1.5">
            {canApprove && (
              <button
                type="button"
                onClick={() => onApproveSuggestedTriple?.(triple.id)}
                className="px-2 py-0.5 bg-emerald-600 hover:bg-emerald-700 text-white text-[10px] rounded font-bold transition-colors"
              >
                ✓ Approve
              </button>
            )}
            {!readOnly && (
              <>
                <button
                  type="button"
                  onClick={() => onSetTripleEditing?.(triple.id, true)}
                  className="px-2 py-0.5 bg-blue-600 hover:bg-blue-700 text-white text-[10px] rounded font-bold transition-colors"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => onRemoveSuggestedTriple?.(triple.id)}
                  className="px-2 py-0.5 bg-red-600 hover:bg-red-700 text-white text-[10px] rounded font-bold transition-colors"
                >
                  Remove
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {isNewApproved && (
        <div className="mb-3 px-3 py-1.5 bg-emerald-100 border border-emerald-300 rounded-lg text-xs font-semibold text-emerald-800 flex items-center justify-between gap-2">
          <span>✓ Suggested Triple (Approved) — Added by {triple.suggested_by || "User"}</span>
          {!readOnly && (
            <button
              type="button"
              onClick={() => onRemoveSuggestedTriple?.(triple.id)}
              className="px-2 py-0.5 bg-red-600 hover:bg-red-700 text-white text-[10px] rounded font-bold transition-colors"
            >
              Remove
            </button>
          )}
        </div>
      )}

      {/* Subject → Predicate → Object badges */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <button
          type="button"
          onClick={() => emitTripleCopy("subject")}
          disabled={!canSuggest}
          className={[
            "inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border transition-colors",
            canSuggest
              ? "bg-blue-100 text-blue-800 border-blue-200 hover:bg-blue-200"
              : "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed",
          ].join(" ")}
          title="Copy subject into suggestion form"
        >
          {subject}
        </button>
        <span className="text-slate-400 font-bold text-lg">→</span>
        <button
          type="button"
          onClick={() => emitTripleCopy("predicate")}
          disabled={!canSuggest}
          className={[
            "inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border transition-colors",
            canSuggest
              ? "bg-indigo-100 text-indigo-800 border-indigo-200 hover:bg-indigo-200"
              : "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed",
          ].join(" ")}
          title="Copy predicate into suggestion form"
        >
          {predicate}
        </button>
        <span className="text-slate-400 font-bold text-lg">→</span>
        <button
          type="button"
          onClick={() => emitTripleCopy("object")}
          disabled={!canSuggest}
          className={[
            "inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border transition-colors",
            canSuggest
              ? "bg-teal-100 text-teal-800 border-teal-200 hover:bg-teal-200"
              : "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed",
          ].join(" ")}
          title="Copy object into suggestion form"
        >
          {object}
        </button>
        {canSuggest && (
          <div className="ml-auto flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => onAddTripleAdjacent?.(triple.id, "above")}
              className="px-2 py-1 text-xs bg-purple-50 text-purple-700 border border-purple-200 rounded hover:bg-purple-100 transition-colors font-medium"
              title="Add a new triple above this one"
            >
              + Add Above
            </button>
            <button
              type="button"
              onClick={() => onAddTripleAdjacent?.(triple.id, "below")}
              className="px-2 py-1 text-xs bg-purple-50 text-purple-700 border border-purple-200 rounded hover:bg-purple-100 transition-colors font-medium"
              title="Add a new triple below this one"
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
              className="px-2 py-1 text-xs bg-green-50 text-green-700 border border-green-200 rounded hover:bg-green-100 transition-colors font-medium"
              title="Create a new suggestion"
            >
              + New Suggestion
            </button>
          </div>
        )}
      </div>

      {/* Triple Quality Section */}
      {!isNewPending && (
        <div className="space-y-3 border-t border-slate-100 pt-3">
          {/* Overall Grade (Quality) */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs font-semibold text-slate-500 w-24 shrink-0">Quality (0-10)</span>

            <div className="flex items-center gap-1 flex-wrap">
              {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                <button
                  key={n}
                  onClick={() => onChange(grade === n ? null : n)}
                  disabled={readOnly}
                  className={[
                    "w-6 h-6 rounded-full text-xs font-semibold border transition-all",
                    "focus:outline-none focus:ring-2 focus:ring-blue-400",
                    grade === n
                      ? "bg-blue-700 text-white border-blue-700 scale-110 shadow"
                      : "bg-white text-slate-600 border-slate-300 hover:bg-blue-50 hover:border-blue-400",
                    readOnly ? "opacity-70 cursor-not-allowed" : "",
                  ].join(" ")}
                >
                  {n}
                </button>
              ))}
            </div>

            {grade !== null && grade !== undefined ? (
              <span className="ml-1 text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
                {grade}/10
              </span>
            ) : (
              <span className="ml-1 text-xs text-slate-400 italic">not graded</span>
            )}
          </div>

          {allGrades.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pl-[6.5rem]">
              {allGrades.map((entry) => {
                const isMine = currentUserId && entry.userId === currentUserId;
                return (
                  <span
                    key={`${entry.userId}-${entry.grade}`}
                    className={[
                      "text-xs font-medium border px-2 py-1 rounded-full",
                      isMine
                        ? "bg-blue-100 text-blue-800 border-blue-300"
                        : "bg-amber-100 text-amber-800 border-amber-300",
                    ].join(" ")}
                  >
                    {entry.userName}
                    {isMine ? " (you)" : ""}
                    : {entry.grade}/10
                  </span>
                );
              })}
            </div>
          )}

          {!allGrades.length && author && (
            <div className="pl-[6.5rem]">
              <span className="text-xs font-medium bg-amber-100 text-amber-800 border border-amber-300 px-2 py-1 rounded-full">
                By {author}
              </span>
            </div>
          )}
        </div>
      )}



      {/* Mark for removal section */}
      {canSuggest && !isNewPending && (
        <div className="mt-3 pt-3 border-t border-slate-100">
          <button
            type="button"
            onClick={() => onMarkForRemoval?.(triple.id, !triple?.marked_for_removal)}
            className={`text-xs px-2 py-1 rounded font-medium transition-colors ${
              triple?.marked_for_removal
                ? "bg-red-100 text-red-700 border border-red-300 hover:bg-red-200"
                : "bg-slate-100 text-slate-600 border border-slate-300 hover:bg-red-50 hover:text-red-700 hover:border-red-300"
            }`}
            title={triple?.marked_for_removal ? "Undo removal request" : "Mark this triple as not needed"}
          >
            {triple?.marked_for_removal ? "✕ Undo Removal" : "⚠ Not Needed"}
          </button>
        </div>
      )}
    </div>
  );
}
