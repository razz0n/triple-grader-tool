// App.jsx -- Root component
import React, { useEffect, useState } from "react";
import FileUpload from "./components/FileUpload";
import ReviewStep from "./components/ReviewStep";
import GradingForm from "./components/GradingForm";
import EvaluationPanel from "./components/EvaluationPanel";
import SettingsPanel from "./components/SettingsPanel";
import AuthPanel from "./components/AuthPanel";
import { Sun, Moon, Settings, LogOut, User as UserIcon, RefreshCw } from "lucide-react";
import { getAuthToken, logoutUser, meUser, saveSession } from "./api";

class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null, errorInfo: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary] Caught an error:', error, errorInfo);
    this.setState({ errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 max-w-2xl mx-auto my-12 bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/40 rounded-2xl shadow-sm space-y-4">
          <h2 className="text-lg font-bold text-rose-700 dark:text-rose-400">Something went wrong rendering the Grading Workspace.</h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
            {this.state.error && this.state.error.toString()}
          </p>
          {this.state.errorInfo && (
            <details className="text-xs bg-slate-900 text-slate-100 p-4 rounded-xl font-mono overflow-auto max-h-96">
              <summary className="cursor-pointer font-semibold mb-2 select-none">Stack trace</summary>
              <pre className="whitespace-pre-wrap">{this.state.error?.stack || ''}</pre>
              <pre className="mt-2 text-slate-400 whitespace-pre-wrap">{this.state.errorInfo?.componentStack || ''}</pre>
            </details>
          )}
          <div className="flex gap-3 pt-2">
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm font-semibold transition-colors shadow-sm cursor-pointer"
            >
              Reload Page
            </button>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null, errorInfo: null });
                if (this.props.onReset) this.props.onReset();
              }}
              className="px-4 py-2 border border-slate-350 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-900 rounded-lg text-sm font-semibold transition-colors cursor-pointer"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

function createManualSessionSeed(options = {}) {
  const randomId =
    globalThis.crypto && typeof globalThis.crypto.randomUUID === "function"
      ? globalThis.crypto.randomUUID()
      : `manual-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  const sourceFilename = String(options.sourceFilename || "").trim() || "Manual Entry.csv";

  return {
    session_id: randomId,
    source_filename: sourceFilename,
    uploaded_at: new Date().toISOString(),
    total_groups: 0,
    sentence_groups: [],
    manual_mode: true,
  };
}

export default function App() {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [isDark, setIsDark] = useState(false);
  // uploadData  : raw parse result from /api/upload (sentence_groups)
  // gradingData : loaded/resumed grading session payload
  const [uploadData, setUploadData] = useState(null);
  const [gradingData, setGradingData] = useState(null);
  const [evalSession, setEvalSession] = useState(null); // { sessionId, sourceFilename }
  const [recentUploadSessionId, setRecentUploadSessionId] = useState(null);
  const [dashboardTab, setDashboardTab] = useState("sessions"); // "sessions" or "settings"
  const [showMenu, setShowMenu] = useState(false);
  const [needsReload, setNeedsReload] = useState(false);

  // Check version / build ID for updates
  useEffect(() => {
    const currentBuildId = typeof __BUILD_ID__ !== "undefined" ? __BUILD_ID__ : null;
    if (!currentBuildId) return;

    const checkVersion = async () => {
      try {
        const res = await fetch("/version.json?t=" + Date.now(), {
          headers: { "Cache-Control": "no-cache" }
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.version && data.version !== currentBuildId) {
            setNeedsReload(true);
          }
        }
      } catch (err) {
        console.warn("[VersionCheck] Failed to check deployed version:", err);
      }
    };

    checkVersion();
    const interval = setInterval(checkVersion, 5 * 60 * 1000);
    const onFocus = () => checkVersion();
    window.addEventListener("focus", onFocus);

    return () => {
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  // Initialize theme on mount
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

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      setAuthLoading(false);
      return;
    }
    meUser()
      .then((me) => setUser(me))
      .catch(() => setUser(null))
      .finally(() => setAuthLoading(false));
  }, []);

  // Listen for token expiry — force user to re-login
  useEffect(() => {
    const onAuthLogout = () => {
      setUser(null);
      handleReset();
    };
    window.addEventListener('auth:logout', onAuthLogout);
    return () => window.removeEventListener('auth:logout', onAuthLogout);
  }, []);

  const handleUploadSuccess = (data) => {
    setUploadData(data);
    setGradingData(null);
    setRecentUploadSessionId(data?.session_id || null);
  };

  const handleStartManual = (manualConfig = {}) => {
    setUploadData(createManualSessionSeed(manualConfig));
    setGradingData(null);
    setRecentUploadSessionId(null);
  };

  const handleReviewConfirm = async (cleanedData) => {
    await saveSession(cleanedData);
    setRecentUploadSessionId(cleanedData?.session_id || null);
    setUploadData(null);
    setGradingData(null);
    setEvalSession(null);
  };

  // Convert a loaded session into a grading-ready shape.
  // The API can return sessions in two forms:
  //   - Full saved sessions: have a `sentences` array
  //   - Draft/upload sessions: have `sentence_groups` (before first /api/save)
  // We normalize both into the `sentences` shape that GradingForm expects.
  function normalizeSessionForGrading(session) {
    if (!session || typeof session !== 'object') return null;
    // Already has sentences array — use as-is
    if (Array.isArray(session.sentences) && session.sentences.length > 0) {
      return session;
    }
    // Has sentence_groups (draft format) — flatten to sentences
    if (Array.isArray(session.sentence_groups)) {
      const sentences = [];
      let sentenceId = 1;
      for (const group of session.sentence_groups) {
        const versions = group.versions || [];
        const selectedVersion = versions.find(
          (v) => v.version_id === group.selected_version_id
        ) || versions[0];
        if (!selectedVersion) continue;
        const triples = (selectedVersion.triples || []).map((t, idx) => ({
          id: t.id || `${sentenceId}_${idx + 1}`,
          subject: t.subject || '',
          predicate: t.predicate || '',
          object: t.object || '',
          grade: null,
        }));
        if (!triples.length) continue;
        sentences.push({
          id: sentenceId++,
          text: group.sentence_text || selectedVersion.sentence_candidate || '(no sentence text)',
          suggestion: '',
          sentence_comments: [],
          comment_count: 0,
          sentence_grade: null,
          completeness: null,
          external_relation: null,
          triples,
        });
      }
      return { ...session, sentences };
    }
    // Fallback: empty sentences so GradingForm can still render
    return { ...session, sentences: [] };
  }

  // Resume a previously saved session — skip upload + review entirely
  const handleLoadSession = (session) => {
    console.log('[App] handleLoadSession called, session_id:', session?.session_id, 'sentences:', session?.sentences?.length, 'sentence_groups:', session?.sentence_groups?.length);
    const normalized = normalizeSessionForGrading(session);
    if (!normalized) {
      console.error('[App] handleLoadSession: null/invalid session data');
      return;
    }
    setGradingData({ ...normalized, resumed: true });
    setUploadData(null);
  };

  const handleOpenEval = (sessionId, sourceFilename) => {
    setEvalSession({ sessionId, sourceFilename });
  };

  const handleCloseEval = () => {
    setEvalSession(null);
  };

  const handleReset = () => {
    setUploadData(null);
    setGradingData(null);
    setEvalSession(null);
  };

  const handleLogout = async () => {
    await logoutUser();
    setUser(null);
    setRecentUploadSessionId(null);
    setDashboardTab("sessions");
    handleReset();
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex items-center justify-center text-slate-500 dark:text-slate-400 text-sm">
        Restoring session...
      </div>
    );
  }

  if (!user) {
    return <AuthPanel onAuthenticated={setUser} />;
  }

  const workspaceView = (() => {
    // No active session/upload → show landing/file-upload page OR settings page
    if (!uploadData && !gradingData) {
      if (dashboardTab === "settings") {
        return (
          <SettingsPanel
            currentUser={user}
            onProfileUpdated={setUser}
            onLogout={handleLogout}
            onBack={() => setDashboardTab("sessions")}
          />
        );
      }
      return (
        <FileUpload
          onUploadSuccess={handleUploadSuccess}
          onLoadSession={handleLoadSession}
          onStartManual={handleStartManual}
          recentUploadSessionId={recentUploadSessionId}
        />
      );
    }

    // Fresh upload awaiting review
    if (uploadData && !gradingData) {
      return (
        <ReviewStep
          uploadData={uploadData}
          onConfirm={handleReviewConfirm}
          onReset={handleReset}
        />
      );
    }

    // Evaluation panel overlay
    if (evalSession) {
      return (
        <EvaluationPanel
          sessionId={evalSession.sessionId}
          sourceFilename={evalSession.sourceFilename}
          onBack={handleCloseEval}
        />
      );
    }

    // Resumed session → grading workspace
    if (gradingData) {
      console.log('[App] Rendering GradingForm with gradingData:', gradingData?.session_id);
      return (
        <ErrorBoundary onReset={handleReset}>
          <GradingForm uploadData={gradingData} onReset={handleReset} currentUser={user} onEvaluate={handleOpenEval} />
        </ErrorBoundary>
      );
    }

    // Fallback
    return (
      <FileUpload
        onUploadSuccess={handleUploadSuccess}
        onLoadSession={handleLoadSession}
        onStartManual={handleStartManual}
        recentUploadSessionId={recentUploadSessionId}
      />
    );
  })();

  const firstName = (user?.name || "").trim().split(/\s+/)[0] || "";
  const greetingName = firstName || user?.username || user?.email || "User";
  const usernameTag = user?.username ? `@${user.username}` : "";

  const isDashboard = !uploadData && !gradingData && !evalSession;

  const isFixedLayout = !!gradingData;

  return (
    <div className={isFixedLayout ? "h-screen overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-100 transition-colors duration-300" : "min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-100 transition-colors duration-300"}>
      {isDashboard && (
        <div className="sticky top-0 z-30 bg-white/95 dark:bg-slate-900/95 backdrop-blur border-b border-slate-200 dark:border-slate-800">
          <div className="max-w-5xl mx-auto px-4 py-2.5 flex items-center justify-between">
            <div className="flex items-center gap-4 sm:gap-6">
              <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400">
                Welcome, <span className="font-semibold text-slate-800 dark:text-white">{greetingName}</span>
                {usernameTag && <span className="ml-2 text-slate-400 dark:text-slate-550 hidden sm:inline">({usernameTag})</span>}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={toggleTheme}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-all cursor-pointer shadow-sm active:scale-95"
                title="Toggle Light/Dark Theme"
              >
                {isDark ? <Sun size={14} /> : <Moon size={14} />}
              </button>
              
              {/* Settings Dropdown menu */}
              <div className="relative">
                <button
                  onClick={() => setShowMenu(!showMenu)}
                  className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-all cursor-pointer shadow-sm active:scale-95 flex items-center justify-center"
                  title="Account Settings"
                >
                  <Settings size={14} />
                </button>
                
                {showMenu && (
                  <>
                    <div 
                      className="fixed inset-0 z-40" 
                      onClick={() => setShowMenu(false)} 
                    />
                    <div className="absolute right-0 mt-2 w-44 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-lg py-1.5 z-50 text-left">
                      <button
                        onClick={() => {
                          setDashboardTab("settings");
                          setShowMenu(false);
                        }}
                        className="w-full px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors flex items-center gap-2 cursor-pointer"
                      >
                        <UserIcon size={13} className="text-slate-400" />
                        Account Settings
                      </button>
                      <button
                        onClick={() => {
                          setShowMenu(false);
                          handleLogout();
                        }}
                        className="w-full px-4 py-2 text-xs font-semibold text-rose-600 dark:text-rose-455 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors flex items-center gap-2 cursor-pointer border-t border-slate-100 dark:border-slate-800"
                      >
                        <LogOut size={13} />
                        Logout
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
      {workspaceView}
      {needsReload && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-900/60 dark:bg-slate-950/80 backdrop-blur-md animate-fadeIn">
          <div className="max-w-md w-full mx-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-2xl text-center space-y-5">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-indigo-50 dark:bg-indigo-950/30 text-indigo-650 dark:text-indigo-400 flex items-center justify-center animate-bounce">
              <RefreshCw size={28} className="animate-spin text-indigo-650 dark:text-indigo-400" style={{ animationDuration: '3s' }} />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-extrabold text-slate-850 dark:text-white tracking-tight">New Update Available!</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed px-2">
                A new version of the Ontology Triple Grader tool has been deployed. Please reload the page to sync and use the latest features.
              </p>
            </div>
            <button
              onClick={() => window.location.reload()}
              className="w-full py-3 bg-gradient-to-r from-indigo-600 to-indigo-550 hover:from-indigo-700 hover:to-indigo-600 text-white font-bold rounded-2xl text-xs transition-all active:scale-95 shadow-md cursor-pointer flex items-center justify-center gap-2"
            >
              <RefreshCw size={14} />
              <span>Reload and Update Now</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
