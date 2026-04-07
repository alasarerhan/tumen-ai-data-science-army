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

export const router = createBrowserRouter([
  {
    path: "/",
    loader: () => redirect("/dashboard"),
  },
  {
    path: "/login",
    Component: Login,
  },
  {
    path: "/onboarding",
    Component: Onboarding,
  },
  {
    element: React.createElement(ProtectedRoute),
    children: [
      { path: "/dashboard", Component: Dashboard },
      { path: "/runs", Component: RunsList },
      { path: "/runs/:id", Component: RunDetail },
      { path: "/workflows", Component: Workflows },
      { path: "/workflows/new", Component: WorkflowDesigner },
      { path: "/workflows/:id", Component: WorkflowDetail },
      { path: "/workflows/:id/designer", Component: WorkflowDesigner },
      { path: "/reports", Component: Reports },
      { path: "/reports/:id", Component: StrategicReport },
      { path: "/deployments", Component: CloudOps },
      { path: "/approvals/:id", Component: HITLApproval },
      { path: "/data-sources", Component: DataSources },
      { path: "/settings", Component: Settings },
      { path: "/agents", Component: Agents },
      { path: "/ai-workspace", Component: AIWorkspace },
      { path: "/monitor", Component: PipelineMonitor },
      { path: "/monitor/:runId", Component: PipelineMonitor },
      { path: "/admin", Component: AdminDashboard },
    ],
  },
]);
