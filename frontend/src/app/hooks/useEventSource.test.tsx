import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useEventSource } from "../hooks/useEventSource";

vi.mock("../api/client", () => ({
  getCsrfToken: vi.fn().mockResolvedValue("csrf-test-token"),
}));

vi.mock("../api/sse", () => ({
  readSseStream: vi.fn(),
}));

const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("useEventSource", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should return initial state when disabled", () => {
    const { result } = renderHook(() =>
      useEventSource({ url: "http://test.com/stream", enabled: false })
    );

    expect(result.current.events).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
    expect(result.current.error).toBe(null);
  });

  it("should return initial state when url is null", () => {
    const { result } = renderHook(() => useEventSource({ url: null }));

    expect(result.current.events).toEqual([]);
    expect(result.current.isStreaming).toBe(false);
  });

  it("should clear events", () => {
    const { result } = renderHook(() =>
      useEventSource({ url: "http://test.com/stream", enabled: false })
    );

    act(() => {
      result.current.clear();
    });

    expect(result.current.events).toEqual([]);
    expect(result.current.error).toBe(null);
  });

  it("should trigger reconnect", () => {
    const { result } = renderHook(() =>
      useEventSource({ url: "http://test.com/stream", enabled: false })
    );

    act(() => {
      result.current.reconnect();
    });

    expect(result.current.reconnectAttempts).toBe(0);
  });

  it("should start streaming when enabled and url provided", async () => {
    const mockBody = {
      getReader: () => ({
        read: vi.fn().mockResolvedValue({ done: true }),
        releaseLock: vi.fn(),
      }),
    };

    mockFetch.mockResolvedValue({
      ok: true,
      body: mockBody,
    });

    const { result } = renderHook(() =>
      useEventSource({ url: "http://test.com/stream", enabled: true })
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  it("should handle fetch error", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
    });

    const { result } = renderHook(() =>
      useEventSource({ url: "http://test.com/stream", enabled: true, autoReconnect: false })
    );

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
    });
  });

  it("should use custom parse function", async () => {
    const customParse = vi.fn((raw) => ({ parsed: raw }));

    const { result } = renderHook(() =>
      useEventSource({
        url: "http://test.com/stream",
        enabled: false,
        parse: customParse,
      })
    );

    expect(result.current.events).toEqual([]);
  });

  it("should include sse accept header", async () => {
    const mockBody = {
      getReader: () => ({
        read: vi.fn().mockResolvedValue({ done: true }),
        releaseLock: vi.fn(),
      }),
    };

    mockFetch.mockResolvedValue({
      ok: true,
      body: mockBody,
    });

    renderHook(() => useEventSource({ url: "http://test.com/stream", enabled: true }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "http://test.com/stream",
        expect.objectContaining({
          headers: expect.objectContaining({
            Accept: "text/event-stream",
          }),
        })
      );
    });
  });

  it("should use POST method when specified", async () => {
    const mockBody = {
      getReader: () => ({
        read: vi.fn().mockResolvedValue({ done: true }),
        releaseLock: vi.fn(),
      }),
    };

    mockFetch.mockResolvedValue({
      ok: true,
      body: mockBody,
    });

    renderHook(() =>
      useEventSource({ url: "http://test.com/stream", enabled: true, method: "POST" })
    );

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "http://test.com/stream",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            "X-CSRF-Token": "csrf-test-token",
          }),
        })
      );
    });
  });
});
