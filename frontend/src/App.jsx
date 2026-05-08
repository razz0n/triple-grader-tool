// App.jsx -- Root component
import { useEffect, useState } from "react";
import FileUpload from "./components/FileUpload";
import ReviewStep from "./components/ReviewStep";
import GradingForm from "./components/GradingForm";
import EvaluationPanel from "./components/EvaluationPanel";
import AuthPanel from "./components/AuthPanel";
import { getAuthToken, logoutUser, meUser, saveSession } from "./api";

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
  // uploadData  : raw parse result from /api/upload (sentence_groups)
  // gradingData : loaded/resumed grading session payload
  const [uploadData, setUploadData]     = useState(null);
  const [gradingData, setGradingData]   = useState(null);
  const [evalSession, setEvalSession]   = useState(null); // { sessionId, sourceFilename }
  const [recentUploadSessionId, setRecentUploadSessionId] = useState(null);

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

  // Resume a previously saved session — skip upload + review entirely
  const handleLoadSession = (session) => {
    setGradingData({ ...session, resumed: true });
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
    handleReset();
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-500 text-sm">
        Restoring session...
      </div>
    );
  }

  if (!user) {
    return <AuthPanel onAuthenticated={setUser} />;
  }

  const workspaceView = (() => {
    if (!uploadData && !gradingData) {
      return (
        <FileUpload
          onUploadSuccess={handleUploadSuccess}
          onLoadSession={handleLoadSession}
          onStartManual={handleStartManual}
          recentUploadSessionId={recentUploadSessionId}
        />
      );
    }

    if (uploadData && !gradingData) {
      return (
        <ReviewStep
          uploadData={uploadData}
          onConfirm={handleReviewConfirm}
          onReset={handleReset}
        />
      );
    }

    if (evalSession) {
      return (
        <EvaluationPanel
          sessionId={evalSession.sessionId}
          sourceFilename={evalSession.sourceFilename}
          onBack={handleCloseEval}
        />
      );
    }

    return <GradingForm uploadData={gradingData} onReset={handleReset} currentUser={user} onEvaluate={handleOpenEval} />;
  })();

  const firstName = (user?.name || "").trim().split(/\s+/)[0] || "";
  const greetingName = firstName || user?.username || user?.email || "User";
  const usernameTag = user?.username ? `@${user.username}` : "";

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 py-2.5 flex items-center justify-between">
          <p className="text-xs sm:text-sm text-slate-600">
            Welcome, <span className="font-semibold text-slate-800">{greetingName}</span>
            {usernameTag && <span className="ml-2 text-slate-400">({usernameTag})</span>}
          </p>
          <button
            onClick={handleLogout}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 transition-colors"
          >
            Logout
          </button>
        </div>
      </div>
      {workspaceView}
    </div>
  );
}

