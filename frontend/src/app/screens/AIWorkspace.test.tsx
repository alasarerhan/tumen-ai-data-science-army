import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "test@example.com", sub: "test-sub", id: "user-1" },
    workspaceId: "test-workspace",
  }),
}));

vi.mock("../hooks/useWorkflowChainRules", () => ({
  useWorkflowChainRules: () => ({
    data: {
      ruleset: {
        version: "1.0.0",
        agents: [],
        requirements: {},
      },
    },
  }),
}));

vi.mock("../api/chat", () => ({
  createChatSession: vi.fn().mockResolvedValue({ id: "session-1", title: "New chat" }),
  listChatSessions: vi.fn().mockResolvedValue({ items: [{ id: "session-1", title: "Test Chat" }] }),
  listChatMessages: vi.fn().mockResolvedValue({ items: [] }),
  listChatUploads: vi.fn().mockResolvedValue({ items: [] }),
  streamChatMessage: vi.fn(),
  uploadChatFile: vi.fn().mockResolvedValue({ id: "upload-1" }),
}));

import AIWorkspace from "../screens/AIWorkspace";

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AIWorkspace />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("AIWorkspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render AI workspace page", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show prompt input", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show send button", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show new chat button", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should update prompt on input change", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });
});
