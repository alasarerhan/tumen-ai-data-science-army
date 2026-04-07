import React from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router";
import { AlertTriangle, ShieldX } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Button } from "../ui/button";

interface ProtectedRouteProps {
  children?: React.ReactNode;
  requiredRole?: "admin";
}

function hasRole(user: { tenant_memberships: Array<{ role: string }>; workspace_memberships: Array<{ role: string }> } | null, role: string): boolean {
  if (!user) return false;
  return (
    user.tenant_memberships.some((m) => m.role === role) ||
    user.workspace_memberships.some((m) => m.role === role)
  );
}

export default function ProtectedRoute({ children, requiredRole }: ProtectedRouteProps) {
  const { token, workspaceId, user, isLoading, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredRole && !hasRole(user, requiredRole)) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 p-6">
        <div className="w-full max-w-md rounded-lg border border-red-200 bg-white p-6 text-center">
          <div className="mb-3 inline-flex rounded-full bg-red-100 p-2 text-red-700">
            <ShieldX size={18} />
          </div>
          <h1 className="text-base font-semibold text-slate-800">Access Denied</h1>
          <p className="mt-2 text-sm text-slate-500">
            You do not have permission to access this page. Please contact an administrator.
          </p>
          <div className="mt-4 flex justify-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => navigate("/dashboard")}>
              Go to Dashboard
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            >
              Sign out
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!workspaceId) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 p-6">
        <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-6 text-center">
          <div className="mb-3 inline-flex rounded-full bg-amber-100 p-2 text-amber-700">
            <AlertTriangle size={18} />
          </div>
          <h1 className="text-base font-semibold text-slate-800">Workspace not selected</h1>
          <p className="mt-2 text-sm text-slate-500">
            Complete onboarding or select a workspace to continue.
          </p>
          <div className="mt-4 flex justify-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => navigate("/onboarding")}>Onboarding</Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            >
              Sign out
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return children ? <>{children}</> : <Outlet />;
}

