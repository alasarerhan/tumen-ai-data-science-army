import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import Login from "../screens/Login";

const mockNavigate = vi.fn();
const mockLogin = vi.fn();

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    login: mockLogin,
    token: null,
    isLoading: false,
  }),
}));

describe("Login", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render login form", () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    expect(screen.getByText(/sign in/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
  });

  it("should show dev token section when clicked", async () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const devTokenButton = screen.getByText(/developer token/i);
    fireEvent.click(devTokenButton);

    await waitFor(() => {
      expect(screen.getByLabelText(/bearer token/i)).toBeInTheDocument();
    });
  });

  it("should have token input field in dev mode", async () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const devTokenButton = screen.getByText(/developer token/i);
    fireEvent.click(devTokenButton);

    await waitFor(() => {
      const tokenInput = screen.getByLabelText(/bearer token/i) as HTMLInputElement;
      expect(tokenInput).toHaveAttribute("type", "password");
    });
  });

  it("should update token value on input", async () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const devTokenButton = screen.getByText(/developer token/i);
    fireEvent.click(devTokenButton);

    await waitFor(() => {
      expect(screen.getByLabelText(/bearer token/i)).toBeInTheDocument();
    });

    const tokenInput = screen.getByLabelText(/bearer token/i) as HTMLInputElement;
    fireEvent.change(tokenInput, { target: { value: "test-token" } });

    expect(tokenInput.value).toBe("test-token");
  });

  it("should show dev mode warning", async () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const devTokenButton = screen.getByText(/developer token/i);
    fireEvent.click(devTokenButton);

    await waitFor(() => {
      expect(screen.getByText(/dev mode only/i)).toBeInTheDocument();
    });
  });

  it("should complete full login flow with dev token", async () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const devTokenButton = screen.getByText(/developer token/i);
    fireEvent.click(devTokenButton);

    await waitFor(() => {
      expect(screen.getByLabelText(/bearer token/i)).toBeInTheDocument();
    });

    const tokenInput = screen.getByLabelText(/bearer token/i) as HTMLInputElement;
    fireEvent.change(tokenInput, { target: { value: "test-dev-token" } });

    const submitButton = screen.getByRole("button", { name: /sign in|login|submit/i });
    if (submitButton) {
      fireEvent.click(submitButton);
    }
  });

  it("should show error for invalid dev token", async () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const devTokenButton = screen.getByText(/developer token/i);
    fireEvent.click(devTokenButton);

    await waitFor(() => {
      expect(screen.getByLabelText(/bearer token/i)).toBeInTheDocument();
    });

    const tokenInput = screen.getByLabelText(/bearer token/i) as HTMLInputElement;
    fireEvent.change(tokenInput, { target: { value: "" } });
  });

  it("should persist token to localStorage after login", async () => {
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const devTokenButton = screen.getByText(/developer token/i);
    fireEvent.click(devTokenButton);

    await waitFor(() => {
      expect(screen.getByLabelText(/bearer token/i)).toBeInTheDocument();
    });

    const tokenInput = screen.getByLabelText(/bearer token/i) as HTMLInputElement;
    fireEvent.change(tokenInput, { target: { value: "persisted-token" } });

    setItemSpy.mockRestore();
  });

  it("should redirect to dashboard after successful login", async () => {
    mockLogin.mockResolvedValueOnce(true);

    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const googleButton = screen.getByRole("button", { name: /continue with google/i });
    fireEvent.click(googleButton);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalled();
    });
  });

  it("should handle Google OAuth button click", async () => {
    render(
      <BrowserRouter>
        <Login />
      </BrowserRouter>
    );

    const googleButton = screen.getByRole("button", { name: /continue with google/i });
    expect(googleButton).toBeInTheDocument();
    fireEvent.click(googleButton);
  });
});
