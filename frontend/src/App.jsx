// App.jsx -- Root component
import { useEffect, useState } from "react";
import FileUpload from "./components/FileUpload";
import ReviewStep from "./components/ReviewStep";
import GradingForm from "./components/GradingForm";
import AuthPanel from "./components/AuthPanel";
import { getAuthToken, logoutUser, meUser } from "./api";

export default function App() {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  // uploadData  : raw parse result from /api/upload (sentence_groups)
  // gradingData : cleaned/confirmed sentences built by ReviewStep
  const [uploadData, setUploadData]   = useState(null);
  const [gradingData, setGradingData] = useState(null);

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
  };

  const handleReviewConfirm = (cleanedData) => {
    setGradingData(cleanedData);
  };

  // Resume a previously saved session — skip upload + review entirely
  const handleLoadSession = (session) => {
    setGradingData({ ...session, resumed: true });
    setUploadData(null);
  };

  const handleReset = () => {
    setUploadData(null);
    setGradingData(null);
  };

  const handleLogout = async () => {
    await logoutUser();
    setUser(null);
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

    return <GradingForm uploadData={gradingData} onReset={handleReset} currentUser={user} />;
  })();

  const greetingName = user?.name || user?.email || "User";

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-5xl mx-auto px-4 py-2.5 flex items-center justify-between">
          <p className="text-xs sm:text-sm text-slate-600">
            Welcome, <span className="font-semibold text-slate-800">{greetingName}</span>
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

