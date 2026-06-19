import { useState, useEffect, useRef } from "react";
import { MessageSquare, CornerDownRight, Trash2, Send, X, User } from "lucide-react";
import { useDialog } from "./CustomDialog";

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

function ReplyNode({
  reply,
  commentId,
  replyingToId,
  setReplyingToId,
  replyData,
  setReplyData,
  handlePostReply,
  handleDeleteReplyClick,
  currentUserId,
  readOnly,
  depth = 0
}) {
  const isReplying = replyingToId === reply.id;
  const indentClass = depth > 0 ? "pl-3 sm:pl-4 border-l border-slate-205 dark:border-slate-800/80 mt-2" : "";

  return (
    <div key={reply.id} className={indentClass}>
      <div className="bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800/80 rounded-xl p-2.5 text-[11px] leading-relaxed relative">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap text-[9px] text-slate-400 dark:text-slate-500 font-semibold">
              <span className="font-bold text-slate-700 dark:text-slate-355 flex items-center gap-0.5">
                <User size={9} className="text-slate-400" />
                {reply.author || "User"}
              </span>
              {reply.parent_reply_author && (
                <>
                  <span className="text-slate-300">&bull;</span>
                  <span className="text-indigo-650 dark:text-indigo-400 font-normal">
                    replying to {reply.parent_reply_author}
                  </span>
                </>
              )}
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
              onClick={() => handleDeleteReplyClick(commentId, reply.id)}
              className="p-1 rounded text-slate-400 hover:text-rose-600 dark:hover:text-rose-455 transition-colors cursor-pointer"
              title="Delete reply"
            >
              <Trash2 size={11} />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 mt-1 select-none">
          <button
            type="button"
            onClick={() => {
              if (isReplying) {
                setReplyingToId(null);
                setReplyData("");
              } else {
                setReplyingToId(reply.id);
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
              onClick={() => handlePostReply(commentId, reply.id)}
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
            <ReplyNode
              key={child.id}
              reply={child}
              commentId={commentId}
              replyingToId={replyingToId}
              setReplyingToId={setReplyingToId}
              replyData={replyData}
              setReplyData={setReplyData}
              handlePostReply={handlePostReply}
              handleDeleteReplyClick={handleDeleteReplyClick}
              currentUserId={currentUserId}
              readOnly={readOnly}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
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
  const { showAlert, showConfirm } = useDialog();
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState("");
  const [replyingToId, setReplyingToId] = useState(null);
  const [replyData, setReplyData] = useState("");
  const textareaRef = useRef(null);

  useEffect(() => {
    if (showForm) {
      textareaRef.current?.focus();
    }
  }, [showForm]);

  useEffect(() => {
    if (replyingToId) {
      setTimeout(() => {
        const replyTextarea = document.querySelector(`textarea[placeholder="Write a reply..."]`);
        if (replyTextarea) {
          replyTextarea.focus();
        }
      }, 50);
    }
  }, [replyingToId]);

  const handleSubmitComment = async () => {
    const text = String(formData || "").trim();
    if (!text) {
      showAlert("Comment cannot be empty", "Validation Error");
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
      showAlert("Failed to add comment: " + err.message, "Error");
    }
  };

  const handleDeleteClick = async (commentId) => {
    const ok = await showConfirm("Remove this comment?", "Remove Comment", "Remove", "Cancel");
    if (!ok) return;
    try {
      await onDeleteComment?.(commentId);
    } catch (err) {
      showAlert("Failed to delete comment: " + err.message, "Error");
    }
  };

  const handlePostReply = async (commentId, parentReplyId = null) => {
    const text = String(replyData || "").trim();
    if (!text) return;
    try {
      const newReply = {
        id: createCommentId(),
        author: currentUserName || "User",
        user_id: currentUserId || "",
        text,
        created_at: new Date().toISOString(),
        parent_reply_id: parentReplyId,
        read_by: currentUserId ? [currentUserId] : [],
      };
      await onAddReply?.(commentId, newReply);
      setReplyData("");
      setReplyingToId(null);
    } catch (err) {
      showAlert("Failed to add reply: " + err.message, "Error");
    }
  };

  const handleDeleteReplyClick = async (commentId, replyId) => {
    const ok = await showConfirm("Remove this reply?", "Remove Reply", "Remove", "Cancel");
    if (!ok) return;
    try {
      await onDeleteReply?.(commentId, replyId);
    } catch (err) {
      showAlert("Failed to delete reply: " + err.message, "Error");
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

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setReplyingToId(replyingToId === comment.id ? null : comment.id);
                    setReplyData("");
                  }}
                  className="text-[9px] font-bold text-indigo-655 dark:text-indigo-450 hover:underline cursor-pointer flex items-center gap-0.5"
                >
                  <CornerDownRight size={10} />
                  Reply
                </button>
              </div>

              {/* Nested Reply form (directly replying to the top-level comment) */}
              {replyingToId === comment.id && (
                <div className="pl-3 border-l-2 border-indigo-200 dark:border-indigo-900 mt-2 space-y-2">
                  <textarea
                    autoFocus
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
                      onClick={() => handlePostReply(comment.id, null)}
                      disabled={!replyData.trim()}
                      className="text-[10px] px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-bold cursor-pointer"
                    >
                      Post Reply
                    </button>
                  </div>
                </div>
              )}

              {/* Threaded Nested Replies List */}
              {comment.replies && comment.replies.length > 0 && (
                <div className="pl-3 border-l-2 border-slate-200 dark:border-slate-800 mt-2.5 space-y-2">
                  {buildReplyTree(comment.replies).map((reply) => (
                    <ReplyNode
                      key={reply.id}
                      reply={reply}
                      commentId={comment.id}
                      replyingToId={replyingToId}
                      setReplyingToId={setReplyingToId}
                      replyData={replyData}
                      setReplyData={setReplyData}
                      handlePostReply={handlePostReply}
                      handleDeleteReplyClick={handleDeleteReplyClick}
                      currentUserId={currentUserId}
                      readOnly={readOnly}
                    />
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
                autoFocus
                ref={textareaRef}
                value={formData}
                onChange={(e) => setFormData(e.target.value)}
                placeholder="Add a comment about this triple annotation..."
                rows={2}
                className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white leading-normal h-16"
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
