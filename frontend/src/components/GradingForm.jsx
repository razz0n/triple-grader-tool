import { useState, useEffect, useRef, useMemo } from "react";
import { saveSession, downloadSession, getAuthToken, loadSession, meUser } from "../api";
import TripleCard from "./TripleCard";
import TripleComments from "./TripleComments";
import TripleSuggestions from "./TripleSuggestions";
import { useDialog } from "./CustomDialog";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  Save,
  BarChart3,
  Download,
  Eye,
  Activity,
  ArrowLeft,
  Bell,
  Sun,
  Moon,
  Menu,
  X,
  Search,
  Filter,
  CheckCircle2,
  HelpCircle,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  AlertCircle,
  MessageSquare,
  Users,
  Award,
  BookOpen
} from "lucide-react";

// ── normalizers ────────────────────────────────────────────────────────────

function normalizeMetricByUser(entry) {
  if (!entry || typeof entry !== "object") return {};
  const normalized = {};
  Object.entries(entry).forEach(([key, val]) => {
    if (val && typeof val === "object") {
      normalized[key] = {
        user_id: val.user_id ? String(val.user_id) : key,
        user_name: val.user_name ? String(val.user_name) : "Unknown Grader",
        value: val.value !== undefined && val.value !== null ? Number(val.value) : null,
      };
    } else {
      normalized[key] = {
        user_id: key,
        user_name: "Unknown Grader",
        value: val !== undefined && val !== null ? Number(val) : null,
      };
    }
  });
  return normalized;
}

function normalizeMetricValue(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function normalizeSentenceComments(comments) {
  const normalized = [];
  if (Array.isArray(comments)) {
    comments.forEach((c) => {
      if (c && typeof c === "object") {
        const author = c.author ? String(c.author) : "User";
        const text = c.text ? String(c.text) : "";
        if (
          author === "System Migration" ||
          author === "System" ||
          text.includes("Legacy Suggestion Migration")
        ) {
          return;
        }

        normalized.push({
          id: c.id ? String(c.id) : `cmt-${Math.random()}`,
          author: author,
          user_id: c.user_id ? String(c.user_id) : "",
          text: text,
          created_at: c.created_at || new Date().toISOString(),
          read_by: Array.isArray(c.read_by) ? c.read_by.map(String) : [],
          replies: Array.isArray(c.replies)
            ? c.replies.map((r) => ({
                id: r.id ? String(r.id) : `rpl-${Math.random()}`,
                author: r.author ? String(r.author) : "User",
                user_id: r.user_id ? String(r.user_id) : "",
                text: r.text ? String(r.text) : "",
                created_at: r.created_at || new Date().toISOString(),
                parent_reply_id: r.parent_reply_id ? String(r.parent_reply_id) : undefined,
                read_by: Array.isArray(r.read_by) ? r.read_by.map(String) : [],
              }))
            : [],
        });
      }
    });
  }
  return normalized;
}

function metricEntries(metricsByUser) {
  if (!metricsByUser || typeof metricsByUser !== "object") return [];
  return Object.entries(metricsByUser)
    .map(([userId, entry]) => {
      const value = normalizeMetricValue(entry?.value);
      if (value === null) return null;
      return {
        userId,
        userName: String(entry?.user_name || "Unknown Grader"),
        value,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.userName.localeCompare(b.userName));
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

const filterRepliesRecursive = (replies = [], replyIdToDelete) => {
  const idsToRemove = new Set([replyIdToDelete]);
  let added = true;
  while (added) {
    added = false;
    for (const r of replies) {
      if (r.parent_reply_id && idsToRemove.has(r.parent_reply_id) && !idsToRemove.has(r.id)) {
        idsToRemove.add(r.id);
        added = true;
      }
    }
  }
  return replies.filter((r) => !idsToRemove.has(r.id));
};

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

function SentenceReplyNode({
  reply,
  commentId,
  replyingToReplyId,
  setReplyingToReplyId,
  replyData,
  setReplyData,
  handlePostReply,
  handleDeleteReply,
  currentUserId,
  canEditSession,
  depth = 0
}) {
  const isReplying = replyingToReplyId === reply.id;
  const indentClass = depth > 0 ? "pl-3 sm:pl-4 border-l border-indigo-150 dark:border-indigo-900 mt-2" : "";

  return (
    <div key={reply.id} className={indentClass}>
      <div className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-805 leading-relaxed text-[11px] relative">
        <div className="flex justify-between items-start gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap text-[9px] text-slate-400 dark:text-slate-550 font-bold select-none">
              <span className="text-slate-700 dark:text-slate-300 font-bold">{reply.author}</span>
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
            <p className="text-slate-655 dark:text-slate-350 mt-0.5 break-words">{reply.text}</p>
          </div>
          {canEditSession && reply.user_id === currentUserId && (
            <button
              type="button"
              onClick={() => handleDeleteReply(reply.id)}
              className="p-1 rounded text-slate-400 hover:text-rose-605 transition-colors cursor-pointer"
              title="Delete reply"
            >
              <X size={11} />
            </button>
          )}
        </div>

        <div className="flex items-center gap-2 mt-1 select-none">
          <button
            type="button"
            onClick={() => {
              if (isReplying) {
                setReplyingToReplyId(null);
                setReplyData("");
              } else {
                setReplyingToReplyId(reply.id);
                setReplyData("");
              }
            }}
            className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
          >
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
                setReplyingToReplyId(null);
                setReplyData("");
              }}
              className="text-[10px] px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-850 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition-colors font-bold cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => handlePostReply(reply.id)}
              disabled={!replyData.trim()}
              className="text-[10px] px-2.5 py-1 rounded-lg bg-indigo-650 hover:bg-indigo-700 text-white font-bold cursor-pointer"
            >
              Reply
            </button>
          </div>
        </div>
      )}

      {reply.replies && reply.replies.length > 0 && (
        <div className="space-y-2 mt-2">
          {reply.replies.map((child) => (
            <SentenceReplyNode
              key={child.id}
              reply={child}
              commentId={commentId}
              replyingToReplyId={replyingToReplyId}
              setReplyingToReplyId={setReplyingToReplyId}
              replyData={replyData}
              setReplyData={setReplyData}
              handlePostReply={handlePostReply}
              handleDeleteReply={handleDeleteReply}
              currentUserId={currentUserId}
              canEditSession={canEditSession}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function GradingForm({ uploadData, onReset, currentUser, onEvaluate }) {
  const { showConfirm, showAlert } = useDialog();
  const {
    session_id: initialSessionId,
    source_filename,
    sentences: initialSentences = [],
    uploaded_at,
    manual_mode,
    resumed,
    can_edit,
    can_suggest,
    can_approve,
    is_owner,
  } = uploadData;

  const canEditSession = can_edit ?? !is_owner;
  const canSuggestTriples = can_suggest ?? !is_owner;
  const canApproveSuggestions = can_approve ?? !!is_owner;
  const readOnly = !canEditSession && !canSuggestTriples;
  const currentUserId = currentUser?.id || "";
  const currentUserName = currentUser?.name || currentUser?.username || currentUser?.email || "User";

  // Exit prompt modal state
  const [showExitPromptModal, setShowExitPromptModal] = useState(false);

  // Inactivity and offline status states
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  const [showIdleWarning, setShowIdleWarning] = useState(false);
  const [idleCountdown, setIdleCountdown] = useState(30);

  const inactivityTimerRef = useRef(null);
  const warningIntervalRef = useRef(null);
  const heartbeatTimerRef = useRef(null);

  // 6-Hour Inactivity/Idle Timeout logic
  useEffect(() => {
    const IDLE_LIMIT = 21570000; // 5 hours 59.5 minutes in milliseconds
    const WARNING_DURATION = 30; // 30 seconds countdown

    const handleForceLogoutOnIdle = async () => {
      if (hasUnsavedChangesRef.current) {
        try {
          const payload = latestPayloadRef.current;
          await saveSession(payload);
        } catch (e) {
          console.error("Auto-save on idle timeout failed:", e);
        }
      }
      window.dispatchEvent(new CustomEvent("auth:logout"));
    };

    const resetInactivityTimer = () => {
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      if (warningIntervalRef.current) clearInterval(warningIntervalRef.current);

      setShowIdleWarning(false);

      inactivityTimerRef.current = setTimeout(() => {
        setShowIdleWarning(true);
        setIdleCountdown(WARNING_DURATION);

        let count = WARNING_DURATION;
        warningIntervalRef.current = setInterval(async () => {
          count -= 1;
          setIdleCountdown(count);
          if (count <= 0) {
            clearInterval(warningIntervalRef.current);
            await handleForceLogoutOnIdle();
          }
        }, 1000);
      }, IDLE_LIMIT);
    };

    const events = ["mousemove", "keydown", "click", "scroll", "touchstart"];
    const handleActivity = () => {
      if (!showIdleWarning) {
        resetInactivityTimer();
      }
    };

    events.forEach((event) => window.addEventListener(event, handleActivity));
    resetInactivityTimer();

    return () => {
      if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current);
      if (warningIntervalRef.current) clearInterval(warningIntervalRef.current);
      events.forEach((event) => window.removeEventListener(event, handleActivity));
    };
  }, [showIdleWarning]);

  // Offline Backup & Heartbeat Monitor
  useEffect(() => {
    const checkConnection = async () => {
      try {
        await meUser();
        setIsOffline(false);
      } catch (err) {
        if (err?.response?.status !== 401 && err?.response?.status !== 403) {
          setIsOffline(true);
          if (hasUnsavedChangesRef.current) {
            try {
              localStorage.setItem(
                `offline_backup_${initialSessionId}`,
                JSON.stringify(latestPayloadRef.current)
              );
            } catch (e) {
              console.error("Local storage backup failed:", e);
            }
          }
        }
      }
    };

    const handleOnline = async () => {
      setIsOffline(false);
      const backup = localStorage.getItem(`offline_backup_${initialSessionId}`);
      if (backup) {
        try {
          const payload = JSON.parse(backup);
          await saveSession(payload);
          localStorage.removeItem(`offline_backup_${initialSessionId}`);
          setSaveMsg("Offline changes synchronized successfully");
          setTimeout(() => setSaveMsg(""), 3000);
        } catch (e) {
          console.error("Syncing offline backup failed:", e);
        }
      }
    };

    const handleOffline = () => {
      setIsOffline(true);
      if (hasUnsavedChangesRef.current) {
        try {
          localStorage.setItem(
            `offline_backup_${initialSessionId}`,
            JSON.stringify(latestPayloadRef.current)
          );
        } catch (e) {
          console.error("Local storage backup failed:", e);
        }
      }
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    heartbeatTimerRef.current = setInterval(checkConnection, 30000);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
    };
  }, [initialSessionId]);

  // Deep-clone sentences into local mutable state
  const [sentences, setSentences] = useState(() =>
    initialSentences.map((s) => {
      const completenessByUser = normalizeMetricByUser(s.completeness_by_user);
      const externalRelationByUser = normalizeMetricByUser(s.external_relation_by_user);
      const sentenceComments = normalizeSentenceComments(s.sentence_comments);

      const completenessValues = Object.values(completenessByUser)
        .map((entry) => normalizeMetricValue(entry?.value))
        .filter((value) => value !== null);
      const externalRelationValues = Object.values(externalRelationByUser)
        .map((entry) => normalizeMetricValue(entry?.value))
        .filter((value) => value !== null);

      return {
        ...s,
        suggestion: "",
        sentence_comments: sentenceComments,
        comment_count: Number.isFinite(s.comment_count) ? s.comment_count : sentenceComments.length,
        completeness:
          normalizeMetricValue(s.completeness) ??
          normalizeMetricValue(
            (s.triples || []).find((t) => t.completeness !== null && t.completeness !== undefined)?.completeness
          ) ??
          null,
        external_relation:
          normalizeMetricValue(s.external_relation) ??
          normalizeMetricValue(s.relation) ??
          normalizeMetricValue(
            (s.triples || []).find((t) => t.relation !== null && t.relation !== undefined)?.relation
          ) ??
          null,
        completeness_by_user: completenessByUser,
        external_relation_by_user: externalRelationByUser,
        completeness_count: Number.isFinite(s.completeness_count)
          ? s.completeness_count
          : completenessValues.length,
        completeness_average:
          s.completeness_average ??
          (completenessValues.length > 0
            ? Number((completenessValues.reduce((acc, value) => acc + value, 0) / completenessValues.length).toFixed(2))
            : null),
        external_relation_count: Number.isFinite(s.external_relation_count)
          ? s.external_relation_count
          : externalRelationValues.length,
        external_relation_average:
          s.external_relation_average ??
          (externalRelationValues.length > 0
            ? Number((externalRelationValues.reduce((acc, value) => acc + value, 0) / externalRelationValues.length).toFixed(2))
            : null),
        triples: (s.triples || []).map((t) => ({
          ...t,
          grade: t.grade ?? null,
          author: t.author || null,
          grades_by_user: t.grades_by_user || {},
          grade_count: Number.isFinite(t.grade_count) ? t.grade_count : undefined,
          grade_average: t.grade_average ?? null,
          suggestions: t.suggestions || [],
          triple_comments: normalizeSentenceComments(t.triple_comments),
        })),
      };
    })
  );

  const [currentIdx, setCurrentIdx]       = useState(0);
  const [savedSessionId, setSavedSessionId] = useState(resumed ? initialSessionId : null);
  const [savedAt, setSavedAt]             = useState(resumed ? new Date() : null);
  const [saving, setSaving]               = useState(false);
  const [saveMsg, setSaveMsg]             = useState("");
  const [saveError, setSaveError]         = useState("");

  const [dlFmt, setDlFmt]           = useState("pdf");
  const [dlOpen, setDlOpen]         = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [dlError, setDlError]       = useState("");
  const dlRef                       = useRef(null);
  const [moreOpen, setMoreOpen]     = useState(false);
  const moreRef                     = useRef(null);
  const idleTimerRef                = useRef(null);
  const hasUnsavedChangesRef        = useRef(false);
  const savingRef                   = useRef(false);
  const latestPayloadRef            = useRef(null);

  // Left sidebar & dark mode toggles
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarFilter, setSidebarFilter] = useState("all"); // "all" | "completed" | "pending"
  const [searchQuery, setSearchQuery] = useState("");
  const [isDark, setIsDark] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [showSentenceMetrics, setShowSentenceMetrics] = useState(true);
  const mainRef = useRef(null);

  useEffect(() => {
    const handleScroll = () => {
      if (mainRef.current) {
        setIsCollapsed(mainRef.current.scrollTop > 80);
      }
    };
    const mainEl = mainRef.current;
    if (mainEl) {
      mainEl.addEventListener("scroll", handleScroll);
    }
    return () => {
      if (mainEl) {
        mainEl.removeEventListener("scroll", handleScroll);
      }
    };
  }, []);

  // Scroll main workspace container to top when sentence index changes
  useEffect(() => {
    if (mainRef.current) {
      mainRef.current.scrollTop = 0;
    }
  }, [currentIdx]);

  const [replyingToSentenceCommentId, setReplyingToSentenceCommentId] = useState(null);
  const [sentenceCommentReplyText, setSentenceCommentReplyText] = useState("");
  const [replyingToSentenceReplyId, setReplyingToSentenceReplyId] = useState(null);
  const [sentenceReplyData, setSentenceReplyData] = useState("");
  const [showSentenceCommentForm, setShowSentenceCommentForm] = useState(false);
  const [sentenceCommentText, setSentenceCommentText] = useState("");
  const sentenceCommentTextareaRef = useRef(null);

  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [highlightedElementId, setHighlightedElementId] = useState(null);
  const [showPaperMetricsModal, setShowPaperMetricsModal] = useState(false);
  const [showDownloadWarningModal, setShowDownloadWarningModal] = useState(false);
  const [pendingDownloadFormat, setPendingDownloadFormat] = useState(null);
  const notificationsRef = useRef(null);
  const total   = sentences.length;
  const current = sentences[currentIdx];
  const completenessMetricEntries = metricEntries(current?.completeness_by_user);
  const externalRelationMetricEntries = metricEntries(current?.external_relation_by_user);

  // Initialize Dark Mode theme from localStorage/system
  useEffect(() => {
    const isDarkTheme =
      localStorage.getItem("theme") === "dark" ||
      (!("theme" in localStorage) && window.matchMedia("(prefers-color-scheme: dark)").matches);
    setIsDark(isDarkTheme);
    if (isDarkTheme) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, []);

  const toggleTheme = () => {
    const nextDark = !isDark;
    setIsDark(nextDark);
    if (nextDark) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  };

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dlRef.current && !dlRef.current.contains(e.target)) setDlOpen(false);
      if (moreRef.current && !moreRef.current.contains(e.target)) setMoreOpen(false);
      if (notificationsRef.current && !notificationsRef.current.contains(e.target)) setNotificationsOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => {
      document.removeEventListener("mousedown", handler);
    };
  }, []);

  // Auto-scroll active sidebar item into view
  useEffect(() => {
    const activeEl = document.getElementById(`sidebar-sentence-${currentIdx}`);
    if (activeEl) {
      activeEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [currentIdx]);

  // Auto-scroll to first ungraded triple on sentence change if in "pending" tab
  useEffect(() => {
    if (sidebarFilter === "pending" && current) {
      const timer = setTimeout(() => {
        const activeTriples = (current.triples || []).filter((t) => {
          const isActive = (!t.is_new_suggestion && !t.marked_for_removal) || (t.is_new_suggestion && t.status === "approved");
          if (!isActive) return false;
          const userGrade = t.grades_by_user?.[currentUserId]?.grade;
          return userGrade === undefined || userGrade === null;
        });
        if (activeTriples.length > 0) {
          const firstUngraded = activeTriples[0];
          const elementId = `triple-card-${firstUngraded.id}`;
          const el = document.getElementById(elementId);
          if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "center" });
            setHighlightedElementId(elementId);
            setTimeout(() => setHighlightedElementId(null), 2050);
            setTimeout(() => {
              const btn = el.querySelector(".grade-button");
              if (btn) btn.focus();
            }, 300);
          }
        }
      }, 150);
      return () => clearTimeout(timer);
    }
  }, [currentIdx, sidebarFilter, currentUserId, current]);

  const currentSentenceComments = useMemo(
    () => normalizeSentenceComments(current?.sentence_comments),
    [current?.sentence_comments]
  );

  const ungradedTriples = useMemo(() => {
    if (!current) return [];
    return (current.triples || []).filter((t) => {
      const isActive = (!t.is_new_suggestion && !t.marked_for_removal) || (t.is_new_suggestion && t.status === "approved");
      if (!isActive) return false;
      const userGrade = t.grades_by_user?.[currentUserId]?.grade;
      return userGrade === undefined || userGrade === null;
    });
  }, [current, currentUserId]);

  const handleJumpToUngraded = () => {
    if (ungradedTriples.length === 0) return;
    const firstUngraded = ungradedTriples[0];
    const elementId = `triple-card-${firstUngraded.id}`;
    const el = document.getElementById(elementId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setHighlightedElementId(elementId);
      setTimeout(() => setHighlightedElementId(null), 2050);
    }
  };

  const paperMetrics = useMemo(() => {
    const totalSentences = sentences.length;
    let totalGoldTriples = 0;
    sentences.forEach((s) => {
      (s.triples || []).forEach((t) => {
        if (
          (!t.is_new_suggestion && !t.marked_for_removal) ||
          (t.is_new_suggestion && t.status === "approved")
        ) {
          totalGoldTriples++;
        }
      });
    });
    
    const avgTriplesPerSentence = totalSentences > 0 ? (totalGoldTriples / totalSentences).toFixed(2) : "0.00";
    
    const uniqueUsers = new Set();
    const ownerId = String(uploadData.owner_user_id || "").trim();
    if (ownerId) uniqueUsers.add(ownerId);
    const ownerName = String(uploadData.owner_name || "").trim();
    if (ownerName) uniqueUsers.add(ownerName);

    sentences.forEach((s) => {
      (s.sentence_comments || []).forEach((c) => {
        if (c.user_id) uniqueUsers.add(c.user_id);
        else if (c.author) uniqueUsers.add(c.author);
        (c.replies || []).forEach((r) => {
          if (r.user_id) uniqueUsers.add(r.user_id);
          else if (r.author) uniqueUsers.add(r.author);
        });
      });
      if (s.completeness_by_user) {
        Object.keys(s.completeness_by_user).forEach((uid) => uniqueUsers.add(uid));
      }
      if (s.external_relation_by_user) {
        Object.keys(s.external_relation_by_user).forEach((uid) => uniqueUsers.add(uid));
      }
      (s.triples || []).forEach((t) => {
        if (t.grades_by_user) {
          Object.keys(t.grades_by_user).forEach((uid) => uniqueUsers.add(uid));
        }
        (t.triple_comments || []).forEach((c) => {
          if (c.user_id) uniqueUsers.add(c.user_id);
          else if (c.author) uniqueUsers.add(c.author);
          (c.replies || []).forEach((r) => {
            if (r.user_id) uniqueUsers.add(r.user_id);
            else if (r.author) uniqueUsers.add(r.author);
          });
        });
        (t.suggestions || []).forEach((sug) => {
          if (sug.user_id) uniqueUsers.add(sug.user_id);
          else if (sug.author) uniqueUsers.add(sug.author);
          (sug.replies || []).forEach((r) => {
            if (r.user_id) uniqueUsers.add(r.user_id);
            else if (r.author) uniqueUsers.add(r.author);
          });
        });
      });
    });
    
    uniqueUsers.delete("");
    uniqueUsers.delete(undefined);
    uniqueUsers.delete(null);
    const numUsers = uniqueUsers.size > 0 ? uniqueUsers.size : 1;
    
    const calibrationSentences = sentences.filter(s => s.is_calibration).length;
    const calibrationPct = totalSentences > 0 ? ((calibrationSentences / totalSentences) * 100).toFixed(1) : "0.0";
    
    let agreedTriples = 0;
    let multiGradeTriples = 0;
    sentences.forEach((s) => {
      (s.triples || []).forEach((t) => {
        if (!t.is_new_suggestion) {
          const grades = Object.values(t.grades_by_user || {})
            .map((g) => g?.grade)
            .filter((g) => g !== null && g !== undefined);
          if (grades.length >= 2) {
            multiGradeTriples++;
            const allSame = grades.every(g => g === grades[0]);
            if (allSame) agreedTriples++;
          }
        }
      });
    });
    const agreementPct = multiGradeTriples > 0 ? ((agreedTriples / multiGradeTriples) * 100).toFixed(1) + "%" : "N/A";
    
    let acceptedWithoutChange = 0;
    let modifiedAfterReview = 0;
    sentences.forEach((s) => {
      (s.triples || []).forEach((t) => {
        if (!t.is_new_suggestion && !t.marked_for_removal) {
          const hasApprovedSug = (t.suggestions || []).some(sug => sug.status === "approved");
          if (hasApprovedSug) {
            modifiedAfterReview++;
          } else {
            acceptedWithoutChange++;
          }
        }
      });
    });
    const acceptedPct = totalGoldTriples > 0 ? ((acceptedWithoutChange / totalGoldTriples) * 100).toFixed(1) : "0.0";
    const modifiedPct = totalGoldTriples > 0 ? ((modifiedAfterReview / totalGoldTriples) * 100).toFixed(1) : "0.0";
    
    let rejectedTriples = 0;
    sentences.forEach((s) => {
      (s.triples || []).forEach((t) => {
        if (!t.is_new_suggestion && t.marked_for_removal) {
          rejectedTriples++;
        }
      });
    });
    
    let missingTriplesAdded = 0;
    sentences.forEach((s) => {
      (s.triples || []).forEach((t) => {
        if (t.is_new_suggestion && t.status === "approved") {
          missingTriplesAdded++;
        }
      });
    });
    
    let methodAdjudicationCount = 0;
    sentences.forEach((s) => {
      if ((s.sentence_comments || []).length > 0) {
        methodAdjudicationCount++;
      }
    });
    
    let tripleAdjudicationCount = 0;
    sentences.forEach((s) => {
      (s.triples || []).forEach((t) => {
        const hasComments = (t.triple_comments || []).length > 0;
        const hasSugReplies = (t.suggestions || []).some(sug => (sug.replies || []).length > 0);
        if (hasComments || hasSugReplies) {
          tripleAdjudicationCount++;
        }
      });
    });
    
    const guidelineKeywords = ["guideline", "rule", "instruction", "method decision"];
    let guidelineUpdatesCount = 0;
    sentences.forEach((s) => {
      (s.sentence_comments || []).forEach((c) => {
        const txt = (c.text || "").toLowerCase();
        if (guidelineKeywords.some(k => txt.includes(k))) guidelineUpdatesCount++;
        (c.replies || []).forEach((r) => {
          const rTxt = (r.text || "").toLowerCase();
          if (guidelineKeywords.some(k => rTxt.includes(k))) guidelineUpdatesCount++;
        });
      });
    });

    const guidelineUpdatesList = Array.isArray(uploadData.guideline_updates) ? uploadData.guideline_updates : [];
    const numGuidelineUpdates = Math.max(guidelineUpdatesList.length, guidelineUpdatesCount);

    let evalF1 = "N/A";
    if (uploadData.evaluation && typeof uploadData.evaluation === "object") {
      const f1Val = uploadData.evaluation.f1;
      if (f1Val !== null && f1Val !== undefined) {
        const parsedF1 = parseFloat(f1Val);
        if (!isNaN(parsedF1)) {
          evalF1 = parsedF1 <= 1.0 ? `${(parsedF1 * 100).toFixed(1)}%` : `${parsedF1.toFixed(1)}%`;
        } else {
          evalF1 = String(f1Val);
        }
      }
    }
    
    return {
      totalSentences,
      totalGoldTriples,
      avgTriplesPerSentence,
      numUsers,
      calibrationPct,
      agreementPct,
      acceptedWithoutChange,
      acceptedPct,
      modifiedAfterReview,
      modifiedPct,
      rejectedTriples,
      missingTriplesAdded,
      methodAdjudicationCount,
      tripleAdjudicationCount,
      numGuidelineUpdates,
      evalF1,
    };
  }, [sentences, uploadData]);

  const isOwner = !!is_owner;

  const notifications = useMemo(() => {
    const list = [];
    if (!currentUserId) return list;

    // Load local storage read states for completion & deletion notifications
    const readCompletions = JSON.parse(localStorage.getItem(`read_completions_${initialSessionId}`) || "[]");
    const readDeletions = JSON.parse(localStorage.getItem(`read_deletions_${initialSessionId}`) || "[]");

    // 1. Calculate active triples and grader completion (for owner notification)
    let totalT = 0;
    const graderGradesCount = {}; // userId -> count
    const graderNames = {}; // userId -> name

    sentences.forEach((s) => {
      const activeTriples = (s.triples || []).filter(t => !t.is_new_suggestion || t.status === "approved");
      totalT += activeTriples.length;
      activeTriples.forEach((t) => {
        Object.entries(t.grades_by_user || {}).forEach(([userId, payload]) => {
          if (payload?.grade !== null && payload?.grade !== undefined && payload?.grade !== "") {
            graderGradesCount[userId] = (graderGradesCount[userId] || 0) + 1;
            graderNames[userId] = payload.user_name || "Grader";
          }
        });
      });
    });

    if (isOwner && totalT > 0) {
      Object.entries(graderGradesCount).forEach(([userId, count]) => {
        if (count === totalT && !readCompletions.includes(userId)) {
          list.push({
            id: `completion-${userId}`,
            type: "grading_completed",
            title: `Grading completed by ${graderNames[userId]}`,
            text: `All ${totalT} triples have been graded.`,
            createdAt: new Date().toISOString(),
            sentenceId: null,
            sentenceIdx: 0,
            graderId: userId,
          });
        }
      });
    }

    sentences.forEach((sentence) => {
      const sentenceIdx = sentences.findIndex(s => s.id === sentence.id);

      // 2. Sentence Comments
      (sentence.sentence_comments || []).forEach((comment) => {
        const isOwnC = comment.user_id === currentUserId;
        const isReadC = (comment.read_by || []).includes(currentUserId);

        // Notify if unread, not own, and user is owner (since owner is involved in all comments)
        if (!isOwnC && !isReadC && isOwner) {
          list.push({
            id: comment.id,
            type: "sentence_comment",
            title: `New comment from ${comment.author || "User"}`,
            text: comment.text,
            createdAt: comment.created_at,
            sentenceId: sentence.id,
            sentenceIdx,
            tripleId: null,
            commentId: comment.id,
          });
        }

        // Replies to sentence comment
        (comment.replies || []).forEach((reply) => {
          const isOwn = reply.user_id === currentUserId;
          const isRead = (reply.read_by || []).includes(currentUserId);
          if (!isOwn && !isRead) {
            // Involved: owner, parent comment author, parent reply author, or anyone who replied in this thread
            const isParentAuthor = comment.user_id === currentUserId;
            const hasRepliedInThread = (comment.replies || []).some(r => r.user_id === currentUserId);
            const isDirectParentAuthor = reply.parent_reply_id && 
              (comment.replies || []).some(r => r.id === reply.parent_reply_id && r.user_id === currentUserId);
            if (isOwner || isParentAuthor || hasRepliedInThread || isDirectParentAuthor) {
              list.push({
                id: reply.id,
                type: "comment_reply",
                title: isDirectParentAuthor
                  ? `New reply to your post from ${reply.author || "User"}`
                  : `New reply from ${reply.author || "User"}`,
                text: reply.text,
                createdAt: reply.created_at,
                sentenceId: sentence.id,
                sentenceIdx,
                tripleId: null,
                commentId: comment.id,
              });
            }
          }
        });
      });

      (sentence.triples || []).forEach((triple) => {
        // 3. Deletion Requests (Owner only)
        if (isOwner && triple.marked_for_removal && !readDeletions.includes(triple.id)) {
          list.push({
            id: `deletion-${triple.id}`,
            type: "deletion_request",
            title: `Deletion requested for triple`,
            text: `Reason: "${triple.removal_reason || "No reason given."}" for (${triple.subject}, ${triple.predicate}, ${triple.object})`,
            createdAt: triple.graded_at || new Date().toISOString(),
            sentenceId: sentence.id,
            sentenceIdx,
            tripleId: triple.id,
          });
        }

        // 4. Triple Comments
        (triple.triple_comments || []).forEach((comment) => {
          const isOwnC = comment.user_id === currentUserId;
          const isReadC = (comment.read_by || []).includes(currentUserId);

          if (!isOwnC && !isReadC) {
            // Involved: owner, or creator of suggestion (if this is a suggested triple)
            const isSuggestionCreator = triple.is_new_suggestion && (triple.suggested_by_id === currentUserId || triple.suggested_by === currentUserName);
            if (isOwner || isSuggestionCreator) {
              list.push({
                id: comment.id,
                type: "triple_comment",
                title: `New comment from ${comment.author || "User"} on triple`,
                text: comment.text,
                createdAt: comment.created_at,
                sentenceId: sentence.id,
                sentenceIdx,
                tripleId: triple.id,
                commentId: comment.id,
              });
            }
          }

          // Replies to triple comment
          (comment.replies || []).forEach((reply) => {
            const isOwn = reply.user_id === currentUserId;
            const isRead = (reply.read_by || []).includes(currentUserId);
            if (!isOwn && !isRead) {
              // Involved: owner, parent comment author, suggestion creator, parent reply author, or anyone who replied in this thread
              const isParentAuthor = comment.user_id === currentUserId;
              const hasRepliedInThread = (comment.replies || []).some(r => r.user_id === currentUserId);
              const isSuggestionCreator = triple.is_new_suggestion && (triple.suggested_by_id === currentUserId || triple.suggested_by === currentUserName);
              const isDirectParentAuthor = reply.parent_reply_id && 
                (comment.replies || []).some(r => r.id === reply.parent_reply_id && r.user_id === currentUserId);
              if (isOwner || isParentAuthor || hasRepliedInThread || isSuggestionCreator || isDirectParentAuthor) {
                list.push({
                  id: reply.id,
                  type: "comment_reply",
                  title: isDirectParentAuthor
                    ? `New reply to your post from ${reply.author || "User"} on triple`
                    : `New reply from ${reply.author || "User"} on triple`,
                  text: reply.text,
                  createdAt: reply.created_at,
                  sentenceId: sentence.id,
                  sentenceIdx,
                  tripleId: triple.id,
                  commentId: comment.id,
                });
              }
            }
          });
        });

        // 5. Triple Suggestions (Owner only gets new suggestion notifications)
        (triple.suggestions || []).forEach((sug) => {
          const isOwnSug = sug.user_id === currentUserId;
          const isReadSug = (sug.read_by || []).includes(currentUserId);
          if (!isOwnSug && !isReadSug && isOwner) {
            list.push({
              id: sug.id,
              type: "triple_suggestion",
              title: `New suggestion from ${sug.author || "User"}`,
              text: `Proposed triple: (${sug.subject || ""}, ${sug.predicate || ""}, ${sug.object || ""})`,
              createdAt: sug.created_at,
              sentenceId: sentence.id,
              sentenceIdx,
              tripleId: triple.id,
              suggestionId: sug.id,
            });
          }

          // Replies to triple suggestion
          (sug.replies || []).forEach((reply) => {
            const isOwnReply = reply.user_id === currentUserId;
            const isRead = (reply.read_by || []).includes(currentUserId);
            if (!isOwnReply && !isRead) {
              // Involved: owner, suggestion author, parent reply author, or anyone who replied in this thread
              const isSuggestionAuthor = sug.user_id === currentUserId;
              const hasRepliedInThread = (sug.replies || []).some(r => r.user_id === currentUserId);
              const isDirectParentAuthor = reply.parent_reply_id && 
                (sug.replies || []).some(r => r.id === reply.parent_reply_id && r.user_id === currentUserId);
              if (isOwner || isSuggestionAuthor || hasRepliedInThread || isDirectParentAuthor) {
                list.push({
                  id: reply.id,
                  type: "suggestion_reply",
                  title: isDirectParentAuthor
                    ? `New reply to your suggestion comment from ${reply.author || "User"}`
                    : `New reply on suggestion from ${reply.author || "User"}`,
                  text: reply.text,
                  createdAt: reply.created_at,
                  sentenceId: sentence.id,
                  sentenceIdx,
                  tripleId: triple.id,
                  suggestionId: sug.id,
                });
              }
            }
          });
        });
      });
    });

    return list.sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""));
  }, [sentences, currentUserId, isOwner, initialSessionId, currentUserName]);

  // Overall grading progress across ALL sentences
  const gradingProgress = useMemo(() => {
    let graded = 0;
    let totalT = 0;
    sentences.forEach((s) => {
      const activeTriples = (s.triples || []).filter(t => !t.is_new_suggestion || t.status === "approved");
      totalT += activeTriples.length;
      graded += activeTriples.filter(
        (t) => t.grade !== null && t.grade !== undefined
      ).length;
    });
    return {
      graded,
      total: totalT,
      pct: totalT > 0 ? Math.round((graded / totalT) * 100) : 0,
    };
  }, [sentences]);

  const graderSummary = useMemo(() => {
    const rowsByUser = new Map();
    let totalGradeEntries = 0;
    let overallGradeSum = 0;

    sentences.forEach((sentence) => {
      (sentence.triples || []).forEach((triple) => {
        if (triple.is_new_suggestion && triple.status !== "approved") return;
        const gradesByUser = triple?.grades_by_user && typeof triple.grades_by_user === "object"
          ? triple.grades_by_user
          : {};

        Object.entries(gradesByUser).forEach(([key, payload]) => {
          if (payload?.grade === null || payload?.grade === undefined || payload?.grade === "") return;
          const uId = String(payload.user_id || key);
          const uName = String(payload.user_name || "Unknown Grader");
          const val = Number(payload.grade);

          totalGradeEntries++;
          overallGradeSum += val;

          if (!rowsByUser.has(uId)) {
            rowsByUser.set(uId, {
              user_id: uId,
              user_name: uName,
              graded_triples: 0,
              grade_sum: 0,
            });
          }
          const existing = rowsByUser.get(uId);
          existing.graded_triples += 1;
          existing.grade_sum += val;
        });
      });
    });

    const rows = [...rowsByUser.values()].map((r) => ({
      ...r,
      average_grade: r.graded_triples > 0 ? Number((r.grade_sum / r.graded_triples).toFixed(2)) : null,
    })).sort((a, b) => b.graded_triples - a.graded_triples);

    const overallAverage = totalGradeEntries > 0 ? Number((overallGradeSum / totalGradeEntries).toFixed(2)) : null;

    return {
      rows,
      overallAverage,
      totalUniqueGraders: rowsByUser.size,
    };
  }, [sentences]);

  // Auto-save logic
  useEffect(() => {
    latestPayloadRef.current = {
      session_id: initialSessionId,
      source_filename,
      uploaded_at,
      manual_mode: !!manual_mode,
      total_sentences: sentences.length,
      sentences: sentences.map((s) => ({
        id: s.id,
        text: s.text,
        is_calibration: !!s.is_calibration,
        completeness: s.completeness,
        external_relation: s.external_relation,
        completeness_by_user: s.completeness_by_user,
        external_relation_by_user: s.external_relation_by_user,
        sentence_comments: s.sentence_comments,
        triples: s.triples.map((t) => ({
          id: t.id,
          subject: t.subject,
          predicate: t.predicate,
          object: t.object,
          grade: t.grade,
          author: t.author,
          grades_by_user: t.grades_by_user,
          is_new_suggestion: !!t.is_new_suggestion,
          status: t.status || null,
          suggested_by: t.suggested_by || null,
          marked_for_removal: !!t.marked_for_removal,
          removal_reason: t.removal_reason || "",
          marked_for_removal_by: t.marked_for_removal_by || null,
          marked_for_removal_by_name: t.marked_for_removal_by_name || null,
          triple_comments: t.triple_comments || [],
          suggestions: t.suggestions || [],
        })),
      })),
    };
  }, [sentences, initialSessionId, source_filename, uploaded_at, manual_mode]);

  useEffect(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);

    idleTimerRef.current = setTimeout(async () => {
      if (!hasUnsavedChangesRef.current || savingRef.current) return;
      savingRef.current = true;
      setSaving(true);
      setSaveError("");
      try {
        const payload = latestPayloadRef.current;
        const result = await saveSession(payload);
        setSavedSessionId(result.session_id);
        setSavedAt(new Date());
        setSaveMsg("Changes auto-saved");
        setTimeout(() => setSaveMsg(""), 3000);
        hasUnsavedChangesRef.current = false;
      } catch (e) {
        setSaveError("Auto-save failed. Connection issues?");
      } finally {
        savingRef.current = false;
        setSaving(false);
      }
    }, 6000);

    return () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    };
  }, [sentences]);

  // Background polling & WebSocket real-time updates
  useEffect(() => {
    if (!initialSessionId) return;

    let isTabFocused = true;
    const handleFocus = () => { isTabFocused = true; };
    const handleBlur = () => { isTabFocused = false; };

    window.addEventListener("focus", handleFocus);
    window.addEventListener("blur", handleBlur);

    const fetchUpdates = async () => {
      // Bypasses sync if tab is inactive, or user has unsaved changes, or save is currently in progress
      if (!isTabFocused || hasUnsavedChangesRef.current || savingRef.current) return;

      try {
        const response = await loadSession(initialSessionId);
        if (response && Array.isArray(response.sentences)) {
          setSentences((prev) =>
            prev.map((s) => {
              const match = response.sentences.find((ns) => ns.id === s.id);
              if (!match) return s;

              // Map updated values while preserving local editing flags
              return {
                ...s,
                sentence_comments: normalizeSentenceComments(match.sentence_comments),
                comment_count: match.comment_count,
                completeness_by_user: match.completeness_by_user,
                external_relation_by_user: match.external_relation_by_user,
                completeness_count: match.completeness_count,
                completeness_average: match.completeness_average,
                external_relation_count: match.external_relation_count,
                external_relation_average: match.external_relation_average,
                triples: (match.triples || []).map((t) => {
                  const localT = s.triples.find((lt) => lt.id === t.id);
                  const normalizedT = {
                    ...t,
                    triple_comments: normalizeSentenceComments(t.triple_comments),
                  };
                  return localT
                    ? {
                        ...normalizedT,
                        is_editing: localT.is_editing,
                        suggestions: (t.suggestions || []).map((sug) => {
                          const localSug = (localT.suggestions || []).find((ls) => ls.id === sug.id);
                          return localSug ? { ...sug, is_editing: localSug.is_editing } : sug;
                        }),
                      }
                    : normalizedT;
                }),
              };
            })
          );
        }
      } catch (err) {
        console.warn("[GradingForm] Collaborative background sync failed:", err);
      }
    };

    // WebSocket real-time connection
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/ws/${initialSessionId}`;
    let socket;
    let reconnectTimeout;

    const connectWS = () => {
      socket = new WebSocket(wsUrl);
      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "session_updated") {
            fetchUpdates();
          }
        } catch (e) {
          console.error("[GradingForm] WS parsing error:", e);
        }
      };
      socket.onclose = () => {
        reconnectTimeout = setTimeout(connectWS, 3000);
      };
      socket.onerror = () => {
        socket.close();
      };
    };

    connectWS();

    const pollInterval = setInterval(fetchUpdates, 15000);

    return () => {
      clearInterval(pollInterval);
      if (socket) socket.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      window.removeEventListener("focus", handleFocus);
      window.removeEventListener("blur", handleBlur);
    };
  }, [initialSessionId]);

  const markChanged = () => {
    hasUnsavedChangesRef.current = true;
  };

  const handleSave = async () => {
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setSaveError("");
    setSaveMsg("");
    try {
      const payload = latestPayloadRef.current;
      const result = await saveSession(payload);
      setSavedSessionId(result.session_id);
      setSavedAt(new Date());
      setSaveMsg("Session saved successfully!");
      setTimeout(() => setSaveMsg(""), 3500);
      hasUnsavedChangesRef.current = false;
    } catch (e) {
      setSaveError(
        e?.response?.data?.detail || "Save failed. Is the backend running?"
      );
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  const DL_FORMATS = [
    { value: "pdf",   label: "PDF Cover & Report",   icon: "📄" },
    { value: "word",  label: "Word Document",  icon: "📝" },
    { value: "excel", label: "Excel Spreadsheet", icon: "📊" },
    { value: "csv",   label: "CSV Sheet",   icon: "⊞" },
    { value: "json",  label: "JSON Output",  icon: "{}" },
  ];

  const handleDownload = async (fmt) => {
    const target = fmt || dlFmt;
    setDlOpen(false);
    setDlError("");
    if (!savedSessionId) {
      setDlError("Please save the session first.");
      return;
    }

    if (!isOwner && gradingProgress.pct < 100) {
      setPendingDownloadFormat(target);
      setShowDownloadWarningModal(true);
      return;
    }

    await executeDownload(target);
  };

  const executeDownload = async (target) => {
    setDownloading(true);
    try {
      await downloadSession(savedSessionId, target);
    } catch (e) {
      setDlError(e?.message || "Download failed.");
    } finally {
      setDownloading(false);
    }
  };

  const handleNotificationClick = async (notif) => {
    setNotificationsOpen(false);
    setCurrentIdx(notif.sentenceIdx);

    setTimeout(() => {
      const elementId = notif.tripleId ? `triple-card-${notif.tripleId}` : `sentence-card-comments`;
      const el = document.getElementById(elementId);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        setHighlightedElementId(elementId);
        setTimeout(() => setHighlightedElementId(null), 3000);
      }
    }, 300);

    try {
      if (notif.type === "grading_completed") {
        const readCompletions = JSON.parse(localStorage.getItem(`read_completions_${initialSessionId}`) || "[]");
        if (!readCompletions.includes(notif.graderId)) {
          readCompletions.push(notif.graderId);
          localStorage.setItem(`read_completions_${initialSessionId}`, JSON.stringify(readCompletions));
          setSentences((prev) => [...prev]); // Trigger re-evaluation of useMemo list
        }
        return;
      }
      if (notif.type === "deletion_request") {
        const readDeletions = JSON.parse(localStorage.getItem(`read_deletions_${initialSessionId}`) || "[]");
        if (!readDeletions.includes(notif.tripleId)) {
          readDeletions.push(notif.tripleId);
          localStorage.setItem(`read_deletions_${initialSessionId}`, JSON.stringify(readDeletions));
          setSentences((prev) => [...prev]); // Trigger re-evaluation of useMemo list
        }
        return;
      }

      const token = getAuthToken();
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const payload = latestPayloadRef.current;

      const nextSentences = payload.sentences.map((s) => {
        if (s.id !== notif.sentenceId) return s;

        const nextComments = (s.sentence_comments || []).map((c) => {
          if (notif.type === "sentence_comment" && c.id === notif.id) {
            if (!(c.read_by || []).includes(currentUserId)) {
              return { ...c, read_by: [...(c.read_by || []), currentUserId] };
            }
          }
          if (c.id === notif.commentId) {
            const nextReplies = (c.replies || []).map((r) => {
              if (r.id === notif.id && !(r.read_by || []).includes(currentUserId)) {
                return { ...r, read_by: [...(r.read_by || []), currentUserId] };
              }
              return r;
            });
            return { ...c, replies: nextReplies };
          }
          return c;
        });

        const nextTriples = (s.triples || []).map((t) => {
          if (t.id === notif.tripleId) {
            const nextComments = (t.triple_comments || []).map((c) => {
              if (notif.type === "triple_comment" && c.id === notif.id) {
                if (!(c.read_by || []).includes(currentUserId)) {
                  return { ...c, read_by: [...(c.read_by || []), currentUserId] };
                }
              }
              if (c.id === notif.commentId) {
                const nextReplies = (c.replies || []).map((r) => {
                  if (r.id === notif.id && !(r.read_by || []).includes(currentUserId)) {
                    return { ...r, read_by: [...(r.read_by || []), currentUserId] };
                  }
                  return r;
                });
                return { ...c, replies: nextReplies };
              }
              return c;
            });

            const nextSuggestions = (t.suggestions || []).map((sug) => {
              if (notif.type === "triple_suggestion" && sug.id === notif.id) {
                if (!(sug.read_by || []).includes(currentUserId)) {
                  return { ...sug, read_by: [...(sug.read_by || []), currentUserId] };
                }
              }
              if (sug.id === notif.suggestionId) {
                const nextReplies = (sug.replies || []).map((r) => {
                  if (r.id === notif.id && !(r.read_by || []).includes(currentUserId)) {
                    return { ...r, read_by: [...(r.read_by || []), currentUserId] };
                  }
                  return r;
                });
                return { ...sug, replies: nextReplies };
              }
              return sug;
            });

            return { ...t, triple_comments: nextComments, suggestions: nextSuggestions };
          }
          return t;
        });

        return { ...s, sentence_comments: nextComments, triples: nextTriples };
      });

      setSentences((prev) =>
        prev.map((s) => {
          const match = nextSentences.find((ns) => ns.id === s.id);
          return match ? { ...s, sentence_comments: match.sentence_comments, triples: match.triples } : s;
        })
      );

      const nextPayload = { ...payload, sentences: nextSentences };
      await saveSession(nextPayload);
    } catch (err) {}
  };

  const handleMarkAllNotificationsRead = async () => {
    setNotificationsOpen(false);
    if (notifications.length === 0) return;

    if (isOwner) {
      const allCompletionIds = notifications
        .filter((n) => n.type === "grading_completed")
        .map((n) => n.graderId);
      if (allCompletionIds.length > 0) {
        const readCompletions = JSON.parse(localStorage.getItem(`read_completions_${initialSessionId}`) || "[]");
        const nextCompletions = Array.from(new Set([...readCompletions, ...allCompletionIds]));
        localStorage.setItem(`read_completions_${initialSessionId}`, JSON.stringify(nextCompletions));
      }

      const allDeletionIds = notifications
        .filter((n) => n.type === "deletion_request")
        .map((n) => n.tripleId);
      if (allDeletionIds.length > 0) {
        const readDeletions = JSON.parse(localStorage.getItem(`read_deletions_${initialSessionId}`) || "[]");
        const nextDeletions = Array.from(new Set([...readDeletions, ...allDeletionIds]));
        localStorage.setItem(`read_deletions_${initialSessionId}`, JSON.stringify(nextDeletions));
      }
    }

    try {
      const payload = latestPayloadRef.current;
      const nextSentences = payload.sentences.map((s) => {
        const nextComments = (s.sentence_comments || []).map((c) => {
          let updatedC = c;
          const isOwn = c.user_id === currentUserId;
          const isRead = (c.read_by || []).includes(currentUserId);
          if (!isOwn && !isRead) {
            updatedC = { ...c, read_by: [...(c.read_by || []), currentUserId] };
          }
          const nextReplies = (updatedC.replies || []).map((r) => {
            if (!(r.read_by || []).includes(currentUserId)) {
              return { ...r, read_by: [...(r.read_by || []), currentUserId] };
            }
            return r;
          });
          return { ...updatedC, replies: nextReplies };
        });

        const nextTriples = (s.triples || []).map((t) => {
          const nextComments = (t.triple_comments || []).map((c) => {
            let updatedC = c;
            const isOwn = c.user_id === currentUserId;
            const isRead = (c.read_by || []).includes(currentUserId);
            if (!isOwn && !isRead) {
              updatedC = { ...c, read_by: [...(c.read_by || []), currentUserId] };
            }
            const nextReplies = (updatedC.replies || []).map((r) => {
              if (!(r.read_by || []).includes(currentUserId)) {
                return { ...r, read_by: [...(r.read_by || []), currentUserId] };
              }
              return r;
            });
            return { ...updatedC, replies: nextReplies };
          });

          const nextSuggestions = (t.suggestions || []).map((sug) => {
            let updatedSug = sug;
            const isOwn = sug.user_id === currentUserId;
            const isRead = (sug.read_by || []).includes(currentUserId);
            if (!isOwn && !isRead) {
              updatedSug = { ...sug, read_by: [...(sug.read_by || []), currentUserId] };
            }
            const nextReplies = (updatedSug.replies || []).map((r) => {
              if (!(r.read_by || []).includes(currentUserId)) {
                return { ...r, read_by: [...(r.read_by || []), currentUserId] };
              }
              return r;
            });
            return { ...updatedSug, replies: nextReplies };
          });

          return { ...t, triple_comments: nextComments, suggestions: nextSuggestions };
        });

        return { ...s, sentence_comments: nextComments, triples: nextTriples };
      });

      setSentences((prev) =>
        prev.map((s) => {
          const match = nextSentences.find((ns) => ns.id === s.id);
          return match ? { ...s, sentence_comments: match.sentence_comments, triples: match.triples } : s;
        })
      );

      const nextPayload = { ...payload, sentences: nextSentences };
      await saveSession(nextPayload);
    } catch (err) {}
  };

  const handleSentenceCompletenessChange = (val) => {
    if (!canEditSession) return;
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const entry = {
          user_id: currentUserId,
          user_name: currentUserName,
          value: val,
        };
        const updatedCompletenessByUser = {
          ...(s.completeness_by_user || {}),
          [currentUserId]: entry,
        };
        const completenessValues = Object.values(updatedCompletenessByUser)
          .map((e) => normalizeMetricValue(e?.value))
          .filter((v) => v !== null);

        return {
          ...s,
          completeness_by_user: updatedCompletenessByUser,
          completeness: val,
          completeness_count: completenessValues.length,
          completeness_average:
            completenessValues.length > 0
              ? Number((completenessValues.reduce((a, b) => a + b, 0) / completenessValues.length).toFixed(2))
              : null,
        };
      })
    );

    // Auto-focus the first button in External Relation row
    setTimeout(() => {
      const externalRelationBtn = document.querySelector("#sentence-external-relation-buttons-row button:not([disabled])");
      if (externalRelationBtn) {
        externalRelationBtn.focus();
      }
    }, 100);
  };

  const handleSentenceExternalRelationChange = (val) => {
    if (!canEditSession) return;
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const entry = {
          user_id: currentUserId,
          user_name: currentUserName,
          value: val,
        };
        const updatedExternalRelationByUser = {
          ...(s.external_relation_by_user || {}),
          [currentUserId]: entry,
        };
        const externalRelationValues = Object.values(updatedExternalRelationByUser)
          .map((e) => normalizeMetricValue(e?.value))
          .filter((v) => v !== null);

        return {
          ...s,
          external_relation_by_user: updatedExternalRelationByUser,
          external_relation: val,
          external_relation_count: externalRelationValues.length,
          external_relation_average:
            externalRelationValues.length > 0
              ? Number((externalRelationValues.reduce((a, b) => a + b, 0) / externalRelationValues.length).toFixed(2))
              : null,
        };
      })
    );
  };

  // Instant Save helper for real-time notifications/comments
  const saveStateInstantly = async (updatedSentences) => {
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setSaveError("");
    setSaveMsg("");
    try {
      const payload = {
        session_id: initialSessionId,
        source_filename,
        uploaded_at,
        manual_mode: !!manual_mode,
        total_sentences: updatedSentences.length,
        sentences: updatedSentences.map((s) => ({
          id: s.id,
          text: s.text,
          is_calibration: !!s.is_calibration,
          completeness: s.completeness,
          external_relation: s.external_relation,
          completeness_by_user: s.completeness_by_user,
          external_relation_by_user: s.external_relation_by_user,
          sentence_comments: s.sentence_comments,
          triples: s.triples.map((t) => ({
            id: t.id,
            subject: t.subject,
            predicate: t.predicate,
            object: t.object,
            grade: t.grade,
            author: t.author,
            grades_by_user: t.grades_by_user,
            is_new_suggestion: !!t.is_new_suggestion,
            status: t.status || null,
            suggested_by: t.suggested_by || null,
            marked_for_removal: !!t.marked_for_removal,
            removal_reason: t.removal_reason || "",
            marked_for_removal_by: t.marked_for_removal_by || null,
            marked_for_removal_by_name: t.marked_for_removal_by_name || null,
            triple_comments: t.triple_comments || [],
            suggestions: t.suggestions || [],
          })),
        })),
      };
      
      const result = await saveSession(payload);
      setSavedSessionId(result.session_id);
      setSavedAt(new Date());
      setSaveMsg("Changes synced instantly");
      setTimeout(() => setSaveMsg(""), 3000);
      hasUnsavedChangesRef.current = false;
    } catch (e) {
      setSaveError(
        e?.response?.data?.detail || "Save failed. Is the backend running?"
      );
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  // Comments / Replies / Suggestions Actions
  const handleSentenceCommentAdd = (newComment) => {
    markChanged();
    const nextSentences = sentences.map((s, idx) => {
      if (idx !== currentIdx) return s;
      const nextComments = [...(s.sentence_comments || []), newComment];
      return {
        ...s,
        sentence_comments: nextComments,
        comment_count: nextComments.length,
      };
    });
    setSentences(nextSentences);
    saveStateInstantly(nextSentences);
  };

  const handleDeleteSentenceComment = (commentId) => {
    markChanged();
    const nextSentences = sentences.map((s, idx) => {
      if (idx !== currentIdx) return s;
      const nextComments = (s.sentence_comments || []).filter((c) => c.id !== commentId);
      return {
        ...s,
        sentence_comments: nextComments,
        comment_count: nextComments.length,
      };
    });
    setSentences(nextSentences);
    saveStateInstantly(nextSentences);
  };

  const handleAddSentenceCommentReply = (commentId, replyText, parentReplyId = null) => {
    markChanged();
    const newReply = {
      id: `rpl-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      author: currentUserName,
      user_id: currentUserId,
      text: replyText,
      created_at: new Date().toISOString(),
      parent_reply_id: parentReplyId,
      read_by: currentUserId ? [currentUserId] : [],
    };
    const nextSentences = sentences.map((s, idx) => {
      if (idx !== currentIdx) return s;
      const nextComments = (s.sentence_comments || []).map((c) => {
        if (c.id !== commentId) return c;
        return { ...c, replies: [...(c.replies || []), newReply] };
      });
      return { ...s, sentence_comments: nextComments };
    });
    setSentences(nextSentences);
    saveStateInstantly(nextSentences);
  };

  const handleDeleteSentenceCommentReply = (commentId, replyId) => {
    markChanged();
    const nextSentences = sentences.map((s, idx) => {
      if (idx !== currentIdx) return s;
      const nextComments = (s.sentence_comments || []).map((c) => {
        if (c.id !== commentId) return c;
        return { ...c, replies: filterRepliesRecursive(c.replies || [], replyId) };
      });
      return { ...s, sentence_comments: nextComments };
    });
    setSentences(nextSentences);
    saveStateInstantly(nextSentences);
  };

  const onTripleGradeChange = (tripleId, val) => {
    if (!canEditSession) return;
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;

          const updatedGradesByUser = {
            ...(t.grades_by_user || {}),
            [currentUserId]: {
              user_id: currentUserId,
              user_name: currentUserName,
              grade: val,
            },
          };

          const gradeValues = Object.values(updatedGradesByUser)
            .map((g) => normalizeMetricValue(g?.grade))
            .filter((v) => v !== null);

          return {
            ...t,
            grade: val,
            grades_by_user: updatedGradesByUser,
            grade_count: gradeValues.length,
            grade_average:
              gradeValues.length > 0
                ? Number((gradeValues.reduce((a, b) => a + b, 0) / gradeValues.length).toFixed(2))
                : null,
          };
        });
        return { ...s, triples: updatedTriples };
      })
    );

    // Auto-scroll to the next ungraded triple in the same sentence
    setTimeout(() => {
      if (val === null || val === undefined) return;
      if (!current) return;
      const activeTriples = (current.triples || []).filter((t) => {
        const isActive = (!t.is_new_suggestion && !t.marked_for_removal) || (t.is_new_suggestion && t.status === "approved");
        return isActive;
      });
      const currentIndexInActive = activeTriples.findIndex((t) => t.id === tripleId);
      if (currentIndexInActive !== -1) {
        // Look for the next ungraded triple after the current one
        let nextUngraded = activeTriples.slice(currentIndexInActive + 1).find((t) => {
          const userGrade = t.grades_by_user?.[currentUserId]?.grade;
          return userGrade === undefined || userGrade === null;
        });
        // If not found after, wrap around and check from the beginning
        if (!nextUngraded) {
          nextUngraded = activeTriples.slice(0, currentIndexInActive).find((t) => {
            const userGrade = t.grades_by_user?.[currentUserId]?.grade;
            return userGrade === undefined || userGrade === null;
          });
        }
        
        if (nextUngraded) {
          const nextElementId = `triple-card-${nextUngraded.id}`;
          const el = document.getElementById(nextElementId);
          if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "center" });
            setHighlightedElementId(nextElementId);
            setTimeout(() => setHighlightedElementId(null), 2050);
            setTimeout(() => {
              const btn = el.querySelector(".grade-button");
              if (btn) btn.focus();
            }, 300);
          }
        } else {
          // All active triples are graded! Focus sentence metrics.
          setShowSentenceMetrics(true);
          setTimeout(() => {
            const el = document.getElementById("sentence-metrics-container");
            if (el) {
              el.scrollIntoView({ behavior: "smooth", block: "center" });
              setHighlightedElementId("sentence-metrics-container");
              setTimeout(() => setHighlightedElementId(null), 2050);
              
              // Focus the first button in completeness row
              const completenessBtn = document.querySelector("#sentence-completeness-buttons-row button:not([disabled])");
              if (completenessBtn) {
                completenessBtn.focus();
              }
            }
          }, 200);
        }
      }
    }, 100);
  };

  const onMarkForRemoval = (tripleId, isMarked) => {
    // Owner can cancel requests, graders can request or cancel their own
    if (isMarked && !canSuggestTriples) return;
    if (!isMarked && !canSuggestTriples && !canApproveSuggestions) return;

    markChanged();
    const reason = isMarked ? "Requested removal" : "";
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;
          return {
            ...t,
            marked_for_removal: isMarked,
            removal_reason: reason,
            marked_for_removal_by: isMarked ? currentUserId : null,
            marked_for_removal_by_name: isMarked ? currentUserName : null,
          };
        });
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const onApproveDeletion = (tripleId) => {
    if (!canApproveSuggestions) return;
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = (s.triples || []).filter((t) => t.id !== tripleId);
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const onAddTripleAdjacent = (tripleId, position) => {
    if (!canSuggestTriples) return;
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const index = s.triples.findIndex((t) => t.id === tripleId);
        if (index === -1) return s;

        const newTripleId = `suggested-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
        const newTriple = {
          id: newTripleId,
          subject: "",
          predicate: "",
          object: "",
          grade: null,
          author: currentUserName,
          grades_by_user: {},
          is_new_suggestion: true,
          status: "pending",
          suggested_by: currentUserName,
          marked_for_removal: false,
          removal_reason: "",
          triple_comments: [],
          suggestions: [],
          is_editing: true,
        };

        const nextTriples = [...s.triples];
        if (position === "above") {
          nextTriples.splice(index, 0, newTriple);
        } else {
          nextTriples.splice(index + 1, 0, newTriple);
        }

        return { ...s, triples: nextTriples };
      })
    );
  };

  const onRemoveSuggestedTriple = (tripleId) => {
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        return { ...s, triples: s.triples.filter((t) => t.id !== tripleId) };
      })
    );
  };

  const onApproveSuggestedTriple = (tripleId) => {
    if (!canApproveSuggestions) return;
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;
          return { ...t, status: "approved" };
        });
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const onSaveSuggestedTriple = (tripleId, payload) => {
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;
          return {
            ...t,
            subject: payload.subject,
            predicate: payload.predicate,
            object: payload.object,
            is_editing: false,
          };
        });
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const onSetTripleEditing = (tripleId, isEditing) => {
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;
          return { ...t, is_editing: isEditing };
        });
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const onAddTripleComment = (tripleId, newComment) => {
    markChanged();
    const nextSentences = sentences.map((s, idx) => {
      if (idx !== currentIdx) return s;
      const updatedTriples = s.triples.map((t) => {
        if (t.id !== tripleId) return t;
        return {
          ...t,
          triple_comments: [...(t.triple_comments || []), newComment],
        };
      });
      return { ...s, triples: updatedTriples };
    });
    setSentences(nextSentences);
    saveStateInstantly(nextSentences);
  };

  const onDeleteTripleComment = (tripleId, commentId) => {
    markChanged();
    const nextSentences = sentences.map((s, idx) => {
      if (idx !== currentIdx) return s;
      const updatedTriples = s.triples.map((t) => {
        if (t.id !== tripleId) return t;
        return {
          ...t,
          triple_comments: (t.triple_comments || []).filter((c) => c.id !== commentId),
        };
      });
      return { ...s, triples: updatedTriples };
    });
    setSentences(nextSentences);
    saveStateInstantly(nextSentences);
  };

  const onAddTripleReply = (tripleId, commentId, newReply) => {
    markChanged();
    const nextSentences = sentences.map((s, idx) => {
      if (idx !== currentIdx) return s;
      const updatedTriples = s.triples.map((t) => {
        if (t.id !== tripleId) return t;
        const nextComments = (t.triple_comments || []).map((c) => {
          if (c.id !== commentId) return c;
          return { ...c, replies: [...(c.replies || []), newReply] };
        });
        return { ...t, triple_comments: nextComments };
      });
      return { ...s, triples: updatedTriples };
    });
    setSentences(nextSentences);
    saveStateInstantly(nextSentences);
  };

  const onDeleteTripleReply = (tripleId, commentId, replyId) => {
    markChanged();
    const nextSentences = sentences.map((s, idx) => {
      if (idx !== currentIdx) return s;
      const updatedTriples = s.triples.map((t) => {
        if (t.id !== tripleId) return t;
        const nextComments = (t.triple_comments || []).map((c) => {
          if (c.id !== commentId) return c;
          return { ...c, replies: filterRepliesRecursive(c.replies || [], replyId) };
        });
        return { ...t, triple_comments: nextComments };
      });
      return { ...s, triples: updatedTriples };
    });
    setSentences(nextSentences);
    saveStateInstantly(nextSentences);
  };

  const onAddSuggestion = (tripleId, payload) => {
    if (!canSuggestTriples) return;
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;

          const newSuggestionId = `sug-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
          const newSuggestion = {
            id: newSuggestionId,
            author: currentUserName,
            user_id: currentUserId,
            subject: payload.subject,
            predicate: payload.predicate,
            object: payload.object,
            reason: payload.reason || "",
            status: "pending",
            votes: {},
            replies: [],
            created_at: new Date().toISOString(),
          };

          return {
            ...t,
            suggestions: [...(t.suggestions || []), newSuggestion],
          };
        });
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const onEditSuggestion = (tripleId, sugId, payload) => {
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;
          const nextSuggestions = (t.suggestions || []).map((sug) => {
            if (sug.id !== sugId) return sug;
            return {
              ...sug,
              subject: payload.subject,
              predicate: payload.predicate,
              object: payload.object,
              reason: payload.reason || "",
            };
          });
          return { ...t, suggestions: nextSuggestions };
        });
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const onVoteSuggestion = (tripleId, sugId, voteType) => {
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;
          const nextSuggestions = (t.suggestions || []).map((sug) => {
            if (sug.id !== sugId) return sug;
            const updatedVotes = {
              ...(sug.votes || {}),
              [displayUserNameVote(sug)]: voteType,
            };
            return { ...sug, votes: updatedVotes };
          });
          return { ...t, suggestions: nextSuggestions };
        });
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const displayUserNameVote = (sug) => {
    return currentUserName || currentUser?.name || "";
  };

  const onDeleteSuggestion = (tripleId, sugId) => {
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;
          return {
            ...t,
            suggestions: (t.suggestions || []).filter((sug) => sug.id !== sugId),
          };
        });
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const onApproveSuggestion = (tripleId, sugId, isCurrentlyApproved) => {
    if (!canApproveSuggestions) return;
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;
          const nextSuggestions = (t.suggestions || []).map((sug) => {
            if (sug.id !== sugId) return sug;
            return {
              ...sug,
              status: isCurrentlyApproved ? "pending" : "approved",
              approved_by: isCurrentlyApproved ? null : currentUserName,
            };
          });
          return { ...t, suggestions: nextSuggestions };
        });
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const onAddSuggestionReply = (tripleId, sugId, replyText, parentReplyId = null) => {
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;
          const nextSuggestions = (t.suggestions || []).map((sug) => {
            if (sug.id !== sugId) return sug;
            const newReply = {
              id: `rpl-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
              author: currentUserName,
              user_id: currentUserId,
              text: replyText,
              created_at: new Date().toISOString(),
              parent_reply_id: parentReplyId,
              read_by: currentUserId ? [currentUserId] : [],
            };
            return {
              ...sug,
              replies: [...(sug.replies || []), newReply],
            };
          });
          return { ...t, suggestions: nextSuggestions };
        });
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const onDeleteSuggestionReply = (tripleId, sugId, replyId) => {
    markChanged();
    setSentences((prev) =>
      prev.map((s, idx) => {
        if (idx !== currentIdx) return s;
        const updatedTriples = s.triples.map((t) => {
          if (t.id !== tripleId) return t;
          const nextSuggestions = (t.suggestions || []).map((sug) => {
            if (sug.id !== sugId) return sug;
            return {
              ...sug,
              replies: filterRepliesRecursive(sug.replies || [], replyId),
            };
          });
          return { ...t, suggestions: nextSuggestions };
        });
        return { ...s, triples: updatedTriples };
      })
    );
  };

  const previewHref = useMemo(() => {
    if (!savedSessionId) return undefined;
    const token = getAuthToken();
    if (!token) return `/api/preview/${savedSessionId}`;
    return `/api/preview/${savedSessionId}?token=${encodeURIComponent(token)}`;
  }, [savedSessionId]);

  const sentenceGrade = useMemo(() => {
    if (!current) return null;
    const activeTriples = (current.triples || []).filter(t => !t.is_new_suggestion || t.status === "approved");
    const grades = activeTriples
      .map((t) => t.grade)
      .filter((g) => g !== null && g !== undefined);
    if (grades.length === 0) return null;
    if (grades.length < activeTriples.length) return "partial";
    return (grades.reduce((a, b) => a + b, 0) / grades.length).toFixed(1);
  }, [current]);

  const gradeColor =
    sentenceGrade === null
      ? "text-slate-400 dark:text-slate-650"
      : sentenceGrade === "partial"
      ? "text-amber-600 dark:text-amber-450"
      : parseFloat(sentenceGrade) >= 7
      ? "text-indigo-650 dark:text-indigo-400"
      : parseFloat(sentenceGrade) >= 4
      ? "text-amber-600 dark:text-amber-450"
      : "text-rose-600 dark:text-rose-455";

  // Sidebar search and filters
  const filteredSentences = useMemo(() => {
    return sentences
      .map((s, originalIndex) => ({ ...s, originalIndex }))
      .filter((s) => {
        // Query filter
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchText = (s.text || "").toLowerCase().includes(q);
          const matchTriples = (s.triples || []).some(
            (t) =>
              (t.subject || "").toLowerCase().includes(q) ||
              (t.predicate || "").toLowerCase().includes(q) ||
              (t.object || "").toLowerCase().includes(q)
          );
          if (!matchText && !matchTriples) return false;
        }

        // Status filter
        const activeTriples = (s.triples || []).filter(t => !t.is_new_suggestion || t.status === "approved");
        const gradedCount = isOwner
          ? activeTriples.filter((t) => t.grade_average !== null && t.grade_average !== undefined).length
          : activeTriples.filter((t) => t.grade !== null && t.grade !== undefined).length;
        const allGraded = activeTriples.length > 0 && gradedCount === activeTriples.length;

        if (sidebarFilter === "completed") {
          return allGraded;
        }
        if (sidebarFilter === "pending") {
          return !allGraded;
        }

        return true;
      });
  }, [sentences, searchQuery, sidebarFilter]);

  if (sentences.length === 0) {
    return (
      <div className="min-h-screen bg-slate-100 dark:bg-slate-950/40 flex flex-col items-center justify-center p-8">
        <div className="max-w-md w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm text-center space-y-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mx-auto">
            <AlertCircle size={24} />
          </div>
          <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">No sentences found</h2>
          <p className="text-xs text-slate-500 dark:text-slate-450">
            This session does not contain any sentences to grade.
          </p>
          <button
            onClick={onReset}
            className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden bg-slate-100 dark:bg-slate-950/40 flex flex-col transition-colors duration-300">
      <header className="bg-white/85 dark:bg-slate-900/85 backdrop-blur border-b border-slate-200 dark:border-slate-800 shadow-sm fixed top-0 left-0 right-0 z-30 h-[60px] flex items-center px-4 justify-between gap-3 select-none">
        
        {/* Title, version & collapse sidebar trigger + Dashboard Link */}
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 cursor-pointer hidden md:flex"
            title={sidebarOpen ? "Hide Sentences List" : "Show Sentences List"}
          >
            <Menu size={16} />
          </button>

          <div className="flex items-center gap-1.5 min-w-0 mr-1.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-600 to-indigo-500 text-white flex items-center justify-center font-bold text-base shrink-0 shadow-sm">
              <Shield size={16} />
            </div>
            <div className="min-w-0">
              <div className="text-xs sm:text-sm font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5 leading-tight">
                <span className="truncate">Ontology Grader</span>
                <span className="bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-900/50 text-[9px] px-1.5 py-0.5 rounded-lg font-bold tracking-wider uppercase shrink-0">v2.0</span>
              </div>
              <p className="text-[10px] text-slate-400 dark:text-slate-500 truncate max-w-[120px] sm:max-w-[150px]">{source_filename}</p>
            </div>
          </div>

          {/* Dashboard Back Link */}
          <button
            onClick={() => setShowExitPromptModal(true)}
            className="inline-flex items-center gap-1 text-xs font-bold text-slate-500 dark:text-slate-400 hover:text-indigo-650 dark:hover:text-indigo-400 border border-slate-200 dark:border-slate-800 rounded-xl px-2.5 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-850 cursor-pointer transition-all shrink-0 shadow-sm"
          >
            <ArrowLeft size={13} />
            <span>Dashboard</span>
          </button>
        </div>

        {/* Global Progress Bar (visible on md screens up) */}
        {!isOwner && (
          <div className="hidden lg:flex items-center gap-2.5 shrink-0 bg-slate-50 dark:bg-slate-950 border border-slate-200/60 dark:border-slate-850 px-3 py-1.5 rounded-xl">
            <div className="flex flex-col text-right">
              <span className="text-[10px] font-bold text-slate-400 dark:text-slate-550 uppercase tracking-wider leading-none">Overall Progress</span>
              <span className="text-xs font-bold text-indigo-700 dark:text-indigo-400 mt-1">{gradingProgress.graded} / {gradingProgress.total} Triples</span>
            </div>
            <div className="w-20 bg-slate-200 dark:bg-slate-800 rounded-full h-2 overflow-hidden shadow-inner">
              <div className="bg-indigo-600 dark:bg-indigo-500 h-2 rounded-full transition-all duration-300" style={{ width: `${gradingProgress.pct}%` }} />
            </div>
            <span className="text-sm font-extrabold text-indigo-650 dark:text-indigo-400 tabular-nums">{gradingProgress.pct}%</span>
          </div>
        )}

        {/* Action Controls */}
        <div className="flex items-center gap-1.5 shrink-0">
          
          {/* 1. Save Action */}
          <div className="relative flex items-center">
            <button
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-700 disabled:opacity-55 text-white shadow-sm transition-all active:scale-95 cursor-pointer"
              title="Save worksheet"
            >
              <Save size={14} />
              <span className="hidden sm:inline">Save</span>
            </button>
            {saveMsg && (
              <span className="absolute right-0 top-full mt-2 bg-slate-800 text-white border border-slate-700 px-2 py-1 rounded-lg text-[10px] font-semibold shadow-lg whitespace-nowrap z-50">
                {saveMsg}
              </span>
            )}
            {saveError && (
              <span className="absolute right-0 top-full mt-2 bg-rose-50 dark:bg-rose-950/90 text-rose-805 dark:text-rose-350 border border-rose-250 dark:border-rose-900/40 px-2.5 py-1 rounded-lg text-[10px] font-semibold shadow-lg whitespace-nowrap z-50">
                {saveError}
              </span>
            )}
          </div>

          {/* 2. Download Split Dropdown Button */}
          <div className="relative shrink-0 flex" ref={dlRef}>
            <div className="flex rounded-xl overflow-hidden shadow-sm border border-emerald-600 dark:border-emerald-700 bg-emerald-600 dark:bg-emerald-700">
              <button
                onClick={() => handleDownload()}
                disabled={downloading || !savedSessionId}
                className="flex items-center gap-1 px-3.5 py-2 text-xs font-bold text-white hover:bg-emerald-700 dark:hover:bg-emerald-800 disabled:opacity-40 cursor-pointer transition-all active:scale-95"
              >
                {downloading ? "..." : (
                  <>
                    <Download size={14} />
                    <span className="hidden md:inline">Download</span>
                  </>
                )}
              </button>
              <button
                onClick={() => setDlOpen((o) => !o)}
                disabled={downloading}
                className="px-2 py-2 text-xs font-bold text-white hover:bg-emerald-700 dark:hover:bg-emerald-800 border-l border-emerald-500 dark:border-emerald-600 transition-all disabled:opacity-40 cursor-pointer"
                aria-label="Choose format"
              >
                {dlOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            </div>

            {dlOpen && (
              <div className="absolute right-0 top-full mt-2 glass-dropdown rounded-2xl shadow-xl py-1 min-w-44 z-50">
                {DL_FORMATS.map((f) => (
                  <button
                    key={f.value}
                    onClick={() => { setDlFmt(f.value); setDlOpen(false); handleDownload(f.value); }}
                    className={`w-full text-left flex items-center gap-2.5 px-4.5 py-2 text-xs font-semibold transition-colors cursor-pointer ${
                      f.value === dlFmt
                        ? "bg-indigo-50/70 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 font-bold"
                        : "text-slate-650 dark:text-slate-350 hover:bg-slate-50 dark:hover:bg-slate-850"
                    }`}
                  >
                    <span className="text-sm shrink-0">{f.icon}</span>
                    <span>{f.label}</span>
                    {f.value === dlFmt && <span className="ml-auto text-indigo-650 text-xs">✔</span>}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 3. View Report tab */}
          <a
            href={previewHref}
            target="_blank"
            rel="noopener noreferrer"
            onClick={!savedSessionId ? (e) => e.preventDefault() : undefined}
            className={`hidden lg:inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border transition-colors shadow-sm ${
              savedSessionId
                ? "border-slate-200 dark:border-slate-800 text-slate-650 dark:text-slate-300 bg-white dark:bg-slate-900 hover:border-indigo-400 hover:bg-indigo-50/30"
                : "border-slate-200 dark:border-slate-800 text-slate-300 dark:text-slate-650 bg-slate-50 dark:bg-slate-950 cursor-not-allowed"
            }`}
            title={savedSessionId ? "Preview report in a new tab" : "Save changes first"}
          >
            <Eye size={14} />
            <span>View</span>
          </a>

          {/* 4. Run Evaluate */}
          {onEvaluate && (
            <button
              onClick={() => onEvaluate(savedSessionId, source_filename)}
              disabled={!savedSessionId}
              className={`hidden lg:inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border transition-colors shadow-sm ${
                savedSessionId
                  ? "border-purple-200 dark:border-purple-900 bg-purple-50/40 dark:bg-purple-950/20 text-purple-700 dark:text-purple-400 hover:bg-purple-100/50"
                  : "border-slate-200 dark:border-slate-800 text-slate-400 dark:text-slate-500 bg-slate-50 dark:bg-slate-950 cursor-not-allowed"
              }`}
              title={savedSessionId ? "Run Stanza OpenIE evaluation match checks" : "Save changes first"}
            >
              <Activity size={14} />
              <span>Evaluate</span>
            </button>
          )}

          {/* 5. Paper Quality indicators */}
          <button
            onClick={() => setShowPaperMetricsModal(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border border-indigo-200 dark:border-indigo-900 bg-indigo-50/50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 hover:bg-indigo-100/60 dark:hover:bg-indigo-900/40 cursor-pointer active:scale-95 transition-all shadow-sm"
            title="View Paper Quality Metrics"
          >
            <BarChart3 size={14} />
            <span className="hidden md:inline">Indicators</span>
          </button>

          {/* 6. Notifications Trigger */}
          <div className="relative" ref={notificationsRef}>
            <button
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              className={`p-2 rounded-xl border bg-white/80 dark:bg-slate-900/80 text-slate-550 dark:text-slate-400 cursor-pointer shadow-sm active:scale-95 transition-all ${
                notifications.length > 0
                  ? "border-rose-250 dark:border-rose-900/60 bg-rose-50/20"
                  : "border-slate-200 dark:border-slate-800"
              }`}
              title="Grading Notifications"
            >
              <div className="relative">
                <Bell size={15} />
                {notifications.length > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 w-3.5 h-3.5 bg-rose-600 text-white rounded-full text-[8px] font-bold flex items-center justify-center shadow-sm">
                    {notifications.length}
                  </span>
                )}
              </div>
            </button>

            {/* Notifications panel overlay */}
            {notificationsOpen && (
              <div className="absolute right-0 top-full mt-2 w-80 glass-dropdown rounded-2xl shadow-xl py-1 z-50 flex flex-col max-h-[360px]">
                <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-800/80 flex justify-between items-center bg-slate-50/50 dark:bg-slate-950/20 shrink-0">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-450 dark:text-slate-500">
                    Notifications ({notifications.length})
                  </span>
                  {notifications.length > 0 && (
                    <button
                      onClick={handleMarkAllNotificationsRead}
                      className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer border-0 bg-transparent"
                    >
                      Mark all read
                    </button>
                  )}
                </div>

                <div className="flex-1 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-850">
                  {notifications.length === 0 ? (
                    <div className="px-4 py-8 text-center text-xs text-slate-400 dark:text-slate-500">
                      <div className="text-xl mb-1">✨</div>
                      You are all caught up!
                    </div>
                  ) : (
                    notifications.map((notif) => (
                      <div
                        key={notif.id}
                        onClick={() => handleNotificationClick(notif)}
                        className="px-4 py-3 hover:bg-slate-55 dark:hover:bg-slate-900/40 transition-colors cursor-pointer text-left space-y-1"
                      >
                        <div className="flex justify-between items-start gap-1">
                          <span className="text-xs font-bold text-slate-700 dark:text-slate-350 leading-snug">{notif.title}</span>
                          <span className="text-[9px] text-slate-400 dark:text-slate-500 whitespace-nowrap mt-0.5 font-mono">
                            {formatCommentTimestamp(notif.createdAt)}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed break-words">{notif.text}</p>
                        <div className="text-[9px] font-bold text-indigo-650 dark:text-indigo-400 flex items-center gap-1.5">
                          <span>Sentence #{notif.sentenceId}</span>
                          {notif.tripleId && (
                            <>
                              <span>&bull;</span>
                              <span>Triple</span>
                            </>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 7. Theme Mode Toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 cursor-pointer shadow-sm active:scale-95 transition-all"
            title="Toggle Light/Dark Theme"
          >
            {isDark ? <Sun size={15} /> : <Moon size={15} />}
          </button>

          {/* Small screens actions overflow toggle */}
          <div className="relative shrink-0 lg:hidden" ref={moreRef}>
            <button
              onClick={() => setMoreOpen(!moreOpen)}
              className="flex items-center justify-center p-2 rounded-xl border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-350 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer shadow-sm text-xs font-bold"
            >
              <Menu size={15} />
            </button>
            {moreOpen && (
              <div className="absolute right-0 top-full mt-2 glass-dropdown rounded-2xl shadow-xl py-1 min-w-44 z-50">
                <a
                  href={previewHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={!savedSessionId ? (e) => e.preventDefault() : undefined}
                  className={`w-full text-left flex items-center gap-2.5 px-4.5 py-2 text-xs font-semibold transition-colors ${
                    savedSessionId
                      ? "text-slate-700 dark:text-slate-300 hover:bg-slate-55 dark:hover:bg-slate-850"
                      : "text-slate-300 dark:text-slate-600 cursor-not-allowed"
                  }`}
                >
                  <Eye size={13} /> View Online
                </a>
                {onEvaluate && (
                  <button
                    onClick={() => {
                      onEvaluate(savedSessionId, source_filename);
                      setMoreOpen(false);
                    }}
                    disabled={!savedSessionId}
                    className={`w-full text-left flex items-center gap-2.5 px-4.5 py-2 text-xs font-semibold transition-colors cursor-pointer ${
                      savedSessionId
                        ? "text-purple-750 dark:text-purple-400 hover:bg-purple-50/50 dark:hover:bg-slate-850"
                        : "text-slate-355 dark:text-slate-650 cursor-not-allowed"
                    }`}
                  >
                    <Activity size={13} /> Evaluate Stanza
                  </button>
                )}
                <button
                  onClick={() => {
                    onReset();
                    setMoreOpen(false);
                  }}
                  className="w-full text-left flex items-center gap-2.5 px-4.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-850 transition-colors cursor-pointer"
                >
                  <ArrowLeft size={13} /> Back to Dashboard
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ── SPLIT TWO-COLUMN WORKSPACE AREA ────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden pt-[60px] h-[calc(100vh-60px)]">
        
        {/* LEFT COLLAPSIBLE SIDEBAR */}
        <AnimatePresence initial={false}>
          {sidebarOpen && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 320, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: "easeInOut" }}
              className="border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 w-[320px] shrink-0 flex flex-col overflow-hidden h-full z-10"
            >
              {/* Sidebar Header & Filters */}
              <div className="p-4 border-b border-slate-100 dark:border-slate-800/80 space-y-3 shrink-0">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-bold text-slate-400 dark:text-slate-555 uppercase tracking-wider flex items-center gap-1.5">
                    <BookOpen size={14} />
                    <span>Sentences List</span>
                  </h2>
                  <div className="flex items-center gap-1.5">
                    <span className="bg-slate-100 dark:bg-slate-950 text-slate-500 dark:text-slate-400 text-[10px] font-bold px-2 py-0.5 rounded-lg border border-slate-200 dark:border-slate-850">
                      {filteredSentences.length} of {total}
                    </span>
                    <button
                      onClick={() => setSidebarOpen(false)}
                      className="p-1 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 cursor-pointer transition-colors shadow-sm"
                      title="Hide Sentences List"
                    >
                      <ChevronLeft size={13} />
                    </button>
                  </div>
                </div>

                {/* Search Field */}
                <div className="relative flex items-center">
                  <Search size={13} className="absolute left-3 text-slate-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search sentences or triples..."
                    className="w-full text-xs pl-8.5 pr-3 py-2 border border-slate-200 dark:border-slate-800 rounded-xl bg-slate-50/50 dark:bg-slate-950 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all placeholder:text-slate-400"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery("")}
                      className="absolute right-2.5 p-1 rounded-lg text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800"
                    >
                      <X size={10} />
                    </button>
                  )}
                </div>

                {/* Sidebar Filter Selector */}
                {!isOwner && (
                  <div className="flex rounded-lg bg-slate-100 dark:bg-slate-950/80 border border-slate-200/50 dark:border-slate-850 p-0.5 text-[10px] font-bold">
                    {["all", "completed", "pending"].map((filterOpt) => (
                      <button
                        key={filterOpt}
                        onClick={() => setSidebarFilter(filterOpt)}
                        className={`flex-1 py-1.5 rounded-md transition-all cursor-pointer ${
                          sidebarFilter === filterOpt
                            ? "bg-white dark:bg-slate-800 text-slate-800 dark:text-white shadow-sm"
                            : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                        }`}
                      >
                        {filterOpt === "all" ? "All" : filterOpt === "completed" ? "Graded" : "Pending"}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Scrollable Sentence List */}
              <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
                {filteredSentences.map((s) => {
                  const isSelected = s.originalIndex === currentIdx;
                  
                  // Progress metrics calculations for item card
                  const activeT = (s.triples || []).filter(t => !t.is_new_suggestion || t.status === "approved");
                  const gradedT = activeT.filter((t) => t.grade !== null && t.grade !== undefined).length;
                  const allGraded = activeT.length > 0 && gradedT === activeT.length;
                  const noneGraded = gradedT === 0;

                  // Badges color code
                  const completenessBadge = allGraded
                    ? "bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600 dark:text-emerald-450 border border-emerald-150 dark:border-emerald-900/30"
                    : noneGraded
                    ? "bg-slate-50 dark:bg-slate-950 text-slate-400 dark:text-slate-500 border border-slate-200 dark:border-slate-850"
                    : "bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-450 border border-amber-150 dark:border-amber-900/30";

                  const badgeIcon = allGraded ? (
                    <CheckCircle2 size={10} className="shrink-0" />
                  ) : noneGraded ? (
                    <AlertCircle size={10} className="shrink-0" />
                  ) : (
                    <AlertTriangle size={10} className="shrink-0" />
                  );

                  return (
                    <button
                      key={s.id}
                      id={`sidebar-sentence-${s.originalIndex}`}
                      onClick={() => setCurrentIdx(s.originalIndex)}
                      className={`w-full text-left p-3 rounded-xl border transition-all cursor-pointer flex flex-col gap-1.5 ${
                        isSelected
                          ? "bg-indigo-50 dark:bg-indigo-950/40 border-indigo-405 dark:border-indigo-800 border-l-4 border-l-indigo-600 dark:border-l-indigo-500 shadow-sm font-medium"
                          : "bg-slate-50/40 dark:bg-slate-900/30 border-slate-200/60 dark:border-slate-800/60 hover:bg-slate-100/50 dark:hover:bg-slate-800/50 border-l-4 border-l-transparent"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[10px] font-bold text-slate-400 dark:text-slate-500">
                          Sentence #{s.id}
                        </span>
                        
                        <div className="flex items-center gap-1.5">
                          {s.comment_count > 0 && (
                            <span className="inline-flex items-center gap-0.5 text-[9px] font-bold text-indigo-650 dark:text-indigo-400">
                              <MessageSquare size={10} />
                              {s.comment_count}
                            </span>
                          )}
                          {!isOwner && (
                            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full inline-flex items-center gap-1 ${completenessBadge}`}>
                              {badgeIcon}
                              <span>{gradedT}/{activeT.length} Graded</span>
                            </span>
                          )}
                        </div>
                      </div>
                      <p className={`text-xs leading-relaxed line-clamp-2 ${
                        isSelected ? "text-slate-850 dark:text-slate-200 font-medium" : "text-slate-550 dark:text-slate-400"
                      }`}>
                        {s.text}
                      </p>
                    </button>
                  );
                })}

                {filteredSentences.length === 0 && (
                  <div className="text-center py-8 text-xs text-slate-400 dark:text-slate-600">
                    No matching sentences found.
                  </div>
                )}
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        {/* RIGHT MAIN PANEL */}
        <main className="flex-1 flex flex-col h-full bg-slate-100 dark:bg-slate-955/40 overflow-hidden relative">
          
          {/* Floating Expand Sidebar Handle (visible when sidebar is closed) */}
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="absolute left-0 top-[45%] z-20 w-5 h-12 bg-white/90 dark:bg-slate-900/90 backdrop-blur-sm border-y border-r border-slate-200 dark:border-slate-800 rounded-r-xl shadow-md text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 flex items-center justify-center cursor-pointer transition-all active:scale-95 hover:w-6"
              title="Expand Sentences List"
            >
              <ChevronRight size={13} />
            </button>
          )}
          
          {/* Active Sentence Workspace Card (Fixed Top Section) */}
          <div className="px-4 sm:px-6 pt-4 shrink-0 bg-slate-100 dark:bg-slate-950/40">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm rounded-2xl p-4 sm:p-5 space-y-3.5">
              <div className="flex items-center justify-between gap-3 flex-wrap border-b border-slate-100 dark:border-slate-800/80 pb-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="bg-indigo-600 text-white text-[10px] font-bold px-2.5 py-1 rounded-xl">
                    {currentIdx + 1} / {total}
                  </span>
                  <span className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                    Active Sentence
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowSentenceMetrics(!showSentenceMetrics)}
                    className="inline-flex items-center gap-1.5 text-[10px] font-bold text-slate-550 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 border border-slate-200 dark:border-slate-850 rounded-xl px-2.5 py-1 hover:bg-slate-50 dark:hover:bg-slate-850 cursor-pointer transition-all shrink-0 shadow-sm"
                    title="Toggle Sentence Completeness & Relation Metrics"
                  >
                    <BarChart3 size={11} />
                    <span>{showSentenceMetrics ? "Hide Metrics" : "Show Metrics"}</span>
                  </button>
                  {!isOwner && ungradedTriples.length > 0 && (
                    <button
                      onClick={handleJumpToUngraded}
                      className="bg-rose-100 hover:bg-rose-200 dark:bg-rose-950/45 dark:hover:bg-rose-900/50 text-rose-700 dark:text-rose-400 border border-rose-200 dark:border-rose-900/50 text-[10px] px-2.5 py-1 rounded-xl font-extrabold cursor-pointer transition-all active:scale-95 flex items-center gap-1 shrink-0"
                      title="Scroll to the first ungraded triple"
                    >
                      <AlertTriangle size={11} className="text-rose-600 dark:text-rose-400" />
                      <span>Jump to Ungraded ({ungradedTriples.length})</span>
                    </button>
                  )}
                </div>

                {/* Status & completeness summary badges */}
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1 mr-2 border-r border-slate-200 dark:border-slate-800 pr-2">
                    <button
                      type="button"
                      onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
                      disabled={currentIdx === 0}
                      className="p-1 rounded bg-slate-50 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 disabled:opacity-40 cursor-pointer text-slate-550 dark:text-slate-400"
                      title="Previous Sentence"
                    >
                      <ChevronLeft size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setCurrentIdx((i) => Math.min(total - 1, i + 1))}
                      disabled={currentIdx === total - 1}
                      className="p-1 rounded bg-slate-50 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 disabled:opacity-40 cursor-pointer text-slate-550 dark:text-slate-400"
                      title="Next Sentence"
                    >
                      <ChevronRight size={14} />
                    </button>
                  </div>

                  {current.completeness_average !== null && (
                    <span className="bg-indigo-50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 border border-indigo-150 dark:border-indigo-900/30 px-2 py-1 rounded-xl text-[10px] font-bold uppercase tracking-wider">
                      Completeness: {Number(current.completeness_average).toFixed(1)}/10
                    </span>
                  )}
                  {current.external_relation_average !== null && (
                    <span className="bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-450 border border-emerald-150 dark:border-emerald-900/30 px-2 py-1 rounded-xl text-[10px] font-bold uppercase tracking-wider">
                      Relation: {Number(current.external_relation_average).toFixed(1)}/10
                    </span>
                  )}

                  <div className={`text-right font-bold ${gradeColor}`}>
                    {sentenceGrade === null ? (
                      canEditSession ? (
                        <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 px-2 py-1 rounded-xl">
                          Ungraded
                        </span>
                      ) : null
                    ) : sentenceGrade === "partial" ? (
                      <span className="text-[10px] font-bold uppercase tracking-wider bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-900/50 px-2 py-1 rounded-xl text-amber-800 dark:text-amber-400">
                        Incomplete
                      </span>
                    ) : (
                      <span className="bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-900 px-2 py-1 rounded-xl text-[10px] font-bold uppercase tracking-wider text-indigo-700 dark:text-indigo-400">
                        Avg Grade: {sentenceGrade}/10
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Sentence Blockquote text */}
              <blockquote className="border-l-4 border-indigo-500 pl-4 bg-slate-50 dark:bg-slate-900/50 rounded-r-2xl border border-slate-200/50 dark:border-slate-800 p-3.5 font-semibold leading-relaxed text-sm sm:text-base text-slate-800 dark:text-slate-100">
                {current.text}
              </blockquote>

              {showSentenceMetrics && (
                <div
                  id="sentence-metrics-container"
                  className={`grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 pb-1 border-t border-slate-100 dark:border-slate-800/80 transition-all duration-300 ${
                    highlightedElementId === "sentence-metrics-container"
                      ? "ring-4 ring-rose-500/25 scale-[1.01]"
                      : ""
                  }`}
                >
                  
                  {/* Completeness Input */}
                  <div className="bg-indigo-50/25 dark:bg-indigo-950/15 border border-indigo-150 dark:border-indigo-900/30 rounded-2xl p-4.5 space-y-3.5">
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="text-xs font-bold text-slate-700 dark:text-slate-200 uppercase tracking-wide">
                          1. Sentence Completeness
                        </h3>
                        <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
                          How completely does the extracted triple set capture the original sentence semantics?
                        </p>
                      </div>
                      <span className="text-xs font-bold text-indigo-700 dark:text-indigo-400">
                        {current.completeness !== null ? `${current.completeness}/10` : "—"}
                      </span>
                    </div>

                    {/* Score rating row */}
                    {!isOwner && (
                      <div id="sentence-completeness-buttons-row" className="flex flex-wrap items-center gap-1">
                        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((scoreVal) => (
                          <button
                            key={scoreVal}
                            onClick={() => handleSentenceCompletenessChange(scoreVal)}
                            disabled={!canEditSession}
                            className={`w-6 h-6 rounded-full text-xs font-bold border transition-all cursor-pointer flex items-center justify-center ${
                              current.completeness === scoreVal
                                ? "bg-indigo-600 border-indigo-655 text-white scale-110 shadow-sm"
                                : "bg-white dark:bg-slate-950 text-slate-655 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-900/30"
                            } ${!canEditSession ? "opacity-60 cursor-not-allowed" : ""}`}
                          >
                            {scoreVal}
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Averages list */}
                    {completenessMetricEntries.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 border-t border-slate-100 dark:border-slate-800 pt-3">
                        {completenessMetricEntries.map((entry) => {
                          const isMe = currentUserId && entry.userId === currentUserId;
                          return (
                            <span
                              key={`c-${entry.userId}`}
                              className={`inline-flex items-center gap-1.5 text-[10px] font-semibold border px-2.5 py-1 rounded-full ${
                                isMe
                                  ? "bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-400 border-indigo-200 dark:border-indigo-900"
                                  : "bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700"
                              }`}
                            >
                              <span>{entry.userName}</span>
                              {isMe && <span className="text-[9px] opacity-75">(you)</span>}
                              <span className="opacity-40">&bull;</span>
                              <span className="font-bold">{entry.value}/10</span>
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* External Relation Input */}
                  <div className="bg-emerald-50/25 dark:bg-emerald-955/15 border border-emerald-150 dark:border-emerald-900/30 rounded-2xl p-4.5 space-y-3.5">
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="text-xs font-bold text-slate-700 dark:text-slate-200 uppercase tracking-wide">
                          2. External Relation mapping
                        </h3>
                        <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
                          Does the predicate match schema properties and domain guidelines accurately?
                        </p>
                      </div>
                      <span className="text-xs font-bold text-emerald-700 dark:text-emerald-400">
                        {current.external_relation !== null ? `${current.external_relation}/10` : "—"}
                      </span>
                    </div>

                    {/* Score rating row */}
                    {!isOwner && (
                      <div id="sentence-external-relation-buttons-row" className="flex flex-wrap items-center gap-1">
                        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((scoreVal) => (
                          <button
                            key={scoreVal}
                            onClick={() => handleSentenceExternalRelationChange(scoreVal)}
                            disabled={!canEditSession}
                            className={`w-6 h-6 rounded-full text-xs font-bold border transition-all cursor-pointer flex items-center justify-center ${
                              current.external_relation === scoreVal
                                ? "bg-emerald-600 border-emerald-650 text-white scale-110 shadow-sm"
                                : "bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-emerald-50 dark:hover:bg-emerald-950/30"
                            } ${!canEditSession ? "opacity-60 cursor-not-allowed" : ""}`}
                          >
                            {scoreVal}
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Averages list */}
                    {externalRelationMetricEntries.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 border-t border-slate-100 dark:border-slate-805 pt-3">
                        {externalRelationMetricEntries.map((entry) => {
                          const isMe = currentUserId && entry.userId === currentUserId;
                          return (
                            <span
                              key={`r-${entry.userId}`}
                              className={`inline-flex items-center gap-1.5 text-[10px] font-semibold border px-2.5 py-1 rounded-full ${
                                isMe
                                  ? "bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900"
                                  : "bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700"
                              }`}
                            >
                              <span>{entry.userName}</span>
                              {isMe && <span className="text-[9px] opacity-75">(you)</span>}
                              <span className="opacity-40">&bull;</span>
                              <span className="font-bold">{entry.value}/10</span>
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>

                </div>
              )}
            </div>
          </div>

          {/* Scrollable Container (Collaborators Activity, Triples Workspace, and Sentence Comments) */}
          <div ref={mainRef} className="flex-1 overflow-y-auto px-4 sm:px-6 py-4 space-y-6">
            
            {/* Graders Collaborators Banner Card */}
          {/* Graders Collaborators Banner Card */}
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-3">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="space-y-1">
                <h2 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                  <Users size={14} />
                  <span>Workspace Grading Activity</span>
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 leading-normal">
                  Graders can score, comment, and suggest. Owner reserves authorization to approve new triple suggestions.
                </p>
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400 font-bold bg-slate-50 dark:bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-850">
                <span className="text-slate-700 dark:text-slate-200">{graderSummary.totalUniqueGraders}</span> Active Graders
                <span className="mx-2 text-slate-200 dark:text-slate-800">|</span>
                Avg Score: <span className="text-indigo-600 dark:text-indigo-400">{graderSummary.overallAverage != null ? graderSummary.overallAverage.toFixed(2) : "—"}/10</span>
              </div>
            </div>

            {graderSummary.rows.length > 0 ? (
              <div className="flex flex-wrap gap-2 pt-1">
                {graderSummary.rows.map((row) => {
                  const isMe = row.user_id === currentUserId;
                  const letter = row.user_name.trim().charAt(0).toUpperCase() || "G";
                  return (
                    <span
                      key={row.user_id}
                      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${
                        isMe
                          ? "bg-indigo-50 border-indigo-200 text-indigo-700 dark:bg-indigo-950/40 dark:border-indigo-900/50 dark:text-indigo-300"
                          : "bg-slate-50 border-slate-200 text-slate-700 dark:bg-slate-950 dark:border-slate-850 dark:text-slate-350"
                      }`}
                    >
                      <span className="w-4.5 h-4.5 rounded-full bg-slate-200 dark:bg-slate-800 text-[9px] font-bold flex items-center justify-center text-slate-700 dark:text-slate-300 uppercase shrink-0">
                        {letter}
                      </span>
                      <span>{row.user_name}{isMe ? " (you)" : ""}</span>
                      <span className="text-slate-300 dark:text-slate-805">&bull;</span>
                      <span className="text-[10px] opacity-75">{row.graded_triples} Triples Graded</span>
                      <span className="text-slate-300 dark:text-slate-805">&bull;</span>
                      <span className="font-bold">{row.average_grade != null ? row.average_grade.toFixed(2) : "—"}/10</span>
                    </span>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-slate-400 dark:text-slate-500 italic">No grading entries recorded yet.</p>
            )}
          </div>

          {/* Triples List Card Panel */}
          <div className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <h2 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                <Award size={14} />
                <span>Triples Workspace ({current.triples.length})</span>
              </h2>
            </div>

            <div className="space-y-4">
              {current.triples.map((t, idx) => {
                const isHighlighted = highlightedElementId === `triple-card-${t.id}`;
                return (
                  <div
                    key={t.id}
                    id={`triple-card-${t.id}`}
                    className={`transition-all duration-300 ${
                      isHighlighted
                        ? "ring-4 ring-rose-500/25 scale-[1.01]"
                        : ""
                    }`}
                  >
                    <TripleCard
                      index={idx}
                      triple={t}
                      grade={
                        t.grades_by_user?.[currentUserId]?.grade !== undefined
                          ? t.grades_by_user[currentUserId].grade
                          : null
                      }
                      author={t.author || uploadData.owner_name}
                      gradesByUser={t.grades_by_user}
                      currentUserId={currentUserId}
                      readOnly={!canEditSession}
                      canSuggest={canSuggestTriples}
                      canApprove={canApproveSuggestions}
                      onChange={(nextVal) => onTripleGradeChange(t.id, nextVal)}
                      onMarkForRemoval={onMarkForRemoval}
                      onAddTripleAdjacent={onAddTripleAdjacent}
                      onRemoveSuggestedTriple={onRemoveSuggestedTriple}
                      onApproveSuggestedTriple={onApproveSuggestedTriple}
                      onSaveSuggestedTriple={onSaveSuggestedTriple}
                      onSetTripleEditing={onSetTripleEditing}
                      onApproveDeletion={onApproveDeletion}
                    />

                    {/* Suggestions Drawer section */}
                    <TripleSuggestions
                      triple={t}
                      canSuggest={canSuggestTriples}
                      canApprove={canApproveSuggestions}
                      currentUserName={currentUserName}
                      currentUser={currentUser}
                      onAddSuggestion={(payload) => onAddSuggestion(t.id, payload)}
                      onEditSuggestion={(sugId, payload) => onEditSuggestion(t.id, sugId, payload)}
                      onVoteSuggestion={(sugId, voteType) => onVoteSuggestion(t.id, sugId, voteType)}
                      onDeleteSuggestion={(sugId) => onDeleteSuggestion(t.id, sugId)}
                      onApproveSuggestion={(sugId, isApproved) => onApproveSuggestion(t.id, sugId, isApproved)}
                      onAddSuggestionReply={(sugId, text, parentReplyId) => onAddSuggestionReply(t.id, sugId, text, parentReplyId)}
                      onDeleteSuggestionReply={(sugId, replyId) => onDeleteSuggestionReply(t.id, sugId, replyId)}
                    />

                    {/* Comments section */}
                    <TripleComments
                      tripleId={t.id}
                      comments={t.triple_comments}
                      currentUserId={currentUserId}
                      currentUserName={currentUserName}
                      readOnly={!canSuggestTriples}
                      onAddComment={(payload) => onAddTripleComment(t.id, payload)}
                      onDeleteComment={(commentId) => onDeleteTripleComment(t.id, commentId)}
                      onAddReply={(commentId, payload) => onAddTripleReply(t.id, commentId, payload)}
                      onDeleteReply={(commentId, replyId) => onDeleteTripleReply(t.id, commentId, replyId)}
                    />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Sentence Comments Box section */}
          <div
            id="sentence-card-comments"
            className={`bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-5 shadow-sm space-y-4 transition-all duration-300 ${
              highlightedElementId === "sentence-card-comments"
                ? "ring-4 ring-rose-500/25 scale-[1.01]"
                : ""
            }`}
          >
            <div className="border-b border-slate-100 dark:border-slate-800/80 pb-3 flex items-center gap-2 select-none">
              <MessageSquare size={16} className="text-slate-450 dark:text-slate-500" />
              <h2 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                Sentence Discussion / Method Decisions
              </h2>
            </div>

            {currentSentenceComments.length > 0 ? (
              <div className="space-y-4">
                {currentSentenceComments.map((comment) => (
                  <div
                    key={comment.id}
                    className="p-4 rounded-2xl bg-slate-50/50 dark:bg-slate-950/20 border border-slate-200/60 dark:border-slate-850 text-xs space-y-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap text-[10px] text-slate-400 dark:text-slate-500 font-bold select-none">
                          <span className="text-slate-700 dark:text-slate-300">{comment.author}</span>
                          <span>&bull;</span>
                          <span>{formatCommentTimestamp(comment.created_at)}</span>
                        </div>
                        <p className="text-slate-650 dark:text-slate-350 mt-1 break-words leading-relaxed text-[11px] sm:text-xs">
                          {comment.text}
                        </p>
                      </div>
                      {canEditSession && comment.user_id === currentUserId && (
                        <button
                          type="button"
                          onClick={async () => {
                            if (await showConfirm("Remove this comment?", "Remove Comment", "Remove", "Cancel")) {
                              handleDeleteSentenceComment(comment.id);
                            }
                          }}
                          className="p-1 rounded text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                          title="Delete comment"
                        >
                          <X size={12} />
                        </button>
                      )}
                    </div>

                    {/* Sentence comments replies list */}
                    {comment.replies && comment.replies.length > 0 && (
                      <div className="pl-4 border-l-2 border-indigo-150 dark:border-indigo-900 space-y-2.5">
                        {buildReplyTree(comment.replies).map((reply) => (
                          <SentenceReplyNode
                            key={reply.id}
                            reply={reply}
                            commentId={comment.id}
                            replyingToReplyId={replyingToSentenceReplyId}
                            setReplyingToReplyId={setReplyingToSentenceReplyId}
                            replyData={sentenceReplyData}
                            setReplyData={setSentenceReplyData}
                            handlePostReply={(parentReplyId) => {
                              const text = sentenceReplyData.trim();
                              if (!text) return;
                              handleAddSentenceCommentReply(comment.id, text, parentReplyId);
                              setReplyingToSentenceReplyId(null);
                              setSentenceReplyData("");
                            }}
                            handleDeleteReply={async (replyId) => {
                              if (await showConfirm("Remove this reply?", "Remove Reply", "Remove", "Cancel")) {
                                handleDeleteSentenceCommentReply(comment.id, replyId);
                              }
                            }}
                            currentUserId={currentUserId}
                            canEditSession={canEditSession}
                          />
                        ))}
                      </div>
                    )}

                    {/* Sentence Comment Reply Field (replying directly to the comment) */}
                    <div className="pt-1 select-none">
                      {replyingToSentenceCommentId === comment.id ? (
                          <div className="space-y-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-805 p-2.5 rounded-xl">
                            <textarea
                              autoFocus
                              value={sentenceCommentReplyText}
                              onChange={(e) => setSentenceCommentReplyText(e.target.value)}
                              placeholder="Write a reply..."
                              rows={1}
                              className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-lg p-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white"
                            />
                            <div className="flex gap-1.5 justify-end">
                              <button
                                type="button"
                                onClick={() => {
                                  setReplyingToSentenceCommentId(null);
                                  setSentenceCommentReplyText("");
                                }}
                                className="text-[10px] px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-855 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition-colors font-bold cursor-pointer"
                              >
                                Cancel
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  const text = sentenceCommentReplyText.trim();
                                  if (!text) return;
                                  handleAddSentenceCommentReply(comment.id, text, null);
                                  setReplyingToSentenceCommentId(null);
                                  setSentenceCommentReplyText("");
                                }}
                                className="text-[10px] px-2.5 py-1 rounded-lg bg-indigo-650 hover:bg-indigo-700 text-white font-bold cursor-pointer"
                              >
                                Reply
                              </button>
                            </div>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              setReplyingToSentenceCommentId(comment.id);
                              setSentenceCommentReplyText("");
                            }}
                            className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
                          >
                            Reply
                          </button>
                        )}
                      </div>

                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 dark:text-slate-500 italic select-none">No discussion posts created for this sentence.</p>
            )}

            {/* Sentence comment entry */}
            {!readOnly && (
              <div className="pt-2 select-none">
                {!showSentenceCommentForm ? (
                  <button
                    type="button"
                    onClick={() => setShowSentenceCommentForm(true)}
                    className="px-3.5 py-2 rounded-xl text-xs font-bold bg-indigo-50 dark:bg-indigo-950/20 text-indigo-700 dark:text-indigo-400 border border-indigo-150 dark:border-indigo-900/50 hover:bg-indigo-100 dark:hover:bg-indigo-900/40 transition-colors shadow-sm cursor-pointer"
                  >
                    + Add Sentence Comment
                  </button>
                ) : (
                  <div className="space-y-2.5 bg-white dark:bg-slate-900 p-3 rounded-xl border border-slate-200/60 dark:border-slate-800/80 shadow-sm">
                    <textarea
                      autoFocus
                      ref={sentenceCommentTextareaRef}
                      value={sentenceCommentText}
                      onChange={(e) => setSentenceCommentText(e.target.value)}
                      placeholder="Add a comment or method decision for this sentence..."
                      rows={2}
                      className="w-full text-xs border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:bg-slate-950 dark:text-white leading-normal h-16"
                    />
                    <div className="flex gap-2 justify-end">
                      <button
                        type="button"
                        onClick={() => {
                          setShowSentenceCommentForm(false);
                          setSentenceCommentText("");
                        }}
                        className="text-xs px-3.5 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 transition-all font-bold cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const text = sentenceCommentText.trim();
                          if (!text) return;
                          const newComment = {
                            id: `cmt-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                            author: currentUserName,
                            user_id: currentUserId,
                            text,
                            created_at: new Date().toISOString(),
                            replies: [],
                          };
                          handleSentenceCommentAdd(newComment);
                          setShowSentenceCommentForm(false);
                          setSentenceCommentText("");
                        }}
                        disabled={!sentenceCommentText.trim()}
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

          </div>
          <div className="h-6" />
        </main>
      </div>

      {/* ── PAPER QUALITY & PROCESS INDICATORS MODAL ── */}
      <AnimatePresence>
        {showPaperMetricsModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop blur */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-950/40 dark:bg-slate-950/70 backdrop-blur-sm transition-opacity"
              onClick={() => setShowPaperMetricsModal(false)}
            />
            
            {/* Modal Container */}
            <motion.div
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ duration: 0.2 }}
              className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-2xl w-full max-h-[85vh] flex flex-col relative overflow-hidden"
            >
              {/* Modal Header */}
              <div className="px-6 py-4.5 border-b border-slate-100 dark:border-slate-800/80 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/25 shrink-0">
                <div className="flex items-center gap-2.5 text-left select-none">
                  <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-400 flex items-center justify-center">
                    <BarChart3 size={16} />
                  </div>
                  <div>
                    <h3 className="text-sm sm:text-base font-bold text-slate-800 dark:text-slate-100 leading-tight">Paper Quality &amp; Process Indicators</h3>
                    <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">Live statistics aligned with the scientific paper evaluation criteria</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowPaperMetricsModal(false)}
                  className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer border-0 bg-transparent"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6 overflow-y-auto space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-left">
                  
                  {/* Summary metric cards */}
                  <div className="bg-slate-50/60 dark:bg-slate-900/20 rounded-xl p-3.5 border border-slate-200 dark:border-slate-800">
                    <span className="text-[9px] uppercase font-bold tracking-wider text-slate-400 dark:text-slate-500 block">Source Sentences</span>
                    <p className="text-lg font-extrabold text-slate-800 dark:text-slate-200 mt-1 tabular-nums">{paperMetrics.totalSentences}</p>
                  </div>

                  <div className="bg-slate-50/60 dark:bg-slate-900/20 rounded-xl p-3.5 border border-slate-200 dark:border-slate-800">
                    <span className="text-[9px] uppercase font-bold tracking-wider text-slate-400 dark:text-slate-500 block">Final Gold Triples</span>
                    <p className="text-lg font-extrabold text-slate-800 dark:text-slate-200 mt-1 tabular-nums">{paperMetrics.totalGoldTriples}</p>
                  </div>

                  <div className="bg-slate-50/60 dark:bg-slate-900/20 rounded-xl p-3.5 border border-slate-200 dark:border-slate-800">
                    <span className="text-[9px] uppercase font-bold tracking-wider text-slate-400 dark:text-slate-500 block">Avg Triples / Sent</span>
                    <p className="text-lg font-extrabold text-slate-800 dark:text-slate-200 mt-1 tabular-nums">{paperMetrics.avgTriplesPerSentence}</p>
                  </div>

                  <div className="bg-slate-50/60 dark:bg-slate-900/20 rounded-xl p-3.5 border border-slate-200 dark:border-slate-800">
                    <span className="text-[9px] uppercase font-bold tracking-wider text-slate-400 dark:text-slate-500 block">Total Graders</span>
                    <p className="text-lg font-extrabold text-slate-800 dark:text-slate-200 mt-1 tabular-nums">{paperMetrics.numUsers}</p>
                  </div>
                </div>

                {/* Metric breakdown Table */}
                <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm bg-white dark:bg-slate-950">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-50 dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-500 font-bold uppercase tracking-wider text-[9px]">
                        <th className="px-4 py-3">Quality &amp; Process Indicator Metric</th>
                        <th className="px-4 py-3 text-right">Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80 text-slate-700 dark:text-slate-300">
                      <tr>
                        <td className="px-4 py-3 font-semibold text-left">Percentage of sentences in calibration phase</td>
                        <td className="px-4 py-3 text-right font-extrabold tabular-nums text-slate-900 dark:text-slate-100">{paperMetrics.calibrationPct}%</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-semibold text-left">Pilot-stage triple overlap / Approximate F1</td>
                        <td className="px-4 py-3 text-right font-extrabold tabular-nums text-slate-900 dark:text-slate-100">{paperMetrics.evalF1}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-semibold text-left">Reviewer agreement on candidate-triple decisions</td>
                        <td className="px-4 py-3 text-right font-extrabold tabular-nums text-slate-900 dark:text-slate-100">{paperMetrics.agreementPct}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-semibold text-left">Triples accepted without change</td>
                        <td className="px-4 py-3 text-right font-extrabold tabular-nums text-slate-900 dark:text-slate-100">
                          {paperMetrics.acceptedWithoutChange} <span className="text-slate-400 dark:text-slate-500 font-normal text-[10px] ml-1">({paperMetrics.acceptedPct}%)</span>
                        </td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-semibold text-left">Triples modified after review</td>
                        <td className="px-4 py-3 text-right font-extrabold tabular-nums text-slate-900 dark:text-slate-100">
                          {paperMetrics.modifiedAfterReview} <span className="text-slate-400 dark:text-slate-500 font-normal text-[10px] ml-1">({paperMetrics.modifiedPct}%)</span>
                        </td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-semibold text-left">Rejected triples</td>
                        <td className="px-4 py-3 text-right font-extrabold tabular-nums text-slate-900 dark:text-slate-100">{paperMetrics.rejectedTriples}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-semibold text-left">Missing triples suggested &amp; added after adjudication</td>
                        <td className="px-4 py-3 text-right font-extrabold tabular-nums text-slate-900 dark:text-slate-100">{paperMetrics.missingTriplesAdded}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-semibold text-left">Method-level adjudication cases <span className="text-slate-400 dark:text-slate-500 font-normal text-[10px]">(general comments)</span></td>
                        <td className="px-4 py-3 text-right font-extrabold tabular-nums text-slate-900 dark:text-slate-100">{paperMetrics.methodAdjudicationCount}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-semibold text-left">Triple-level adjudication cases <span className="text-slate-400 dark:text-slate-500 font-normal text-[10px]">(triple comments/replies)</span></td>
                        <td className="px-4 py-3 text-right font-extrabold tabular-nums text-slate-900 dark:text-slate-100">{paperMetrics.tripleAdjudicationCount}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-semibold text-left">Guideline updates or documented method decisions</td>
                        <td className="px-4 py-3 text-right font-extrabold tabular-nums text-slate-900 dark:text-slate-100">{paperMetrics.numGuidelineUpdates}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Explain note */}
                <div className="bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/30 rounded-xl p-3.5 flex items-start gap-2.5 mt-2 text-left">
                  <AlertCircle size={15} className="text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
                  <p className="text-[10px] leading-relaxed text-indigo-805 dark:text-indigo-350">
                    <strong>Adjudication Calculations Note:</strong> Sentence-level general comments represents method adjudications discussing guidelines. Individual triple comments &amp; suggestion replies represents triple-level adjudications. These are calculated in real-time and appended to the cover sheet on PDF download.
                  </p>
                </div>
              </div>

              {/* Modal Footer */}
              <div className="px-6 py-4 bg-slate-50 dark:bg-slate-950/30 border-t border-slate-105 dark:border-slate-800/80 flex justify-end shrink-0">
                <button
                  onClick={() => setShowPaperMetricsModal(false)}
                  className="px-4 py-2 text-xs font-bold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-750 rounded-xl hover:bg-slate-55 active:scale-95 transition-all cursor-pointer"
                >
                  Close Metrics
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── INCOMPLETE DOWNLOAD WARNING MODAL ── */}
      <AnimatePresence>
        {showDownloadWarningModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop blur */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-950/40 dark:bg-slate-950/70 backdrop-blur-sm transition-opacity"
              onClick={() => {
                setShowDownloadWarningModal(false);
                setPendingDownloadFormat(null);
              }}
            />
            
            {/* Modal container */}
            <motion.div
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full relative overflow-hidden"
            >
              <div className="p-6">
                <div className="flex items-center gap-2.5 text-amber-600 dark:text-amber-500 select-none">
                  <AlertTriangle size={20} />
                  <h3 className="text-sm sm:text-base font-bold text-slate-800 dark:text-slate-100">Grading Session Incomplete</h3>
                </div>
                
                <p className="mt-3 text-xs text-slate-650 dark:text-slate-350 leading-relaxed text-left">
                  This worksheet is currently only <strong className="text-slate-800 dark:text-white font-bold">{gradingProgress.pct}%</strong> graded (<strong className="text-slate-850 dark:text-slate-200 font-bold">{gradingProgress.graded}</strong> of <strong className="text-slate-850 dark:text-slate-200 font-bold">{gradingProgress.total}</strong> active triples scored).
                </p>

                <div className="mt-3.5 bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200/60 dark:border-amber-900/30 rounded-xl p-3 flex items-start gap-2.5 text-left">
                  <AlertCircle size={14} className="text-amber-600 dark:text-amber-450 shrink-0 mt-0.5" />
                  <p className="text-[10px] leading-normal text-amber-800 dark:text-amber-400">
                    Downloading the report prior to 100% grading completion will generate incomplete statistics and process indicators in the exported file output.
                  </p>
                </div>
              </div>

              {/* Footer */}
              <div className="px-6 py-4 bg-slate-50 dark:bg-slate-950/20 border-t border-slate-100 dark:border-slate-800/80 flex justify-end gap-2">
                <button
                  onClick={() => {
                    setShowDownloadWarningModal(false);
                    setPendingDownloadFormat(null);
                  }}
                  className="px-3.5 py-2 text-xs font-bold text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-750 rounded-xl hover:bg-slate-55 active:scale-95 transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={async () => {
                    setShowDownloadWarningModal(false);
                    const format = pendingDownloadFormat;
                    setPendingDownloadFormat(null);
                    await executeDownload(format);
                  }}
                  className="px-3.5 py-2 text-xs font-bold text-white bg-amber-600 hover:bg-amber-700 rounded-xl active:scale-95 transition-all cursor-pointer"
                >
                  Download Anyway
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Offline banner overlay */}
      {isOffline && (
        <div className="bg-rose-600 text-white text-xs font-semibold px-4 py-2 flex items-center justify-center gap-2 select-none z-40 fixed top-[60px] left-0 right-0 animate-fade-in shadow-md">
          <AlertCircle size={14} className="animate-pulse" />
          <span>Offline Mode: Internet connection lost. Unsaved changes are backed up locally in your browser.</span>
        </div>
      )}

      {/* Inactivity warning modal */}
      {showIdleWarning && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center z-50 p-4 select-none">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 max-w-sm w-full shadow-2xl text-center space-y-4 animate-scale-in">
            <div className="w-12 h-12 rounded-xl bg-amber-50 dark:bg-amber-950/30 text-amber-600 dark:text-amber-400 flex items-center justify-center mx-auto">
              <AlertTriangle size={24} className="animate-bounce" />
            </div>
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">Inactivity Warning</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              You have been inactive for over 9 minutes. To protect your security, you will be disconnected in{" "}
              <span className="font-bold text-rose-600 dark:text-rose-455 text-sm">{idleCountdown}</span> seconds.
            </p>
            <button
              onClick={() => {
                setShowIdleWarning(false);
              }}
              className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold transition-colors shadow-sm cursor-pointer"
            >
              Stay Connected
            </button>
          </div>
        </div>
      )}

      {/* Exit prompt warning modal */}
      {showExitPromptModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center z-50 p-4 select-none animate-fade-in">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 max-w-sm w-full shadow-2xl space-y-4 animate-scale-in">
            <div className="w-12 h-12 rounded-xl bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mx-auto">
              <Save size={24} />
            </div>
            <h3 className="text-base font-bold text-center text-slate-800 dark:text-slate-100">Save Session?</h3>
            <p className="text-xs text-center text-slate-500 dark:text-slate-400 leading-relaxed">
              Would you like to save your progress before returning to the dashboard?
            </p>
            <div className="flex flex-col gap-2 pt-2">
              <button
                onClick={async () => {
                  setShowExitPromptModal(false);
                  setSaving(true);
                  try {
                    const payload = latestPayloadRef.current;
                    await saveSession(payload);
                  } catch (e) {
                    console.error("Save on exit failed:", e);
                  } finally {
                    setSaving(false);
                    onReset();
                  }
                }}
                className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold transition-all cursor-pointer shadow-sm active:scale-95 text-center"
              >
                Yes, Save & Exit
              </button>
              <button
                onClick={() => {
                  setShowExitPromptModal(false);
                  onReset();
                }}
                className="w-full py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-xl text-xs font-semibold transition-all cursor-pointer hover:bg-slate-200 dark:hover:bg-slate-750 text-center"
              >
                No, Exit Without Saving
              </button>
              <button
                onClick={() => {
                  setShowExitPromptModal(false);
                }}
                className="w-full py-2 border border-slate-200 dark:border-slate-850 text-slate-550 dark:text-slate-400 rounded-xl text-xs font-semibold transition-all cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-900 text-center"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
