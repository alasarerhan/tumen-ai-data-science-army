/**
 * Thin fetch wrapper for the Platform API.
 *
 * Security model:
 * - Authentication: HttpOnly cookies (browser cannot read token)
 * - CSRF protection: double-submit token in X-CSRF-Token header for mutations
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || "http://localhost:8000";
const DEFAULT_TIMEOUT = 30_000;
const MAX_RETRIES = 3;
const RETRY_DELAY_BASE = 1_000;
const CSRF_HEADER = "X-CSRF-Token";
const CSRF_ENDPOINT = "/v1/auth/csrf";

let csrfTokenCache: string | null = null;

function jitter(): number {
  return 0.5 + Math.random() * 0.5;
}

function shouldAttachCsrf(method: string): boolean {
  return ["POST", "PUT", "PATCH", "DELETE"].includes(method.toUpperCase());
}

async function fetchCsrfToken(): Promise<string> {
  const response = await fetch(`${BASE_URL}${CSRF_ENDPOINT}`, {
    method: "GET",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error("Failed to initialize CSRF token");
  }
  const payload = (await response.json()) as { csrf_token?: string };
  if (!payload.csrf_token) {
    throw new Error("Missing CSRF token from server");
  }
  csrfTokenCache = payload.csrf_token;
  return payload.csrf_token;
}

export async function getCsrfToken(forceRefresh = false): Promise<string> {
  if (!forceRefresh && csrfTokenCache) {
    return csrfTokenCache;
  }
  return fetchCsrfToken();
}

function buildHeaders(
  method: string,
  body: unknown,
  extraHeaders?: Record<string, string>,
): Record<string, string> {
  const base: Record<string, string> = {
    ...extraHeaders,
  };

  if (!(body instanceof FormData) && !(extraHeaders && "Content-Type" in extraHeaders)) {
    base["Content-Type"] = "application/json";
  }
  if (shouldAttachCsrf(method) && csrfTokenCache) {
    base[CSRF_HEADER] = csrfTokenCache;
  }
  return base;
}

function serializeBody(body: unknown): BodyInit | undefined {
  if (body === undefined) return undefined;
  if (body instanceof FormData) return body;
  if (typeof body === "string") return body;
  return JSON.stringify(body);
}

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetryableError(status: number): boolean {
  return status === 429 || status >= 500;
}

async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeout: number,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      credentials: "include",
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function apiRequest<T = unknown>(
  method: string,
  path: string,
  body?: unknown,
  extraHeaders?: Record<string, string>,
): Promise<T> {
  if (shouldAttachCsrf(method)) {
    await getCsrfToken();
  }
  const headers = buildHeaders(method, body, extraHeaders);
  const url = `${BASE_URL}${path}`;
  const serializedBody = serializeBody(body);

  let lastError: Error | null = null;

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const res = await fetchWithTimeout(
        url,
        {
          method,
          headers,
          body: serializedBody,
        },
        DEFAULT_TIMEOUT,
      );

      if (!res.ok) {
        if (res.status === 403 && shouldAttachCsrf(method) && attempt < MAX_RETRIES - 1) {
          await getCsrfToken(true);
          headers[CSRF_HEADER] = csrfTokenCache || "";
          continue;
        }

        if (isRetryableError(res.status) && attempt < MAX_RETRIES - 1) {
          const delay = RETRY_DELAY_BASE * Math.pow(2, attempt) * jitter();
          await sleep(delay);
          continue;
        }

        let detail = `HTTP ${res.status}`;
        try {
          const err = await res.json();
          detail = err?.detail || `HTTP ${res.status}`;
        } catch {
          /* ignore parse errors */
        }
        throw new Error(detail);
      }

      if (res.status === 204) return undefined as T;

      return res.json() as Promise<T>;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));

      if (lastError.name === "AbortError") {
        throw new Error("Request timed out");
      }

      if (attempt < MAX_RETRIES - 1) {
        const delay = RETRY_DELAY_BASE * Math.pow(2, attempt) * jitter();
        await sleep(delay);
        continue;
      }
    }
  }

  throw lastError || new Error("Request failed after retries");
}

export const apiGet = <T = unknown>(path: string) => apiRequest<T>("GET", path);
export const apiPost = <T = unknown>(path: string, body?: unknown) =>
  apiRequest<T>("POST", path, body);
export const apiPut = <T = unknown>(path: string, body?: unknown) =>
  apiRequest<T>("PUT", path, body);
export const apiDelete = <T = unknown>(path: string) => apiRequest<T>("DELETE", path);

/** Build a URL search string from an object, skipping undefined/null values */
export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export { BASE_URL };

