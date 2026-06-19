import React from "react";
import { createBrowserRouter, redirect } from "react-router";
import Login from "./screens/Login";
import Dashboard from "./screens/Dashboard";
import RunsList from "./screens/RunsList";
import RunDetail from "./screens/RunDetail";
import Workflows from "./screens/Workflows";
import WorkflowDetail from "./screens/WorkflowDetail";
import WorkflowDesigner from "./screens/WorkflowDesigner";
import Reports from "./screens/Reports";
import ModelOps from "./screens/ModelOps";
import StrategicReport from "./screens/StrategicReport";
import CloudOps from "./screens/CloudOps";
import HITLApproval from "./screens/HITLApproval";
import DataSources from "./screens/DataSources";
import Settings from "./screens/Settings";
import Onboarding from "./screens/Onboarding";
import Agents from "./screens/Agents";
import AIWorkspace from "./screens/AIWorkspace";
import PipelineMonitor from "./screens/PipelineMonitor";
import AdminDashboard from "./screens/AdminDashboard";
import ProtectedRoute from "./components/layout/ProtectedRoute";
import RouteErrorBoundary from "./components/layout/RouteErrorBoundary";

export const router = createBrowserRouter([
  {
    path: "/",
    loader: () => redirect("/dashboard"),
    errorElement: React.createElement(RouteErrorBoundary),
  },
  {
    path: "/login",
    Component: Login,
    errorElement: React.createElement(RouteErrorBoundary),
  },
  {
    path: "/onboarding",
    Component: Onboarding,
    errorElement: React.createElement(RouteErrorBoundary),
  },
  {
    element: React.createElement(ProtectedRoute),
    errorElement: React.createElement(RouteErrorBoundary),
    children: [
      { path: "/dashboard", Component: Dashboard, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/runs", Component: RunsList, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/runs/:id", Component: RunDetail, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/workflows", Component: Workflows, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/workflows/new", Component: WorkflowDesigner, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/workflows/:id", Component: WorkflowDetail, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/workflows/:id/designer", Component: WorkflowDesigner, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/reports", Component: Reports, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/modelops", Component: ModelOps, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/reports/:id", Component: StrategicReport, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/deployments", Component: CloudOps, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/approvals/:id", Component: HITLApproval, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/data-sources", Component: DataSources, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/settings", Component: Settings, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/agents", Component: Agents, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/ai-workspace", Component: AIWorkspace, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/monitor", Component: PipelineMonitor, errorElement: React.createElement(RouteErrorBoundary) },
      { path: "/monitor/:runId", Component: PipelineMonitor, errorElement: React.createElement(RouteErrorBoundary) },
    ],
  },
  {
    element: React.createElement(ProtectedRoute, { requiredRole: "admin" }),
    errorElement: React.createElement(RouteErrorBoundary),
    children: [
      { path: "/admin", Component: AdminDashboard, errorElement: React.createElement(RouteErrorBoundary) },
    ],
  },
]);
