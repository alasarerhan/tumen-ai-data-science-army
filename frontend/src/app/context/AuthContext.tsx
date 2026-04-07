import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { getCsrfToken } from "../api/client";
import { getMe, type MeResponse } from "../api/me";

const IDLE_TIMEOUT_MS = 30 * 60 * 1000;
const ABSOLUTE_TIMEOUT_MS = 8 * 60 * 60 * 1000;
const ACTIVITY_EVENTS = ["mousedown", "keydown", "touchstart", "scroll"];

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? match[2] : null;
}

function deleteCookie(name: string): void {
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
}

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

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(
    () => getCookie("access_token"),
  );
  const [user, setUser] = useState<MeResponse | null>(null);
  const [workspaceId, _setWorkspaceId] = useState<string | null>(
    () => localStorage.getItem("workspace_id"),
  );
  const [isLoading, setIsLoading] = useState<boolean>(Boolean(token));
  const loginTimeRef = useRef<number | null>(null);
  const idleTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const absoluteTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const logout = useCallback(() => {
    deleteCookie("access_token");
    localStorage.removeItem("workspace_id");
    setToken(null);
    setUser(null);
    _setWorkspaceId(null);
    if (idleTimeoutRef.current) clearTimeout(idleTimeoutRef.current);
    if (absoluteTimeoutRef.current) clearTimeout(absoluteTimeoutRef.current);
    void (async () => {
      try {
        const csrf = await getCsrfToken();
        await fetch("/v1/auth/logout", {
          method: "POST",
          credentials: "include",
          headers: { "X-CSRF-Token": csrf },
        });
      } catch {
        // best effort logout
      }
    })();
  }, []);

  const resetIdleTimeout = useCallback(() => {
    if (idleTimeoutRef.current) {
      clearTimeout(idleTimeoutRef.current);
      idleTimeoutRef.current = null;
    }
    if (!token) return;
    const currentToken = token;
    idleTimeoutRef.current = setTimeout(() => {
      if (currentToken === token) {
        console.log("Session expired due to inactivity");
        logout();
      }
    }, IDLE_TIMEOUT_MS);
  }, [token, logout]);

  const setAbsoluteTimeout = useCallback(() => {
    if (absoluteTimeoutRef.current) {
      clearTimeout(absoluteTimeoutRef.current);
      absoluteTimeoutRef.current = null;
    }
    if (!token) return;
    const currentToken = token;
    absoluteTimeoutRef.current = setTimeout(() => {
      if (currentToken === token) {
        console.log("Session expired due to absolute timeout");
        logout();
      }
    }, ABSOLUTE_TIMEOUT_MS);
  }, [token, logout]);

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
  const fetchMe = useCallback(async (tok: string): Promise<boolean> => {
    if (tok === "dev") {
      const stubMe: MeResponse = {
        id: "dev-user",
        sub: "dev",
        email: "dev@localhost",
        tenant_memberships: [{ tenant_id: "t-dev", role: "admin" }],
        workspace_memberships: [{ workspace_id: "ws-dev", role: "admin" }],
        claims: {},
      };
      setUser(stubMe);
      const wid = stubMe.workspace_memberships[0].workspace_id;
      if (!localStorage.getItem("workspace_id")) {
        localStorage.setItem("workspace_id", wid);
        _setWorkspaceId(wid);
      }
      return true;
    }

    try {
      const me = await getMe();
      setUser(me);
      if (!localStorage.getItem("workspace_id") && me.workspace_memberships.length > 0) {
        const wid = me.workspace_memberships[0].workspace_id;
        localStorage.setItem("workspace_id", wid);
        _setWorkspaceId(wid);
      }
      return true;
    } catch {
      deleteCookie("access_token");
      localStorage.removeItem("workspace_id");
      setToken(null);
      setUser(null);
      _setWorkspaceId(null);
      return false;
    }
  }, []);

  useEffect(() => {
    if (token) {
      setIsLoading(true);
      fetchMe(token).finally(() => setIsLoading(false));
    }
  }, []);

  const login = useCallback(async (newToken: string) => {
    if (import.meta.env.DEV && newToken === "dev") {
      const response = await fetch("/v1/auth/login/dev", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ token: newToken }),
      });
      if (!response.ok) {
        throw new Error("Authentication failed. Check your token.");
      }
      setToken(newToken);
      setIsLoading(true);
      loginTimeRef.current = Date.now();
      const ok = await fetchMe(newToken);
      setIsLoading(false);
      if (!ok) {
        throw new Error("Authentication failed. Check your token.");
      }
    } else {
      setToken(newToken);
      setIsLoading(true);
      loginTimeRef.current = Date.now();
      const ok = await fetchMe(newToken);
      setIsLoading(false);
      if (!ok) {
        throw new Error("Authentication failed. Check your token.");
      }
    }
  }, [fetchMe]);

  const setWorkspaceId = useCallback((id: string) => {
    localStorage.setItem("workspace_id", id);
    _setWorkspaceId(id);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ token, user, workspaceId, isLoading, login, logout, setWorkspaceId }),
    [token, user, workspaceId, isLoading, login, logout, setWorkspaceId],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

