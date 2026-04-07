import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  useSchedules,
  useWorkflowSchedule,
  usePauseSchedule,
  useResumeSchedule,
} from "../hooks/useSchedules";

vi.mock("../api/scheduler", () => ({
  listScheduledDeployments: vi.fn().mockResolvedValue({ items: [{ deployment_id: "dep-1" }] }),
  getWorkflowSchedule: vi.fn().mockResolvedValue({ deployment_id: "dep-1", paused: false }),
  pauseScheduledDeployment: vi.fn().mockResolvedValue({ deployment_id: "dep-1", paused: true }),
  resumeScheduledDeployment: vi.fn().mockResolvedValue({ deployment_id: "dep-1", paused: false }),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useSchedules", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return schedules data when workspace_id is provided", async () => {
    const { result } = renderHook(() => useSchedules("ws-1"), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toHaveLength(1);
  });

  it("should not fetch when workspace_id is null", () => {
    const { result } = renderHook(() => useSchedules(null), { wrapper: createWrapper() });

    expect(result.current.isFetching).toBe(false);
  });
});

describe("useWorkflowSchedule", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return schedule data when workflow_id is provided", async () => {
    const { result } = renderHook(() => useWorkflowSchedule("wf-1", "ws-1"), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.deployment_id).toBe("dep-1");
  });

  it("should not fetch when workflow_id is undefined", () => {
    const { result } = renderHook(() => useWorkflowSchedule(undefined, "ws-1"), {
      wrapper: createWrapper(),
    });

    expect(result.current.isFetching).toBe(false);
  });
});

describe("usePauseSchedule", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should pause schedule mutation", async () => {
    const { result } = renderHook(() => usePauseSchedule(), { wrapper: createWrapper() });

    result.current.mutate({ deployment_id: "dep-1", workspace_id: "ws-1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe("useResumeSchedule", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should resume schedule mutation", async () => {
    const { result } = renderHook(() => useResumeSchedule(), { wrapper: createWrapper() });

    result.current.mutate({ deployment_id: "dep-1", workspace_id: "ws-1" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});
