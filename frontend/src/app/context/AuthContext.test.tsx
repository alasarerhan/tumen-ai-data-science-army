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
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/v1/auth/login/dev")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ access_token: "dev-token", user: { email: "dev@localhost" } }),
        });
      }
      if (url.includes("/v1/me")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ email: "test@example.com" }),
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

  it("should show loading state initially when token exists", async () => {
    Object.defineProperty(document, "cookie", {
      writable: true,
      value: "access_token=existing-token",
    });

    let resolveMe: (value: unknown) => void;
    const pendingMe = new Promise((resolve) => {
      resolveMe = resolve;
    });

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/v1/me")) {
        return pendingMe.then(() => ({
          ok: true,
          json: () => Promise.resolve({ email: "test@example.com" }),
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
});
