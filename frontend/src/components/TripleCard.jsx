// TripleCard.jsx — Displays one triple with a 1-10 rating using button pickers

export default function TripleCard({ triple, grade, onChange }) {
  const { subject, predicate, object } = triple;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow">
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

      {/* Rating row */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-xs font-semibold text-slate-500 w-10 shrink-0">Grade</span>

        <div className="flex items-center gap-1 flex-wrap">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
            <button
              key={n}
              onClick={() => onChange(n)}
              className={[
                "w-7 h-7 rounded-full text-xs font-semibold border transition-all",
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
          <span className="ml-1 text-sm font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
            {grade}/10
          </span>
        ) : (
          <span className="ml-1 text-xs text-slate-400 italic">not graded</span>
        )}
      </div>
    </div>
  );
}
