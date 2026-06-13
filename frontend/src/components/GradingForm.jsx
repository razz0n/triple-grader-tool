// GradingForm.jsx — Main grading interface: one sentence at a time

import { useState, useMemo, useRef, useEffect } from "react";
import TripleCard from "./TripleCard";
import TripleSuggestions from "./TripleSuggestions";
import TripleComments from "./TripleComments";
import { saveSession, downloadSession, getAuthToken, addSuggestion, voteOnSuggestion, deleteSuggestion, editSuggestion, approveSuggestion, unapproveSuggestion, replyToComment, deleteCommentReply, replyToSuggestion, deleteSuggestionReply, markNotificationRead, markAllNotificationsRead } from "../api";

const IDLE_AUTOSAVE_MS = 10 * 60 * 1000;

function normalizeMetricValue(value) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  if (numeric < 0 || numeric > 10) return null;
  return Number.isInteger(numeric) ? numeric : Number(numeric.toFixed(2));
}

function normalizeMetricByUser(rawMetrics) {
  if (!rawMetrics || typeof rawMetrics !== "object") return {};
  const normalized = {};
  Object.entries(rawMetrics).forEach(([key, payload]) => {
    if (!payload || typeof payload !== "object") return;
    const value = normalizeMetricValue(payload.value);
    if (value === null) return;
    const userId = String(payload.user_id || key || "").trim();
    if (!userId) return;
    const userName = String(payload.user_name || userId).trim() || userId;
    normalized[userId] = {
      user_id: userId,
      user_name: userName,
      value,
      updated_at: payload.updated_at,
    };
  });
  return normalized;
}

function metricEntries(metricByUser) {
  return Object.values(metricByUser || {})
    .map((entry) => {
      const value = normalizeMetricValue(entry?.value);
      if (value === null) return null;
      return {
        userId: String(entry?.user_id || ""),
        userName: String(entry?.user_name || "Unknown"),
        value,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.userName.localeCompare(b.userName));
}

function stableTextHash(input) {
  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = ((hash << 5) - hash + input.charCodeAt(i)) | 0;
  }
  return Math.abs(hash).toString(36);
}

function normalizeSentenceComments(rawComments, fallbackText = "") {
  const normalized = [];
  const seenIds = new Set();

  if (Array.isArray(rawComments)) {
    rawComments.forEach((comment, idx) => {
      if (!comment || typeof comment !== "object") return;

      const text = String(comment.text || comment.comment || "").trim();
      if (!text) return;

      const commentId = String(comment.id || `comment_${idx}_${stableTextHash(text)}`).trim();
      if (!commentId || seenIds.has(commentId)) return;
      seenIds.add(commentId);

      const userId = String(comment.user_id || comment.author_user_id || "").trim();
      const author = String(comment.author || comment.user_name || userId || "User").trim() || "User";

      normalized.push({
        id: commentId,
        user_id: userId,
        author,
        text,
        created_at: comment.created_at || comment.posted_at || null,
      });
    });
  }

  if (normalized.length === 0) {
    const legacyText = String(fallbackText || "").trim();
    if (legacyText) {
      normalized.push({
        id: `legacy_comment_${stableTextHash(legacyText)}`,
        user_id: "",
        author: "Legacy comment",
        text: legacyText,
        created_at: null,
      });
    }
  }

  return normalized.sort((a, b) => String(a.created_at || "").localeCompare(String(b.created_at || "")));
}

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

export default function GradingForm({ uploadData, onReset, currentUser, onEvaluate }) {
  const {
    session_id: initialSessionId,
    source_filename,
    sentences: initialSentences,
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
  const currentUserId = currentUser?.id || "";
  const currentUserName = currentUser?.name || currentUser?.username || currentUser?.email || "User";

  // Deep-clone sentences into local mutable state
  const [sentences, setSentences] = useState(() =>
    initialSentences.map((s) => {
      const completenessByUser = normalizeMetricByUser(s.completeness_by_user);
      const externalRelationByUser = normalizeMetricByUser(s.external_relation_by_user);
      const sentenceComments = normalizeSentenceComments(s.sentence_comments, s.suggestion || "");

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
            s.triples.find((t) => t.completeness !== null && t.completeness !== undefined)?.completeness
          ) ??
          null,
        external_relation:
          normalizeMetricValue(s.external_relation) ??
          normalizeMetricValue(s.relation) ??
          normalizeMetricValue(
            s.triples.find((t) => t.relation !== null && t.relation !== undefined)?.relation
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
        triples: s.triples.map((t) => ({
          ...t,
          grade: t.grade ?? null,
          author: t.author || null,
          grades_by_user: t.grades_by_user || {},
          grade_count: Number.isFinite(t.grade_count) ? t.grade_count : undefined,
          grade_average: t.grade_average ?? null,
          suggestions: t.suggestions || [],
        })),
      };
    })
  );

  const [currentIdx, setCurrentIdx]       = useState(0);
  // When resuming a saved session, the session is already saved on the server
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

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [replyingToSentenceCommentId, setReplyingToSentenceCommentId] = useState(null);
  const [sentenceCommentReplyText, setSentenceCommentReplyText] = useState("");

  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [highlightedElementId, setHighlightedElementId] = useState(null);
  const [showPaperMetricsModal, setShowPaperMetricsModal] = useState(false);
  const [showDownloadWarningModal, setShowDownloadWarningModal] = useState(false);
  const [pendingDownloadFormat, setPendingDownloadFormat] = useState(null);
  const notificationsRef = useRef(null);

  // Close dropdowns on outside click and handle scroll collapse
  useEffect(() => {
    const handler = (e) => {
      if (dlRef.current && !dlRef.current.contains(e.target)) setDlOpen(false);
      if (moreRef.current && !moreRef.current.contains(e.target)) setMoreOpen(false);
      if (notificationsRef.current && !notificationsRef.current.contains(e.target)) setNotificationsOpen(false);
    };
    const handleScroll = () => {
      if (window.scrollY > 80) {
        setIsCollapsed(true);
      } else {
        setIsCollapsed(false);
      }
    };
    document.addEventListener("mousedown", handler);
    window.addEventListener("scroll", handleScroll);
    return () => {
      document.removeEventListener("mousedown", handler);
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  const total   = sentences.length;
  const current = sentences[currentIdx];
  const completenessMetricEntries = metricEntries(current?.completeness_by_user);
  const externalRelationMetricEntries = metricEntries(current?.external_relation_by_user);
  const currentSentenceComments = useMemo(
    () => normalizeSentenceComments(current?.sentence_comments),
    [current?.sentence_comments]
  );

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
    
    // Remove empty/falsy values
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

  const notifications = useMemo(() => {
    const list = [];
    if (!currentUserId) return list;

    sentences.forEach((sentence) => {
      // 1. Sentence comments replies
      (sentence.sentence_comments || []).forEach((comment) => {
        (comment.replies || []).forEach((reply) => {
          const isOwn = reply.user_id === currentUserId;
          const isRead = (reply.read_by || []).includes(currentUserId);
          if (!isOwn && !isRead) {
            list.push({
              id: reply.id,
              type: "comment_reply",
              title: `New reply from ${reply.author || "User"}`,
              text: reply.text,
              createdAt: reply.created_at,
              sentenceId: sentence.id,
              sentenceIdx: sentences.findIndex(s => s.id === sentence.id),
              tripleId: null,
              commentId: comment.id,
            });
          }
        });
      });

      // 2. Triple comments replies & suggestions & suggestion replies
      (sentence.triples || []).forEach((triple) => {
        (triple.triple_comments || []).forEach((comment) => {
          (comment.replies || []).forEach((reply) => {
            const isOwn = reply.user_id === currentUserId;
            const isRead = (reply.read_by || []).includes(currentUserId);
            if (!isOwn && !isRead) {
              list.push({
                id: reply.id,
                type: "comment_reply",
                title: `New reply from ${reply.author || "User"} on triple`,
                text: reply.text,
                createdAt: reply.created_at,
                sentenceId: sentence.id,
                sentenceIdx: sentences.findIndex(s => s.id === sentence.id),
                tripleId: triple.id,
                commentId: comment.id,
              });
            }
          });
        });

        (triple.suggestions || []).forEach((sug) => {
          // Check suggestion itself
          const isOwnSug = sug.user_id === currentUserId;
          const isReadSug = (sug.read_by || []).includes(currentUserId);
          if (!isOwnSug && !isReadSug) {
            list.push({
              id: sug.id,
              type: "suggestion",
              title: `New suggestion from ${sug.author || "User"}`,
              text: `Triple: ${sug.subject} → ${sug.predicate} → ${sug.object}`,
              createdAt: sug.created_at,
              sentenceId: sentence.id,
              sentenceIdx: sentences.findIndex(s => s.id === sentence.id),
              tripleId: triple.id,
            });
          }

          // Check suggestion replies
          (sug.replies || []).forEach((reply) => {
            const isOwnReply = reply.user_id === currentUserId;
            const isReadReply = (reply.read_by || []).includes(currentUserId);
            if (!isOwnReply && !isReadReply) {
              list.push({
                id: reply.id,
                type: "suggestion_reply",
                title: `New reply from ${reply.author || "User"} on suggestion`,
                text: reply.text,
                createdAt: reply.created_at,
                sentenceId: sentence.id,
                sentenceIdx: sentences.findIndex(s => s.id === sentence.id),
                tripleId: triple.id,
                suggestionId: sug.id,
              });
            }
          });
        });
      });
    });

    // Sort notifications by date (newest first)
    return list.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  }, [sentences, currentUserId]);

  const handleNotificationClick = async (notif) => {
    // Mark as read on the backend
    try {
      const sessionId = savedSessionId || initialSessionId;
      await markNotificationRead(sessionId, notif.id);
      
      // Update local state to mark as read immediately
      setSentences((prev) =>
        prev.map((s) => {
          if (s.id !== notif.sentenceId) return s;
          
          // Update sentence comments replies
          const updatedComments = (s.sentence_comments || []).map((c) => {
            const readBy = c.id === notif.id ? [...(c.read_by || []), currentUserId] : (c.read_by || []);
            const updatedReplies = (c.replies || []).map((r) => ({
              ...r,
              read_by: r.id === notif.id ? [...(r.read_by || []), currentUserId] : (r.read_by || []),
            }));
            return { ...c, read_by: readBy, replies: updatedReplies };
          });

          // Update triples (comments, replies, suggestions, replies)
          const updatedTriples = (s.triples || []).map((t) => {
            const updatedTripleComments = (t.triple_comments || []).map((c) => {
              const readBy = c.id === notif.id ? [...(c.read_by || []), currentUserId] : (c.read_by || []);
              const updatedReplies = (c.replies || []).map((r) => ({
                ...r,
                read_by: r.id === notif.id ? [...(r.read_by || []), currentUserId] : (r.read_by || []),
              }));
              return { ...c, read_by: readBy, replies: updatedReplies };
            });

            const updatedSuggestions = (t.suggestions || []).map((sug) => {
              const readBy = sug.id === notif.id ? [...(sug.read_by || []), currentUserId] : (sug.read_by || []);
              const updatedReplies = (sug.replies || []).map((r) => ({
                ...r,
                read_by: r.id === notif.id ? [...(r.read_by || []), currentUserId] : (r.read_by || []),
              }));
              return { ...sug, read_by: readBy, replies: updatedReplies };
            });

            return { ...t, triple_comments: updatedTripleComments, suggestions: updatedSuggestions };
          });

          return { ...s, sentence_comments: updatedComments, triples: updatedTriples };
        })
      );
    } catch (e) {
      console.error("Failed to mark notification as read:", e);
    }

    // Navigate to the correct sentence
    setCurrentIdx(notif.sentenceIdx);
    setNotificationsOpen(false);

    // Wait for the render update, then scroll and highlight
    setTimeout(() => {
      const targetId = notif.tripleId ? `triple-card-${notif.tripleId}` : `sentence-comment-box-${notif.sentenceId}`;
      const element = document.getElementById(targetId);
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "center" });
        setHighlightedElementId(targetId);
        setTimeout(() => {
          setHighlightedElementId(null);
        }, 3000);
      }
    }, 200);
  };

  const handleMarkAllNotificationsRead = async () => {
    try {
      const sessionId = savedSessionId || initialSessionId;
      await markAllNotificationsRead(sessionId);

      // Update all locally
      setSentences((prev) =>
        prev.map((s) => {
          const updatedComments = (s.sentence_comments || []).map((c) => {
            const readBy = (c.read_by || []).includes(currentUserId) ? c.read_by : [...(c.read_by || []), currentUserId];
            const updatedReplies = (c.replies || []).map((r) => ({
              ...r,
              read_by: (r.read_by || []).includes(currentUserId) ? r.read_by : [...(r.read_by || []), currentUserId],
            }));
            return { ...c, read_by: readBy, replies: updatedReplies };
          });

          const updatedTriples = (s.triples || []).map((t) => {
            const updatedTripleComments = (t.triple_comments || []).map((c) => {
              const readBy = (c.read_by || []).includes(currentUserId) ? c.read_by : [...(c.read_by || []), currentUserId];
              const updatedReplies = (c.replies || []).map((r) => ({
                ...r,
                read_by: (r.read_by || []).includes(currentUserId) ? r.read_by : [...(r.read_by || []), currentUserId],
              }));
              return { ...c, read_by: readBy, replies: updatedReplies };
            });

            const updatedSuggestions = (t.suggestions || []).map((sug) => {
              const readBy = (sug.read_by || []).includes(currentUserId) ? sug.read_by : [...(sug.read_by || []), currentUserId];
              const updatedReplies = (sug.replies || []).map((r) => ({
                ...r,
                read_by: (r.read_by || []).includes(currentUserId) ? r.read_by : [...(r.read_by || []), currentUserId],
              }));
              return { ...sug, read_by: readBy, replies: updatedReplies };
            });

            return { ...t, triple_comments: updatedTripleComments, suggestions: updatedSuggestions };
          });

          return { ...s, sentence_comments: updatedComments, triples: updatedTriples };
        })
      );
      setNotificationsOpen(false);
    } catch (e) {
      console.error("Failed to mark all as read:", e);
    }
  };

  // Compute live sentence grade for the current sentence
  const sentenceGrade = useMemo(() => {
    const activeTriples = (current.triples || []).filter(t => !t.is_new_suggestion || t.status === "approved");
    const grades = activeTriples
      .map((t) => t.grade)
      .filter((g) => g !== null && g !== undefined);
    if (grades.length === 0) return null;
    if (grades.length < activeTriples.length) return "partial";
    return (grades.reduce((a, b) => a + b, 0) / grades.length).toFixed(1);
  }, [current]);

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
          const grade = Number(payload.grade);
          if (!Number.isFinite(grade)) return;

          const userId = String(payload?.user_id || key || "");
          const userName = String(payload?.user_name || userId || "Unknown");
          const current = rowsByUser.get(userId) || {
            user_id: userId,
            user_name: userName,
            graded_triples: 0,
            grade_sum: 0,
            grade_count: 0,
          };

          current.graded_triples += 1;
          current.grade_count += 1;
          current.grade_sum += grade;
          rowsByUser.set(userId, current);

          totalGradeEntries += 1;
          overallGradeSum += grade;
        });
      });
    });

    const rows = Array.from(rowsByUser.values())
      .map((row) => ({
        ...row,
        average_grade: row.grade_count > 0 ? Number((row.grade_sum / row.grade_count).toFixed(2)) : null,
      }))
      .sort((a, b) => {
        if (b.graded_triples !== a.graded_triples) return b.graded_triples - a.graded_triples;
        return String(a.user_name).localeCompare(String(b.user_name));
      });

    return {
      rows,
      totalUniqueGraders: rows.length,
      totalGradeEntries,
      overallAverage: totalGradeEntries > 0 ? Number((overallGradeSum / totalGradeEntries).toFixed(2)) : null,
    };
  }, [sentences]);

  const handleGradeChange = (tripleId, grade) => {
    if (!canEditSession) return;
    hasUnsavedChangesRef.current = true;
    setSentences((prev) =>
      prev.map((s, i) =>
        i !== currentIdx
          ? s
          : {
              ...s,
              triples: s.triples.map((t) => {
                if (t.id !== tripleId) return t;

                if (!currentUserId) {
                  return {
                    ...t,
                    grade: grade ?? null,
                    author: grade === null || grade === undefined ? null : currentUserName,
                  };
                }

                const nextGradesByUser = {
                  ...(t.grades_by_user || {}),
                };

                if (grade === null || grade === undefined || grade === "") {
                  delete nextGradesByUser[currentUserId];
                } else {
                  nextGradesByUser[currentUserId] = {
                    user_id: currentUserId,
                    user_name: currentUserName,
                    grade,
                    graded_at: new Date().toISOString(),
                  };
                }

                const values = Object.values(nextGradesByUser)
                  .filter((item) => item?.grade !== null && item?.grade !== undefined && item?.grade !== "")
                  .map((item) => Number(item.grade))
                  .filter((value) => Number.isFinite(value));

                return {
                  ...t,
                  grade: grade ?? null,
                  author: grade === null || grade === undefined ? null : currentUserName,
                  grades_by_user: nextGradesByUser,
                  grade_count: values.length,
                  grade_average: values.length > 0 ? Number((values.reduce((acc, value) => acc + value, 0) / values.length).toFixed(2)) : null,
                };
              }),
            }
      )
    );
  };

  const handleSentenceMetricChange = (field, value) => {
    if (!canEditSession) return;
    const isUndo = current[field] === value;
    const normalizedValue = isUndo ? null : normalizeMetricValue(value);
    const byUserField = field === "completeness" ? "completeness_by_user" : "external_relation_by_user";
    const countField = field === "completeness" ? "completeness_count" : "external_relation_count";
    const averageField = field === "completeness" ? "completeness_average" : "external_relation_average";

    hasUnsavedChangesRef.current = true;
    setSentences((prev) =>
      prev.map((s, i) =>
        i !== currentIdx
          ? s
          : {
              ...s,
              [field]: normalizedValue,
              [byUserField]: (() => {
                const currentMap = { ...(s[byUserField] || {}) };
                if (!currentUserId) return currentMap;

                if (normalizedValue === null) {
                  delete currentMap[currentUserId];
                } else {
                  currentMap[currentUserId] = {
                    user_id: currentUserId,
                    user_name: currentUserName,
                    value: normalizedValue,
                    updated_at: new Date().toISOString(),
                  };
                }
                return currentMap;
              })(),
              [countField]: (() => {
                const currentMap = { ...(s[byUserField] || {}) };
                if (currentUserId) {
                  if (normalizedValue === null) {
                    delete currentMap[currentUserId];
                  } else {
                    currentMap[currentUserId] = {
                      user_id: currentUserId,
                      user_name: currentUserName,
                      value: normalizedValue,
                      updated_at: new Date().toISOString(),
                    };
                  }
                }

                return Object.values(currentMap)
                  .map((entry) => normalizeMetricValue(entry?.value))
                  .filter((metricValue) => metricValue !== null).length;
              })(),
              [averageField]: (() => {
                const currentMap = { ...(s[byUserField] || {}) };
                if (currentUserId) {
                  if (normalizedValue === null) {
                    delete currentMap[currentUserId];
                  } else {
                    currentMap[currentUserId] = {
                      user_id: currentUserId,
                      user_name: currentUserName,
                      value: normalizedValue,
                      updated_at: new Date().toISOString(),
                    };
                  }
                }

                const values = Object.values(currentMap)
                  .map((entry) => normalizeMetricValue(entry?.value))
                  .filter((metricValue) => metricValue !== null);
                return values.length > 0
                  ? Number((values.reduce((acc, metricValue) => acc + metricValue, 0) / values.length).toFixed(2))
                  : null;
              })(),
            }
      )
    );
  };

  const handleSuggestionChange = (value) => {
    hasUnsavedChangesRef.current = true;
    setSentences((prev) =>
      prev.map((s, i) => (i === currentIdx ? { ...s, suggestion: value } : s))
    );
  };

  const handlePostSentenceComment = async () => {
    const draft = String(current?.suggestion || "").trim();
    if (!draft || !canEditSession || saving) return;

    const postedAt = new Date().toISOString();
    const newComment = {
      id: createCommentId(),
      user_id: String(currentUserId || "").trim(),
      author: String(currentUserName || "User").trim() || "User",
      text: draft,
      created_at: postedAt,
    };

    const updatedSentences = sentences.map((sentence, index) => {
      if (index !== currentIdx) return sentence;
      const nextComments = normalizeSentenceComments([
        ...(Array.isArray(sentence.sentence_comments) ? sentence.sentence_comments : []),
        newComment,
      ]);
      return {
        ...sentence,
        suggestion: "",
        sentence_comments: nextComments,
        comment_count: nextComments.length,
      };
    });

    hasUnsavedChangesRef.current = true;
    setSentences(updatedSentences);

    savingRef.current = true;
    setSaving(true);
    setSaveMsg("");
    setSaveError("");
    try {
      const result = await saveSession(buildPayload(updatedSentences));
      setSavedSessionId(result.session_id);
      setSavedAt(new Date());
      setSaveMsg("Comment posted.");
      setTimeout(() => setSaveMsg(""), 3500);
      hasUnsavedChangesRef.current = false;
    } catch (e) {
      setSaveError(
        e?.response?.data?.detail || "Comment post failed. Try Save to persist your changes."
      );
      hasUnsavedChangesRef.current = true;
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  const handleAddSuggestion = async (tripleId, suggestionData) => {
    if (!canSuggestTriples) {
      throw new Error("You are not allowed to add triple suggestions in this session.");
    }

    // Ensure session is saved before adding suggestion
    if (!savedSessionId) {
      await handleSave();
    }
    try {
      const sessionId = savedSessionId || initialSessionId;
      const result = await addSuggestion(
        sessionId,
        current.id,
        tripleId,
        suggestionData.subject,
        suggestionData.predicate,
        suggestionData.object,
        suggestionData.reason
      );
      
      // Update local state with the new suggestion
      setSentences((prev) =>
        prev.map((s, i) =>
          i !== currentIdx
            ? s
            : {
                ...s,
                triples: s.triples.map((t) =>
                  t.id === tripleId
                    ? {
                        ...t,
                        suggestions: [
                          ...(t.suggestions || []),
                          {
                            id: result?.suggestion_id || Math.random().toString(36).substr(2, 9),
                            author: currentUserName,
                            subject: suggestionData.subject,
                            predicate: suggestionData.predicate,
                            object: suggestionData.object,
                            reason: suggestionData.reason || "",
                            created_at: new Date().toISOString(),
                            votes: {},
                          },
                        ],
                      }
                    : t
                ),
              }
        )
      );
    } catch (err) {
      console.error("Error adding suggestion:", err);
      throw err;
    }
  };

  const handleEditSuggestion = async (tripleId, suggestionId, suggestionData) => {
    if (!savedSessionId) {
      await handleSave();
    }
    try {
      const sessionId = savedSessionId || initialSessionId;
      await editSuggestion(
        sessionId,
        current.id,
        tripleId,
        suggestionId,
        suggestionData.subject,
        suggestionData.predicate,
        suggestionData.object,
        suggestionData.reason
      );

      setSentences((prev) =>
        prev.map((s, i) =>
          i !== currentIdx
            ? s
            : {
                ...s,
                triples: s.triples.map((t) =>
                  t.id === tripleId
                    ? {
                        ...t,
                        suggestions: (t.suggestions || []).map((sug) =>
                          sug.id === suggestionId
                            ? {
                                ...sug,
                                subject: suggestionData.subject,
                                predicate: suggestionData.predicate,
                                object: suggestionData.object,
                                reason: suggestionData.reason || "",
                              }
                            : sug
                        ),
                      }
                    : t
                ),
              }
        )
      );
    } catch (err) {
      console.error("Error editing suggestion:", err);
      throw err;
    }
  };

  const handleVoteSuggestion = async (tripleId, suggestionId, vote) => {
    // Ensure session is saved before voting
    if (!savedSessionId) {
      await handleSave();
    }
    try {
      const sessionId = savedSessionId || initialSessionId;
      const targetTriple = current.triples.find((t) => t.id === tripleId);
      const targetSuggestion = targetTriple?.suggestions?.find((sug) => sug.id === suggestionId);
      const existingVote = targetSuggestion?.votes?.[currentUserName] || null;
      const nextVote = existingVote === vote ? null : vote;
      await voteOnSuggestion(
        sessionId,
        current.id,
        tripleId,
        suggestionId,
        nextVote
      );
      
      // Update local state with the vote
      setSentences((prev) =>
        prev.map((s, i) =>
          i !== currentIdx
            ? s
            : {
                ...s,
                triples: s.triples.map((t) =>
                  t.id === tripleId
                    ? {
                        ...t,
                        suggestions: t.suggestions.map((sug) =>
                          sug.id === suggestionId
                            ? {
                                ...sug,
                                votes: (() => {
                                  const updatedVotes = { ...(sug.votes || {}) };
                                  if (updatedVotes[currentUserName] === vote) {
                                    delete updatedVotes[currentUserName];
                                  } else {
                                    updatedVotes[currentUserName] = vote;
                                  }
                                  return updatedVotes;
                                })(),
                              }
                            : sug
                        ),
                      }
                    : t
                ),
              }
        )
      );
    } catch (err) {
      console.error("Error voting on suggestion:", err);
      throw err;
    }
  };

  const handleDeleteSuggestion = async (tripleId, suggestionId) => {
    // Ensure session is saved before deleting
    if (!savedSessionId) {
      await handleSave();
    }
    try {
      const sessionId = savedSessionId || initialSessionId;
      await deleteSuggestion(
        sessionId,
        current.id,
        tripleId,
        suggestionId
      );
      
      // Update local state by removing the suggestion
      setSentences((prev) =>
        prev.map((s, i) =>
          i !== currentIdx
            ? s
            : {
                ...s,
                triples: s.triples.map((t) =>
                  t.id === tripleId
                    ? {
                        ...t,
                        suggestions: t.suggestions.filter((sug) => sug.id !== suggestionId),
                      }
                    : t
                ),
              }
        )
      );
    } catch (err) {
      console.error("Error deleting suggestion:", err);
      throw err;
    }
  };

  const handleToggleSuggestionApproval = async (tripleId, suggestionId, isApproved) => {
    if (!savedSessionId) {
      await handleSave();
    }
    const sessionId = savedSessionId || initialSessionId;
    const result = isApproved
      ? await unapproveSuggestion(sessionId, current.id, tripleId, suggestionId)
      : await approveSuggestion(sessionId, current.id, tripleId, suggestionId);

    setSentences((prev) =>
      prev.map((s, i) =>
        i !== currentIdx
          ? s
          : {
              ...s,
              triples: s.triples.map((t) =>
                t.id !== tripleId
                  ? t
                  : {
                      ...t,
                      subject: result?.triple?.subject ?? t.subject,
                      predicate: result?.triple?.predicate ?? t.predicate,
                      object: result?.triple?.object ?? t.object,
                      author: result?.triple?.author ?? t.author,
                      suggestions: (t.suggestions || []).map((sug) =>
                        sug.id === suggestionId
                          ? isApproved
                            ? { ...sug, status: "pending", approved_by: undefined, approved_at: undefined }
                            : { ...sug, status: "approved", approved_by: currentUser?.name || "Owner", approved_at: new Date().toISOString() }
                          : sug
                      ),
                    }
              ),
            }
      )
    );
  };

  const handleAddTripleComment = async (tripleId, comment) => {
    hasUnsavedChangesRef.current = true;
    setSentences((prev) =>
      prev.map((s, i) =>
        i !== currentIdx
          ? s
          : {
              ...s,
              triples: s.triples.map((t) =>
                t.id === tripleId
                  ? {
                      ...t,
                      triple_comments: [...(t.triple_comments || []), comment],
                    }
                  : t
              ),
            }
      )
    );
  };

  const handleDeleteTripleComment = async (tripleId, commentId) => {
    hasUnsavedChangesRef.current = true;
    setSentences((prev) =>
      prev.map((s, i) =>
        i !== currentIdx
          ? s
          : {
              ...s,
              triples: s.triples.map((t) =>
                t.id === tripleId
                  ? {
                      ...t,
                      triple_comments: (t.triple_comments || []).filter(
                        (c) => c.id !== commentId
                      ),
                    }
                  : t
              ),
            }
      )
    );
  };

  const handleAddTripleCommentReply = async (tripleId, commentId, replyData) => {
    if (!savedSessionId) {
      await handleSave();
    }
    const sessionId = savedSessionId || initialSessionId;
    try {
      const result = await replyToComment(sessionId, current.id, tripleId, commentId, replyData.text);
      if (result.ok && result.reply) {
        setSentences((prev) =>
          prev.map((s, i) =>
            i !== currentIdx
              ? s
              : {
                  ...s,
                  triples: s.triples.map((t) =>
                    t.id === tripleId
                      ? {
                          ...t,
                          triple_comments: (t.triple_comments || []).map((c) =>
                            c.id === commentId
                              ? {
                                  ...c,
                                  replies: [...(c.replies || []), result.reply],
                                }
                              : c
                          ),
                        }
                      : t
                  ),
                }
          )
        );
      }
    } catch (err) {
      console.error("Error adding triple comment reply:", err);
      alert("Failed to add reply: " + err.message);
    }
  };

  const handleDeleteTripleCommentReply = async (tripleId, commentId, replyId) => {
    if (!savedSessionId) {
      await handleSave();
    }
    const sessionId = savedSessionId || initialSessionId;
    try {
      const result = await deleteCommentReply(sessionId, current.id, commentId, replyId, tripleId);
      if (result.ok) {
        setSentences((prev) =>
          prev.map((s, i) =>
            i !== currentIdx
              ? s
              : {
                  ...s,
                  triples: s.triples.map((t) =>
                    t.id === tripleId
                      ? {
                          ...t,
                          triple_comments: (t.triple_comments || []).map((c) =>
                            c.id === commentId
                              ? {
                                  ...c,
                                  replies: (c.replies || []).filter((r) => r.id !== replyId),
                                }
                              : c
                          ),
                        }
                      : t
                  ),
                }
          )
        );
      }
    } catch (err) {
      console.error("Error deleting triple comment reply:", err);
      alert("Failed to delete reply: " + err.message);
    }
  };

  const handleAddSentenceCommentReply = async (commentId, replyData) => {
    if (!savedSessionId) {
      await handleSave();
    }
    const sessionId = savedSessionId || initialSessionId;
    try {
      const result = await replyToComment(sessionId, current.id, null, commentId, replyData.text);
      if (result.ok && result.reply) {
        setSentences((prev) =>
          prev.map((s, i) =>
            i !== currentIdx
              ? s
              : {
                  ...s,
                  sentence_comments: (s.sentence_comments || []).map((c) =>
                    c.id === commentId
                      ? {
                          ...c,
                          replies: [...(c.replies || []), result.reply],
                        }
                      : c
                  ),
                }
          )
        );
      }
    } catch (err) {
      console.error("Error adding sentence comment reply:", err);
      alert("Failed to add reply: " + err.message);
    }
  };

  const handleDeleteSentenceCommentReply = async (commentId, replyId) => {
    if (!savedSessionId) {
      await handleSave();
    }
    const sessionId = savedSessionId || initialSessionId;
    try {
      const result = await deleteCommentReply(sessionId, current.id, commentId, replyId, null);
      if (result.ok) {
        setSentences((prev) =>
          prev.map((s, i) =>
            i !== currentIdx
              ? s
              : {
                  ...s,
                  sentence_comments: (s.sentence_comments || []).map((c) =>
                    c.id === commentId
                      ? {
                          ...c,
                          replies: (c.replies || []).filter((r) => r.id !== replyId),
                        }
                      : c
                  ),
                }
          )
        );
      }
    } catch (err) {
      console.error("Error deleting sentence comment reply:", err);
      alert("Failed to delete reply: " + err.message);
    }
  };

  const handleAddSuggestionReply = async (suggestionId, text) => {
    // Find tripleId for this suggestion
    let foundTripleId = null;
    for (const t of current.triples || []) {
      if ((t.suggestions || []).some((sug) => sug.id === suggestionId)) {
        foundTripleId = t.id;
        break;
      }
    }
    if (!foundTripleId) return;

    if (!savedSessionId) {
      await handleSave();
    }
    const sessionId = savedSessionId || initialSessionId;
    try {
      const result = await replyToSuggestion(sessionId, current.id, foundTripleId, suggestionId, text);
      if (result.ok && result.reply) {
        setSentences((prev) =>
          prev.map((s, i) =>
            i !== currentIdx
              ? s
              : {
                  ...s,
                  triples: s.triples.map((t) =>
                    t.id === foundTripleId
                      ? {
                          ...t,
                          suggestions: (t.suggestions || []).map((sug) =>
                            sug.id === suggestionId
                              ? {
                                  ...sug,
                                  replies: [...(sug.replies || []), result.reply],
                                }
                              : sug
                          ),
                        }
                      : t
                  ),
                }
          )
        );
      }
    } catch (err) {
      console.error("Error adding suggestion reply:", err);
      alert("Failed to add reply: " + err.message);
    }
  };

  const handleDeleteSuggestionReply = async (suggestionId, replyId) => {
    // Find tripleId for this suggestion
    let foundTripleId = null;
    for (const t of current.triples || []) {
      if ((t.suggestions || []).some((sug) => sug.id === suggestionId)) {
        foundTripleId = t.id;
        break;
      }
    }
    if (!foundTripleId) return;

    if (!savedSessionId) {
      await handleSave();
    }
    const sessionId = savedSessionId || initialSessionId;
    try {
      const result = await deleteSuggestionReply(sessionId, current.id, foundTripleId, suggestionId, replyId);
      if (result.ok) {
        setSentences((prev) =>
          prev.map((s, i) =>
            i !== currentIdx
              ? s
              : {
                  ...s,
                  triples: s.triples.map((t) =>
                    t.id === foundTripleId
                      ? {
                          ...t,
                          suggestions: (t.suggestions || []).map((sug) =>
                            sug.id === suggestionId
                              ? {
                                  ...sug,
                                  replies: (sug.replies || []).filter((r) => r.id !== replyId),
                                }
                              : sug
                          ),
                        }
                      : t
                  ),
                }
          )
        );
      }
    } catch (err) {
      console.error("Error deleting suggestion reply:", err);
      alert("Failed to delete reply: " + err.message);
    }
  };

  const handleMarkTripleForRemoval = async (tripleId, marked) => {
    hasUnsavedChangesRef.current = true;
    setSentences((prev) =>
      prev.map((s, i) =>
        i !== currentIdx
          ? s
          : {
              ...s,
              triples: s.triples.map((t) =>
                t.id === tripleId
                  ? {
                      ...t,
                      marked_for_removal: marked,
                      removal_reason: marked ? "Not needed" : null,
                    }
                  : t
              ),
            }
      )
    );
  };

  const handleAddTripleAdjacent = (tripleId, direction) => {
    if (!canSuggestTriples) return;
    const newTriple = {
      id: `new_triple_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
      subject: "",
      predicate: "",
      object: "",
      is_new_suggestion: true,
      is_editing: true,
      status: "pending",
      suggested_by: currentUserName,
      suggested_by_id: currentUserId,
      grade: null,
      grades_by_user: {},
      suggestions: [],
      triple_comments: []
    };

    setSentences((prev) =>
      prev.map((s, i) => {
        if (i !== currentIdx) return s;
        const index = s.triples.findIndex((t) => t.id === tripleId);
        if (index === -1) return s;
        const newTriples = [...s.triples];
        if (direction === "above") {
          newTriples.splice(index, 0, newTriple);
        } else {
          newTriples.splice(index + 1, 0, newTriple);
        }
        return { ...s, triples: newTriples };
      })
    );
    hasUnsavedChangesRef.current = true;
  };

  const handleRemoveSuggestedTriple = (tripleId) => {
    if (!window.confirm("Are you sure you want to remove this suggested triple?")) return;
    setSentences((prev) =>
      prev.map((s, i) => {
        if (i !== currentIdx) return s;
        return {
          ...s,
          triples: s.triples.filter((t) => t.id !== tripleId)
        };
      })
    );
    hasUnsavedChangesRef.current = true;
  };

  const handleApproveSuggestedTriple = (tripleId) => {
    setSentences((prev) =>
      prev.map((s, i) => {
        if (i !== currentIdx) return s;
        return {
          ...s,
          triples: s.triples.map((t) =>
            t.id === tripleId
              ? {
                  ...t,
                  status: "approved",
                  approved_by: currentUserName,
                  approved_at: new Date().toISOString()
                }
              : t
          )
        };
      })
    );
    hasUnsavedChangesRef.current = true;
    setTimeout(() => handleSave(), 100);
  };

  const handleSaveSuggestedTriple = (tripleId, fields) => {
    setSentences((prev) =>
      prev.map((s, i) => {
        if (i !== currentIdx) return s;
        return {
          ...s,
          triples: s.triples.map((t) =>
            t.id === tripleId
              ? {
                  ...t,
                  ...fields,
                  is_editing: false
                }
              : t
          )
        };
      })
    );
    hasUnsavedChangesRef.current = true;
  };

  const handleSetTripleEditing = (tripleId, isEditing) => {
    setSentences((prev) =>
      prev.map((s, i) => {
        if (i !== currentIdx) return s;
        return {
          ...s,
          triples: s.triples.map((t) =>
            t.id === tripleId
              ? {
                  ...t,
                  is_editing: isEditing
                }
              : t
          )
        };
      })
    );
  };

  const buildPayload = (sentencesSource = sentences) => ({
    session_id:      savedSessionId || initialSessionId,
    source_filename: source_filename,
    uploaded_at:     uploaded_at,
    manual_mode:     !!manual_mode,
    sentences: sentencesSource.map((s) => {
      const grades = s.triples
        .map((t) => t.grade)
        .filter((g) => g != null);
      const avg =
        grades.length === s.triples.length && grades.length > 0
          ? parseFloat(
              (grades.reduce((a, b) => a + b, 0) / grades.length).toFixed(2)
            )
          : null;
      const sentenceComments = normalizeSentenceComments(s.sentence_comments);
      return {
        ...s,
        suggestion:
          sentenceComments.length > 0
            ? sentenceComments[sentenceComments.length - 1].text
            : "",
        sentence_comments: sentenceComments,
        comment_count: sentenceComments.length,
        sentence_grade: avg,
        completeness: s.completeness ?? null,
        external_relation: s.external_relation ?? null,
        completeness_by_user: normalizeMetricByUser(s.completeness_by_user),
        external_relation_by_user: normalizeMetricByUser(s.external_relation_by_user),
        triples: s.triples.map((t) => {
          const cleaned = { ...t };
          delete cleaned.completeness;
          delete cleaned.relation;
          delete cleaned.grade_count;
          delete cleaned.grade_average;
          return cleaned;
        }),
      };
    }),
  });

  useEffect(() => {
    latestPayloadRef.current = buildPayload();
  }, [savedSessionId, initialSessionId, source_filename, uploaded_at, sentences]);

  useEffect(() => {
    savingRef.current = saving;
  }, [saving]);

  useEffect(() => {
    const autosaveIfIdle = async () => {
      if (savingRef.current || !hasUnsavedChangesRef.current) return;

      savingRef.current = true;
      setSaving(true);
      setSaveError("");
      try {
        const result = await saveSession(latestPayloadRef.current);
        setSavedSessionId(result.session_id);
        setSavedAt(new Date());
        setSaveMsg("Autosaved after 10 minutes idle.");
        setTimeout(() => setSaveMsg(""), 3500);
        hasUnsavedChangesRef.current = false;
      } catch (e) {
        setSaveError(
          e?.response?.data?.detail || "Autosave failed. Is the backend running?"
        );
      } finally {
        savingRef.current = false;
        setSaving(false);
      }
    };

    const resetIdleTimer = () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      idleTimerRef.current = setTimeout(() => {
        void autosaveIfIdle();
      }, IDLE_AUTOSAVE_MS);
    };

    const events = ["mousedown", "mousemove", "keydown", "scroll", "touchstart"];
    events.forEach((evt) => window.addEventListener(evt, resetIdleTimer, { passive: true }));
    resetIdleTimer();

    return () => {
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      events.forEach((evt) => window.removeEventListener(evt, resetIdleTimer));
    };
  }, []);

  const handleSave = async () => {
    savingRef.current = true;
    setSaving(true);
    setSaveMsg("");
    setSaveError("");
    try {
      const result = await saveSession(buildPayload());
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
    { value: "pdf",   label: "PDF",   icon: "📄" },
    { value: "word",  label: "Word",  icon: "📝" },
    { value: "excel", label: "Excel", icon: "📊" },
    { value: "csv",   label: "CSV",   icon: "⊞" },
    { value: "json",  label: "JSON",  icon: "{}" },
  ];

  const handleDownload = async (fmt) => {
    const target = fmt || dlFmt;
    setDlOpen(false);
    setDlError("");
    if (!savedSessionId) {
      setDlError("Save the session first.");
      return;
    }

    if (gradingProgress.pct < 100) {
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

  const gradeColor =
    sentenceGrade === null
      ? "text-slate-400"
      : sentenceGrade === "partial"
      ? "text-amber-600"
      : parseFloat(sentenceGrade) >= 7
      ? "text-green-700"
      : parseFloat(sentenceGrade) >= 4
      ? "text-amber-600"
      : "text-red-600";

  const previewHref = useMemo(() => {
    if (!savedSessionId) return undefined;
    const token = getAuthToken();
    if (!token) return `/api/preview/${savedSessionId}`;
    return `/api/preview/${savedSessionId}?token=${encodeURIComponent(token)}`;
  }, [savedSessionId]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">

      {/* ── Top bar ────────────────────────────────────────────────────── */}
      <div className="bg-white/95 backdrop-blur border-b border-slate-200 shadow-sm fixed top-0 left-0 right-0 z-30">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between gap-3">

          {/* Logo + filename */}
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <div className="text-blue-700 text-xl font-bold select-none shrink-0">◈</div>
            <div className="min-w-0 flex-1">
              <div className="text-xs sm:text-sm font-semibold text-slate-700 leading-tight flex items-center gap-1.5 min-w-0">
                <span className="truncate">Ontology Triple Grader</span>
                <span className="bg-blue-50 text-blue-700 border border-blue-200 text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider whitespace-nowrap shrink-0">v2.0</span>
              </div>
              <div className="text-xs text-slate-400 truncate max-w-[120px] sm:max-w-[240px]">{source_filename}</div>
            </div>
          </div>

          {/* Progress bar — hidden on small screens */}
          <div className="hidden lg:flex items-center gap-2 shrink-0">
            <span className="text-xs text-slate-500">
              {gradingProgress.graded}/{gradingProgress.total}
            </span>
            <div className="w-28 bg-slate-200 rounded-full h-2 overflow-hidden">
              <div className="bg-blue-600 h-2 rounded-full transition-all" style={{ width: `${gradingProgress.pct}%` }} />
            </div>
            <span className="text-xs font-semibold text-blue-700">{gradingProgress.pct}%</span>
          </div>

          {/* ── Save button + last-saved stamp ── */}
          <div className="flex items-center gap-2 shrink-0">
            {savedAt && (
              <div className="hidden sm:flex flex-col items-end">
                <span className="text-xs text-slate-400 leading-tight">Last saved</span>
                <span className="text-xs font-medium text-slate-500 leading-tight tabular-nums">
                  {savedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                </span>
              </div>
            )}
            <div className="flex flex-col items-end">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-700 text-white hover:bg-blue-800 active:scale-95 transition-all disabled:opacity-50 shadow-sm whitespace-nowrap cursor-pointer"
              >
                {saving ? "Saving…" : <><span className="hidden sm:inline">💾 Save</span><span className="sm:hidden">💾</span></>}
              </button>
              {saveMsg && <span className="text-xs text-emerald-600 mt-0.5 max-w-32 text-right leading-tight">{saveMsg}</span>}
              {saveError && <span className="text-xs text-red-500 mt-0.5 max-w-28 text-right leading-tight">{saveError}</span>}
            </div>
          </div>

          {/* ── Notification Bell Icon 🔔 ── */}
          <div className="relative shrink-0" ref={notificationsRef}>
            <button
              onClick={() => setNotificationsOpen(prev => !prev)}
              className={[
                "flex items-center justify-center w-8 h-8 rounded-lg text-slate-600 border border-slate-200 bg-white hover:bg-slate-50 transition-all relative cursor-pointer active:scale-95 shadow-sm",
                notifications.length > 0 ? "border-red-200 text-red-600 font-bold" : ""
              ].join(" ")}
              title="Notifications"
            >
              <span className="text-sm">🔔</span>
              {notifications.length > 0 && (
                <span className="absolute -top-1.5 -right-1.5 bg-red-600 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full leading-none scale-95 animate-pulse">
                  {notifications.length}
                </span>
              )}
            </button>

            {/* Notification Dropdown Panel */}
            {notificationsOpen && (
              <div className="absolute right-0 top-full mt-2 bg-white border border-slate-200 rounded-xl shadow-xl py-2 w-80 z-50 overflow-hidden flex flex-col max-h-[420px]">
                <div className="px-4 py-2 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                  <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">Notifications</span>
                  {notifications.length > 0 && (
                    <button
                      onClick={handleMarkAllNotificationsRead}
                      className="text-[10px] text-blue-600 hover:text-blue-800 font-bold border-0 bg-transparent cursor-pointer"
                    >
                      Mark all read
                    </button>
                  )}
                </div>

                <div className="flex-1 overflow-y-auto divide-y divide-slate-100 max-h-[300px]">
                  {notifications.length === 0 ? (
                    <div className="px-4 py-8 text-center text-xs text-slate-400">
                      <div className="text-2xl mb-1">✨</div>
                      You are all caught up!
                    </div>
                  ) : (
                    notifications.map((notif) => (
                      <div
                        key={notif.id}
                        onClick={() => handleNotificationClick(notif)}
                        className="px-4 py-3 hover:bg-slate-50 transition-colors cursor-pointer text-left space-y-1"
                      >
                        <div className="flex justify-between items-start gap-1">
                          <span className="text-xs font-bold text-slate-700 leading-snug">{notif.title}</span>
                          <span className="text-[9px] text-slate-400 whitespace-nowrap tabular-nums mt-0.5">
                            {formatCommentTimestamp(notif.createdAt)}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed break-words">{notif.text}</p>
                        <div className="text-[9px] font-semibold text-blue-600 flex items-center gap-1">
                          <span>Sentence #{notif.sentenceId}</span>
                          {notif.tripleId && (
                            <>
                              <span>•</span>
                              <span>Triple comment/suggestion</span>
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

          {/* ── Paper Quality & Process Indicators Button ── */}
          <button
            onClick={() => setShowPaperMetricsModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border border-blue-200 text-blue-700 bg-blue-50/50 hover:bg-blue-100 hover:border-blue-300 active:scale-95 transition-all shadow-sm whitespace-nowrap cursor-pointer shrink-0"
            title="View Paper Quality & Process Indicators"
          >
            📊 <span className="hidden sm:inline">Indicators</span>
          </button>

          {/* ── Download split button ── */}
          <div className="relative shrink-0" ref={dlRef}>
            <div className="flex rounded-lg overflow-hidden shadow-sm border border-green-600 bg-green-600">
              {/* Main: download in selected format */}
              <button
                onClick={() => handleDownload()}
                disabled={downloading || !savedSessionId}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold bg-green-600 text-white hover:bg-green-700 active:scale-95 transition-all disabled:opacity-40 whitespace-nowrap cursor-pointer"
              >
                {downloading ? "…" : <><span className="hidden sm:inline">⬇ Download</span><span className="sm:hidden">⬇</span></>}
              </button>
              {/* Chevron: open format picker */}
              <button
                onClick={() => setDlOpen((o) => !o)}
                disabled={downloading}
                className="px-2 py-1.5 text-xs font-bold bg-green-600 text-white hover:bg-green-700 border-l border-green-500 transition-all disabled:opacity-40 cursor-pointer"
                aria-label="Choose download format"
              >
                {dlOpen ? "▲" : "▼"}
              </button>
            </div>

            {/* Dropdown */}
            {dlOpen && (
              <div className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-36 z-50">
                {DL_FORMATS.map((f) => (
                  <button
                    key={f.value}
                    onClick={() => { setDlFmt(f.value); setDlOpen(false); }}
                    className={[
                      "w-full text-left flex items-center gap-2 px-4 py-2 text-sm transition-colors cursor-pointer",
                      f.value === dlFmt
                        ? "bg-green-50 text-green-700 font-semibold"
                        : "text-slate-700 hover:bg-slate-50",
                    ].join(" ")}
                  >
                    <span>{f.icon}</span>
                    {f.label}
                    {f.value === dlFmt && <span className="ml-auto text-green-500 text-xs">✔</span>}
                  </button>
                ))}
              </div>
            )}

            {dlError && (
              <p className="absolute right-0 top-full mt-8 text-xs text-red-500 whitespace-nowrap bg-white border border-red-200 rounded-lg px-2 py-1 shadow">
                {dlError}
              </p>
            )}
          </div>

          {/* ── View Online ── */}
          <a
            href={previewHref}
            target="_blank"
            rel="noopener noreferrer"
            onClick={!savedSessionId ? (e) => e.preventDefault() : undefined}
            className={[
              "hidden lg:flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all shrink-0 whitespace-nowrap",
              savedSessionId
                ? "border-slate-300 text-slate-600 hover:border-blue-400 hover:text-blue-700 hover:bg-blue-50"
                : "border-slate-200 text-slate-300 cursor-not-allowed",
            ].join(" ")}
            title={savedSessionId ? "Preview graded report in a new tab" : "Save the session first"}
          >
            👁 View
          </a>

          {/* ── Evaluate button ── */}
          {onEvaluate && (
            <button
              onClick={() => onEvaluate(savedSessionId, source_filename)}
              disabled={!savedSessionId}
              className={[
                "hidden lg:flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all shrink-0 whitespace-nowrap",
                savedSessionId
                  ? "border-purple-300 text-purple-700 hover:bg-purple-50 hover:border-purple-500"
                  : "border-slate-200 text-slate-300 cursor-not-allowed",
              ].join(" ")}
              title={savedSessionId ? "Run OpenIE evaluation" : "Save the session first"}
            >
              🔬 Evaluate
            </button>
          )}

          {/* Back to Dashboard */}
          <button
            onClick={onReset}
            className="hidden lg:flex text-xs text-slate-500 hover:text-blue-700 transition-colors px-2 py-1 rounded-lg hover:bg-blue-50 shrink-0 whitespace-nowrap items-center gap-1 cursor-pointer"
          >
            ← Dashboard
          </button>

          {/* ── More actions dropdown button (visible on screens below lg) ── */}
          <div className="relative shrink-0 lg:hidden" ref={moreRef}>
            <button
              onClick={() => setMoreOpen((o) => !o)}
              className="flex items-center justify-center p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 active:scale-95 transition-all text-xs font-semibold gap-1 cursor-pointer"
              title="More Actions"
            >
              <span>•••</span>
            </button>
            {moreOpen && (
              <div className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg py-1 min-w-40 z-50">
                <a
                  href={previewHref}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={!savedSessionId ? (e) => e.preventDefault() : undefined}
                  className={[
                    "w-full text-left flex items-center gap-2 px-4 py-2 text-sm transition-colors",
                    savedSessionId
                      ? "text-slate-700 hover:bg-slate-50"
                      : "text-slate-300 cursor-not-allowed",
                  ].join(" ")}
                >
                  <span>👁</span> View Online
                </a>
                {onEvaluate && (
                  <button
                    onClick={() => {
                      onEvaluate(savedSessionId, source_filename);
                      setMoreOpen(false);
                    }}
                    disabled={!savedSessionId}
                    className={[
                      "w-full text-left flex items-center gap-2 px-4 py-2 text-sm transition-colors cursor-pointer",
                      savedSessionId
                        ? "text-purple-700 hover:bg-purple-50"
                        : "text-slate-300 cursor-not-allowed",
                    ].join(" ")}
                  >
                    <span>🔬</span> Evaluate
                  </button>
                )}
                <button
                  onClick={() => {
                    setShowPaperMetricsModal(true);
                    setMoreOpen(false);
                  }}
                  className="w-full text-left flex items-center gap-2 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  <span>📊</span> Indicators
                </button>
                <div className="border-t border-slate-100 my-1"></div>
                <button
                  onClick={() => {
                    onReset();
                    setMoreOpen(false);
                  }}
                  className="w-full text-left flex items-center gap-2 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  <span>←</span> Dashboard
                </button>
              </div>
            )}
          </div>

        </div>

        {/* Inline status bar on small screens */}
        <div className="lg:hidden px-4 pb-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 shrink-0">
              {gradingProgress.graded}/{gradingProgress.total}
            </span>
            <div className="flex-1 bg-slate-200 rounded-full h-1.5 overflow-hidden">
              <div className="bg-blue-600 h-1.5 rounded-full transition-all" style={{ width: `${gradingProgress.pct}%` }} />
            </div>
            <span className="text-xs text-blue-700 font-semibold shrink-0">{gradingProgress.pct}%</span>
          </div>
        </div>
      </div>

      {/* ── Main content ───────────────────────────────────────────────── */}
      <div className="max-w-4xl mx-auto px-4 pb-8 space-y-6 pt-24">

        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-5">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <h2 className="text-sm font-semibold text-slate-700">Shared Grading Activity</h2>
              <p className="text-xs text-slate-500 mt-1">
                Collaborators can grade, suggest, and vote. Owner can vote and approve suggestions.
              </p>
            </div>
            <div className="text-xs text-slate-600">
              <span className="font-semibold text-slate-700">{graderSummary.totalUniqueGraders}</span> grader{graderSummary.totalUniqueGraders === 1 ? "" : "s"}
              <span className="mx-1 text-slate-300">|</span>
              Avg. Grade <span className="font-semibold text-blue-700">{graderSummary.overallAverage != null ? graderSummary.overallAverage.toFixed(2) : "—"}</span>
            </div>
          </div>
          {graderSummary.rows.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {graderSummary.rows.map((row) => {
                const isMe = row.user_id === currentUserId;
                return (
                  <span
                    key={row.user_id}
                    className={[
                      "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs",
                      isMe
                        ? "bg-blue-50 border-blue-300 text-blue-700"
                        : "bg-slate-50 border-slate-200 text-slate-700",
                    ].join(" ")}
                  >
                    <span className="font-semibold">{row.user_name}{isMe ? " (you)" : ""}</span>
                    <span className="text-slate-400">•</span>
                    <span>{row.graded_triples} triple{row.graded_triples === 1 ? "" : "s"}</span>
                    <span className="text-slate-400">•</span>
                    <span>{row.average_grade != null ? row.average_grade.toFixed(2) : "—"}/10</span>
                  </span>
                );
              })}
            </div>
          ) : (
            <p className="mt-3 text-xs text-slate-500">No grades yet.</p>
          )}
        </div>

        {/* Sentence card */}
        <div className={`bg-white shadow-md border border-slate-200 sticky top-[88px] lg:top-[60px] z-20 transition-all duration-300 ${isCollapsed ? 'p-3 rounded-xl' : 'p-6 rounded-2xl'}`}>
          {isCollapsed ? (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="bg-blue-700 text-white text-xs font-bold px-3 py-1 rounded-full shrink-0">
                    {currentIdx + 1} / {total}
                  </span>
                  <span className="text-sm text-slate-500 font-medium">Sentence</span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {/* Sentence metrics summary badges */}
                  {current.completeness !== null && current.completeness !== undefined && (
                    <span className="bg-green-50 border border-green-200 px-2 py-0.5 rounded text-[10px] font-bold text-green-700">
                      Comp: {current.completeness}/10
                    </span>
                  )}
                  {current.external_relation !== null && current.external_relation !== undefined && (
                    <span className="bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded text-[10px] font-bold text-indigo-700">
                      Rel: {current.external_relation}/10
                    </span>
                  )}

                  {/* Grade state */}
                  <div className={`text-right ${gradeColor}`}>
                    {sentenceGrade === null ? (
                      <span className="text-xs italic text-slate-400">
                        No triples graded
                      </span>
                    ) : sentenceGrade === "partial" ? (
                      <span className="text-xs font-semibold text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded">
                        Grading incomplete
                      </span>
                    ) : (
                      <span className="bg-blue-50 border border-blue-200 px-2 py-0.5 rounded text-[10px] font-bold text-blue-700">
                        Grade: {sentenceGrade}/10 avg
                      </span>
                    )}
                  </div>

                  {/* Navigation Controls */}
                  <div className="flex items-center gap-1 border-l border-slate-200 pl-2">
                    <button
                      onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
                      disabled={currentIdx === 0}
                      className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                      title="Previous Sentence"
                    >
                      ◀
                    </button>
                    <button
                      onClick={() => setCurrentIdx((i) => Math.min(total - 1, i + 1))}
                      disabled={currentIdx === total - 1}
                      className="p-1 rounded text-slate-400 hover:text-slate-600 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                      title="Next Sentence"
                    >
                      ▶
                    </button>
                  </div>
                </div>
              </div>

              {/* Sentence text */}
              <blockquote className="text-xs sm:text-sm text-slate-800 font-medium leading-relaxed border-l-4 border-blue-300 pl-3 bg-blue-50/40 py-1.5 pr-2 rounded-r-lg">
                {current.text}
              </blockquote>
            </div>
          ) : (
            <>
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className="bg-blue-700 text-white text-xs font-bold px-3 py-1 rounded-full">
                    {currentIdx + 1} / {total}
                  </span>
                  <span className="text-sm text-slate-500 font-medium">Sentence</span>
                </div>

                {/* Grade badge */}
                <div className={`text-right ${gradeColor}`}>
                  {sentenceGrade === null ? (
                    <span className="text-xs italic text-slate-400">
                      No triples graded
                    </span>
                  ) : sentenceGrade === "partial" ? (
                    <span className="text-xs font-semibold">Grading incomplete</span>
                  ) : (
                    <div className="flex flex-col items-end">
                      <span className="text-2xl font-bold leading-none">
                        {sentenceGrade}
                      </span>
                      <span className="text-xs">/ 10 avg</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Sentence text */}
              <blockquote className="text-base text-slate-800 font-medium leading-relaxed border-l-4 border-blue-300 pl-4 bg-blue-50/40 py-2 pr-2 rounded-r-xl">
                {current.text}
              </blockquote>

              <div className="mt-5 border-t border-slate-100 pt-4 space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Sentence-level Metrics
                </h3>

                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-xs font-semibold text-slate-500 w-40 shrink-0">Completeness (0-10)</span>
                  <div className="flex items-center gap-1 flex-wrap">
                    {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                      <button
                        key={`comp-${n}`}
                        onClick={() => handleSentenceMetricChange("completeness", n)}
                        disabled={!canEditSession}
                        className={[
                          "w-6 h-6 rounded text-xs font-semibold border transition-all",
                          "focus:outline-none focus:ring-2 focus:ring-green-400",
                          current.completeness === n
                            ? "bg-green-600 text-white border-green-600 scale-110 shadow"
                            : "bg-white text-slate-600 border-slate-300 hover:bg-green-50 hover:border-green-400",
                          !canEditSession ? "opacity-70 cursor-not-allowed" : "",
                        ].join(" ")}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                  {current.completeness !== null && current.completeness !== undefined ? (
                    <span className="ml-1 text-xs font-bold text-green-700 bg-green-50 px-2 py-0.5 rounded-full border border-green-200">
                      {current.completeness}/10
                    </span>
                  ) : (
                    <span className="ml-1 text-xs text-slate-400 italic">not set</span>
                  )}

                  {current.completeness_average !== null && current.completeness_average !== undefined && (
                    <span className="ml-1 text-xs font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
                      Avg. {Number(current.completeness_average).toFixed(2)} ({current.completeness_count || 0})
                    </span>
                  )}

                  {completenessMetricEntries.length > 0 && (
                    <div className="w-full sm:pl-[10.4rem] flex flex-wrap gap-1.5 mt-1">
                      {completenessMetricEntries.map((entry) => {
                        const isMe = currentUserId && entry.userId === currentUserId;
                        return (
                          <span
                            key={`comp-${entry.userId}`}
                            className={[
                              "text-xs font-medium border px-2 py-1 rounded-full",
                              isMe
                                ? "bg-green-100 text-green-800 border-green-300"
                                : "bg-slate-100 text-slate-700 border-slate-300",
                            ].join(" ")}
                          >
                            {entry.userName}
                            {isMe ? " (you)" : ""}
                            : {entry.value}/10
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-xs font-semibold text-slate-500 w-40 shrink-0">External Relation (0-10)</span>
                  <div className="flex items-center gap-1 flex-wrap">
                    {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                      <button
                        key={`rel-${n}`}
                        onClick={() => handleSentenceMetricChange("external_relation", n)}
                        disabled={!canEditSession}
                        className={[
                          "w-6 h-6 rounded text-xs font-semibold border transition-all",
                          "focus:outline-none focus:ring-2 focus:ring-indigo-400",
                          current.external_relation === n
                            ? "bg-indigo-600 text-white border-indigo-600 scale-110 shadow"
                            : "bg-white text-slate-600 border-slate-300 hover:bg-indigo-50 hover:border-indigo-400",
                          !canEditSession ? "opacity-70 cursor-not-allowed" : "",
                        ].join(" ")}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                  {current.external_relation !== null && current.external_relation !== undefined ? (
                    <span className="ml-1 text-xs font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200">
                      {current.external_relation}/10
                    </span>
                  ) : (
                    <span className="ml-1 text-xs text-slate-400 italic">not set</span>
                  )}

                  {current.external_relation_average !== null && current.external_relation_average !== undefined && (
                    <span className="ml-1 text-xs font-semibold text-slate-700 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
                      Avg. {Number(current.external_relation_average).toFixed(2)} ({current.external_relation_count || 0})
                    </span>
                  )}

                  {externalRelationMetricEntries.length > 0 && (
                    <div className="w-full sm:pl-[10.4rem] flex flex-wrap gap-1.5 mt-1">
                      {externalRelationMetricEntries.map((entry) => {
                        const isMe = currentUserId && entry.userId === currentUserId;
                        return (
                          <span
                            key={`rel-${entry.userId}`}
                            className={[
                              "text-xs font-medium border px-2 py-1 rounded-full",
                              isMe
                                ? "bg-indigo-100 text-indigo-800 border-indigo-300"
                                : "bg-slate-100 text-slate-700 border-slate-300",
                            ].join(" ")}
                          >
                            {entry.userName}
                            {isMe ? " (you)" : ""}
                            : {entry.value}/10
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Navigation arrows */}
              <div className="flex items-center justify-between mt-5">
                <button
                  onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
                  disabled={currentIdx === 0}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                >
                  ← Previous
                </button>

                {/* Dot navigator */}
                <div className="hidden sm:flex gap-1 flex-wrap justify-center max-w-xs">
                  {sentences.map((s, i) => {
                    const allGraded = s.triples.every((t) => t.grade !== null);
                    const anyGraded = s.triples.some((t) => t.grade !== null);
                    return (
                      <button
                        key={s.id}
                        onClick={() => setCurrentIdx(i)}
                        title={`Sentence ${i + 1}`}
                        className={[
                          "w-3 h-3 rounded-full transition-all",
                          i === currentIdx
                            ? "bg-blue-700 scale-125"
                            : allGraded
                            ? "bg-green-500"
                            : anyGraded
                            ? "bg-amber-400"
                            : "bg-slate-300 hover:bg-slate-400",
                        ].join(" ")}
                      />
                    );
                  })}
                </div>

                <button
                  onClick={() =>
                    setCurrentIdx((i) => Math.min(total - 1, i + 1))
                  }
                  disabled={currentIdx === total - 1}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                >
                  Next →
                </button>
              </div>
            </>
          )}
        </div>

        {/* Triples */}
        <div>
          <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
            Triples ({current.triples.length})
          </h2>
          <div className="space-y-4">
            {current.triples.map((triple, idx) => {
              const htmlId = `triple-card-${triple.id}`;
              const isHighlighted = highlightedElementId === htmlId;
              return (
                <div
                  key={triple.id}
                  id={htmlId}
                  className={[
                    "bg-white rounded-xl shadow-md border overflow-hidden transition-all duration-500",
                    isHighlighted ? "ring-4 ring-amber-400 border-amber-400 scale-[1.01] shadow-lg" : "border-slate-200"
                  ].join(" ")}
                >
                  {/* Triple number pill */}
                  <div className="bg-gradient-to-r from-blue-600 to-blue-500 px-4 py-1.5 flex items-center gap-2">
                    <span className="text-white text-[11px] font-bold uppercase tracking-wider">
                      Triple {idx + 1}
                    </span>
                    {triple.grade_average !== null && triple.grade_average !== undefined && (
                      <span className="ml-auto bg-white/20 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
                        Avg. Grade: {Number(triple.grade_average).toFixed(2)}/10
                      </span>
                    )}
                  </div>
                  <TripleCard
                    triple={triple}
                    grade={triple.grade}
                    author={triple.author}
                    gradesByUser={triple.grades_by_user}
                    currentUserId={currentUserId}
                    readOnly={!canEditSession}
                    canSuggest={canSuggestTriples}
                    canApprove={canApproveSuggestions}
                    onChange={(grade) => handleGradeChange(triple.id, grade)}
                    onAddTripleComment={(tripleId, comment) => handleAddTripleComment(tripleId, comment)}
                    onDeleteTripleComment={(tripleId, commentId) => handleDeleteTripleComment(tripleId, commentId)}
                    onMarkForRemoval={(tripleId, marked) => handleMarkTripleForRemoval(tripleId, marked)}
                    onAddTripleAdjacent={(tripleId, direction) => handleAddTripleAdjacent(tripleId, direction)}
                    onRemoveSuggestedTriple={(tripleId) => handleRemoveSuggestedTriple(tripleId)}
                    onApproveSuggestedTriple={(tripleId) => handleApproveSuggestedTriple(tripleId)}
                    onSaveSuggestedTriple={(tripleId, fields) => handleSaveSuggestedTriple(tripleId, fields)}
                    onSetTripleEditing={(tripleId, isEditing) => handleSetTripleEditing(tripleId, isEditing)}
                  />
                  {(!triple.is_new_suggestion || triple.status === "approved") && (
                    <TripleSuggestions
                      triple={triple}
                      currentUser={currentUser}
                      canSuggest={canSuggestTriples}
                      canApprove={canApproveSuggestions}
                      onAddSuggestion={(data) => handleAddSuggestion(triple.id, data)}
                      onEditSuggestion={(suggestionId, data) => handleEditSuggestion(triple.id, suggestionId, data)}
                      onVoteSuggestion={(suggestionId, vote) => handleVoteSuggestion(triple.id, suggestionId, vote)}
                      onDeleteSuggestion={(suggestionId) => handleDeleteSuggestion(triple.id, suggestionId)}
                      onApproveSuggestion={(suggestionId, isApproved) => handleToggleSuggestionApproval(triple.id, suggestionId, isApproved)}
                      onAddSuggestionReply={handleAddSuggestionReply}
                      onDeleteSuggestionReply={handleDeleteSuggestionReply}
                    />
                  )}
                  <TripleComments
                    tripleId={triple.id}
                    comments={triple?.triple_comments || []}
                    currentUserId={currentUserId}
                    currentUserName={currentUserName}
                    readOnly={!canEditSession}
                    onAddComment={(comment) => handleAddTripleComment(triple.id, comment)}
                    onDeleteComment={(commentId) => handleDeleteTripleComment(triple.id, commentId)}
                    onAddReply={(commentId, reply) => handleAddTripleCommentReply(triple.id, commentId, reply)}
                    onDeleteReply={(commentId, replyId) => handleDeleteTripleCommentReply(triple.id, commentId, replyId)}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* Suggestion */}
        <div
          id={`sentence-comment-box-${current.id}`}
          className={[
            "bg-white rounded-2xl shadow-sm border p-5 transition-all duration-500",
            highlightedElementId === `sentence-comment-box-${current.id}`
              ? "ring-4 ring-amber-400 border-amber-400 scale-[1.01] shadow-lg"
              : "border-slate-200"
          ].join(" ")}
        >
          <label className="block text-sm font-semibold text-slate-600 mb-2">
            Suggestion / Comment for this Sentence
          </label>
          <textarea
            value={current.suggestion}
            onChange={(e) => handleSuggestionChange(e.target.value)}
            rows={3}
            disabled={!canEditSession}
            placeholder="Add any suggestions or notes about the quality, accuracy or completeness of the triples for this sentence…"
            className="w-full text-sm text-slate-700 border border-slate-200 rounded-xl p-3 resize-none focus:outline-none focus:ring-2 focus:ring-blue-300 focus:border-blue-400 placeholder:text-slate-300 disabled:bg-slate-100 disabled:text-slate-500"
          />
          <div className="mt-2 flex items-center gap-2 flex-wrap">
            <button
              onClick={handlePostSentenceComment}
              disabled={!canEditSession || saving || !(current.suggestion || "").trim()}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "Posting..." : "Post Comment"}
            </button>
            <span className="text-xs text-slate-500">
              Posts immediately with your name and is visible to collaborators.
            </span>
          </div>
          {currentSentenceComments.length > 0 ? (
            <div className="mt-3 space-y-2">
              {currentSentenceComments.map((comment) => (
                <div
                  key={comment.id}
                  className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2"
                >
                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span className="font-semibold text-slate-700">{comment.author || "User"}</span>
                    <span className="text-slate-300">•</span>
                    <span>{formatCommentTimestamp(comment.created_at)}</span>
                  </div>
                  <p className="mt-1 text-sm text-slate-700 whitespace-pre-wrap break-words">
                    {comment.text}
                  </p>

                  {/* Sentence Comment Reply actions */}
                  {canEditSession && (
                    <div className="mt-2 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setReplyingToSentenceCommentId(replyingToSentenceCommentId === comment.id ? null : comment.id);
                          setSentenceCommentReplyText("");
                        }}
                        className="text-[10px] font-bold text-blue-600 hover:text-blue-800 transition-colors cursor-pointer"
                      >
                        Reply
                      </button>
                    </div>
                  )}

                  {/* Nested Sentence Comment Reply Form */}
                  {canEditSession && replyingToSentenceCommentId === comment.id && (
                    <div className="pl-3 border-l-2 border-blue-200 mt-2 space-y-1.5">
                      <textarea
                        value={sentenceCommentReplyText}
                        onChange={(e) => setSentenceCommentReplyText(e.target.value)}
                        placeholder="Write a reply…"
                        rows={1}
                        className="w-full text-xs border border-slate-200 rounded p-1.5 resize-none focus:outline-none focus:ring-1 focus:ring-blue-300 focus:border-blue-400 placeholder:text-slate-300"
                      />
                      <div className="flex gap-1">
                        <button
                          type="button"
                          onClick={async () => {
                            const text = String(sentenceCommentReplyText || "").trim();
                            if (!text) return;
                            const newReply = {
                              id: `reply_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
                              author: currentUserName || "User",
                              user_id: currentUserId || "",
                              text,
                              created_at: new Date().toISOString(),
                            };
                            await handleAddSentenceCommentReply(comment.id, newReply);
                            setSentenceCommentReplyText("");
                            setReplyingToSentenceCommentId(null);
                          }}
                          disabled={!sentenceCommentReplyText.trim()}
                          className="text-[10px] px-2 py-0.5 rounded bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium cursor-pointer"
                        >
                          Reply
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setReplyingToSentenceCommentId(null);
                            setSentenceCommentReplyText("");
                          }}
                          className="text-[10px] px-2 py-0.5 rounded bg-slate-200 text-slate-700 hover:bg-slate-300 transition-colors font-medium cursor-pointer"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Nested Sentence Comment Replies List */}
                  {comment.replies && comment.replies.length > 0 && (
                    <div className="pl-3 border-l-2 border-blue-200 mt-2 space-y-2">
                      {comment.replies.map((reply) => (
                        <div key={reply.id} className="bg-white border border-slate-100 rounded p-2 text-[11px] leading-relaxed">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1 flex-wrap text-[10px] text-slate-500">
                                <span className="font-semibold text-slate-700">{reply.author || "User"}</span>
                                <span>•</span>
                                <span>{formatCommentTimestamp(reply.created_at)}</span>
                              </div>
                              <p className="text-slate-600 mt-0.5 break-words">{reply.text}</p>
                            </div>
                            {canEditSession && reply.user_id === currentUserId && (
                              <button
                                type="button"
                                onClick={() => {
                                  if (window.confirm("Remove this reply?")) {
                                    handleDeleteSentenceCommentReply(comment.id, reply.id);
                                  }
                                }}
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
          ) : (
            <p className="mt-3 text-xs text-slate-400 italic">No comments yet for this sentence.</p>
          )}
          <p className="mt-2 text-xs text-slate-500">
            Shared mode: collaborators grade, suggest, and vote; owner votes and approves.
          </p>
        </div>

        {/* ── Paper Quality & Process Indicators Modal ── */}
        {showPaperMetricsModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
              className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm transition-opacity"
              onClick={() => setShowPaperMetricsModal(false)}
            />
            
            {/* Modal Content */}
            <div className="bg-white rounded-2xl shadow-2xl border border-slate-100 max-w-2xl w-full max-h-[85vh] flex flex-col relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
              {/* Header */}
              <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50 shrink-0">
                <div className="flex items-center gap-2 text-left">
                  <span className="text-xl">📊</span>
                  <div>
                    <h3 className="text-base font-bold text-slate-800">Paper Quality & Process Indicators</h3>
                    <p className="text-[11px] text-slate-500">Live statistics mapped to the scientific paper evaluation criteria</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowPaperMetricsModal(false)}
                  className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors font-bold cursor-pointer border-0 bg-transparent"
                >
                  ✕
                </button>
              </div>

              {/* Content Body */}
              <div className="p-6 overflow-y-auto space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                  {/* Metric cards */}
                  <div className="bg-slate-50/80 rounded-xl p-4 border border-slate-100 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Source Sentences</span>
                      <p className="text-2xl font-extrabold text-slate-800 mt-1">{paperMetrics.totalSentences}</p>
                    </div>
                    <span className="text-slate-300 text-2xl font-light">📝</span>
                  </div>

                  <div className="bg-slate-50/80 rounded-xl p-4 border border-slate-100 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Final Gold Triples</span>
                      <p className="text-2xl font-extrabold text-slate-800 mt-1">{paperMetrics.totalGoldTriples}</p>
                    </div>
                    <span className="text-slate-300 text-2xl font-light">✨</span>
                  </div>

                  <div className="bg-slate-50/80 rounded-xl p-4 border border-slate-100 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Avg Triples / Sentence</span>
                      <p className="text-2xl font-extrabold text-slate-800 mt-1">{paperMetrics.avgTriplesPerSentence}</p>
                    </div>
                    <span className="text-slate-300 text-2xl font-light">📊</span>
                  </div>

                  <div className="bg-slate-50/80 rounded-xl p-4 border border-slate-100 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">Annotators & Reviewers</span>
                      <p className="text-2xl font-extrabold text-slate-800 mt-1">{paperMetrics.numUsers}</p>
                    </div>
                    <span className="text-slate-300 text-2xl font-light">👥</span>
                  </div>
                </div>

                {/* Detail Table */}
                <div className="border border-slate-150 rounded-xl overflow-hidden shadow-sm bg-white mt-4">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-50 border-b border-slate-150 text-slate-500 font-bold uppercase tracking-wider text-[10px]">
                        <th className="px-4 py-3">Quality & Process Indicator Metric</th>
                        <th className="px-4 py-3 text-right">Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700">
                      <tr>
                        <td className="px-4 py-3 font-medium text-left">Percentage of sentences in calibration phase</td>
                        <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">{paperMetrics.calibrationPct}%</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-medium text-left">Pilot-stage triple overlap / Approximate F1</td>
                        <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">{paperMetrics.evalF1}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-medium text-left">Reviewer agreement on candidate-triple decisions</td>
                        <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">{paperMetrics.agreementPct}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-medium text-left">Triples accepted without change</td>
                        <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">
                          {paperMetrics.acceptedWithoutChange} <span className="text-slate-400 font-normal">({paperMetrics.acceptedPct}%)</span>
                        </td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-medium text-left">Triples modified after review</td>
                        <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">
                          {paperMetrics.modifiedAfterReview} <span className="text-slate-400 font-normal">({paperMetrics.modifiedPct}%)</span>
                        </td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-medium text-left">Rejected triples</td>
                        <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">{paperMetrics.rejectedTriples}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-medium text-left">Missing triples suggested & added after adjudication</td>
                        <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">{paperMetrics.missingTriplesAdded}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-medium text-left">Method-level adjudication cases <span className="text-slate-400 font-normal text-[10px]">(general comments)</span></td>
                        <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">{paperMetrics.methodAdjudicationCount}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-medium text-left">Triple-level adjudication cases <span className="text-slate-400 font-normal text-[10px]">(triple comments/replies)</span></td>
                        <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">{paperMetrics.tripleAdjudicationCount}</td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-medium text-left">Guideline updates or documented method decisions</td>
                        <td className="px-4 py-3 text-right font-semibold tabular-nums text-slate-900">{paperMetrics.numGuidelineUpdates}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Extra note / help */}
                <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-3.5 flex items-start gap-2.5 mt-2 text-left">
                  <span className="text-blue-600 mt-0.5 text-sm">ℹ</span>
                  <p className="text-[11px] leading-relaxed text-blue-800">
                    <strong>How Adjudications are Determined:</strong> As requested, sentence-level adjudication events are tracked via general comments on the sentence (which discuss overall method and guidelines). Triple-level adjudication events are tracked via comments and discussion replies on individual triples and candidate suggestions. These metrics are dynamically calculated in real-time and will be rendered on the cover sheet when exporting a PDF report.
                  </p>
                </div>
              </div>

              {/* Footer */}
              <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end gap-2 shrink-0">
                <button
                  onClick={() => setShowPaperMetricsModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 active:scale-95 transition-all cursor-pointer"
                >
                  Close View
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Download Warning Modal ── */}
        {showDownloadWarningModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            {/* Backdrop */}
            <div
              className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm transition-opacity"
              onClick={() => {
                setShowDownloadWarningModal(false);
                setPendingDownloadFormat(null);
              }}
            />
            
            {/* Modal Content */}
            <div className="bg-white rounded-2xl shadow-2xl border border-slate-100 max-w-md w-full relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
              <div className="p-6">
                <div className="flex items-center gap-3 text-amber-600">
                  <span className="text-2xl text-left">⚠️</span>
                  <h3 className="text-base font-bold text-slate-800">Incomplete Grading Session</h3>
                </div>
                
                <p className="mt-3 text-xs text-slate-600 leading-relaxed text-left">
                  This document is currently only <strong className="text-slate-800 font-bold">{gradingProgress.pct}%</strong> graded (<strong className="text-slate-800 font-semibold">{gradingProgress.graded}</strong> of <strong className="text-slate-800 font-semibold">{gradingProgress.total}</strong> active triples have been graded).
                </p>

                <div className="mt-3 bg-amber-50 border border-amber-200 rounded-xl p-3 flex items-start gap-2.5 text-left">
                  <span className="text-amber-700 text-xs">⚠️</span>
                  <p className="text-[10px] leading-normal text-amber-800">
                    Downloading the report before completing the grading process will lead to incomplete or inaccurate quality and process statistics in the exported files.
                  </p>
                </div>
              </div>

              {/* Footer */}
              <div className="px-6 py-4 bg-slate-50 border-t border-slate-100 flex justify-end gap-2">
                <button
                  onClick={() => {
                    setShowDownloadWarningModal(false);
                    setPendingDownloadFormat(null);
                  }}
                  className="px-3.5 py-1.5 text-xs font-semibold text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 active:scale-95 transition-all cursor-pointer"
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
                  className="px-3.5 py-1.5 text-xs font-bold text-white bg-amber-600 hover:bg-amber-700 rounded-lg active:scale-95 transition-all cursor-pointer"
                >
                  Download Anyway
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="h-8" />
      </div>
    </div>
  );
}
