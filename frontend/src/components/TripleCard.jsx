// TripleCard.jsx — Displays one triple with quality rating and author info

export default function TripleCard({
  triple,
  grade,
  author,
  gradesByUser = {},
  currentUserId,
  readOnly = false,
  canSuggest = true,
  onChange,
}) {
  const { subject, predicate, object } = triple;
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

  return (
    <div className="bg-white border-t border-r border-b border-slate-200 border-l-4 border-l-blue-500 rounded-none p-4 shadow-none transition-shadow">
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
          <button
            type="button"
            onClick={() =>
              window.dispatchEvent(
                new CustomEvent("triple-copy", {
                  detail: { tripleId: triple.id, action: "new" },
                })
              )
            }
            className="ml-auto px-2 py-1 text-xs bg-green-50 text-green-700 border border-green-200 rounded hover:bg-green-100 transition-colors font-medium"
            title="Create a new suggestion"
          >
            + New Suggestion
          </button>
        )}
      </div>

      {/* Triple Quality Section */}
      <div className="space-y-3 border-t border-slate-100 pt-3">
        {/* Overall Grade (Quality) */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-semibold text-slate-500 w-24 shrink-0">Quality (0-10)</span>

          <div className="flex items-center gap-1 flex-wrap">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
              <button
                key={n}
                onClick={() => onChange(n)}
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
    </div>
  );
}
