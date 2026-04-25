// TripleSuggestions.jsx — Displays suggestions for a triple with voting

import { useEffect, useRef, useState } from "react";

export default function TripleSuggestions({ 
  triple, 
  onAddSuggestion, 
  onEditSuggestion,
  onVote,
  onVoteSuggestion,
  onDeleteSuggestion,
  onApproveSuggestion,
  canApprove = false,
  currentUserName,
  currentUser,
}) {
  const { subject, predicate, object, suggestions = [] } = triple;
  const displayUserName = currentUserName || currentUser?.name || "";
  const voteHandler = onVote || onVoteSuggestion;
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    subject: "",
    predicate: "",
    object: "",
    reason: "",
  });
  const [editingSuggestionId, setEditingSuggestionId] = useState(null);
  const [editFormData, setEditFormData] = useState({
    subject: "",
    predicate: "",
    object: "",
    reason: "",
  });
  const [focusField, setFocusField] = useState(null);
  const subjectInputRef = useRef(null);
  const predicateInputRef = useRef(null);
  const objectInputRef = useRef(null);

  const handleQuickCopy = (type) => {
    // Copy full triple, but clear the clicked field so user can edit that part.
    setFormData({
      subject,
      predicate,
      object,
      reason: "",
      [type]: "",
    });
    setFocusField(type);
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
  const gradeOptions = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"];

  const startEditSuggestion = (sug) => {
    setEditingSuggestionId(sug.id);
    setEditFormData({
      subject: sug.subject || "",
      predicate: sug.predicate || "",
      object: sug.object || "",
      reason: sug.reason || "",
    });
  };

  const cancelEditSuggestion = () => {
    setEditingSuggestionId(null);
    setEditFormData({ subject: "", predicate: "", object: "", reason: "" });
  };

  const saveEditSuggestion = async (suggestionId) => {
    if (!editFormData.subject || !editFormData.predicate || !editFormData.object) {
      alert("Please fill in all triple fields");
      return;
    }

    try {
      await onEditSuggestion?.(suggestionId, {
        subject: editFormData.subject,
        predicate: editFormData.predicate,
        object: editFormData.object,
        reason: editFormData.reason,
      });
      cancelEditSuggestion();
    } catch (err) {
      alert("Failed to edit suggestion: " + err.message);
    }
  };

  useEffect(() => {
    const onTripleCopy = (event) => {
      const { tripleId, field, action } = event.detail || {};
      if (tripleId !== triple.id) return;
      if (action === "new") {
        setFormData({ subject: "", predicate: "", object: "", reason: "" });
        setShowForm(true);
        return;
      }
      if (!["subject", "predicate", "object"].includes(field)) return;
      handleQuickCopy(field);
    };

    window.addEventListener("triple-copy", onTripleCopy);
    return () => window.removeEventListener("triple-copy", onTripleCopy);
  }, [triple.id, subject, predicate, object]);

  useEffect(() => {
    if (!showForm || !focusField) return;
    const targetRef =
      focusField === "subject"
        ? subjectInputRef
        : focusField === "predicate"
        ? predicateInputRef
        : objectInputRef;
    targetRef.current?.focus();
    targetRef.current?.select();
    setFocusField(null);
  }, [showForm, focusField]);

  if (!showForm && suggestions.length === 0) {
    return null;
  }

  return (
    <div className="border-t border-amber-200 bg-gradient-to-b from-amber-50 to-orange-50 overflow-hidden">
      {/* Suggestions header bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-amber-100 border-b border-amber-200">
        <div className="flex items-center gap-2">
          <span className="text-amber-600 text-sm">💡</span>
          <span className="text-xs font-bold text-amber-800 uppercase tracking-wide">Suggestions</span>
          {suggestions.length > 0 && (
            <span className="bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-none">
              {suggestions.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 text-xs text-amber-600">
          <span className="font-medium">{subject}</span>
          <span className="text-amber-400">→</span>
          <span className="font-medium">{predicate}</span>
          <span className="text-amber-400">→</span>
          <span className="font-medium">{object}</span>
        </div>
      </div>

      <div className="p-3 space-y-3">

      {/* Suggestion form */}
      {showForm && (
        <div className="bg-white border border-amber-200 rounded-lg p-3 space-y-2 shadow-sm">
          <div className="text-xs font-semibold text-amber-700 mb-2 flex items-center gap-1">
            <span>✏️</span> New Triple Suggestion
          </div>
          <input
            type="text"
            ref={subjectInputRef}
            value={formData.subject}
            onChange={(e) => setFormData(prev => ({ ...prev, subject: e.target.value }))}
            placeholder="Subject"
            className="w-full border border-slate-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
          />
          <input
            type="text"
            ref={predicateInputRef}
            value={formData.predicate}
            onChange={(e) => setFormData(prev => ({ ...prev, predicate: e.target.value }))}
            placeholder="Predicate"
            className="w-full border border-slate-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <input
            type="text"
            ref={objectInputRef}
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
              className="px-2 py-1 text-xs bg-white border border-amber-300 text-amber-700 rounded hover:bg-amber-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmitSuggestion}
              className="px-2 py-1 text-xs bg-amber-600 text-white rounded hover:bg-amber-700 transition-colors font-medium"
            >
              Save Suggestion
            </button>
          </div>
        </div>
      )}

      {/* Suggestions list */}
      {suggestions.length > 0 && (
        <div className="space-y-2">
          {suggestions.map((sug) => {
            const canDelete = sug.author === displayUserName;
            const isEditing = editingSuggestionId === sug.id;
            const currentUserVote = (sug.votes || {})[displayUserName] ?? null;
            const gradeVotes = Object.values(sug.votes || {})
              .map((v) => String(v))
              .filter((v) => /^(10|[0-9])$/.test(v));
            const gradeAverage =
              gradeVotes.length > 0
                ? (gradeVotes.reduce((a, b) => a + Number(b), 0) / gradeVotes.length).toFixed(1)
                : null;
            return (
              <div key={sug.id} className={[
                "bg-white border rounded-lg p-3 text-xs shadow-sm",
                sug.status === "approved"
                  ? "border-emerald-300 border-l-4 border-l-emerald-500"
                  : "border-amber-200 border-l-4 border-l-amber-400",
              ].join(" ")}>
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-[10px] font-bold shrink-0">
                      {sug.author?.[0]?.toUpperCase() || "?"}
                    </span>
                    <span className="font-semibold text-slate-700">{sug.author}</span>
                    {sug.status === "approved" && (
                      <span className="inline-flex items-center gap-1 bg-emerald-100 text-emerald-700 border border-emerald-300 px-1.5 py-0.5 rounded-full text-[10px] font-bold">
                        ✓ Approved
                      </span>
                    )}
                  </div>
                  {!isEditing && (
                    <div className="flex items-center gap-2 flex-wrap justify-end">
                      {canApprove && sug.status !== "approved" && (
                        <button
                          onClick={() => onApproveSuggestion?.(sug.id)}
                          className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700 border border-emerald-300 hover:bg-emerald-200 transition-colors"
                        >
                          ✓ Approve
                        </button>
                      )}
                      {canDelete && (
                        <>
                      <button
                        onClick={() => startEditSuggestion(sug)}
                        className="text-slate-500 hover:text-blue-700 font-semibold"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => onDeleteSuggestion(sug.id)}
                        className="text-slate-400 hover:text-red-600 font-bold"
                      >
                        ✕
                      </button>
                        </>
                      )}
                    </div>
                  )}
                </div>

                {isEditing ? (
                  <div className="space-y-2 mb-2">
                    <input
                      type="text"
                      value={editFormData.subject}
                      onChange={(e) => setEditFormData((prev) => ({ ...prev, subject: e.target.value }))}
                      placeholder="Subject"
                      className="w-full border border-slate-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                    <input
                      type="text"
                      value={editFormData.predicate}
                      onChange={(e) => setEditFormData((prev) => ({ ...prev, predicate: e.target.value }))}
                      placeholder="Predicate"
                      className="w-full border border-slate-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
                    />
                    <input
                      type="text"
                      value={editFormData.object}
                      onChange={(e) => setEditFormData((prev) => ({ ...prev, object: e.target.value }))}
                      placeholder="Object"
                      className="w-full border border-slate-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-teal-300"
                    />
                    <textarea
                      value={editFormData.reason}
                      onChange={(e) => setEditFormData((prev) => ({ ...prev, reason: e.target.value }))}
                      placeholder="Reason (optional)"
                      className="w-full border border-slate-300 rounded px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-slate-300 h-12 resize-none"
                    />
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={cancelEditSuggestion}
                        className="px-2 py-1 text-xs bg-white border border-slate-300 rounded hover:bg-slate-100 transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => saveEditSuggestion(sug.id)}
                        className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors font-medium"
                      >
                        Save Edit
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
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
                      <div className="text-slate-500 italic mb-1 text-[11px]">"{sug.reason}"</div>
                    )}
                    {sug.status === "approved" && (
                      <div className="text-emerald-600 text-[11px] mb-1 font-medium">
                        ✓ Approved by {sug.approved_by || "owner"}
                      </div>
                    )}
                  </>
                )}

                <div className="flex gap-2 items-center flex-wrap">
                  <button
                    onClick={() => voteHandler?.(sug.id, "yes")}
                    className={[
                      "px-2 py-0.5 border rounded transition-colors text-xs font-medium",
                      currentUserVote === "yes"
                        ? "bg-green-600 text-white border-green-600"
                        : "bg-green-100 text-green-700 border-green-300 hover:bg-green-200",
                    ].join(" ")}
                  >
                    👍 {countVotes(sug.votes, "yes")}
                  </button>
                  <button
                    onClick={() => voteHandler?.(sug.id, "no")}
                    className={[
                      "px-2 py-0.5 border rounded transition-colors text-xs font-medium",
                      currentUserVote === "no"
                        ? "bg-red-600 text-white border-red-600"
                        : "bg-red-100 text-red-700 border-red-300 hover:bg-red-200",
                    ].join(" ")}
                  >
                    👎 {countVotes(sug.votes, "no")}
                  </button>
                  <div className="flex items-center gap-1 ml-1 flex-wrap">
                    <span className="text-slate-500">Grade:</span>
                    {gradeOptions.map((grade) => (
                      <button
                        key={grade}
                        onClick={() => voteHandler?.(sug.id, grade)}
                        className={[
                          "w-5 h-5 border rounded text-[10px] leading-none font-semibold transition-colors",
                          currentUserVote === grade
                            ? "bg-blue-600 text-white border-blue-600"
                            : "bg-white text-slate-700 border-slate-300 hover:bg-blue-100",
                        ].join(" ")}
                        title={`Vote grade ${grade}`}
                      >
                        {grade}
                      </button>
                    ))}
                  </div>
                  {gradeAverage !== null && (
                    <span className="ml-auto text-xs font-semibold text-blue-700 bg-blue-100 border border-blue-300 rounded px-2 py-0.5">
                      Avg {gradeAverage} ({gradeVotes.length})
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
      </div>
    </div>
  );
}
