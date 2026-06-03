import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import ProtectedRoute from "./ProtectedRoute";

const authState = {
  token: null as string | null,
  workspaceId: null as string | null,
  isLoading: false,
  user: null,
  login: async () => {},
  logout: () => {},
  setWorkspaceId: () => {},
};

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => authState,
}));

function renderWithRoutes(initialEntry = "/dashboard") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<div>Protected Content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  it("redirects to login when token is missing", async () => {
    authState.token = null;
    authState.workspaceId = null;
    authState.isLoading = false;

    renderWithRoutes();

    expect(await screen.findByText("Login Page")).toBeInTheDocument();
  });

  it("renders child route when authenticated with workspace", async () => {
    authState.token = "dev";
    authState.workspaceId = "ws-1";
    authState.isLoading = false;

    renderWithRoutes();

    expect(await screen.findByText("Protected Content")).toBeInTheDocument();
  });

  it("shows workspace guard state when workspace is missing", async () => {
    authState.token = "dev";
    authState.workspaceId = null;
    authState.isLoading = false;

    renderWithRoutes();

    expect(await screen.findByText("Workspace not selected")).toBeInTheDocument();
  });
});
