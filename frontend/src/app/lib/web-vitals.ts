/**
 * Web Vitals reporting bootstrap.
 *
 * Captures Core Web Vitals (CLS, INP, FCP, LCP, TTFB) once the page is loaded
 * and forwards them to the platform's `/v1/telemetry/client-errors` endpoint
 * via `reportClientError` so they can be correlated with backend traces and
 * surfaced through the platform's FinOps / observability dashboards.
 *
 * The `web-vitals` package is already listed in `package.json` (`^5.2.0`).
 */

import { onCLS, onFCP, onINP, onLCP, onTTFB } from "web-vitals";

import { reportClientError } from "./error-reporting";

interface VitalMetric {
  id: string;
  name: string;
  value: number;
  rating: "good" | "needs-improvement" | "poor";
}

function sendVital(metric: VitalMetric): void {
  // Treat each metric capture as a non-error telemetry event by wrapping
  // the metric payload in an Error so the existing `reportClientError`
  // contract (error + context) is satisfied without introducing a new
  // telemetry transport.
  const wrapped = new Error(
    `web-vital:${metric.name}=${metric.value.toFixed(2)} (${metric.rating})`,
  );
  wrapped.name = "WebVitalMetric";
  void reportClientError(wrapped, {
    source: "web-vitals",
    route:
      typeof window !== "undefined" ? window.location.pathname : "unknown",
    context: {
      metricId: metric.id,
      metricName: metric.name,
      metricValue: metric.value,
      metricRating: metric.rating,
    },
  });
}

let installed = false;

export function initWebVitals(): void {
  if (typeof window === "undefined") return;
  if (installed) return;
  installed = true;

  const handler = (metric: VitalMetric) => sendVital(metric);

  onCLS(handler);
  onFCP(handler);
  onINP(handler);
  onLCP(handler);
  onTTFB(handler);
}
