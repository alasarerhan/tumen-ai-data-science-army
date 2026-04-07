import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useRuns, useRun, useTriggerRun, useCancelRun, useRetryRun } from "../hooks/useRuns";

vi.mock("../api/runs", () => ({
  getRuns: vi.fn().mockResolvedValue({ items: [{ id: "run-1", status: "completed" }] }),
  getRun: vi.fn().mockResolvedValue({ id: "run-1", status: "running" }),
  triggerRun: vi.fn().mockResolvedValue({ id: "run-2", status: "pending" }),
  cancelRun: vi.fn().mockResolvedValue({ id: "run-1", status: "cancelled" }),
  retryRun: vi.fn().mockResolvedValue({ id: "run-3", status: "pending" }),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useRuns", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return runs data when workspace_id is provided", async () => {
    const { result } = renderHook(() => useRuns("ws-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
  });

  it("should not fetch when workspace_id is null", () => {
    const { result } = renderHook(() => useRuns(null), { wrapper: createWrapper() });

    expect(result.current.isFetching).toBe(false);
  });
});

describe("useRun", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return run data when run_id is provided", async () => {
    const { result } = renderHook(() => useRun("run-1", "ws-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.id).toBe("run-1");
  });

  it("should not fetch when run_id is undefined", () => {
    const { result } = renderHook(() => useRun(undefined, "ws-1"), { wrapper: createWrapper() });

    expect(result.current.isFetching).toBe(false);
  });
});

describe("useTriggerRun", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should trigger run mutation", async () => {
    const { result } = renderHook(() => useTriggerRun(), { wrapper: createWrapper() });

    result.current.mutate({ workspace_id: "ws-1", flow_key: "test-flow" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe("useCancelRun", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should cancel run mutation", async () => {
    const { result } = renderHook(() => useCancelRun("ws-1"), { wrapper: createWrapper() });

    result.current.mutate("run-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe("useRetryRun", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should retry run mutation", async () => {
    const { result } = renderHook(() => useRetryRun("ws-1"), { wrapper: createWrapper() });

    result.current.mutate("run-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
