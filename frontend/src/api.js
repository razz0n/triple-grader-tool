// api.js — Axios wrappers for all backend API calls

import axios from "axios";

const AUTH_TOKEN_KEY = "otg_auth_token";

// In production the frontend is served by FastAPI on the same origin, so
// relative paths work. In dev, Vite proxies /api/* to http://localhost:8001.
const API = axios.create({ baseURL: "" });

export function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
  } else {
    localStorage.removeItem(AUTH_TOKEN_KEY);
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
    }
    return Promise.reject(error);
  }
);

export async function registerUser(name, username, email, password) {
  const { data } = await API.post("/api/auth/register", { name, username, email, password });
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
