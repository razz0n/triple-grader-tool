// TripleComments.jsx — Comments section for individual triples

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
}) {
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState("");

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

  return (
    <div className="bg-slate-50 border border-slate-100 rounded-lg p-3 mt-3">
      <h4 className="text-xs font-bold uppercase tracking-wide text-slate-600 mb-2">
        Comments
      </h4>

      {/* Comments list */}
      {comments.length > 0 ? (
        <div className="space-y-2 mb-3">
          {comments.map((comment) => (
            <div
              key={comment.id}
              className="bg-white border border-slate-100 rounded p-2 text-xs"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1 flex-wrap">
                    <span className="font-semibold text-slate-700">
                      {comment.author || "User"}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="text-slate-500">
                      {formatCommentTimestamp(comment.created_at)}
                    </span>
                  </div>
                  <p className="text-slate-600 mt-1 break-words">
                    {comment.text}
                  </p>
                </div>
                {!readOnly && comment.user_id === currentUserId && (
                  <button
                    type="button"
                    onClick={() => handleDeleteClick(comment.id)}
                    className="flex-shrink-0 px-1.5 py-0.5 text-slate-400 hover:text-red-600 transition-colors text-xs"
                    title="Delete comment"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-400 italic mb-2">No comments yet</p>
      )}

      {/* Add comment form */}
      {!readOnly && (
        <>
          {!showForm ? (
            <button
              type="button"
              onClick={() => setShowForm(true)}
              className="text-xs px-2 py-1 rounded bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors font-medium"
            >
              + Add Comment
            </button>
          ) : (
            <div className="space-y-1.5">
              <textarea
                value={formData}
                onChange={(e) => setFormData(e.target.value)}
                placeholder="Add a comment about this triple…"
                rows={2}
                className="w-full text-xs border border-slate-200 rounded p-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-blue-300 focus:border-blue-400 placeholder:text-slate-300"
              />
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={handleSubmitComment}
                  disabled={!formData.trim()}
                  className="text-xs px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                >
                  Post
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowForm(false);
                    setFormData("");
                  }}
                  className="text-xs px-2 py-1 rounded bg-slate-200 text-slate-700 hover:bg-slate-300 transition-colors font-medium"
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
