import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  useWorkflows,
  useWorkflow,
  useCreateWorkflow,
  usePublishWorkflow,
  useArchiveWorkflow,
} from "../hooks/useWorkflows";

vi.mock("../api/workflows", () => ({
  getWorkflows: vi.fn().mockResolvedValue({ items: [{ id: "wf-1", name: "Test" }] }),
  getWorkflow: vi.fn().mockResolvedValue({ id: "wf-1", name: "Test", spec: {} }),
  createWorkflow: vi.fn().mockResolvedValue({ id: "wf-2", name: "New" }),
  publishWorkflow: vi.fn().mockResolvedValue({ id: "wf-1", status: "published" }),
  archiveWorkflow: vi.fn().mockResolvedValue({ id: "wf-1", archived: true }),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useWorkflows", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return workflows data when workspace_id is provided", async () => {
    const { result } = renderHook(() => useWorkflows("ws-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
  });

  it("should not fetch when workspace_id is null", () => {
    const { result } = renderHook(() => useWorkflows(null), { wrapper: createWrapper() });

    expect(result.current.isFetching).toBe(false);
  });
});

describe("useWorkflow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return workflow data when workflow_id is provided", async () => {
    const { result } = renderHook(() => useWorkflow("wf-1", "ws-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe("wf-1");
  });

  it("should not fetch when workflow_id is undefined", () => {
    const { result } = renderHook(() => useWorkflow(undefined, "ws-1"), { wrapper: createWrapper() });

    expect(result.current.isFetching).toBe(false);
  });
});

describe("useCreateWorkflow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should create workflow mutation", async () => {
    const { result } = renderHook(() => useCreateWorkflow(), { wrapper: createWrapper() });

    result.current.mutate({ workspace_id: "ws-1", name: "New", spec: {} });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe("usePublishWorkflow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should publish workflow mutation", async () => {
    const { result } = renderHook(() => usePublishWorkflow(), { wrapper: createWrapper() });

    result.current.mutate({ id: "wf-1", workspace_id: "ws-1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe("useArchiveWorkflow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should archive workflow mutation", async () => {
    const { result } = renderHook(() => useArchiveWorkflow(), { wrapper: createWrapper() });

    result.current.mutate({ id: "wf-1", workspace_id: "ws-1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
