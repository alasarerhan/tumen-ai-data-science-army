/**
 * Frontend error-reporting bootstrap.
 *
 * Wires the browser's `window.onerror` and `unhandledrejection` handlers to
 * forward uncaught errors to the platform's `/v1/telemetry/client-errors`
 * endpoint via `reportClientError`. This is intentionally minimal: the
 * project does not depend on the `@sentry/browser` SDK, so the function
 * name is preserved for compatibility while the implementation routes
 * through the project's existing telemetry pipeline.
 */

import { reportClientError } from "./error-reporting";

/**
 * Install global error handlers that forward uncaught exceptions to the
 * platform's telemetry endpoint. Safe to call multiple times — handlers
 * are guarded against double-registration.
 */
let installed = false;

export function initSentry(): void {
  if (typeof window === "undefined") return;
  if (installed) return;
  installed = true;

  window.addEventListener("error", (event) => {
    const err =
      event.error instanceof Error
        ? event.error
        : new Error(event.message || "Unknown window error");
    void reportClientError(err, {
      source: "window.error",
      route: window.location.pathname,
      context: {
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      },
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason =
      event.reason instanceof Error
        ? event.reason
        : new Error(
            typeof event.reason === "string"
              ? event.reason
              : "Unhandled promise rejection",
          );
    void reportClientError(reason, {
      source: "window.unhandledrejection",
      route: window.location.pathname,
    });
  });
}
