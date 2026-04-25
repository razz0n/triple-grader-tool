import { useState } from "react";
import { loginUser, registerUser } from "../api";

export default function AuthPanel({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const emailTrimmed = identifier.trim();
  const emailHasTypingSignals = emailTrimmed.includes("@") || emailTrimmed.includes(".");
  const isEmailValid = emailRegex.test(emailTrimmed);
  const emailError =
    emailTrimmed && emailHasTypingSignals && !isEmailValid
      ? "Use a valid email format, e.g. name@example.com."
      : "";
  const confirmError =
    mode === "register" && confirmPassword && password !== confirmPassword
      ? "Confirm password does not match."
      : "";

  const submit = async (e) => {
    e.preventDefault();
    setInfo("");
    if (mode === "register" && !isEmailValid) {
      setError("Please enter a valid email address.");
      return;
    }
    if (mode === "register") {
      if (!name.trim()) {
        setError("Please enter your name.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Confirm password does not match.");
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
        await registerUser(name.trim(), identifier, password);
        setMode("login");
        setPassword("");
        setConfirmPassword("");
        setInfo("Account created successfully. Please log in.");
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-sm p-6">
        <div className="text-center mb-5">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-700 text-white text-2xl mb-3 select-none">
            ◈
          </div>
          <h1 className="text-2xl font-bold text-slate-800">Ontology Triple Grader</h1>
          <p className="text-sm text-slate-500 mt-1">
            {mode === "login" ? "Sign in to your workspace" : "Create your account"}
          </p>
          {mode === "login" && (
            <p className="text-xs text-slate-500 mt-2">
              Default users: user_ysh / psd_ysh_psd, user_jw / psd_jw_psd, user_rl / psd_rl_psd, user_ab / psd_ab_psd, user_cd / psd_cd_psd
            </p>
          )}
        </div>
        <div className="flex rounded-xl bg-slate-100 p-1 mb-4">
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setError("");
            }}
            className={[
              "flex-1 text-sm font-semibold rounded-lg py-2 transition-colors",
              mode === "login" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500",
            ].join(" ")}
          >
            Login
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("register");
              setError("");
              setInfo("");
            }}
            className={[
              "flex-1 text-sm font-semibold rounded-lg py-2 transition-colors",
              mode === "register" ? "bg-white text-slate-800 shadow-sm" : "text-slate-500",
            ].join(" ")}
          >
            Register
          </button>
        </div>

        <form onSubmit={submit} className="space-y-3">
          {mode === "register" && (
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Full name"
              required
              className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
          )}

          <div>
            <div className="relative">
              <input
                type={mode === "login" ? "text" : "email"}
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder={mode === "login" ? "Username or email" : "Email"}
                required
                className="w-full border border-slate-300 rounded-xl px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
              {mode === "register" && isEmailValid && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-green-600 text-sm font-bold" aria-label="valid email">
                  ✓
                </span>
              )}
            </div>
            {mode === "register" && emailError && <p className="text-xs text-amber-700 mt-1">{emailError}</p>}
          </div>

          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password (min 8 chars)"
            minLength={8}
            required
            className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
          />

          {mode === "register" && (
            <div>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm password"
                minLength={8}
                required
                className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
              {confirmError && <p className="text-xs text-amber-700 mt-1">{confirmError}</p>}
            </div>
          )}

          {info && <p className="text-xs text-green-700">{info}</p>}
          {error && <p className="text-xs text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-700 text-white text-sm font-semibold rounded-xl py-2.5 hover:bg-blue-800 transition-colors disabled:opacity-60"
          >
            {loading ? "Please wait..." : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </form>
      </div>
    </div>
  );
}
