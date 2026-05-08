import React, { useEffect } from "react";
import { isRouteErrorResponse, useLocation, useNavigate, useRouteError } from "react-router";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";
import { Button } from "../ui/button";
import { reportClientError } from "../../lib/error-reporting";

function getRouteErrorMessage(error: unknown): { message: string; title: string } {
  if (isRouteErrorResponse(error)) {
    return {
      title: `${error.status} ${error.statusText}`,
      message:
        typeof error.data === "string" && error.data.trim()
          ? error.data
          : "The requested route failed to load.",
    };
  }

  if (error instanceof Error) {
    return {
      title: "Route crashed",
      message: error.message,
    };
  }

  return {
    title: "Route crashed",
    message: "An unexpected route error occurred.",
  };
}

export default function RouteErrorBoundary() {
  const error = useRouteError();
  const location = useLocation();
  const navigate = useNavigate();
  const detail = getRouteErrorMessage(error);

  useEffect(() => {
    const normalized =
      error instanceof Error
        ? error
        : new Error(isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : detail.message);

    void reportClientError(normalized, {
      source: "route",
      route: location.pathname,
      context: isRouteErrorResponse(error)
        ? {
            data: error.data,
            status: error.status,
            status_text: error.statusText,
          }
        : undefined,
    });
  }, [detail.message, error, location.pathname]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 text-center shadow-lg">
        <div className="mb-4 inline-flex rounded-full bg-amber-100 p-3">
          <AlertTriangle size={24} className="text-amber-700" />
        </div>
        <h1 className="mb-2 text-xl font-semibold text-slate-900">{detail.title}</h1>
        <p className="mb-6 text-sm text-slate-500">{detail.message}</p>
        <div className="flex justify-center gap-3">
          <Button
            variant="secondary"
            size="md"
            leadingIcon={<RefreshCw size={14} />}
            onClick={() => window.location.reload()}
          >
            Try Again
          </Button>
          <Button
            variant="primary"
            size="md"
            leadingIcon={<Home size={14} />}
            onClick={() => navigate("/dashboard", { replace: true })}
          >
            Go Home
          </Button>
        </div>
      </div>
    </div>
  );
}
