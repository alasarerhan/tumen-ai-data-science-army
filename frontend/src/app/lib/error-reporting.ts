/**
 * Client-side error reporting.
 *
 * Captures errors thrown by the React tree (ErrorBoundary), route loaders
 * (RouteErrorBoundary), and background auth flows (AuthContext), and ships
 * them to the backend telemetry endpoint for aggregation.
 *
 * The transport is best-effort: failures during reporting must never propagate
 * back to the caller or crash the UI further. All network errors are swallowed
 * after logging to the console.
 */

export interface ErrorReportContext {
  /** Which subsystem raised the error. Free-form, but typical values:
   *  "app" | "route" | "auth" | "ui" */
  source: string;
  /** Route path where the error was captured (e.g. window.location.pathname). */
  route: string;
  /** Arbitrary extra structured context — component stack, phase label, etc. */
  context?: Record<string, unknown>;
}

interface SerializedError {
  name: string;
  message: string;
  stack?: string;
}

function serializeError(error: unknown): SerializedError {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      stack: error.stack,
    };
  }
  if (typeof error === "string") {
    return { name: "StringError", message: error };
  }
  try {
    return {
      name: "UnknownError",
      message: JSON.stringify(error),
    };
  } catch {
    return { name: "UnknownError", message: String(error) };
  }
}

/**
 * Report a client-side error to the backend telemetry endpoint.
 * Resolves once the request completes (or is silently dropped on failure).
 * Never throws — reporting failures must not affect the host application.
 */
export async function reportClientError(
  error: unknown,
  context: ErrorReportContext,
): Promise<void> {
  const payload = {
    error: serializeError(error),
    source: context.source,
    route: context.route,
    context: context.context ?? {},
    userAgent:
      typeof navigator !== "undefined" ? navigator.userAgent : "unknown",
    timestamp: new Date().toISOString(),
  };

  try {
    await fetch("/v1/telemetry/client-errors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(payload),
      // Reporting should not block UX; rely on browser default + page lifecycle.
      keepalive: true,
    });
  } catch (reportingError) {
    // Telemetry must never throw — log to console for local debugging only.
    // eslint-disable-next-line no-console
    console.warn("[error-reporting] failed to submit report:", reportingError);
  }
}
