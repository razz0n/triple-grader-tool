// api.js — Axios wrappers for all backend API calls

import axios from "axios";

const AUTH_TOKEN_KEY = "otg_auth_token";

// In production the frontend is served by FastAPI on the same origin, so
// relative paths work. In dev, Vite proxies /api/* to http://localhost:8001.
const API = axios.create({ baseURL: "" });

export function getAuthToken() {
  return sessionStorage.getItem(AUTH_TOKEN_KEY);
}

export function setAuthToken(token) {
  if (token) {
    sessionStorage.setItem(AUTH_TOKEN_KEY, token);
  } else {
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
  }
}

API.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

API.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      setAuthToken(null);
      // Dispatch a global event so App can redirect to login immediately
      window.dispatchEvent(new CustomEvent('auth:logout'));
    }
    return Promise.reject(error);
  }
);

export async function registerUser(name, username, email, password, security_question, security_answer) {
  const { data } = await API.post("/api/auth/register", { name, username, email, password, security_question, security_answer });
  return data;
}

export async function loginUser(login, password) {
  const { data } = await API.post("/api/auth/login", { login, password });
  setAuthToken(data.access_token);
  return data.user;
}

export async function meUser() {
  const { data } = await API.get("/api/auth/me");
  return data;
}

export async function logoutUser() {
  try {
    await API.post("/api/auth/logout");
  } finally {
    setAuthToken(null);
  }
}

/**
 * Upload a file for parsing.
 * @param {File} file
 * @returns {Promise<{session_id, source_filename, uploaded_at, total_sentences, sentences}>}
 */
export async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await API.post("/api/upload", form);
  return data;
}

/**
 * Save a graded session to the server.
 * @param {object} session
 * @returns {Promise<{session_id, saved_at}>}
 */
export async function saveSession(session) {
  const { data } = await API.post("/api/save", session);
  return data;
}

/**
 * Download a graded session in the chosen format.
 * @param {string} sessionId
 * @param {"json"|"csv"|"excel"|"pdf"|"word"} fmt
 */
export async function downloadSession(sessionId, fmt) {
  let response;
  try {
    response = await API.get(`/api/download/${sessionId}/${fmt}`, {
      responseType: "blob",
    });
  } catch (e) {
    // axios error responses with responseType:"blob" arrive as Blobs —
    // decode to get the actual error detail from the server.
    if (e?.response?.data instanceof Blob) {
      const text = await e.response.data.text();
      let msg = `Download failed (HTTP ${e.response.status})`;
      try { msg = JSON.parse(text).detail || msg; } catch {
        // Keep fallback message when blob is not valid JSON.
      }
      throw new Error(msg);
    }
    throw e;
  }

  const disposition = response.headers["content-disposition"] || "";
  let filename = `graded.${fmt === "excel" ? "xlsx" : fmt === "word" ? "docx" : fmt}`;
  const match = disposition.match(/filename="([^"]+)"/);
  if (match) filename = match[1];

  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * List all saved sessions.
 * @returns {Promise<Array>}
 */
export async function listSessions() {
  const { data } = await API.get("/api/sessions");
  return data;
}

/**
 * Load a full saved session by ID (used to resume a previous session).
 * @param {string} sessionId
 * @returns {Promise<object>}
 */
export async function loadSession(sessionId) {
  const { data } = await API.get(`/api/session/${sessionId}`);
  return data;
}

/**
 * Delete a saved session (owner only).
 * @param {string} sessionId
 * @returns {Promise<{ok: boolean, deleted_session_id: string}>}
 */
export async function deleteSession(sessionId) {
  const { data } = await API.delete(`/api/session/${sessionId}`);
  return data;
}

/**
 * Add a suggestion to a triple.
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} tripleId
 * @param {string} subject
 * @param {string} predicate
 * @param {string} object
 * @param {string} reason
 * @returns {Promise<{suggestion_id, ok}>}
 */
export async function addSuggestion(sessionId, sentenceId, tripleId, subject, predicate, object, reason = "") {
  const { data } = await API.post("/api/suggestions/add", {
    session_id: sessionId,
    sentence_id: sentenceId,
    triple_id: tripleId,
    subject,
    predicate,
    object,
    reason,
  });
  return data;
}

/**
 * Vote on a suggestion.
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} tripleId
 * @param {string} suggestionId
 * @param {string} vote
 * @returns {Promise<{ok}>}
 */
export async function voteOnSuggestion(sessionId, sentenceId, tripleId, suggestionId, vote) {
  const { data } = await API.post("/api/suggestions/vote", {
    session_id: sessionId,
    sentence_id: sentenceId,
    triple_id: tripleId,
    suggestion_id: suggestionId,
    vote,
  });
  return data;
}

/**
 * Edit a suggestion.
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} tripleId
 * @param {string} suggestionId
 * @param {string} subject
 * @param {string} predicate
 * @param {string} object
 * @param {string} reason
 * @returns {Promise<{ok}>}
 */
export async function editSuggestion(sessionId, sentenceId, tripleId, suggestionId, subject, predicate, object, reason = "") {
  const { data } = await API.post("/api/suggestions/edit", {
    session_id: sessionId,
    sentence_id: sentenceId,
    triple_id: tripleId,
    suggestion_id: suggestionId,
    subject,
    predicate,
    object,
    reason,
  });
  return data;
}

/**
 * Delete a suggestion.
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} tripleId
 * @param {string} suggestionId
 * @returns {Promise<{ok}>}
 */
export async function deleteSuggestion(sessionId, sentenceId, tripleId, suggestionId) {
  const { data } = await API.delete(`/api/suggestions/${sessionId}/${sentenceId}/${tripleId}/${suggestionId}`);
  return data;
}

/**
 * Approve a suggestion (owner only) and apply it to the triple.
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} tripleId
 * @param {string} suggestionId
 * @returns {Promise<{ok: boolean, triple: object}>}
 */
export async function approveSuggestion(sessionId, sentenceId, tripleId, suggestionId) {
  const { data } = await API.post("/api/suggestions/approve", {
    session_id: sessionId,
    sentence_id: sentenceId,
    triple_id: tripleId,
    suggestion_id: suggestionId,
  });
  return data;
}

/**
 * Undo approval for a suggestion (owner only).
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} tripleId
 * @param {string} suggestionId
 * @returns {Promise<{ok: boolean}>}
 */
export async function unapproveSuggestion(sessionId, sentenceId, tripleId, suggestionId) {
  const { data } = await API.post("/api/suggestions/unapprove", {
    session_id: sessionId,
    sentence_id: sentenceId,
    triple_id: tripleId,
    suggestion_id: suggestionId,
  });
  return data;
}

/**
 * Preview evaluation: returns sentence metadata without running stanza.
 * @param {string} sessionId
 * @param {"graded_only"|"all"} goldSource
 * @returns {Promise<object>} preview data
 */
export async function previewEvaluation(sessionId, goldSource = "graded_only") {
  const { data } = await API.post(`/api/evaluate/${sessionId}/preview`, {
    gold_source: goldSource,
  });
  return data;
}

/**
 * Run OpenIE evaluation for a session.
 * @param {string} sessionId
 * @param {"exact"|"soft"} matchMode
 * @param {"graded_only"|"all"} goldSource
 * @returns {Promise<object>} evaluation result
 */
export async function runEvaluation(sessionId, matchMode = "soft", goldSource = "graded_only") {
  const { data } = await API.post(`/api/evaluate/${sessionId}`, {
    match_mode: matchMode,
    gold_source: goldSource,
  });
  return data;
}

/**
 * Download evaluation results as JSON or CSV.
 * @param {string} sessionId
 * @param {"json"|"csv"} fmt
 */
export async function downloadEvaluation(sessionId, fmt) {
  let response;
  try {
    response = await API.get(`/api/evaluate/${sessionId}/download/${fmt}`, {
      responseType: "blob",
    });
  } catch (e) {
    if (e?.response?.data instanceof Blob) {
      const text = await e.response.data.text();
      let msg = `Download failed (HTTP ${e.response.status})`;
      try { msg = JSON.parse(text).detail || msg; } catch {
        // Keep fallback message when blob is not valid JSON.
      }
      throw new Error(msg);
    }
    throw e;
  }

  const disposition = response.headers["content-disposition"] || "";
  let filename = `evaluation.${fmt}`;
  const match = disposition.match(/filename="([^"]+)"/);
  if (match) filename = match[1];

  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * Add a comment to a triple.
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} tripleId
 * @param {string} commentText
 * @returns {Promise<{ok: boolean}>}
 */
export async function addTripleComment(sessionId, sentenceId, tripleId, commentText) {
  const { data } = await API.post("/api/triples/comments/add", {
    session_id: sessionId,
    sentence_id: sentenceId,
    triple_id: tripleId,
    text: commentText,
  });
  return data;
}

/**
 * Delete a comment from a triple.
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} tripleId
 * @param {string} commentId
 * @returns {Promise<{ok: boolean}>}
 */
export async function deleteTripleComment(sessionId, sentenceId, tripleId, commentId) {
  const { data } = await API.delete(`/api/triples/comments/${sessionId}/${sentenceId}/${tripleId}/${commentId}`);
  return data;
}

/**
 * Mark a triple as not needed / request removal.
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} tripleId
 * @param {boolean} marked
 * @returns {Promise<{ok: boolean}>}
 */
export async function markTripleForRemoval(sessionId, sentenceId, tripleId, marked) {
  const { data } = await API.post("/api/triples/mark-removal", {
    session_id: sessionId,
    sentence_id: sentenceId,
    triple_id: tripleId,
    marked,
  });
  return data;
}

/**
 * Add a reply to a comment (either sentence level or triple level).
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string|null} tripleId
 * @param {string} commentId
 * @param {string} text
 * @returns {Promise<{ok: boolean, reply: object}>}
 */
export async function replyToComment(sessionId, sentenceId, tripleId, commentId, text, parentReplyId = null) {
  const { data } = await API.post("/api/comments/reply", {
    session_id: sessionId,
    sentence_id: sentenceId,
    triple_id: tripleId,
    comment_id: commentId,
    text,
    parent_reply_id: parentReplyId,
  });
  return data;
}

/**
 * Delete a comment reply.
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} commentId
 * @param {string} replyId
 * @param {string|null} tripleId
 * @returns {Promise<{ok: boolean}>}
 */
export async function deleteCommentReply(sessionId, sentenceId, commentId, replyId, tripleId = null) {
  const url = `/api/comments/reply/${sessionId}/${sentenceId}/${commentId}/${replyId}`;
  const { data } = await API.delete(url, {
    params: tripleId ? { triple_id: tripleId } : {},
  });
  return data;
}

/**
 * Add a reply to a suggestion.
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} tripleId
 * @param {string} suggestionId
 * @param {string} text
 * @returns {Promise<{ok: boolean, reply: object}>}
 */
export async function replyToSuggestion(sessionId, sentenceId, tripleId, suggestionId, text, parentReplyId = null) {
  const { data } = await API.post("/api/suggestions/reply", {
    session_id: sessionId,
    sentence_id: sentenceId,
    triple_id: tripleId,
    suggestion_id: suggestionId,
    text,
    parent_reply_id: parentReplyId,
  });
  return data;
}

/**
 * Delete a reply to a suggestion.
 * @param {string} sessionId
 * @param {number} sentenceId
 * @param {string} tripleId
 * @param {string} suggestionId
 * @param {string} replyId
 * @returns {Promise<{ok: boolean}>}
 */
export async function deleteSuggestionReply(sessionId, sentenceId, tripleId, suggestionId, replyId) {
  const { data } = await API.delete(`/api/suggestions/reply/${sessionId}/${sentenceId}/${tripleId}/${suggestionId}/${replyId}`);
  return data;
}

/**
 * Mark a specific notification item as read.
 * @param {string} sessionId
 * @param {string} itemId
 * @returns {Promise<{ok: boolean}>}
 */
export async function markNotificationRead(sessionId, itemId) {
  const { data } = await API.post("/api/notifications/read", {
    session_id: sessionId,
    item_id: itemId,
  });
  return data;
}

/**
 * Mark all notifications in a session as read.
 * @param {string} sessionId
 * @returns {Promise<{ok: boolean}>}
 */
export async function markAllNotificationsRead(sessionId) {
  const { data } = await API.post("/api/notifications/read-all", {
    session_id: sessionId,
  });
  return data;
}

/**
 * Update user profile settings.
 * @param {object} profileData
 * @returns {Promise<{ok: boolean, user: object}>}
 */
export async function updateProfile(profileData) {
  const { data } = await API.put("/api/auth/profile", profileData);
  return data;
}

/**
 * Fetch a user's security question.
 * @param {string} login
 * @returns {Promise<{security_question: string, login: string}>}
 */
export async function getSecurityQuestion(login) {
  const { data } = await API.post("/api/auth/forgot-password/question", { login });
  return data;
}

/**
 * Reset password using security question verification.
 * @param {string} login
 * @param {string} answer
 * @param {string} password
 * @returns {Promise<{ok: boolean, message: string}>}
 */
export async function resetPasswordWithQuestion(login, answer, password) {
  const { data } = await API.post("/api/auth/forgot-password/reset", { login, answer, password });
  return data;
}

/**
 * Delete user account.
 * @param {string} password
 * @param {string} securityAnswer
 * @returns {Promise<{ok: boolean, message: string}>}
 */
export async function deleteAccount(password, securityAnswer) {
  const { data } = await API.post("/api/auth/delete-account", { password, security_answer: securityAnswer });
  return data;
}


