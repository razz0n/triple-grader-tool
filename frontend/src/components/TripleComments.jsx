// TripleComments.jsx — Comments section for individual triples with nested replies

import { useState } from "react";

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

  // If there are no comments and the main add comment form is not open,
  // do not render the container box. Just render a clean "Add Comment" button.
  if (comments.length === 0 && !showForm) {
    return (
      <div className="px-5 py-3 bg-slate-50/50 border-t border-slate-100 flex items-center">
        {!readOnly && (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="text-xs px-3 py-1.5 rounded-lg bg-white text-slate-600 border border-slate-200 hover:bg-slate-50 hover:text-slate-800 active:scale-95 transition-all font-semibold cursor-pointer flex items-center gap-2 shadow-sm"
          >
            💬 Add Comment
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="px-5 py-4 bg-slate-50/50 border-t border-slate-100 space-y-4">
      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
        Comments
      </h4>

      {/* Comments list */}
      {comments.length > 0 && (
        <div className="space-y-3 mb-3">
          {comments.map((comment) => (
            <div
              key={comment.id}
              className="bg-white border border-slate-200/60 rounded-xl p-3.5 text-xs space-y-2 shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1 flex-wrap text-slate-500">
                    <span className="font-semibold text-slate-700">
                      {comment.author || "User"}
                    </span>
                    <span>•</span>
                    <span>
                      {formatCommentTimestamp(comment.created_at)}
                    </span>
                  </div>
                  <p className="text-slate-600 mt-1 break-words leading-relaxed">
                    {comment.text}
                  </p>
                </div>
                {!readOnly && comment.user_id === currentUserId && (
                  <button
                    type="button"
                    onClick={() => handleDeleteClick(comment.id)}
                    className="flex-shrink-0 px-1 py-0.5 text-slate-400 hover:text-red-600 transition-colors text-xs cursor-pointer"
                    title="Delete comment"
                  >
                    ✕
                  </button>
                )}
              </div>

              {/* Reply actions */}
              {!readOnly && (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setReplyingToId(replyingToId === comment.id ? null : comment.id);
                      setReplyData("");
                    }}
                    className="text-[10px] font-bold text-blue-600 hover:text-blue-800 transition-colors cursor-pointer"
                  >
                    Reply
                  </button>
                </div>
              )}

              {/* Nested Reply Form */}
              {!readOnly && replyingToId === comment.id && (
                <div className="pl-3 border-l-2 border-blue-200 mt-2 space-y-1.5">
                  <textarea
                    value={replyData}
                    onChange={(e) => setReplyData(e.target.value)}
                    placeholder="Write a reply…"
                    rows={1}
                    className="w-full text-xs border border-slate-200 rounded p-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-blue-300 focus:border-blue-400 placeholder:text-slate-300"
                  />
                  <div className="flex gap-1">
                    <button
                      type="button"
                      onClick={() => handlePostReply(comment.id)}
                      disabled={!replyData.trim()}
                      className="text-[10px] px-2 py-0.5 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium cursor-pointer"
                    >
                      Reply
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setReplyingToId(null);
                        setReplyData("");
                      }}
                      className="text-[10px] px-2 py-0.5 rounded bg-slate-200 text-slate-700 hover:bg-slate-300 transition-colors font-medium cursor-pointer"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Nested Replies List */}
              {comment.replies && comment.replies.length > 0 && (
                <div className="pl-3 border-l-2 border-slate-200 mt-2 space-y-2">
                  {comment.replies.map((reply) => (
                    <div key={reply.id} className="bg-slate-50 border border-slate-100 rounded-lg p-2.5 text-[11px] leading-relaxed">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1 flex-wrap text-[10px] text-slate-500">
                            <span className="font-semibold text-slate-700">{reply.author || "User"}</span>
                            <span>•</span>
                            <span>{formatCommentTimestamp(reply.created_at)}</span>
                          </div>
                          <p className="text-slate-600 mt-0.5 break-words">{reply.text}</p>
                        </div>
                        {!readOnly && reply.user_id === currentUserId && (
                          <button
                            type="button"
                            onClick={() => handleDeleteReplyClick(comment.id, reply.id)}
                            className="flex-shrink-0 px-1 text-slate-400 hover:text-red-600 transition-colors text-[10px] cursor-pointer"
                            title="Delete reply"
                          >
                            ✕
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

      {/* Add comment form */}
      {!readOnly && (
        <>
          {!showForm ? (
            <button
              type="button"
              onClick={() => setShowForm(true)}
              className="text-xs px-3 py-1.5 rounded-lg bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors font-semibold cursor-pointer shadow-sm"
            >
              + Add Comment
            </button>
          ) : (
            <div className="space-y-2 mt-2">
              <textarea
                value={formData}
                onChange={(e) => setFormData(e.target.value)}
                placeholder="Add a comment about this triple…"
                rows={2}
                className="w-full text-xs border border-slate-200 rounded-lg p-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all placeholder:text-slate-300 h-16"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleSubmitComment}
                  disabled={!formData.trim()}
                  className="text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed font-semibold cursor-pointer shadow-sm"
                >
                  Post
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowForm(false);
                    setFormData("");
                  }}
                  className="text-xs px-3 py-1.5 rounded-lg bg-slate-200 text-slate-700 hover:bg-slate-300 transition-all font-semibold cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
