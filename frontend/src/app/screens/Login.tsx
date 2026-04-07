import React, { useState } from "react";
import { useNavigate, Navigate } from "react-router";
import { Zap, Bot, BarChart2, Users, Eye, EyeOff, AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { cn } from "../lib/utils";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const { login, token: authToken } = useAuth();
  const [devOpen, setDevOpen] = useState(false);
  const [tokenInput, setTokenInput] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Already authenticated → skip login page
  if (authToken) return <Navigate to="/dashboard" replace />;

  const signIn = async (bearerToken: string) => {
    setLoading(true);
    setError("");
    try {
      await login(bearerToken);
      navigate("/dashboard", { replace: true });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Sign-in failed. Check your token and try again.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  /** Google SSO — production uses real OIDC, dev mode uses dev token */
  const handleGoogle = () => {
    if (import.meta.env.DEV) {
      signIn("dev");
    } else {
      window.location.href = "/auth/google";
    }
  };

  const handleDevSignIn = (e: React.FormEvent) => {
    e.preventDefault();
    const t = tokenInput.trim();
    if (!t) {
      setError("Please enter a valid bearer token.");
      return;
    }
    signIn(t);
  };

  return (
    <div className="flex min-h-screen w-full font-[Inter,sans-serif]">
      {/* Left panel — Marketing */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between bg-slate-950 p-10 relative overflow-hidden">
        {/* Background gradient decoration */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-32 -left-32 w-96 h-96 bg-indigo-900/30 rounded-full blur-3xl" />
          <div className="absolute -bottom-32 -right-32 w-96 h-96 bg-violet-900/20 rounded-full blur-3xl" />
        </div>

        {/* Logo */}
        <div className="flex items-center gap-3 relative z-10">
          <div className="size-9 bg-indigo-600 rounded-[8px] flex items-center justify-center">
            <Zap size={18} className="text-white" />
          </div>
          <span className="text-white font-semibold text-lg">Insight Platform</span>
        </div>

        {/* Hero */}
        <div className="relative z-10 space-y-8">
          <div className="space-y-4">
            <h1 className="text-slate-50" style={{ fontSize: "36px", fontWeight: 700, lineHeight: "44px", textWrap: "balance" }}>
              AI-Powered Analytics.<br />Delivered at Scale.
            </h1>
            <p className="text-slate-400" style={{ fontSize: "16px", lineHeight: "24px" }}>
              Orchestrate multi-agent pipelines, synthesize strategic insights, and deploy at enterprise speed.
            </p>
          </div>

          {/* Feature pills */}
          <div className="flex flex-col gap-3">
            {[
              { icon: <Bot size={16} />, label: "Autonomous Agents" },
              { icon: <BarChart2 size={16} />, label: "Strategic Reports" },
              { icon: <Users size={16} />, label: "Human-in-the-Loop" },
            ].map((feature) => (
              <div
                key={feature.label}
                className="flex items-center gap-3 px-4 py-3 rounded-[8px] bg-slate-800/60 border border-slate-700/50 w-fit"
              >
                <span className="text-indigo-400">{feature.icon}</span>
                <span className="text-slate-200 text-sm font-medium">{feature.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="relative z-10 text-slate-600 text-xs">
          v1.0.0 · © 2026 Insight Platform, Inc.
        </div>
      </div>

      {/* Right panel — Auth form */}
      <div className="flex flex-1 items-center justify-center bg-white dark:bg-slate-950 p-6">
        <div className="w-full max-w-sm space-y-6">
          {/* Mobile logo */}
          <div className="flex items-center gap-2 lg:hidden">
            <div className="size-7 bg-indigo-600 rounded-[6px] flex items-center justify-center">
              <Zap size={14} className="text-white" />
            </div>
            <span className="text-slate-900 dark:text-slate-50 font-semibold">Insight Platform</span>
          </div>

          <div className="space-y-1">
            <h2 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "20px", fontWeight: 600, lineHeight: "30px" }}>
              Sign In
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-sm">Use your corporate Google Workspace account.</p>
          </div>

          {/* Error */}
          {error && (
            <div
              role="alert"
              className="flex items-start gap-3 px-4 py-3 rounded-[8px] bg-red-50 border border-red-200 dark:bg-red-900/20 dark:border-red-800"
            >
              <AlertTriangle size={16} className="text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-red-700 dark:text-red-400 text-sm">{error}</p>
            </div>
          )}

          <form aria-label="Sign in" onSubmit={(e) => e.preventDefault()} className="space-y-4">
            {/* Google button */}
            <Button
              type="button"
              variant="secondary"
              size="lg"
              fullWidth
              loading={loading}
              onClick={handleGoogle}
              className="justify-center"
            >
              {!loading && (
                <svg className="size-4" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                </svg>
              )}
              Continue with Google
            </Button>

            {/* Divider */}
            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-slate-200 dark:bg-slate-700" />
              <span className="text-xs text-slate-400 dark:text-slate-500">or</span>
              <div className="flex-1 h-px bg-slate-200 dark:bg-slate-700" />
            </div>

            {/* Dev token toggle */}
            <div>
              <button
                type="button"
                onClick={() => setDevOpen(!devOpen)}
                className="text-xs text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors flex items-center gap-1"
              >
                <span>Developer Token (local only)</span>
                <span className="text-slate-400">{devOpen ? "▲" : "▼"}</span>
              </button>

              {devOpen && (
                <div className="mt-3 space-y-3">
                  {/* Amber warning */}
                  <div className="flex items-start gap-2 px-3 py-2.5 rounded-[6px] bg-amber-50 border border-amber-200 dark:bg-amber-900/20 dark:border-amber-700">
                    <AlertTriangle size={14} className="text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                    <p className="text-amber-700 dark:text-amber-400 text-xs">Dev mode only — not for production.</p>
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="token" className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                      Bearer Token
                    </label>
                    <div className="relative">
                      <input
                        id="token"
                        type={showToken ? "text" : "password"}
                        autoComplete="current-password"
                        spellCheck={false}
                        placeholder="Bearer eyJ…"
                        value={tokenInput}
                        onChange={(e) => setTokenInput(e.target.value)}
                        className="w-full h-9 px-3 pr-10 rounded-[6px] border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                      />
                      <button
                        type="button"
                        onClick={() => setShowToken(!showToken)}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                        aria-label={showToken ? "Hide token" : "Show token"}
                      >
                        {showToken ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                  </div>

                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    fullWidth
                    loading={loading}
                    onClick={handleDevSignIn}
                  >
                    Sign In
                  </Button>
                </div>
              )}
            </div>
          </form>

          <p className="text-center text-xs text-slate-400">
            <a href="#" className="hover:text-slate-600 transition-colors">Privacy Policy</a>
            {" · "}
            <a href="#" className="hover:text-slate-600 transition-colors">Terms of Service</a>
          </p>
        </div>
      </div>
    </div>
  );
}

