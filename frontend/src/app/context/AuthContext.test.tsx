import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { AuthProvider, useAuth } from "../context/AuthContext";

const mockNavigate = vi.fn();

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockFetch = vi.fn();
let meAuthenticated = false;

function TestComponent() {
  const { token, user, workspaceId, isLoading, login, logout, setWorkspaceId } = useAuth();

  return (
    <div>
      <span data-testid="token">{token ?? "null"}</span>
      <span data-testid="user">{user?.email ?? "null"}</span>
      <span data-testid="workspaceId">{workspaceId ?? "null"}</span>
      <span data-testid="isLoading">{isLoading.toString()}</span>
      <button onClick={() => login("dev")}>Login</button>
      <button onClick={logout}>Logout</button>
      <button onClick={() => setWorkspaceId("test-ws")}>Set Workspace</button>
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    meAuthenticated = false;
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/v1/auth/login/dev")) {
        meAuthenticated = true;
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true, user_id: "dev-user" }),
        });
      }
      if (url.includes("/v1/me")) {
        if (!meAuthenticated) {
          return Promise.resolve({
            ok: false,
            status: 401,
            json: () => Promise.resolve({ detail: "Unauthorized" }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            id: "dev-user",
            sub: "dev-user",
            email: "test@example.com",
            tenant_memberships: [{ tenant_id: "tenant-1", role: "admin" }],
            workspace_memberships: [{ workspace_id: "workspace-1", role: "admin" }],
            claims: {},
          }),
        });
      }
      if (url.includes("/v1/auth/csrf")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ csrf_token: "csrf-test-token" }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should provide initial null values", () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByTestId("token").textContent).toBe("null");
    expect(screen.getByTestId("user").textContent).toBe("null");
    expect(screen.getByTestId("workspaceId").textContent).toBe("null");
  });

  it("should throw error when useAuth is used outside provider", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      render(<TestComponent />);
    }).toThrow("useAuth must be used inside <AuthProvider>");

    consoleError.mockRestore();
  });

  it("should set workspace id", async () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    fireEvent.click(screen.getByText("Set Workspace"));

    await waitFor(() => {
      expect(screen.getByTestId("workspaceId").textContent).toBe("test-ws");
    });
  });

  it("should logout and clear state", async () => {
    const removeItemSpy = vi.spyOn(Storage.prototype, "removeItem");

    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    fireEvent.click(screen.getByText("Logout"));

    await waitFor(() => {
      expect(screen.getByTestId("token").textContent).toBe("null");
    });

    removeItemSpy.mockRestore();
  });

  it("should retry session fetch after successful dev login", async () => {
    let postLoginMeFailures = 2;

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/v1/auth/login/dev")) {
        meAuthenticated = true;
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true, user_id: "dev-user" }),
        });
      }
      if (url.includes("/v1/me")) {
        if (!meAuthenticated || postLoginMeFailures > 0) {
          if (meAuthenticated && postLoginMeFailures > 0) {
            postLoginMeFailures -= 1;
          }
          return Promise.resolve({
            ok: false,
            status: 401,
            json: () => Promise.resolve({ detail: "Unauthorized" }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            id: "dev-user",
            sub: "dev-user",
            email: "test@example.com",
            tenant_memberships: [{ tenant_id: "tenant-1", role: "admin" }],
            workspace_memberships: [{ workspace_id: "workspace-1", role: "admin" }],
            claims: {},
          }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    fireEvent.click(screen.getByText("Login"));

    await waitFor(() => {
      expect(screen.getByTestId("token").textContent).toBe("cookie-session");
      expect(screen.getByTestId("user").textContent).toBe("test@example.com");
    });
  });

  it("should show loading state initially when token exists", async () => {
    meAuthenticated = true;

    let resolveMe: (value: unknown) => void;
    const pendingMe = new Promise((resolve) => {
      resolveMe = resolve;
    });

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/v1/me")) {
        return pendingMe.then(() => ({
          ok: true,
          json: () => Promise.resolve({
            id: "dev-user",
            sub: "dev-user",
            email: "test@example.com",
            tenant_memberships: [{ tenant_id: "tenant-1", role: "admin" }],
            workspace_memberships: [{ workspace_id: "workspace-1", role: "admin" }],
            claims: {},
          }),
        }));
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByTestId("isLoading").textContent).toBe("true");

    resolveMe!({});
    await waitFor(() => {
      expect(screen.getByTestId("isLoading").textContent).toBe("false");
    });
  });

  it("should register a silent refresh interval for authenticated sessions", async () => {
    meAuthenticated = true;
    const intervalRegistrations: Array<{ callback: () => void; delay: number }> = [];
    const setIntervalSpy = vi
      .spyOn(window, "setInterval")
      .mockImplementation(((handler: TimerHandler, timeout?: number) => {
        if (typeof handler === "function") {
          intervalRegistrations.push({
            callback: handler as () => void,
            delay: Number(timeout ?? 0),
          });
        }
        return 1 as unknown as ReturnType<typeof setInterval>;
      }) as typeof window.setInterval);

    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("token").textContent).toBe("cookie-session");
    });

    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 12 * 60 * 1000);
    const refreshRegistration = intervalRegistrations.find((entry) => entry.delay === 12 * 60 * 1000);
    expect(refreshRegistration).toBeDefined();

    setIntervalSpy.mockRestore();
  });
});
