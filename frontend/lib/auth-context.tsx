"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { AuthUser, TokenResponse } from "@/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  // Auth actions
  loginWithEmail: (email: string, password: string) => Promise<void>;
  registerWithEmail: (name: string, email: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  loginDemo: () => Promise<void>;
  logout: () => void;
  updateProfile: (name: string) => Promise<void>;
  uploadAvatar: (file: File) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = "afc_token";
const USER_KEY  = "afc_user";
const API_BASE  = `${process.env.NEXT_PUBLIC_API_URL || ""}/api/auth`;

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]     = useState<AuthUser | null>(null);
  const [token, setToken]   = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Hydrate from localStorage on first mount
  useEffect(() => {
    try {
      const storedToken = localStorage.getItem(TOKEN_KEY);
      const storedUser  = localStorage.getItem(USER_KEY);
      if (storedToken && storedUser) {
        setToken(storedToken);
        setUser(JSON.parse(storedUser));
      }
    } catch {
      // Ignore parse errors — treat as not authenticated
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Persist session to localStorage
  const persistSession = useCallback((data: TokenResponse) => {
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  // Generic fetch helper that posts to an auth endpoint
  const authPost = useCallback(async (endpoint: string, body: unknown): Promise<TokenResponse> => {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `Auth request failed (${res.status})`);
    }
    return data as TokenResponse;
  }, []);

  // ---- Actions ------------------------------------------------------------

  const loginWithEmail = useCallback(async (email: string, password: string) => {
    const data = await authPost("/login", { email, password });
    persistSession(data);
  }, [authPost, persistSession]);

  const registerWithEmail = useCallback(async (name: string, email: string, password: string) => {
    const data = await authPost("/register", { name, email, password });
    persistSession(data);
  }, [authPost, persistSession]);

  const loginWithGoogle = useCallback(async (credential: string) => {
    const data = await authPost("/google", { credential });
    persistSession(data);
  }, [authPost, persistSession]);

  const loginDemo = useCallback(async () => {
    const data = await authPost("/demo", {});
    persistSession(data);
  }, [authPost, persistSession]);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const updateProfile = useCallback(async (name: string) => {
    if (!token) return;
    const res = await fetch(`${API_BASE}/me`, {
      method: "PATCH",
      headers: { 
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}` 
      },
      body: JSON.stringify({ name }),
    });
    const updatedUser = await res.json();
    if (!res.ok) throw new Error(updatedUser.detail || "Failed to update profile");
    setUser(updatedUser);
    localStorage.setItem(USER_KEY, JSON.stringify(updatedUser));
  }, [token]);

  const uploadAvatar = useCallback(async (file: File) => {
    if (!token) return;
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/me/avatar`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` },
      body: formData,
    });
    const updatedUser = await res.json();
    if (!res.ok) throw new Error(updatedUser.detail || "Failed to upload avatar");
    setUser(updatedUser);
    localStorage.setItem(USER_KEY, JSON.stringify(updatedUser));
  }, [token]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user && !!token,
        isLoading,
        loginWithEmail,
        registerWithEmail,
        loginWithGoogle,
        loginDemo,
        logout,
        updateProfile,
        uploadAvatar,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
