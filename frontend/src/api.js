// api.js — Axios wrappers for all backend API calls

import axios from "axios";

const API = axios.create({ baseURL: "http://localhost:8001" });

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
      try { msg = JSON.parse(text).detail || msg; } catch {}
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
