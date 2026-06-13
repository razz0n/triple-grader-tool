import { useState, useEffect } from "react";
import { loginUser, registerUser } from "../api";
import { motion, AnimatePresence } from "framer-motion";
import { Lock, User, Mail, Shield, AlertCircle, CheckCircle, Sun, Moon, Eye, EyeOff } from "lucide-react";

export default function AuthPanel({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [isDark, setIsDark] = useState(false);

  // Initialize theme
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

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const emailTrimmed = identifier.trim();
  const emailHasTypingSignals = emailTrimmed.includes("@") || emailTrimmed.includes(".");
  const isEmailValid = emailRegex.test(emailTrimmed);
  
  const emailError =
    emailTrimmed && emailHasTypingSignals && !isEmailValid && mode === "register"
      ? "Please enter a valid email format (e.g., name@example.com)."
      : "";

  const confirmError =
    mode === "register" && confirmPassword && password !== confirmPassword
      ? "Confirm password does not match original password."
      : "";

  const usernameTrimmed = username.trim().toLowerCase();
  const usernameRegex = /^[a-z][a-z0-9_]{2,23}$/;
  const usernameHasTypingSignals = usernameTrimmed.length > 0;
  const isUsernameValid = usernameRegex.test(usernameTrimmed);
  
  const usernameError =
    mode === "register" && usernameHasTypingSignals && !isUsernameValid
      ? "Username must be 3-24 characters, start with a letter, and use lowercase letters, numbers, or _."
      : "";

  const submit = async (e) => {
    e.preventDefault();
    setInfo("");
    if (mode === "register") {
      if (!isEmailValid) {
        setError("Please enter a valid email address.");
        return;
      }
      if (!name.trim()) {
        setError("Please enter your name.");
        return;
      }
      if (!isUsernameValid) {
        setError("Please enter a valid username.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
    }
    setLoading(true);
    setError("");
    try {
      if (mode === "login") {
        const user = await loginUser(identifier, password);
        onAuthenticated(user);
      } else {
        await registerUser(name.trim(), usernameTrimmed, identifier, password);
        setMode("login");
        setPassword("");
        setConfirmPassword("");
        setUsername("");
        setInfo("Account created successfully. Please log in.");
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-gradient-to-br from-slate-50 via-slate-100 to-indigo-50/50 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950/20 transition-colors duration-300">
      
      {/* Background decoration elements */}
      <div className="absolute top-1/4 left-1/4 w-72 h-72 bg-indigo-400/10 dark:bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-violet-400/10 dark:bg-violet-500/5 rounded-full blur-3xl pointer-events-none" />

      {/* Theme Toggle Button */}
      <button
        onClick={toggleTheme}
        className="absolute top-6 right-6 p-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-all cursor-pointer shadow-sm active:scale-95"
        title="Toggle Light/Dark Theme"
      >
        {isDark ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="w-full max-w-md glass-panel rounded-2xl shadow-xl overflow-hidden p-8 z-10"
      >
        {/* Header Logo & Title */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 text-white shadow-md shadow-indigo-500/20 mb-3 select-none">
            <Shield size={24} className="animate-pulse" />
          </div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-slate-800 to-slate-900 dark:from-white dark:to-slate-200 bg-clip-text text-transparent">
            Ontology Triple Grader
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 font-medium">
            {mode === "login" ? "Sign in to access your grading workspace" : "Register a new evaluator account"}
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex rounded-xl bg-slate-100 dark:bg-slate-800/80 p-1 mb-6 border border-slate-200/50 dark:border-slate-800/30">
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setError("");
              setInfo("");
            }}
            className={`flex-1 text-xs font-semibold rounded-lg py-2.5 transition-all duration-200 cursor-pointer ${
              mode === "login"
                ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-white shadow-sm"
                : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("register");
              setError("");
              setInfo("");
            }}
            className={`flex-1 text-xs font-semibold rounded-lg py-2.5 transition-all duration-200 cursor-pointer ${
              mode === "register"
                ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-white shadow-sm"
                : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            Create Account
          </button>
        </div>

        {/* Info & Error Banner */}
        <AnimatePresence mode="wait">
          {info && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-4 p-3 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/30 rounded-xl flex items-start gap-2.5"
            >
              <CheckCircle size={16} className="text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
              <p className="text-xs text-emerald-800 dark:text-emerald-300 font-medium leading-normal">{info}</p>
            </motion.div>
          )}

          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-4 p-3 bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/30 rounded-xl flex items-start gap-2.5"
            >
              <AlertCircle size={16} className="text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
              <p className="text-xs text-rose-800 dark:text-rose-300 font-medium leading-normal">{error}</p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Input Form */}
        <form onSubmit={submit} className="space-y-4">
          <AnimatePresence mode="popLayout">
            {mode === "register" && (
              <motion.div
                key="reg-fields"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                {/* Full Name */}
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Full Name
                  </label>
                  <div className="relative flex items-center">
                    <User size={16} className="absolute left-3.5 text-slate-400 dark:text-slate-500" />
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g. John Doe"
                      required
                      className="w-full pl-10 pr-4 py-2.5 text-xs bg-slate-50/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                    />
                  </div>
                </div>

                {/* Username */}
                <div className="space-y-1">
                  <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    Username
                  </label>
                  <div className="relative flex items-center">
                    <User size={16} className="absolute left-3.5 text-slate-400 dark:text-slate-500" />
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="e.g. john_doe"
                      minLength={3}
                      maxLength={24}
                      required
                      className="w-full pl-10 pr-4 py-2.5 text-xs bg-slate-50/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                    />
                  </div>
                  {usernameError && (
                    <p className="text-[10px] text-amber-600 dark:text-amber-400 mt-1 leading-normal">
                      {usernameError}
                    </p>
                  )}
                </div>
              </motion.div>
            )}

            {/* Identifier input (Username or Email for login, Email only for register) */}
            <div key="identifier-field" className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                {mode === "login" ? "Username or Email" : "Email Address"}
              </label>
              <div className="relative flex items-center">
                <Mail size={16} className="absolute left-3.5 text-slate-400 dark:text-slate-500" />
                <input
                  type={mode === "login" ? "text" : "email"}
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder={mode === "login" ? "Enter username or email" : "Enter email address"}
                  required
                  className="w-full pl-10 pr-10 py-2.5 text-xs bg-slate-50/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                />
                {mode === "register" && isEmailValid && (
                  <CheckCircle size={16} className="absolute right-3.5 text-emerald-500 shrink-0" />
                )}
              </div>
              {emailError && (
                <p className="text-[10px] text-amber-600 dark:text-amber-400 mt-1 leading-normal">{emailError}</p>
              )}
            </div>

            {/* Password input */}
            <div key="password-field" className="space-y-1">
              <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Password
              </label>
              <div className="relative flex items-center">
                <Lock size={16} className="absolute left-3.5 text-slate-400 dark:text-slate-500" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 8 characters"
                  minLength={8}
                  required
                  className="w-full pl-10 pr-10 py-2.5 text-xs bg-slate-50/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors cursor-pointer"
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Confirm Password input */}
            {mode === "register" && (
              <motion.div
                key="confirm-password-field"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="space-y-1"
              >
                <label className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Confirm Password
                </label>
                <div className="relative flex items-center">
                  <Lock size={16} className="absolute left-3.5 text-slate-400 dark:text-slate-500" />
                  <input
                    type={showPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Verify your password"
                    minLength={8}
                    required
                    className="w-full pl-10 pr-10 py-2.5 text-xs bg-slate-50/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:text-white transition-all"
                  />
                </div>
                {confirmError && (
                  <p className="text-[10px] text-amber-600 dark:text-amber-400 mt-1 leading-normal">
                    {confirmError}
                  </p>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="w-full mt-4 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white text-xs font-semibold rounded-xl py-3 shadow-md shadow-indigo-600/10 hover:shadow-indigo-600/20 active:scale-98 transition-all disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer flex items-center justify-center"
          >
            {loading ? (
              <div className="flex items-center gap-2">
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                <span>Authenticating...</span>
              </div>
            ) : mode === "login" ? (
              "Sign In"
            ) : (
              "Create Account"
            )}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
