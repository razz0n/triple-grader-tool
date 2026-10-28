import { useEffect, useRef, useState } from "react";
import { useDialog } from "./CustomDialog";
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

function buildReplyTree(replies = []) {
  const replyMap = {};
  const rootReplies = [];

  replies.forEach((r) => {
    replyMap[r.id] = { ...r, replies: [] };
  });

  replies.forEach((r) => {
    const mapped = replyMap[r.id];
    if (r.parent_reply_id && replyMap[r.parent_reply_id]) {
      mapped.parent_reply_author = replyMap[r.parent_reply_id].author;
      replyMap[r.parent_reply_id].replies.push(mapped);
    } else {
      rootReplies.push(mapped);
    }
  });

  const sortReplies = (list) => {
    list.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    list.forEach((item) => sortReplies(item.replies));
  };
  sortReplies(rootReplies);

  return rootReplies;
}

function SuggestionReplyNode({
  reply,
  sugId,
  replyingToReplyId,
  setReplyingToReplyId,
  replyData,
  setReplyData,
  handlePostSuggestionReply,
  handleDeleteSuggestionReply,
  currentUser,
  depth = 0
}) {
  const isReplying = replyingToReplyId === reply.id;
  const isOwnReply = reply.user_id === (currentUser?.id || "");
  const indentClass = depth > 0 ? "pl-3 sm:pl-4 border-l border-indigo-150 dark:border-indigo-900/50 mt-2" : "";

  return (
    <div key={reply.id} className={indentClass}>
      <div className="bg-slate-50/50 dark:bg-slate-950/20 border border-slate-100/60 dark:border-slate-800/80 rounded-xl p-2.5 text-[11px] leading-relaxed relative">
        <div className="flex justify-between items-start gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap text-[9px] text-slate-400 dark:text-slate-500 font-semibold">
              <span className="font-bold text-slate-700 dark:text-slate-300">{reply.author || "Grader"}</span>
              {reply.parent_reply_author && (
                <>
                  <span className="text-slate-350">&bull;</span>
                  <span className="text-indigo-500 dark:text-indigo-400 font-normal">
                    replying to {reply.parent_reply_author}
                  </span>
                </>
              )}
              <span>&bull;</span>
              <span>{formatCommentTimestamp(reply.created_at)}</span>
            </div>
            <p className="text-slate-600 dark:text-slate-300 mt-0.5 break-words">
              {reply.text}
            </p>
          </div>
          <div className="flex items-center gap-1">
            {isOwnReply && (
              <button
                onClick={() => handleDeleteSuggestionReply(sugId, reply.id)}
                className="p-1 rounded text-slate-400 hover:text-rose-650 transition-colors cursor-pointer"
                title="Delete reply"
              >
                <X size={10} />
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 mt-1 select-none">
          <button
            onClick={() => {
              if (isReplying) {
                setReplyingToReplyId(null);
                setReplyData("");
              } else {
                setReplyingToReplyId(reply.id);
                setReplyData("");
              }
            }}
            className="text-[9px] font-bold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer flex items-center gap-0.5"
          >
            <CornerDownRight size={10} />
            Reply
          </button>
        </div>
      </div>

      {isReplying && (
        <div className="pl-3 border-l-2 border-indigo-200 dark:border-indigo-900 mt-2 space-y-2">
          <textarea
            autoFocus
            value={replyData}
            onChange={(e) => setReplyData(e.target.value)}
            placeholder={`Reply to ${reply.author || "User"}...`}
            rows={1}
            className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-lg p-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white"
          />
          <div className="flex gap-1.5 justify-end">
            <button
              onClick={() => {
                setReplyingToReplyId(null);
                setReplyData("");
              }}
              className="text-[10px] px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition-colors font-bold cursor-pointer"
            >
              Cancel
            </button>
            <button
              onClick={() => handlePostSuggestionReply(sugId, reply.id)}
              disabled={!replyData.trim()}
              className="text-[10px] px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-bold cursor-pointer"
            >
              Post Reply
            </button>
          </div>
        </div>
      )}

      {reply.replies && reply.replies.length > 0 && (
        <div className="space-y-2 mt-2">
          {reply.replies.map((child) => (
            <SuggestionReplyNode
              key={child.id}
              reply={child}
              sugId={sugId}
              replyingToReplyId={replyingToReplyId}
              setReplyingToReplyId={setReplyingToReplyId}
              replyData={replyData}
              setReplyData={setReplyData}
              handlePostSuggestionReply={handlePostSuggestionReply}
              handleDeleteSuggestionReply={handleDeleteSuggestionReply}
              currentUser={currentUser}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
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
  const { showAlert, showConfirm } = useDialog();
  const { subject, predicate, object, suggestions = [] } = triple;
  const displayUserName = currentUserName || currentUser?.name || "";
  const voteHandler = onVote || onVoteSuggestion;
  const [showForm, setShowForm] = useState(false);

  const [expandedDiscussionIds, setExpandedDiscussionIds] = useState({});
  const [discussionDrafts, setDiscussionDrafts] = useState({});
  const [replyingToReplyId, setReplyingToReplyId] = useState(null);
  const [replyData, setReplyData] = useState("");

  const toggleDiscussion = (sugId) => {
    setExpandedDiscussionIds((prev) => ({
      ...prev,
      [sugId]: !prev[sugId],
    }));
  };

  const handlePostSuggestionReply = async (sugId, parentReplyId = null) => {
    const text = parentReplyId
      ? String(replyData || "").trim()
      : String(discussionDrafts[sugId] || "").trim();
    if (!text) return;
    try {
      await onAddSuggestionReply?.(sugId, text, parentReplyId);
      if (parentReplyId) {
        setReplyData("");
        setReplyingToReplyId(null);
      } else {
        setDiscussionDrafts((prev) => ({ ...prev, [sugId]: "" }));
      }
    } catch (err) {
      showAlert("Failed to add reply: " + err.message, "Error");
    }
  };

  const handleDeleteSuggestionReply = async (sugId, replyId) => {
    const ok = await showConfirm("Remove this reply?", "Remove Reply", "Remove", "Cancel");
    if (!ok) return;
    try {
      await onDeleteSuggestionReply?.(sugId, replyId);
    } catch (err) {
      showAlert("Failed to delete reply: " + err.message, "Error");
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
      showAlert("You are not allowed to add suggestions in this session.", "Action Not Allowed");
      return;
    }

    if (!formData.subject || !formData.predicate || !formData.object) {
      showAlert("Please fill in all triple fields", "Validation Error");
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
      showAlert("Failed to add suggestion: " + err.message, "Error");
    }
  };

  const countVotes = (votes, voteType) => {
    return Object.values(votes || {}).filter((v) => v === voteType).length;
  };

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
      showAlert("Please fill in all triple fields", "Validation Error");
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
      showAlert("Failed to edit suggestion: " + err.message, "Error");
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
                className="w-full border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-xs bg-slate-50/50 dark:bg-slate-950 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white"
              />
              <input
                type="text"
                ref={predicateInputRef}
                value={formData.predicate}
                onChange={(e) => setFormData((prev) => ({ ...prev, predicate: e.target.value }))}
                placeholder="Predicate"
                className="w-full border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-xs bg-slate-50/50 dark:bg-slate-950 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white"
              />
              <input
                type="text"
                ref={objectInputRef}
                value={formData.object}
                onChange={(e) => setFormData((prev) => ({ ...prev, object: e.target.value }))}
                placeholder="Object"
                className="w-full border border-slate-200 dark:border-slate-800 rounded-xl px-3 py-2 text-xs bg-slate-50/50 dark:bg-slate-950 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white"
              />
            </div>
            <div className="flex gap-2 justify-end pt-1">
              <button
                onClick={() => {
                  setFormData({ subject: "", predicate: "", object: "", reason: "" });
                  setShowForm(false);
                }}
                className="px-3.5 py-2 text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-xl hover:bg-slate-50 transition-colors cursor-pointer"
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
                                ? "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-200"
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
                        className="w-full border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white"
                      />
                      <input
                        type="text"
                        value={editFormData.predicate}
                        onChange={(e) => setEditFormData((prev) => ({ ...prev, predicate: e.target.value }))}
                        placeholder="Predicate"
                        className="w-full border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white"
                      />
                      <input
                        type="text"
                        value={editFormData.object}
                        onChange={(e) => setEditFormData((prev) => ({ ...prev, object: e.target.value }))}
                        placeholder="Object"
                        className="w-full border border-slate-200 dark:border-slate-800 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white"
                      />
                      <div className="flex gap-1.5 justify-end">
                        <button
                          onClick={cancelEditSuggestion}
                          className="px-2.5 py-1 text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded hover:bg-slate-55 transition-colors cursor-pointer"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={() => saveEditSuggestion(sug.id)}
                          className="px-2.5 py-1 text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded font-bold transition-colors cursor-pointer"
                        >
                          Save Changes
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex flex-wrap items-center gap-1.5 mb-2">
                        <span className="inline-flex px-2 py-0.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 border border-indigo-100/30 font-bold">
                          {sug.subject}
                        </span>
                        <ChevronRight size={10} className="text-slate-400" />
                        <span className="inline-flex px-2 py-0.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-100/30 font-bold">
                          {sug.predicate}
                        </span>
                        <ChevronRight size={10} className="text-slate-400" />
                        <span className="inline-flex px-2 py-0.5 rounded-lg bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-400 border border-purple-100/30 font-bold">
                          {sug.object}
                        </span>
                      </div>

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
                          ? "bg-slate-50 dark:bg-slate-950 text-slate-400 dark:text-slate-500 border-slate-200 dark:border-slate-800 cursor-not-allowed"
                          : currentUserVote === "yes"
                          ? "bg-emerald-600 border-emerald-700 text-white shadow-sm"
                          : "bg-emerald-50/50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400 border-emerald-200/60 dark:border-emerald-900/30 hover:bg-emerald-100/60"
                      }`}
                    >
                      <ThumbsUp size={11} /> {countVotes(sug.votes, "yes")}
                    </button>
                    <button
                      onClick={() => voteHandler?.(sug.id, "no")}
                      disabled={!canVote}
                      className={`inline-flex items-center gap-1 px-2.5 py-1 border rounded-lg transition-all text-[11px] font-bold cursor-pointer ${
                        !canVote
                          ? "bg-slate-50 dark:bg-slate-950 text-slate-400 dark:text-slate-500 border-slate-200 dark:border-slate-800 cursor-not-allowed"
                          : currentUserVote === "no"
                          ? "bg-rose-600 border-rose-700 text-white shadow-sm"
                          : "bg-rose-50/50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-455 border-rose-200/60 dark:border-rose-900/30 hover:bg-rose-100/60"
                      }`}
                    >
                      <ThumbsDown size={11} /> {countVotes(sug.votes, "no")}
                    </button>
                    <button
                      onClick={() => toggleDiscussion(sug.id)}
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border transition-all text-[11px] font-bold cursor-pointer ${
                        expandedDiscussionIds[sug.id]
                          ? "bg-indigo-600 border-indigo-700 text-white shadow-sm"
                          : "bg-indigo-50/50 dark:bg-indigo-950/30 text-indigo-700 dark:text-indigo-400 border-indigo-200 dark:border-indigo-900/30 hover:bg-indigo-100/60"
                      }`}
                    >
                      <MessageSquare size={11} /> Discuss ({sug.replies?.length || 0})
                    </button>

                  </div>

                  {/* Discussion replies drawer */}
                  {expandedDiscussionIds[sug.id] && (
                    <div className="mt-4 pl-3.5 border-l-2 border-indigo-300 dark:border-indigo-900 space-y-2.5">
                      {sug.replies && sug.replies.length > 0 && (
                        <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                          {buildReplyTree(sug.replies).map((reply) => (
                            <SuggestionReplyNode
                              key={reply.id}
                              reply={reply}
                              sugId={sug.id}
                              replyingToReplyId={replyingToReplyId}
                              setReplyingToReplyId={setReplyingToReplyId}
                              replyData={replyData}
                              setReplyData={setReplyData}
                              handlePostSuggestionReply={handlePostSuggestionReply}
                              handleDeleteSuggestionReply={handleDeleteSuggestionReply}
                              currentUser={currentUser}
                            />
                          ))}
                        </div>
                      )}

                      {/* Reply field (replying to main suggestion) */}
                      <div className="space-y-2 pt-1 bg-white dark:bg-slate-900 rounded-xl border border-slate-100 dark:border-slate-800 p-2.5">
                        <textarea
                          value={discussionDrafts[sug.id] || ""}
                          onChange={(e) =>
                            setDiscussionDrafts((prev) => ({ ...prev, [sug.id]: e.target.value }))
                          }
                          placeholder="Reply to this discussion thread..."
                          rows={1}
                          className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white"
                        />
                        <div className="flex gap-1.5 justify-end">
                          <button
                            onClick={() => toggleDiscussion(sug.id)}
                            className="text-[10px] px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition-colors font-bold cursor-pointer"
                          >
                            Close Thread
                          </button>
                          <button
                            onClick={() => handlePostSuggestionReply(sug.id, null)}
                            disabled={!(discussionDrafts[sug.id] || "").trim()}
                            className="text-[10px] px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-bold cursor-pointer shadow-sm"
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
