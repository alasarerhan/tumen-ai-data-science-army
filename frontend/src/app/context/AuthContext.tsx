import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { withCsrfHeader } from "../api/client";
import { getMe, type MeResponse } from "../api/me";
import { reportClientError } from "../lib/error-reporting";
import { useToast } from "../hooks/useToast";

const IDLE_TIMEOUT_MS = 30 * 60 * 1000;
const ABSOLUTE_TIMEOUT_MS = 8 * 60 * 60 * 1000;
const ACCESS_TOKEN_REFRESH_INTERVAL_MS = 12 * 60 * 1000;
const ACTIVITY_EVENTS = ["mousedown", "keydown", "touchstart", "scroll"];
const SESSION_TOKEN = "cookie-session";
const SESSION_STARTED_AT_KEY = "auth_session_started_at";
const LOGIN_SESSION_RETRY_ATTEMPTS = 5;
const LOGIN_SESSION_RETRY_DELAY_MS = 200;

/** Shape returned by useAuth() */
export interface AuthContextValue {
  token: string | null;
  user: MeResponse | null;
  workspaceId: string | null;
  isLoading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
  setWorkspaceId: (id: string) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const toast = useToast();
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<MeResponse | null>(null);
  const [workspaceId, _setWorkspaceId] = useState<string | null>(
    () => localStorage.getItem("workspace_id"),
  );
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const idleTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const absoluteTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearSessionTimers = useCallback(() => {
    if (idleTimeoutRef.current) clearTimeout(idleTimeoutRef.current);
    if (absoluteTimeoutRef.current) clearTimeout(absoluteTimeoutRef.current);
    idleTimeoutRef.current = null;
    absoluteTimeoutRef.current = null;
  }, []);

  const ensureSessionStartedAt = useCallback((): number => {
    const rawValue = sessionStorage.getItem(SESSION_STARTED_AT_KEY);
    const parsed = rawValue ? Number(rawValue) : Number.NaN;
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
    const now = Date.now();
    sessionStorage.setItem(SESSION_STARTED_AT_KEY, String(now));
    return now;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("workspace_id");
    sessionStorage.removeItem(SESSION_STARTED_AT_KEY);
    setToken(null);
    setUser(null);
    _setWorkspaceId(null);
    clearSessionTimers();
    void (async () => {
      try {
        const headers = await withCsrfHeader();
        await fetch("/v1/auth/logout", {
          method: "POST",
          credentials: "include",
          headers,
        });
      } catch {
        // best effort logout
      }
    })();
  }, [clearSessionTimers]);

  const resetIdleTimeout = useCallback(() => {
    if (idleTimeoutRef.current) {
      clearTimeout(idleTimeoutRef.current);
      idleTimeoutRef.current = null;
    }
    if (!token) return;
    idleTimeoutRef.current = setTimeout(() => {
      toast.warning("Session ended", "You were signed out after 30 minutes of inactivity.");
      logout();
    }, IDLE_TIMEOUT_MS);
  }, [token, logout, toast]);

  const setAbsoluteTimeout = useCallback(() => {
    if (absoluteTimeoutRef.current) {
      clearTimeout(absoluteTimeoutRef.current);
      absoluteTimeoutRef.current = null;
    }
    if (!token) return;
    const elapsedMs = Date.now() - ensureSessionStartedAt();
    const remainingMs = ABSOLUTE_TIMEOUT_MS - elapsedMs;
    if (remainingMs <= 0) {
      toast.warning("Session ended", "The maximum session duration has been reached.");
      logout();
      return;
    }
    absoluteTimeoutRef.current = setTimeout(() => {
      toast.warning("Session ended", "The maximum session duration has been reached.");
      logout();
    }, remainingMs);
  }, [ensureSessionStartedAt, token, logout, toast]);

  useEffect(() => {
    if (!token) return;

    const handleActivity = () => resetIdleTimeout();
    ACTIVITY_EVENTS.forEach((event) => window.addEventListener(event, handleActivity, { passive: true }));

    resetIdleTimeout();
    setAbsoluteTimeout();

    return () => {
      ACTIVITY_EVENTS.forEach((event) => window.removeEventListener(event, handleActivity));
      if (idleTimeoutRef.current) clearTimeout(idleTimeoutRef.current);
      if (absoluteTimeoutRef.current) clearTimeout(absoluteTimeoutRef.current);
    };
  }, [token, resetIdleTimeout, setAbsoluteTimeout]);

  /** Fetch /v1/me and populate user state */
  const fetchMe = useCallback(async (): Promise<boolean> => {
    try {
      const me = await getMe();
      setUser(me);
      setToken(SESSION_TOKEN);
      ensureSessionStartedAt();
      if (!localStorage.getItem("workspace_id") && me.workspace_memberships.length > 0) {
        const wid = me.workspace_memberships[0].workspace_id;
        localStorage.setItem("workspace_id", wid);
        _setWorkspaceId(wid);
      }
      return true;
    } catch {
      localStorage.removeItem("workspace_id");
      sessionStorage.removeItem(SESSION_STARTED_AT_KEY);
      setToken(null);
      setUser(null);
      _setWorkspaceId(null);
      return false;
    }
  }, [ensureSessionStartedAt]);

  const refreshSession = useCallback(async () => {
    const headers = await withCsrfHeader();
    const response = await fetch("/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
      headers,
    });
    if (!response.ok) {
      throw new Error(`Session refresh failed with status ${response.status}`);
    }
  }, []);

  useEffect(() => {
    setIsLoading(true);
    fetchMe().finally(() => setIsLoading(false));
  }, [fetchMe]);

  const login = useCallback(async (newToken: string) => {
    if (!import.meta.env.DEV) {
      throw new Error("Interactive login must be handled by the configured SSO redirect.");
    }
    const response = await fetch("/v1/auth/login/dev", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ token: newToken }),
    });
    if (!response.ok) {
      throw new Error("Authentication failed. Check your token.");
    }
    setIsLoading(true);
    sessionStorage.setItem(SESSION_STARTED_AT_KEY, String(Date.now()));
    let ok = false;
    for (let attempt = 0; attempt < LOGIN_SESSION_RETRY_ATTEMPTS; attempt += 1) {
      ok = await fetchMe();
      if (ok) {
        break;
      }
      if (attempt < LOGIN_SESSION_RETRY_ATTEMPTS - 1) {
        await sleep(LOGIN_SESSION_RETRY_DELAY_MS);
      }
    }
    setIsLoading(false);
    if (!ok) {
      throw new Error("Authentication failed. Check your token.");
    }
  }, [fetchMe]);

  useEffect(() => {
    if (!token) return undefined;

    const refreshInterval = window.setInterval(() => {
      void refreshSession().catch((error: unknown) => {
        const message = error instanceof Error ? error.message : "Session refresh failed";
        const shouldLogout = /status 401/.test(message);

        void reportClientError(error, {
          source: "auth",
          route: window.location.pathname,
          context: { phase: "silent_refresh" },
        });

        if (shouldLogout) {
          toast.warning("Session expired", "Please sign in again to continue.");
          logout();
          return;
        }

        toast.warning("Session refresh delayed", "The app will retry in the background.");
      });
    }, ACCESS_TOKEN_REFRESH_INTERVAL_MS);

    return () => {
      window.clearInterval(refreshInterval);
    };
  }, [logout, refreshSession, toast, token]);

  const setWorkspaceId = useCallback((id: string) => {
    localStorage.setItem("workspace_id", id);
    _setWorkspaceId(id);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, workspaceId, isLoading, login, logout, setWorkspaceId }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

