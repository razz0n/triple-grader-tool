import { useState } from "react";
import { updateProfile, deleteAccount } from "../api";
import { motion, AnimatePresence } from "framer-motion";
import { User, Mail, Lock, Shield, AlertCircle, CheckCircle, ArrowLeft, Trash2, Edit2, Check, X } from "lucide-react";

export const SECURITY_QUESTIONS = [
  "What was the name of your first pet?",
  "What is your mother's maiden name?",
  "What was the name of your elementary school?",
  "In what city or town was your first job?",
  "What is the name of the street you grew up on?"
];

export default function SettingsPanel({ currentUser, onProfileUpdated, onLogout, onBack }) {
  // Field editing state tracking: null or 'name', 'username', 'email', 'password', 'security'
  const [editingField, setEditingField] = useState(null);

  // Field values
  const [name, setName] = useState(currentUser?.name || "");
  const [username, setUsername] = useState(currentUser?.username || "");
  const [email, setEmail] = useState(currentUser?.email || "");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [securityQuestion, setSecurityQuestion] = useState(currentUser?.security_question || SECURITY_QUESTIONS[0]);
  const [securityAnswer, setSecurityAnswer] = useState("");

  // Account deletion states
  const [showDeleteForm, setShowDeleteForm] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteAnswer, setDeleteAnswer] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  // Loading & Alert states for inline edits
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const usernameRegex = /^[a-z][a-z0-9_]{2,23}$/;

  const handleCancel = (field) => {
    setEditingField(null);
    setError("");
    setSuccess("");
    // Revert state values
    if (field === "name") setName(currentUser?.name || "");
    if (field === "username") setUsername(currentUser?.username || "");
    if (field === "email") setEmail(currentUser?.email || "");
    if (field === "password") {
      setPassword("");
      setConfirmPassword("");
      setSecurityAnswer("");
    }
    if (field === "security") {
      setSecurityQuestion(currentUser?.security_question || SECURITY_QUESTIONS[0]);
      setSecurityAnswer("");
    }
  };

  const handleSaveField = async (field) => {
    setError("");
    setSuccess("");

    const payload = {};

    if (field === "name") {
      if (name.trim().length < 2) {
        setError("Name must be at least 2 characters.");
        return;
      }
      payload.name = name.trim();
    }

    if (field === "username") {
      if (!usernameRegex.test(username.trim().toLowerCase())) {
        setError("Username must be 3-24 characters, start with a letter, and use only lowercase letters, numbers, or underscore.");
        return;
      }
      payload.username = username.trim().toLowerCase();
    }

    if (field === "email") {
      if (!emailRegex.test(email.trim().toLowerCase())) {
        setError("Please enter a valid email address.");
        return;
      }
      payload.email = email.trim().toLowerCase();
    }

    if (field === "password") {
      if (password.length < 8) {
        setError("Password must be at least 8 characters.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
      if (!securityAnswer.trim()) {
        setError("Please answer your security question to change your password.");
        return;
      }
      payload.password = password;
      payload.security_answer = securityAnswer.trim();
    }

    if (field === "security") {
      if (!securityAnswer.trim()) {
        setError("Please enter an answer for the security question.");
        return;
      }
      payload.security_question = securityQuestion;
      payload.security_answer = securityAnswer.trim();
    }

    setLoading(true);

    try {
      const res = await updateProfile(payload);
      if (res.ok) {
        setSuccess(`${field.charAt(0).toUpperCase() + field.slice(1)} updated successfully!`);
        setEditingField(null);
        setPassword("");
        setConfirmPassword("");
        setSecurityAnswer("");
        if (onProfileUpdated) {
          onProfileUpdated(res.user);
        }
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to update profile.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteAccountSubmit = async (e) => {
    e.preventDefault();
    setDeleteError("");

    if (!deletePassword) {
      setDeleteError("Password is required to delete your account.");
      return;
    }
    if (!deleteAnswer.trim()) {
      setDeleteError("Security answer is required to delete your account.");
      return;
    }

    const confirmPurge = window.confirm(
      "WARNING: This will permanently delete your account, your authentication status, and ALL of your uploaded/graded session files. This cannot be undone. Are you sure you want to proceed?"
    );
    if (!confirmPurge) return;

    setDeleteLoading(true);

    try {
      const res = await deleteAccount(deletePassword, deleteAnswer.trim());
      if (res.ok) {
        alert("Your account and all associated sessions have been successfully deleted.");
        if (onLogout) onLogout();
      }
    } catch (err) {
      setDeleteError(err?.response?.data?.detail || err?.message || "Failed to delete account. Double check your credentials.");
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="max-w-2xl mx-auto px-4 py-8 sm:py-12"
    >
      <div className="w-full">
        
        {/* Navigation Header */}
        <div className="flex items-center justify-between mb-6 border-b border-slate-200 dark:border-slate-800 pb-4">
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white transition-colors cursor-pointer"
          >
            <ArrowLeft size={16} />
            Back to Dashboard
          </button>
          <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Account Settings</span>
        </div>

        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-650 to-indigo-500 text-white shadow-lg shadow-indigo-500/20 mb-4 select-none">
            <Shield size={28} />
          </div>
          <h1 className="text-2xl font-extrabold text-slate-800 dark:text-white">
            Manage Credentials
          </h1>
          <p className="mt-1.5 text-slate-500 dark:text-slate-400 text-xs sm:text-sm max-w-md mx-auto leading-relaxed">
            Update individual credentials inline. Changing your password requires answering your verification question.
          </p>
        </div>

        {/* Feedback Messages */}
        {error && (
          <div className="mb-4 p-4 bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/30 rounded-xl text-xs text-rose-800 dark:text-rose-350 flex items-start gap-2.5">
            <AlertCircle size={16} className="text-rose-600 dark:text-rose-450 shrink-0 mt-0.5" />
            <p className="font-medium leading-normal">{error}</p>
          </div>
        )}

        {success && (
          <div className="mb-4 p-4 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/30 rounded-xl text-xs text-emerald-800 dark:text-emerald-350 flex items-start gap-2.5">
            <CheckCircle size={16} className="text-emerald-600 dark:text-emerald-450 shrink-0 mt-0.5" />
            <p className="font-medium leading-normal">{success}</p>
          </div>
        )}

        {/* Credentials Edit List */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl divide-y divide-slate-100 dark:divide-slate-800 overflow-hidden shadow-sm">
          
          {/* Row 1: Full Name */}
          <div className="p-5 sm:p-6 transition-colors">
            {editingField === "name" ? (
              <div className="space-y-3">
                <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Full Name</label>
                <div className="flex items-center gap-3">
                  <div className="relative flex-1 flex items-center">
                    <User size={14} className="absolute left-3 text-slate-400" />
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      required
                      placeholder="Enter new full name"
                      className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => handleSaveField("name")}
                      disabled={loading}
                      className="p-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors cursor-pointer active:scale-95 disabled:opacity-50"
                      title="Confirm Change"
                    >
                      <Check size={14} />
                    </button>
                    <button
                      onClick={() => handleCancel("name")}
                      className="p-2 border border-slate-250 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950 text-slate-500 dark:text-slate-450 rounded-lg transition-colors cursor-pointer active:scale-95"
                      title="Cancel"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-0.5">Full Name</span>
                  <p className="text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-200">{currentUser?.name || "—"}</p>
                </div>
                <button
                  onClick={() => setEditingField("name")}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950 text-xs font-bold text-indigo-600 dark:text-indigo-400 transition-all cursor-pointer flex items-center gap-1 active:scale-95"
                >
                  <Edit2 size={12} />
                  Change
                </button>
              </div>
            )}
          </div>

          {/* Row 2: Username */}
          <div className="p-5 sm:p-6 transition-colors">
            {editingField === "username" ? (
              <div className="space-y-3">
                <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Username</label>
                <div className="flex items-center gap-3">
                  <div className="relative flex-1 flex items-center">
                    <User size={14} className="absolute left-3 text-slate-400" />
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                      placeholder="Enter new username"
                      className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => handleSaveField("username")}
                      disabled={loading}
                      className="p-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors cursor-pointer active:scale-95 disabled:opacity-50"
                      title="Confirm Change"
                    >
                      <Check size={14} />
                    </button>
                    <button
                      onClick={() => handleCancel("username")}
                      className="p-2 border border-slate-250 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950 text-slate-500 dark:text-slate-450 rounded-lg transition-colors cursor-pointer active:scale-95"
                      title="Cancel"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-0.5">Username</span>
                  <p className="text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-200">@{currentUser?.username || "—"}</p>
                </div>
                <button
                  onClick={() => setEditingField("username")}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950 text-xs font-bold text-indigo-600 dark:text-indigo-400 transition-all cursor-pointer flex items-center gap-1 active:scale-95"
                >
                  <Edit2 size={12} />
                  Change
                </button>
              </div>
            )}
          </div>

          {/* Row 3: Email */}
          <div className="p-5 sm:p-6 transition-colors">
            {editingField === "email" ? (
              <div className="space-y-3">
                <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Email Address</label>
                <div className="flex items-center gap-3">
                  <div className="relative flex-1 flex items-center">
                    <Mail size={14} className="absolute left-3 text-slate-400" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      placeholder="Enter new email"
                      className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => handleSaveField("email")}
                      disabled={loading}
                      className="p-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors cursor-pointer active:scale-95 disabled:opacity-50"
                      title="Confirm Change"
                    >
                      <Check size={14} />
                    </button>
                    <button
                      onClick={() => handleCancel("email")}
                      className="p-2 border border-slate-250 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950 text-slate-500 dark:text-slate-450 rounded-lg transition-colors cursor-pointer active:scale-95"
                      title="Cancel"
                    >
                      <X size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-0.5">Email Address</span>
                  <p className="text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-200">{currentUser?.email || "—"}</p>
                </div>
                <button
                  onClick={() => setEditingField("email")}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950 text-xs font-bold text-indigo-600 dark:text-indigo-400 transition-all cursor-pointer flex items-center gap-1 active:scale-95"
                >
                  <Edit2 size={12} />
                  Change
                </button>
              </div>
            )}
          </div>

          {/* Row 4: Security Question Configuration */}
          <div className="p-5 sm:p-6 transition-colors">
            {editingField === "security" ? (
              <div className="space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Security Question</label>
                  <select
                    value={securityQuestion}
                    onChange={(e) => setSecurityQuestion(e.target.value)}
                    className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all animate-none"
                  >
                    {SECURITY_QUESTIONS.map((q, idx) => (
                      <option key={idx} value={q}>
                        {q}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Security Answer</label>
                  <div className="relative flex items-center">
                    <Shield size={14} className="absolute left-3 text-slate-400" />
                    <input
                      type="text"
                      value={securityAnswer}
                      onChange={(e) => setSecurityAnswer(e.target.value)}
                      placeholder="Type security answer here"
                      required
                      className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                    />
                  </div>
                </div>
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={() => handleSaveField("security")}
                    disabled={loading}
                    className="px-3 py-1.5 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors cursor-pointer active:scale-95 disabled:opacity-50 flex items-center gap-1"
                  >
                    <Check size={14} />
                    Confirm Change
                  </button>
                  <button
                    onClick={() => handleCancel("security")}
                    className="px-3 py-1.5 text-xs font-bold border border-slate-250 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950 text-slate-500 dark:text-slate-450 rounded-lg transition-colors cursor-pointer active:scale-95 flex items-center gap-1"
                  >
                    <X size={14} />
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-0.5">Verification Question</span>
                  <p className="text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-200 leading-snug">{currentUser?.security_question || "Not set"}</p>
                </div>
                <button
                  onClick={() => setEditingField("security")}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950 text-xs font-bold text-indigo-600 dark:text-indigo-400 transition-all cursor-pointer flex items-center gap-1 active:scale-95"
                >
                  <Edit2 size={12} />
                  Change
                </button>
              </div>
            )}
          </div>

          {/* Row 5: Password (Requires Security Question Answer) */}
          <div className="p-5 sm:p-6 transition-colors">
            {editingField === "password" ? (
              <div className="space-y-4">
                
                {/* Security Verification Question Block */}
                <div className="bg-slate-50 dark:bg-slate-950 p-4 border border-slate-200 dark:border-slate-850 rounded-xl leading-normal">
                  <span className="text-[9px] font-bold text-indigo-500 uppercase tracking-wider block mb-1">
                    Security Verification Check
                  </span>
                  <p className="text-xs text-slate-700 dark:text-slate-350 font-medium">
                    {currentUser?.security_question || "Verification question is not set. Please update your verification question first."}
                  </p>
                </div>

                {/* Answer Input */}
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Security Answer</label>
                  <div className="relative flex items-center">
                    <Shield size={14} className="absolute left-3 text-slate-400" />
                    <input
                      type="text"
                      value={securityAnswer}
                      onChange={(e) => setSecurityAnswer(e.target.value)}
                      placeholder="Type security question answer"
                      required
                      className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                    />
                  </div>
                </div>

                {/* Password Inputs */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">New Password</label>
                    <div className="relative flex items-center">
                      <Lock size={14} className="absolute left-3 text-slate-400" />
                      <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="Min 8 characters"
                        required
                        className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                      />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Confirm Password</label>
                    <div className="relative flex items-center">
                      <Lock size={14} className="absolute left-3 text-slate-400" />
                      <input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="Confirm new password"
                        required
                        className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={() => handleSaveField("password")}
                    disabled={loading}
                    className="px-3 py-1.5 text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors cursor-pointer active:scale-95 disabled:opacity-50 flex items-center gap-1"
                  >
                    <Check size={14} />
                    Confirm Change
                  </button>
                  <button
                    onClick={() => handleCancel("password")}
                    className="px-3 py-1.5 text-xs font-bold border border-slate-250 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950 text-slate-500 dark:text-slate-450 rounded-lg transition-colors cursor-pointer active:scale-95 flex items-center gap-1"
                  >
                    <X size={14} />
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block mb-0.5">Password</span>
                  <p className="text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-200">••••••••</p>
                </div>
                <button
                  onClick={() => setEditingField("password")}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950 text-xs font-bold text-indigo-600 dark:text-indigo-400 transition-all cursor-pointer flex items-center gap-1 active:scale-95"
                >
                  <Edit2 size={12} />
                  Change
                </button>
              </div>
            )}
          </div>

        </div>

        {/* Delete Account Panel Section */}
        <div className="mt-8 bg-white dark:bg-slate-900 border border-rose-100 dark:border-rose-950/40 rounded-2xl p-6 shadow-sm">
          <h3 className="text-sm font-bold text-rose-600 dark:text-rose-450 flex items-center gap-2 mb-2">
            <Trash2 size={18} />
            Danger Zone - Delete Account
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 leading-normal mb-4">
            Deleting your account will permanently delete all your credentials, grading profiles, and all your uploaded grading spreadsheets/session files from the database. This action is irreversible.
          </p>

          <AnimatePresence mode="wait">
            {!showDeleteForm ? (
              <button
                type="button"
                onClick={() => {
                  setShowDeleteForm(true);
                  setDeletePassword("");
                  setDeleteAnswer("");
                  setDeleteError("");
                }}
                className="px-4 py-2 border border-rose-200 dark:border-rose-900/50 hover:bg-rose-50/50 dark:hover:bg-rose-950/20 text-rose-600 dark:text-rose-400 text-xs font-bold rounded-xl transition-all cursor-pointer active:scale-95"
              >
                Delete Account...
              </button>
            ) : (
              <motion.form
                onSubmit={handleDeleteAccountSubmit}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="space-y-4 border-t border-rose-100 dark:border-rose-950/20 pt-4"
              >
                {deleteError && (
                  <div className="p-3 bg-rose-50 dark:bg-rose-950/20 border border-rose-250 dark:border-rose-900/30 rounded-xl text-xs text-rose-800 dark:text-rose-350 flex items-center gap-2">
                    <AlertCircle size={14} className="text-rose-600 shrink-0" />
                    <p className="font-semibold">{deleteError}</p>
                  </div>
                )}

                {/* Password field verification */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block">Confirm Password</label>
                    <div className="relative flex items-center">
                      <Lock size={14} className="absolute left-3 text-slate-400" />
                      <input
                        type="password"
                        value={deletePassword}
                        onChange={(e) => setDeletePassword(e.target.value)}
                        placeholder="Enter password to verify"
                        required
                        className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 dark:text-white transition-all"
                      />
                    </div>
                  </div>

                  {/* Verification Answer verification */}
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider block">Security Question Answer</label>
                    <div className="relative flex items-center">
                      <Shield size={14} className="absolute left-3 text-slate-400" />
                      <input
                        type="text"
                        value={deleteAnswer}
                        onChange={(e) => setDeleteAnswer(e.target.value)}
                        placeholder="Answer security question"
                        required
                        className="w-full pl-9 pr-4 py-2 text-xs bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 dark:text-white transition-all"
                      />
                    </div>
                  </div>
                </div>

                <div className="text-[10px] bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400 p-3 rounded-xl leading-normal border border-amber-200/50 dark:border-amber-900/30">
                  <span className="font-bold">Security Question:</span> {currentUser?.security_question || "Verification question is not set."}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="submit"
                    disabled={deleteLoading}
                    className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-xl transition-all cursor-pointer active:scale-95 disabled:opacity-55 flex items-center gap-1.5"
                  >
                    {deleteLoading ? (
                      <>
                        <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Deleting Account...
                      </>
                    ) : (
                      <>
                        <Trash2 size={14} />
                        Permanently Purge My Account
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowDeleteForm(false)}
                    className="px-4 py-2 border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-950 text-slate-500 dark:text-slate-400 text-xs font-bold rounded-xl transition-all cursor-pointer active:scale-95"
                  >
                    Cancel
                  </button>
                </div>
              </motion.form>
            )}
          </AnimatePresence>
        </div>

      </div>
    </motion.div>
  );
}
