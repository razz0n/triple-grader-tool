// TripleCard.jsx — Displays one triple with ratings and author info

export default function TripleCard({ triple, grade, completeness, relation, author, onChange, onCompletenessChange, onRelationChange }) {
  const { subject, predicate, object } = triple;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow">
      {/* Author badge in top-right */}
      {author && (
        <div className="flex justify-end mb-2">
          <span className="text-xs font-medium bg-amber-100 text-amber-800 border border-amber-300 px-2 py-1 rounded-full">
            By {author}
          </span>
        </div>
      )}

      {/* Subject → Predicate → Object badges */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 border border-blue-200">
          {subject}
        </span>
        <span className="text-slate-400 font-bold text-lg">→</span>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-800 border border-indigo-200">
          {predicate}
        </span>
        <span className="text-slate-400 font-bold text-lg">→</span>
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-teal-100 text-teal-800 border border-teal-200">
          {object}
        </span>
      </div>

      {/* Quality Grades Section */}
      <div className="space-y-3 border-t border-slate-100 pt-3">
        {/* Overall Grade (Quality) */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-semibold text-slate-500 w-24 shrink-0">Quality (0-10)</span>

          <div className="flex items-center gap-1 flex-wrap">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
              <button
                key={n}
                onClick={() => onChange(n)}
                className={[
                  "w-6 h-6 rounded-full text-xs font-semibold border transition-all",
                  "focus:outline-none focus:ring-2 focus:ring-blue-400",
                  grade === n
                    ? "bg-blue-700 text-white border-blue-700 scale-110 shadow"
                    : "bg-white text-slate-600 border-slate-300 hover:bg-blue-50 hover:border-blue-400",
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

        {/* Completeness */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-semibold text-slate-500 w-24 shrink-0">Completeness</span>

          <div className="flex items-center gap-1 flex-wrap">
            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
              <button
                key={n}
                onClick={() => onCompletenessChange(n)}
                className={[
                  "w-5 h-5 rounded text-xs font-semibold border transition-all",
                  "focus:outline-none focus:ring-2 focus:ring-green-400",
                  completeness === n
                    ? "bg-green-600 text-white border-green-600 scale-110 shadow"
                    : "bg-white text-slate-600 border-slate-300 hover:bg-green-50 hover:border-green-400",
                ].join(" ")}
              >
                {n === 10 ? "✓" : n}
              </button>
            ))}
          </div>

          {completeness !== null && completeness !== undefined ? (
            <span className="ml-1 text-xs font-bold text-green-700 bg-green-50 px-2 py-0.5 rounded-full border border-green-200">
              {completeness}/10
            </span>
          ) : (
            <span className="ml-1 text-xs text-slate-400 italic">not set</span>
          )}
        </div>

        {/* Relation */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-semibold text-slate-500 w-24 shrink-0">Relation</span>

          <div className="flex items-center gap-1 flex-wrap">
            {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
              <button
                key={n}
                onClick={() => onRelationChange(n)}
                className={[
                  "w-5 h-5 rounded text-xs font-semibold border transition-all",
                  "focus:outline-none focus:ring-2 focus:ring-purple-400",
                  relation === n
                    ? "bg-purple-600 text-white border-purple-600 scale-110 shadow"
                    : "bg-white text-slate-600 border-slate-300 hover:bg-purple-50 hover:border-purple-400",
                ].join(" ")}
              >
                {n === 10 ? "✓" : n}
              </button>
            ))}
          </div>

          {relation !== null && relation !== undefined ? (
            <span className="ml-1 text-xs font-bold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full border border-purple-200">
              {relation}/10
            </span>
          ) : (
            <span className="ml-1 text-xs text-slate-400 italic">not set</span>
          )}
        </div>
      </div>
    </div>
  );
}
