// TripleSuggestions.jsx — Displays suggestions for a triple with voting

import { useState } from "react";

export default function TripleSuggestions({ 
  triple, 
  onAddSuggestion, 
  onVote, 
  onDeleteSuggestion,
  currentUserName 
}) {
  const { subject, predicate, object, suggestions = [] } = triple;
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    subject: "",
    predicate: "",
    object: "",
    reason: "",
  });

  const handleQuickCopy = (type) => {
    const value = type === "subject" ? subject : type === "predicate" ? predicate : object;
    setFormData(prev => ({
      ...prev,
      [type]: value
    }));
    setShowForm(true);
  };

  const handleSubmitSuggestion = async () => {
    if (!formData.subject || !formData.predicate || !formData.object) {
      alert("Please fill in all triple fields");
      return;
    }
    
    try {
      await onAddSuggestion({
        subject: formData.subject,
        predicate: formData.predicate,
        object: formData.object,
        reason: formData.reason,
      });
      setFormData({ subject: "", predicate: "", object: "", reason: "" });
      setShowForm(false);
    } catch (err) {
      alert("Failed to add suggestion: " + err.message);
    }
  };

  const countVotes = (votes, voteType) => {
    return Object.values(votes || {}).filter(v => v === voteType).length;
  };

  return (
    <div className="mt-4 space-y-3 border-t border-slate-100 pt-3">
      {/* Quick copy buttons */}
      {!showForm && (
        <div className="flex gap-2 text-xs">
          <button
            onClick={() => handleQuickCopy("subject")}
            className="px-2 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded hover:bg-blue-100 transition-colors"
          >
            Copy Subject
          </button>
          <button
            onClick={() => handleQuickCopy("predicate")}
            className="px-2 py-1 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded hover:bg-indigo-100 transition-colors"
          >
            Copy Predicate
          </button>
          <button
            onClick={() => handleQuickCopy("object")}
            className="px-2 py-1 bg-teal-50 text-teal-700 border border-teal-200 rounded hover:bg-teal-100 transition-colors"
          >
            Copy Object
          </button>
          <button
            onClick={() => {
              setFormData({ subject: "", predicate: "", object: "", reason: "" });
              setShowForm(true);
            }}
            className="ml-auto px-2 py-1 bg-green-50 text-green-700 border border-green-200 rounded hover:bg-green-100 transition-colors font-medium"
          >
            + New Suggestion
          </button>
        </div>
      )}

      {/* Suggestion form */}
      {showForm && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
          <div className="text-xs font-semibold text-slate-600 mb-2">Add Triple Suggestion</div>
          <input
            type="text"
            value={formData.subject}
            onChange={(e) => setFormData(prev => ({ ...prev, subject: e.target.value }))}
            placeholder="Subject"
            className="w-full border border-slate-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
          />
          <input
            type="text"
            value={formData.predicate}
            onChange={(e) => setFormData(prev => ({ ...prev, predicate: e.target.value }))}
            placeholder="Predicate"
            className="w-full border border-slate-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <input
            type="text"
            value={formData.object}
            onChange={(e) => setFormData(prev => ({ ...prev, object: e.target.value }))}
            placeholder="Object"
            className="w-full border border-slate-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-teal-300"
          />
          <textarea
            value={formData.reason}
            onChange={(e) => setFormData(prev => ({ ...prev, reason: e.target.value }))}
            placeholder="Reason (optional)"
            className="w-full border border-slate-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-slate-300 h-12 resize-none"
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => {
                setFormData({ subject: "", predicate: "", object: "", reason: "" });
                setShowForm(false);
              }}
              className="px-2 py-1 text-xs bg-white border border-slate-300 rounded hover:bg-slate-100 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmitSuggestion}
              className="px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 transition-colors font-medium"
            >
              Save Suggestion
            </button>
          </div>
        </div>
      )}

      {/* Suggestions list */}
      {suggestions.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-semibold text-slate-600">Suggestions ({suggestions.length})</div>
          {suggestions.map((sug) => {
            const canDelete = sug.author === currentUserName;
            return (
              <div key={sug.id} className="bg-blue-50 border border-blue-200 rounded-lg p-2 text-xs">
                <div className="flex justify-between items-start mb-1">
                  <span className="font-medium text-blue-800">By {sug.author}</span>
                  {canDelete && (
                    <button
                      onClick={() => onDeleteSuggestion(sug.id)}
                      className="text-red-600 hover:text-red-700 font-bold"
                    >
                      ✕
                    </button>
                  )}
                </div>
                
                <div className="flex flex-wrap gap-1 mb-1">
                  <span className="inline-flex px-2 py-0.5 rounded bg-blue-100 text-blue-700 border border-blue-300">
                    {sug.subject}
                  </span>
                  <span className="text-slate-400">→</span>
                  <span className="inline-flex px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 border border-indigo-300">
                    {sug.predicate}
                  </span>
                  <span className="text-slate-400">→</span>
                  <span className="inline-flex px-2 py-0.5 rounded bg-teal-100 text-teal-700 border border-teal-300">
                    {sug.object}
                  </span>
                </div>

                {sug.reason && (
                  <div className="text-slate-600 italic mb-1">"{sug.reason}"</div>
                )}

                <div className="flex gap-2 items-center">
                  <button
                    onClick={() => onVote(sug.id, "yes")}
                    className="px-2 py-0.5 bg-green-100 text-green-700 border border-green-300 rounded hover:bg-green-200 transition-colors text-xs font-medium"
                  >
                    👍 {countVotes(sug.votes, "yes")}
                  </button>
                  <button
                    onClick={() => onVote(sug.id, "no")}
                    className="px-2 py-0.5 bg-red-100 text-red-700 border border-red-300 rounded hover:bg-red-200 transition-colors text-xs font-medium"
                  >
                    👎 {countVotes(sug.votes, "no")}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
