import { useState } from "react";
import { MessageSquare, CornerDownRight, Trash2, Send, X, User } from "lucide-react";

function createCommentId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `comment_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

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

export default function TripleComments({
  tripleId,
  comments = [],
  currentUserId = "",
  currentUserName = "User",
  readOnly = false,
  onAddComment,
  onDeleteComment,
  onAddReply,
  onDeleteReply,
}) {
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState("");
  const [replyingToId, setReplyingToId] = useState(null);
  const [replyData, setReplyData] = useState("");

  const handleSubmitComment = async () => {
    const text = String(formData || "").trim();
    if (!text) {
      alert("Comment cannot be empty");
      return;
    }

    try {
      const newComment = {
        id: createCommentId(),
        author: currentUserName || "User",
        user_id: currentUserId || "",
        text,
        created_at: new Date().toISOString(),
        replies: [],
      };
      await onAddComment?.(newComment);
      setFormData("");
      setShowForm(false);
    } catch (err) {
      alert("Failed to add comment: " + err.message);
    }
  };

  const handleDeleteClick = async (commentId) => {
    if (!window.confirm("Remove this comment?")) return;
    try {
      await onDeleteComment?.(commentId);
    } catch (err) {
      alert("Failed to delete comment: " + err.message);
    }
  };

  const handlePostReply = async (commentId) => {
    const text = String(replyData || "").trim();
    if (!text) return;
    try {
      const newReply = {
        id: createCommentId(),
        author: currentUserName || "User",
        user_id: currentUserId || "",
        text,
        created_at: new Date().toISOString(),
      };
      await onAddReply?.(commentId, newReply);
      setReplyData("");
      setReplyingToId(null);
    } catch (err) {
      alert("Failed to add reply: " + err.message);
    }
  };

  const handleDeleteReplyClick = async (commentId, replyId) => {
    if (!window.confirm("Remove this reply?")) return;
    try {
      await onDeleteReply?.(commentId, replyId);
    } catch (err) {
      alert("Failed to delete reply: " + err.message);
    }
  };

  if (comments.length === 0 && !showForm) {
    return (
      <div className="px-5 py-3 bg-slate-50/50 dark:bg-slate-900/20 border-t border-slate-100 dark:border-slate-800/80 flex items-center">
        {!readOnly && (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="text-xs px-3.5 py-2 rounded-xl bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-350 border border-slate-200 dark:border-slate-750 hover:bg-slate-50 dark:hover:bg-slate-700 hover:text-slate-800 dark:hover:text-white active:scale-95 transition-all font-bold cursor-pointer flex items-center gap-1.5 shadow-sm"
          >
            <MessageSquare size={13} />
            <span>Add Comment</span>
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="px-5 py-4 bg-slate-50/50 dark:bg-slate-900/20 border-t border-slate-100 dark:border-slate-800/80 space-y-4">
      <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 flex items-center gap-1.5 select-none">
        <MessageSquare size={12} />
        <span>Comments ({comments.length})</span>
      </h4>

      {/* Comments List */}
      {comments.length > 0 && (
        <div className="space-y-3">
          {comments.map((comment) => (
            <div
              key={comment.id}
              className="bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-800/80 rounded-xl p-3.5 text-xs space-y-2.5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap text-[10px] text-slate-400 dark:text-slate-500 font-semibold">
                    <span className="font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1">
                      <User size={10} className="text-slate-400" />
                      {comment.author || "User"}
                    </span>
                    <span>&bull;</span>
                    <span>{formatCommentTimestamp(comment.created_at)}</span>
                  </div>
                  <p className="text-slate-650 dark:text-slate-300 mt-1 break-words leading-relaxed">
                    {comment.text}
                  </p>
                </div>
                {!readOnly && comment.user_id === currentUserId && (
                  <button
                    type="button"
                    onClick={() => handleDeleteClick(comment.id)}
                    className="p-1 rounded text-slate-400 hover:text-rose-600 dark:hover:text-rose-455 transition-colors cursor-pointer"
                    title="Delete comment"
                  >
                    <Trash2 size={12} />
                  </button>
                )}
              </div>

              {/* Reply trigger action */}
              {!readOnly && (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setReplyingToId(replyingToId === comment.id ? null : comment.id);
                      setReplyData("");
                    }}
                    className="text-[9px] font-bold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer flex items-center gap-0.5"
                  >
                    <CornerDownRight size={10} />
                    Reply
                  </button>
                </div>
              )}

              {/* Nested Reply form */}
              {!readOnly && replyingToId === comment.id && (
                <div className="pl-3 border-l-2 border-indigo-200 dark:border-indigo-900 mt-2 space-y-2">
                  <textarea
                    value={replyData}
                    onChange={(e) => setReplyData(e.target.value)}
                    placeholder="Write a reply..."
                    rows={1}
                    className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-lg p-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white"
                  />
                  <div className="flex gap-1.5 justify-end">
                    <button
                      type="button"
                      onClick={() => {
                        setReplyingToId(null);
                        setReplyData("");
                      }}
                      className="text-[10px] px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition-colors font-bold cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => handlePostReply(comment.id)}
                      disabled={!replyData.trim()}
                      className="text-[10px] px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-bold cursor-pointer"
                    >
                      Post Reply
                    </button>
                  </div>
                </div>
              )}

              {/* Nested Replies List */}
              {comment.replies && comment.replies.length > 0 && (
                <div className="pl-3 border-l-2 border-slate-200 dark:border-slate-800 mt-2.5 space-y-2">
                  {comment.replies.map((reply) => (
                    <div
                      key={reply.id}
                      className="bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800/80 rounded-xl p-2.5 text-[11px] leading-relaxed"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap text-[9px] text-slate-400 dark:text-slate-500 font-semibold">
                            <span className="font-bold text-slate-700 dark:text-slate-355 flex items-center gap-0.5">
                              <User size={9} className="text-slate-400" />
                              {reply.author || "User"}
                            </span>
                            <span>&bull;</span>
                            <span>{formatCommentTimestamp(reply.created_at)}</span>
                          </div>
                          <p className="text-slate-650 dark:text-slate-300 mt-0.5 break-words">
                            {reply.text}
                          </p>
                        </div>
                        {!readOnly && reply.user_id === currentUserId && (
                          <button
                            type="button"
                            onClick={() => handleDeleteReplyClick(comment.id, reply.id)}
                            className="p-1 rounded text-slate-400 hover:text-rose-600 dark:hover:text-rose-455 transition-colors cursor-pointer"
                            title="Delete reply"
                          >
                            <Trash2 size={11} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Main Comment addition input */}
      {!readOnly && (
        <div className="pt-1">
          {!showForm ? (
            <button
              type="button"
              onClick={() => setShowForm(true)}
              className="text-xs px-3.5 py-2 rounded-xl bg-indigo-50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 border border-indigo-150 dark:border-indigo-900/50 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 transition-colors font-bold cursor-pointer shadow-sm"
            >
              + Add Comment
            </button>
          ) : (
            <div className="space-y-2.5 bg-white dark:bg-slate-900 p-3 rounded-xl border border-slate-200/60 dark:border-slate-800/80 shadow-sm">
              <textarea
                value={formData}
                onChange={(e) => setFormData(e.target.value)}
                placeholder="Add a comment about this triple annotation..."
                rows={2}
                className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-955 dark:text-white leading-normal h-16"
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => {
                    setShowForm(false);
                    setFormData("");
                  }}
                  className="text-xs px-3.5 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition-all font-bold cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSubmitComment}
                  disabled={!formData.trim()}
                  className="text-xs px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed font-bold cursor-pointer shadow-sm"
                >
                  Post Comment
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
