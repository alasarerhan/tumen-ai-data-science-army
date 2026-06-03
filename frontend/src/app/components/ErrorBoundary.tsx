import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import { Button } from "./ui/button";
import { reportClientError } from "../lib/error-reporting";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo });
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    void reportClientError(error, {
      source: "app",
      route: window.location.pathname,
      componentStack: errorInfo.componentStack ?? undefined,
    });
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    this.props.onReset?.();
  };

  handleGoHome = (): void => {
    window.location.href = "/dashboard";
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
          <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 text-center shadow-lg">
            <div className="mb-4 inline-flex rounded-full bg-red-100 p-3">
              <AlertTriangle size={24} className="text-red-600" />
            </div>
            <h1 className="mb-2 text-xl font-semibold text-slate-900">
              Something went wrong
            </h1>
            <p className="mb-6 text-sm text-slate-500">
              An unexpected error occurred. Please try again or contact support if the problem persists.
            </p>
            {this.state.error && (
              <details className="mb-6 rounded bg-slate-100 p-3 text-left">
                <summary className="cursor-pointer text-xs font-medium text-slate-600">
                  Error details
                </summary>
                <pre className="mt-2 overflow-auto text-xs text-slate-500">
                  {this.state.error.message}
                  {this.state.errorInfo?.componentStack && (
                    <>
                      {"\n\nComponent Stack:"}
                      {this.state.errorInfo.componentStack}
                    </>
                  )}
                </pre>
              </details>
            )}
            <div className="flex justify-center gap-3">
              <Button
                variant="secondary"
                size="md"
                leadingIcon={<RefreshCw size={14} />}
                onClick={this.handleReset}
              >
                Try Again
              </Button>
              <Button
                variant="primary"
                size="md"
                leadingIcon={<Home size={14} />}
                onClick={this.handleGoHome}
              >
                Go Home
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
