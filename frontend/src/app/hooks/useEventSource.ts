import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { withCsrfHeader } from "../api/client";
import { readSseStream } from "../api/sse";

export interface UseEventSourceOptions<TEvent> {
  url: string | null;
  enabled?: boolean;
  method?: "GET" | "POST";
  body?: string;
  headers?: Record<string, string>;
  parse?: (raw: string) => TEvent;
  onEvent?: (event: TEvent) => void;
  eventIdField?: string;
  maxRetries?: number;
  retryDelayMs?: number;
  autoReconnect?: boolean;
}

interface UseEventSourceResult<TEvent> {
  events: TEvent[];
  isStreaming: boolean;
  error: string | null;
  clear: () => void;
  reconnect: () => void;
  lastEventId: string | null;
  reconnectAttempts: number;
}

function defaultParse(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return raw;
  }
}

export function useEventSource<TEvent = unknown>({
  url,
  enabled = true,
  method = "GET",
  body,
  headers,
  parse,
  onEvent,
  eventIdField = "id",
  maxRetries = 3,
  retryDelayMs = 1000,
  autoReconnect = true,
}: UseEventSourceOptions<TEvent>): UseEventSourceResult<TEvent> {
  const [events, setEvents] = useState<TEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastEventId, setLastEventId] = useState<string | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [reconnectTrigger, setReconnectTrigger] = useState(0);

  const abortRef = useRef<AbortController | null>(null);
  const lastEventIdRef = useRef<string | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isCurrentStreamRef = useRef(false);

  const parser = useMemo(() => parse ?? (defaultParse as (raw: string) => TEvent), [parse]);

  const clear = useCallback(() => {
    setEvents([]);
    setError(null);
    setLastEventId(null);
    lastEventIdRef.current = null;
    setReconnectAttempts(0);
    reconnectAttemptsRef.current = 0;
  }, []);

  const reconnect = useCallback(() => {
    setReconnectTrigger((prev) => prev + 1);
  }, []);

  useEffect(() => {
    isCurrentStreamRef.current = false;
    abortRef.current?.abort();
    abortRef.current = null;

    if (!enabled || !url) {
      setIsStreaming(false);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    isCurrentStreamRef.current = true;
    setIsStreaming(true);
    setError(null);

    const requestHeaders: Record<string, string> = {
      Accept: "text/event-stream",
      ...(lastEventIdRef.current ? { "Last-Event-ID": lastEventIdRef.current } : {}),
      ...headers,
    };

    const readStream = async () => {
      try {
        if (method !== "GET") {
          Object.assign(requestHeaders, await withCsrfHeader());
        }
        const response = await fetch(url, {
          method,
          body,
          headers: requestHeaders,
          credentials: "include",
          signal: controller.signal,
        });

        if (!isCurrentStreamRef.current) return;

        if (!response.ok || !response.body) {
          throw new Error(`Stream failed with HTTP ${response.status}`);
        }

        setReconnectAttempts(0);
        reconnectAttemptsRef.current = 0;

        await readSseStream({
          stream: response.body,
          parse: parser,
          onEvent: (event) => {
            if (!isCurrentStreamRef.current) return;

            const eventId = (event as Record<string, unknown>)?.[eventIdField];
            if (typeof eventId === "string" && eventId) {
              lastEventIdRef.current = eventId;
              setLastEventId(eventId);
            }

            setEvents((prev) => {
              const existingIds = new Set(
                prev
                  .map((e) => (e as Record<string, unknown>)?.[eventIdField])
                  .filter((id): id is string => typeof id === "string")
              );
              const newEventId = (event as Record<string, unknown>)?.[eventIdField];
              if (typeof newEventId === "string" && existingIds.has(newEventId)) {
                return prev;
              }
              return [...prev, event];
            });
            onEvent?.(event);
          },
        });
      } catch (err: unknown) {
        if (!isCurrentStreamRef.current || controller.signal.aborted) return;

        const message = err instanceof Error ? err.message : "Unknown stream error";
        setError(message);

        if (autoReconnect && reconnectAttemptsRef.current < maxRetries) {
          const baseDelay = retryDelayMs * Math.pow(2, reconnectAttemptsRef.current);
          const jitter = baseDelay * 0.1 * Math.random();
          const delay = baseDelay + jitter;
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current += 1;
            setReconnectAttempts(reconnectAttemptsRef.current);
            setReconnectTrigger((prev) => prev + 1);
          }, delay);
        }
      } finally {
        if (isCurrentStreamRef.current && !controller.signal.aborted) {
          setIsStreaming(false);
        }
      }
    };

    void readStream();

    return () => {
      isCurrentStreamRef.current = false;
      controller.abort();
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      setIsStreaming(false);
    };
  }, [
    url,
    enabled,
    method,
    body,
    headers,
    parser,
    onEvent,
    eventIdField,
    maxRetries,
    retryDelayMs,
    autoReconnect,
    reconnectTrigger,
  ]);

  return {
    events,
    isStreaming,
    error,
    clear,
    reconnect,
    lastEventId,
    reconnectAttempts,
  };
}
