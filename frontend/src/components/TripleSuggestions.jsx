import { useEffect, useRef, useState } from "react";
import {
  Lightbulb,
  Edit,
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  X,
  Check,
  CornerDownRight,
  AlertCircle,
  HelpCircle,
  Trash2,
  ChevronRight
} from "lucide-react";

function formatCommentTimestamp(isoTime) {
  if (!isoTime) return "just now";
  const parsed = new Date(isoTime);
  if (Number.isNaN(parsed.getTime())) return "just now";
  return parsed.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function TripleSuggestions({
  triple,
  onAddSuggestion,
  onEditSuggestion,
  onVote,
  onVoteSuggestion,
  onDeleteSuggestion,
  onApproveSuggestion,
  onAddSuggestionReply,
  onDeleteSuggestionReply,
  canSuggest = true,
  canApprove = false,
  currentUserName,
  currentUser,
}) {
  const { subject, predicate, object, suggestions = [] } = triple;
  const displayUserName = currentUserName || currentUser?.name || "";
  const voteHandler = onVote || onVoteSuggestion;
  const [showForm, setShowForm] = useState(false);

  const [expandedDiscussionIds, setExpandedDiscussionIds] = useState({});
  const [discussionDrafts, setDiscussionDrafts] = useState({});

  const toggleDiscussion = (sugId) => {
    setExpandedDiscussionIds((prev) => ({
      ...prev,
      [sugId]: !prev[sugId],
    }));
  };

  const handlePostSuggestionReply = async (sugId) => {
    const text = String(discussionDrafts[sugId] || "").trim();
    if (!text) return;
    try {
      await onAddSuggestionReply?.(sugId, text);
      setDiscussionDrafts((prev) => ({ ...prev, [sugId]: "" }));
    } catch (err) {
      alert("Failed to add reply: " + err.message);
    }
  };

  const handleDeleteSuggestionReply = async (sugId, replyId) => {
    if (!window.confirm("Remove this reply?")) return;
    try {
      await onDeleteSuggestionReply?.(sugId, replyId);
    } catch (err) {
      alert("Failed to delete reply: " + err.message);
    }
  };

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
    if (!canSuggest) {
      alert("You are not allowed to add suggestions in this session.");
      return;
    }

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
    return Object.values(votes || {}).filter((v) => v === voteType).length;
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
      if (!canSuggest) return;

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
  }, [canSuggest, triple.id, subject, predicate, object]);

  useEffect(() => {
    if (canSuggest) return;
    setShowForm(false);
  }, [canSuggest]);

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
    <div className="bg-slate-50/20 dark:bg-slate-900/10 overflow-hidden">
      {/* Suggestions Header Bar */}
      <div className="flex items-center justify-between px-5 py-3.5 bg-amber-50/30 dark:bg-amber-950/10 border-t border-b border-slate-100 dark:border-slate-800/80">
        <div className="flex items-center gap-2 select-none">
          <span className="text-xs font-bold text-amber-800 dark:text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
            <Lightbulb size={14} className="text-amber-600 dark:text-amber-400" />
            <span>Suggestions</span>
          </span>
          {suggestions.length > 0 && (
            <span className="bg-amber-600 dark:bg-amber-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full leading-none">
              {suggestions.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 text-[10px] text-slate-400 dark:text-slate-500 font-semibold max-w-[150px] sm:max-w-none truncate">
          <span className="bg-indigo-50/50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 px-1.5 py-0.5 rounded-lg border border-indigo-100/30">{subject}</span>
          <ChevronRight size={10} />
          <span className="bg-emerald-50/50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 px-1.5 py-0.5 rounded-lg border border-emerald-100/30">{predicate}</span>
          <ChevronRight size={10} />
          <span className="bg-purple-50/50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-400 px-1.5 py-0.5 rounded-lg border border-purple-100/30">{object}</span>
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* New Suggestion Form */}
        {canSuggest && showForm && (
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4.5 space-y-3 shadow-md">
            <div className="text-xs font-bold text-amber-850 dark:text-amber-400 mb-2 flex items-center gap-1.5 uppercase tracking-wide">
              <Lightbulb size={14} />
              <span>Create Triple Suggestion</span>
            </div>
            <div className="grid grid-cols-1 gap-2.5">
              <input
                type="text"
                ref={subjectInputRef}
                value={formData.subject}
                onChange={(e) => setFormData((prev) => ({ ...prev, subject: e.target.value }))}
                placeholder="Subject"
                className="w-full border border-slate-250 dark:border-slate-850 rounded-xl px-3 py-2 text-xs bg-slate-50/50 dark:bg-slate-950 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white"
              />
              <input
                type="text"
                ref={predicateInputRef}
                value={formData.predicate}
                onChange={(e) => setFormData((prev) => ({ ...prev, predicate: e.target.value }))}
                placeholder="Predicate"
                className="w-full border border-slate-250 dark:border-slate-855 rounded-xl px-3 py-2 text-xs bg-slate-50/50 dark:bg-slate-955 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white"
              />
              <input
                type="text"
                ref={objectInputRef}
                value={formData.object}
                onChange={(e) => setFormData((prev) => ({ ...prev, object: e.target.value }))}
                placeholder="Object"
                className="w-full border border-slate-250 dark:border-slate-855 rounded-xl px-3 py-2 text-xs bg-slate-50/50 dark:bg-slate-955 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white"
              />
              <textarea
                value={formData.reason}
                onChange={(e) => setFormData((prev) => ({ ...prev, reason: e.target.value }))}
                placeholder="Reason or discussion context (optional)"
                className="w-full border border-slate-250 dark:border-slate-855 rounded-xl px-3 py-2 text-xs bg-slate-50/50 dark:bg-slate-955 focus:outline-none focus:ring-2 focus:ring-slate-400 dark:focus:ring-slate-700 focus:border-transparent transition-all h-16 resize-none dark:text-white leading-normal"
              />
            </div>
            <div className="flex gap-2 justify-end pt-1">
              <button
                onClick={() => {
                  setFormData({ subject: "", predicate: "", object: "", reason: "" });
                  setShowForm(false);
                }}
                className="px-3.5 py-2 text-xs bg-white dark:bg-slate-800 border border-slate-250 dark:border-slate-750 text-slate-700 dark:text-slate-350 rounded-xl hover:bg-slate-55 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitSuggestion}
                className="px-3.5 py-2 text-xs bg-amber-600 hover:bg-amber-700 text-white rounded-xl active:scale-95 transition-all font-bold shadow-sm cursor-pointer"
              >
                Submit Suggestion
              </button>
            </div>
          </div>
        )}

        {/* Suggestions List */}
        {suggestions.length > 0 && (
          <div className="space-y-3">
            {suggestions.map((sug) => {
              const canDelete = canSuggest && sug.author === displayUserName;
              const isEditing = editingSuggestionId === sug.id;
              const currentUserVote = (sug.votes || {})[displayUserName] ?? null;
              const canVote = sug.author !== displayUserName;
              const gradeVotes = Object.values(sug.votes || {})
                .map((v) => String(v))
                .filter((v) => /^(10|[0-9])$/.test(v));
              const gradeAverage =
                gradeVotes.length > 0
                  ? (gradeVotes.reduce((a, b) => a + Number(b), 0) / gradeVotes.length).toFixed(1)
                  : null;
              return (
                <div
                  key={sug.id}
                  className={`bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-4.5 text-xs shadow-sm border-l-4 ${
                    sug.status === "approved"
                      ? "border-l-emerald-500 dark:border-l-emerald-600"
                      : "border-l-amber-500 dark:border-l-amber-600"
                  }`}
                >
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-2 select-none">
                      <span className="w-5 h-5 rounded-full bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-450 flex items-center justify-center text-[10px] font-bold shrink-0">
                        {sug.author?.[0]?.toUpperCase() || "?"}
                      </span>
                      <span className="font-bold text-slate-850 dark:text-slate-300">{sug.author}</span>
                      {sug.status === "approved" && (
                        <span className="inline-flex items-center gap-0.5 bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-450 border border-emerald-150 dark:border-emerald-900/30 px-2 py-0.5 rounded-full text-[9px] font-bold">
                          Approved
                        </span>
                      )}
                    </div>
                    {!isEditing && (
                      <div className="flex items-center gap-2 flex-wrap justify-end">
                        {canApprove && (
                          <button
                            onClick={() => onApproveSuggestion?.(sug.id, sug.status === "approved")}
                            className={`flex items-center gap-1 px-2.5 py-1 rounded-xl text-[10px] font-bold border transition-colors cursor-pointer active:scale-95 ${
                              sug.status === "approved"
                                ? "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-250 dark:border-slate-750 hover:bg-slate-200"
                                : "bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900/30 hover:bg-emerald-100"
                            }`}
                          >
                            {sug.status === "approved" ? "Undo Approval" : "Approve Suggestion"}
                          </button>
                        )}
                        {canDelete && (
                          <>
                            <button
                              onClick={() => startEditSuggestion(sug)}
                              className="text-indigo-600 dark:text-indigo-400 hover:underline font-bold cursor-pointer"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => onDeleteSuggestion(sug.id)}
                              className="p-1 rounded text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                              title="Delete suggestion"
                            >
                              <X size={13} />
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </div>

                  {isEditing ? (
                    <div className="space-y-2.5 mb-3">
                      <input
                        type="text"
                        value={editFormData.subject}
                        onChange={(e) => setEditFormData((prev) => ({ ...prev, subject: e.target.value }))}
                        placeholder="Subject"
                        className="w-full border border-slate-250 dark:border-slate-800 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white"
                      />
                      <input
                        type="text"
                        value={editFormData.predicate}
                        onChange={(e) => setEditFormData((prev) => ({ ...prev, predicate: e.target.value }))}
                        placeholder="Predicate"
                        className="w-full border border-slate-250 dark:border-slate-800 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-955 dark:text-white"
                      />
                      <input
                        type="text"
                        value={editFormData.object}
                        onChange={(e) => setEditFormData((prev) => ({ ...prev, object: e.target.value }))}
                        placeholder="Object"
                        className="w-full border border-slate-250 dark:border-slate-800 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-955 dark:text-white"
                      />
                      <textarea
                        value={editFormData.reason}
                        onChange={(e) => setEditFormData((prev) => ({ ...prev, reason: e.target.value }))}
                        placeholder="Reason (optional)"
                        className="w-full border border-slate-250 dark:border-slate-800 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-slate-300 h-12 resize-none dark:text-white"
                      />
                      <div className="flex gap-1.5 justify-end">
                        <button
                          onClick={cancelEditSuggestion}
                          className="px-2.5 py-1 text-xs bg-white dark:bg-slate-800 border border-slate-250 dark:border-slate-750 text-slate-700 dark:text-slate-300 rounded hover:bg-slate-50 transition-colors cursor-pointer"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => saveEditSuggestion(sug.id)}
                          className="px-2.5 py-1 text-xs bg-indigo-650 hover:bg-indigo-700 text-white rounded font-bold transition-colors cursor-pointer"
                        >
                          Save Changes
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex flex-wrap items-center gap-1.5 mb-2">
                        <span className="inline-flex px-2 py-0.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 border border-indigo-100/35 font-bold">
                          {sug.subject}
                        </span>
                        <ChevronRight size={10} className="text-slate-350" />
                        <span className="inline-flex px-2 py-0.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-450 border border-emerald-100/35 font-bold">
                          {sug.predicate}
                        </span>
                        <ChevronRight size={10} className="text-slate-350" />
                        <span className="inline-flex px-2 py-0.5 rounded-lg bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-400 border border-purple-100/35 font-bold">
                          {sug.object}
                        </span>
                      </div>

                      {sug.reason && (
                        <div className="text-slate-500 dark:text-slate-400 italic mb-2 pl-1.5 border-l border-slate-200 dark:border-slate-800">
                          "{sug.reason}"
                        </div>
                      )}
                      {sug.status === "approved" && (
                        <div className="text-emerald-700 dark:text-emerald-450 text-[10px] mb-2 font-bold select-none">
                          Approved by {sug.approved_by || "owner"}
                        </div>
                      )}
                    </>
                  )}

                  {/* Actions (Vote / Discussion) */}
                  <div className="flex gap-2 items-center flex-wrap pt-1.5 border-t border-slate-100 dark:border-slate-800/80 mt-2">
                    <button
                      onClick={() => voteHandler?.(sug.id, "yes")}
                      disabled={!canVote}
                      className={`inline-flex items-center gap-1 px-2.5 py-1 border rounded-lg transition-all text-[11px] font-bold cursor-pointer ${
                        !canVote
                          ? "bg-slate-50 dark:bg-slate-950 text-slate-350 dark:text-slate-650 border-slate-200 dark:border-slate-850 cursor-not-allowed"
                          : currentUserVote === "yes"
                          ? "bg-emerald-600 border-emerald-650 text-white shadow-sm"
                          : "bg-emerald-50/50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900/30 hover:bg-emerald-100/60"
                      }`}
                    >
                      <ThumbsUp size={11} /> {countVotes(sug.votes, "yes")}
                    </button>
                    <button
                      onClick={() => voteHandler?.(sug.id, "no")}
                      disabled={!canVote}
                      className={`inline-flex items-center gap-1 px-2.5 py-1 border rounded-lg transition-all text-[11px] font-bold cursor-pointer ${
                        !canVote
                          ? "bg-slate-50 dark:bg-slate-950 text-slate-350 dark:text-slate-650 border-slate-200 dark:border-slate-850 cursor-not-allowed"
                          : currentUserVote === "no"
                          ? "bg-rose-600 border-rose-650 text-white shadow-sm"
                          : "bg-rose-50/50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-455 border-rose-200 dark:border-rose-900/30 hover:bg-rose-100/60"
                      }`}
                    >
                      <ThumbsDown size={11} /> {countVotes(sug.votes, "no")}
                    </button>
                    <button
                      onClick={() => toggleDiscussion(sug.id)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border transition-all text-[11px] font-bold cursor-pointer ${
                        expandedDiscussionIds[sug.id]
                          ? "bg-indigo-600 border-indigo-650 text-white shadow-sm"
                          : "bg-indigo-50/50 dark:bg-indigo-950/30 text-indigo-750 dark:text-indigo-400 border-indigo-200 dark:border-indigo-900/35 hover:bg-indigo-100/60"
                      }`}
                    >
                      <MessageSquare size={11} /> Discuss ({sug.replies?.length || 0})
                    </button>

                    {/* Quality score voter */}
                    <div className="flex items-center gap-1 ml-1 flex-wrap pt-1 lg:pt-0">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mr-1 select-none">Score:</span>
                      {gradeOptions.map((grade) => (
                        <button
                          key={grade}
                          onClick={() => voteHandler?.(sug.id, grade)}
                          disabled={!canVote}
                          className={`w-5 h-5 border rounded text-[9px] font-bold transition-all flex items-center justify-center cursor-pointer ${
                            !canVote
                              ? "bg-slate-50 dark:bg-slate-950 text-slate-300 dark:text-slate-650 border-slate-200 dark:border-slate-850 cursor-not-allowed"
                              : currentUserVote === grade
                              ? "bg-indigo-600 border-indigo-650 text-white"
                              : "bg-white dark:bg-slate-950 text-slate-600 dark:text-slate-400 border-slate-250 dark:border-slate-850 hover:bg-indigo-50"
                          }`}
                          title={canVote ? `Vote score ${grade}` : "Cannot vote on your own suggestion"}
                        >
                          {grade}
                        </button>
                      ))}
                    </div>

                    {gradeAverage !== null && (
                      <span className="ml-auto text-[10px] font-bold text-indigo-700 dark:text-indigo-455 bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-900 px-2 py-0.5 rounded-lg select-none">
                        Avg {gradeAverage} ({gradeVotes.length})
                      </span>
                    )}
                  </div>

                  {/* Discussion replies drawer */}
                  {expandedDiscussionIds[sug.id] && (
                    <div className="mt-4 pl-3.5 border-l-2 border-indigo-250 dark:border-indigo-900 space-y-2.5">
                      {sug.replies && sug.replies.length > 0 && (
                        <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                          {sug.replies.map((reply) => {
                            const isOwnReply = reply.user_id === (currentUser?.id || "");
                            return (
                              <div
                                key={reply.id}
                                className="bg-slate-50/50 dark:bg-slate-950/20 border border-slate-100/60 dark:border-slate-800/80 rounded-xl p-2.5 text-[11px] leading-relaxed relative"
                              >
                                <div className="flex justify-between items-start gap-2">
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5 flex-wrap text-[9px] text-slate-400 dark:text-slate-500 font-semibold">
                                      <span className="font-bold text-slate-700 dark:text-slate-300">{reply.author || "Grader"}</span>
                                      <span>&bull;</span>
                                      <span>{formatCommentTimestamp(reply.created_at)}</span>
                                    </div>
                                    <p className="text-slate-650 dark:text-slate-350 mt-0.5 break-words">
                                      {reply.text}
                                    </p>
                                  </div>
                                  {isOwnReply && (
                                    <button
                                      onClick={() => handleDeleteSuggestionReply(sug.id, reply.id)}
                                      className="p-1 rounded text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                                      title="Delete reply"
                                    >
                                      <X size={10} />
                                    </button>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* Reply field */}
                      <div className="space-y-2 pt-1 bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-2.5">
                        <textarea
                          value={discussionDrafts[sug.id] || ""}
                          onChange={(e) =>
                            setDiscussionDrafts((prev) => ({ ...prev, [sug.id]: e.target.value }))
                          }
                          placeholder="Reply to this discussion thread..."
                          rows={1}
                          className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-955 dark:text-white"
                        />
                        <div className="flex gap-1.5 justify-end">
                          <button
                            onClick={() => toggleDiscussion(sug.id)}
                            className="text-[10px] px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition-colors font-bold cursor-pointer"
                          >
                            Close Thread
                          </button>
                          <button
                            onClick={() => handlePostSuggestionReply(sug.id)}
                            disabled={!(discussionDrafts[sug.id] || "").trim()}
                            className="text-[10px] px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-755 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-bold cursor-pointer shadow-sm"
                          >
                            Post Reply
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
