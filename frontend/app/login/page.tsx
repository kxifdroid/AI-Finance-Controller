"use client";

import { useState, useCallback, FormEvent, useEffect } from "react";
import { useRouter } from "next/navigation";
import Script from "next/script";
import {
  TrendingUp,
  Mail,
  Lock,
  User,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  Sparkles,
  Shield,
  CheckCircle2,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            auto_select?: boolean;
            use_fedcm_for_prompt?: boolean;
          }) => void;
          renderButton: (
            element: HTMLElement | null,
            config: {
              type?: string;
              theme?: string;
              size?: string;
              text?: string;
              shape?: string;
              width?: number;
              logo_alignment?: string;
            }
          ) => void;
          prompt: () => void;
        };
      };
    };
  }
}

type AuthMode = "login" | "register";

export default function LoginPage() {
  const router = useRouter();
  const {
    loginWithEmail,
    registerWithEmail,
    loginWithGoogle,
    loginDemo,
    isAuthenticated,
  } = useAuth();

  const [mode, setMode]             = useState<AuthMode>("login");
  const [name, setName]             = useState("");
  const [email, setEmail]           = useState("");
  const [password, setPassword]     = useState("");
  const [showPwd, setShowPwd]       = useState(false);
  const [loading, setLoading]       = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [success, setSuccess]       = useState<string | null>(null);
  const [googleReady, setGoogleReady] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, router]);


  // ---------------------------------------------------------------------------
  // Called by Next.js <Script onLoad> after Google GSI SDK finishes loading
  // ---------------------------------------------------------------------------
  const initGoogleSignIn = useCallback(() => {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    if (!clientId || !window.google?.accounts?.id) {
      return; // No client ID configured — skip silently
    }

    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: async ({ credential }) => {
        setLoading(true);
        setError(null);
        try {
          await loginWithGoogle(credential);
          router.replace("/");
        } catch (err: any) {
          setError(err.message || "Google sign-in failed. Please try again.");
        } finally {
          setLoading(false);
        }
      },
      use_fedcm_for_prompt: false,
    });

    const btnEl = document.getElementById("google-signin-btn");
    if (btnEl) {
      window.google.accounts.id.renderButton(btnEl, {
        type: "standard",
        theme: "filled_black",
        size: "large",
        text: "continue_with",
        shape: "rectangular",
        width: 340,
        logo_alignment: "left",
      });
    }

    setGoogleReady(true);
  }, [loginWithGoogle, router]);

  // ---------------------------------------------------------------------------
  // Email / Password form submit
  // ---------------------------------------------------------------------------
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      if (mode === "login") {
        await loginWithEmail(email, password);
        router.replace("/");
      } else {
        if (name.trim().length < 2) throw new Error("Name must be at least 2 characters.");
        await registerWithEmail(name.trim(), email, password);
        setSuccess("Account created! Redirecting to dashboard...");
        setTimeout(() => router.replace("/"), 800);
      }
    } catch (err: any) {
      setError(err.message || "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Demo login
  // ---------------------------------------------------------------------------
  const handleDemoLogin = async () => {
    setDemoLoading(true);
    setError(null);
    try {
      await loginDemo();
      router.replace("/");
    } catch (err: any) {
      setError(err.message || "Demo login failed.");
    } finally {
      setDemoLoading(false);
    }
  };

  const googleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

  // Avoid flashing the login page while redirecting
  if (isAuthenticated) {
    return null;
  }

  return (
    <>
      {/*
        Load Google Identity Services SDK here (not layout) so we can use onLoad.
        Only injected when NEXT_PUBLIC_GOOGLE_CLIENT_ID is set.
      */}
      {googleClientId && (
        <Script
          src="https://accounts.google.com/gsi/client"
          strategy="afterInteractive"
          onLoad={initGoogleSignIn}
          onError={() => setError("Failed to load Google Sign-In SDK. Please refresh.")}
        />
      )}

      <div className="min-h-screen bg-background flex items-center justify-center p-4 relative overflow-hidden">
        {/* Ambient glow orbs */}
        <div className="absolute top-0 left-1/4 h-96 w-96 rounded-full bg-primary/10 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 right-1/4 h-72 w-72 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />

        <div className="w-full max-w-md space-y-6 relative z-10">

          {/* Logo / Brand */}
          <div className="text-center space-y-2">
            <div className="flex items-center justify-center mb-4">
              <div className="p-2.5 rounded-xl bg-primary/15 border border-primary/30">
                <TrendingUp className="h-7 w-7 text-primary-light" />
              </div>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              AI Finance Controller
            </h1>
            <p className="text-xs text-gray-400">
              Enterprise multi-source financial reconciliation platform
            </p>
          </div>

          {/* Main Card */}
          <div className="rounded-2xl border border-border bg-card shadow-2xl overflow-hidden">

            {/* Mode Toggle Tabs */}
            <div className="grid grid-cols-2 border-b border-border">
              {(["login", "register"] as AuthMode[]).map((m) => (
                <button
                  key={m}
                  onClick={() => { setMode(m); setError(null); setSuccess(null); }}
                  className={cn(
                    "py-3 text-sm font-semibold transition-all",
                    mode === m
                      ? "text-white bg-gray-800 border-b-2 border-primary"
                      : "text-gray-400 hover:text-white hover:bg-gray-800/50"
                  )}
                >
                  {m === "login" ? "Sign In" : "Create Account"}
                </button>
              ))}
            </div>

            <div className="p-6 space-y-5">

              {/* Google Sign-In Section */}
              {googleClientId ? (
                <div className="w-full flex justify-center min-h-[44px] items-center">
                  {/* This div is populated by Google GSI renderButton() after SDK loads */}
                  <div id="google-signin-btn" className="w-full flex justify-center" />
                  {!googleReady && (
                    <div className="flex items-center gap-2 text-xs text-gray-500 py-2">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Loading Google Sign-In...
                    </div>
                  )}
                </div>
              ) : (
                /* No Client ID — show informational notice */
                <div className="rounded-xl border border-border bg-background/40 px-4 py-3 text-xs text-gray-400 text-center">
                  <span className="font-semibold text-gray-300">Google Sign-In not configured.</span>
                  <br />
                  Set <code className="text-primary-light">NEXT_PUBLIC_GOOGLE_CLIENT_ID</code> in your <code>.env</code> to enable it.
                </div>
              )}

              {/* Divider */}
              <div className="relative flex items-center gap-3">
                <div className="flex-1 border-t border-border" />
                <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">
                  or with email
                </span>
                <div className="flex-1 border-t border-border" />
              </div>

              {/* Email / Password Form */}
              <form onSubmit={handleSubmit} className="space-y-3">

                {/* Name — register only */}
                {mode === "register" && (
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                    <input
                      type="text"
                      required
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Full name"
                      className="w-full rounded-xl border border-border bg-background/70 pl-9 pr-4 py-2.5 text-sm text-gray-900 placeholder-gray-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                  </div>
                )}

                {/* Email */}
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Work email address"
                    className="w-full rounded-xl border border-border bg-background/70 pl-9 pr-4 py-2.5 text-sm text-gray-900 placeholder-gray-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>

                {/* Password */}
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
                  <input
                    type={showPwd ? "text" : "password"}
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={mode === "register" ? "Password (min. 8 characters)" : "Password"}
                    className="w-full rounded-xl border border-border bg-background/70 pl-9 pr-10 py-2.5 text-sm text-gray-900 placeholder-gray-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(!showPwd)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                  >
                    {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>

                {/* Error / Success Messages */}
                {error && (
                  <div className="flex items-start gap-2 rounded-lg bg-rose-500/10 border border-rose-500/30 px-3 py-2 text-xs text-rose-300">
                    <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
                    {error}
                  </div>
                )}
                {success && (
                  <div className="flex items-center gap-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-3 py-2 text-xs text-emerald-300">
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                    {success}
                  </div>
                )}

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-sm font-bold text-white hover:bg-primary-hover transition-all shadow-lg glow-primary disabled:opacity-50"
                >
                  {loading ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Authenticating...</>
                  ) : mode === "login" ? (
                    "Sign In to Dashboard"
                  ) : (
                    "Create My Account"
                  )}
                </button>
              </form>

              {/* Divider */}
              <div className="relative flex items-center gap-3">
                <div className="flex-1 border-t border-border" />
                <span className="text-xs text-gray-600 font-medium">or</span>
                <div className="flex-1 border-t border-border" />
              </div>

              {/* Instant Demo Login */}
              <div className="rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-4 space-y-3">
                <div className="flex items-start gap-2">
                  <Sparkles className="h-4 w-4 text-indigo-400 shrink-0 mt-0.5" />
                  <div>
                    <div className="text-xs font-bold text-indigo-300">Instant Demo Access</div>
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      Explore the full platform as Senior Finance Controller — no account needed.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  disabled={demoLoading}
                  onClick={handleDemoLogin}
                  className="w-full flex items-center justify-center gap-2 rounded-xl border border-indigo-500/40 bg-indigo-500/10 py-2.5 text-sm font-bold text-indigo-300 hover:bg-indigo-500/20 hover:text-white transition-all disabled:opacity-50"
                >
                  {demoLoading ? (
                    <><Loader2 className="h-4 w-4 animate-spin" /> Loading Demo...</>
                  ) : (
                    <><Shield className="h-4 w-4" /> Launch Instant Demo</>
                  )}
                </button>
              </div>

            </div>
          </div>

          {/* Footer */}
          <p className="text-center text-[11px] text-gray-600">
            AI Finance Controller — Multi-Source Reconciliation Platform · Learning Project
          </p>

        </div>
      </div>
    </>
  );
}
