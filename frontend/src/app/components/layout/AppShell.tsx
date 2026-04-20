import React, { useState } from "react";
import { NavLink, useNavigate } from "react-router";
import {
  LayoutDashboard,
  PlayCircle,
  GitBranch,
  Database,
  Bot,
  BarChart2,
  Cloud,
  Settings,
  ChevronLeft,
  ChevronRight,
  Bell,
  Search,
  LogOut,
  ChevronsUpDown,
  Zap,
  Menu,
  X,
  MessageSquare,
  Activity,
  Shield,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { Avatar } from "../ui/avatar";
import { useAuth } from "../../context/AuthContext";
import { Tooltip, TooltipContent, TooltipTrigger } from "../ui/tooltip";

interface NavItem {
  label: string;
  icon: React.ReactNode;
  to: string;
}

const navItems: NavItem[] = [
  { label: "Home", icon: <LayoutDashboard size={18} />, to: "/dashboard" },
  { label: "Runs", icon: <PlayCircle size={18} />, to: "/runs" },
  { label: "Workflows", icon: <GitBranch size={18} />, to: "/workflows" },
  { label: "AI Workspace", icon: <MessageSquare size={18} />, to: "/ai-workspace" },
  { label: "Monitor", icon: <Activity size={18} />, to: "/monitor" },
  { label: "Data Sources", icon: <Database size={18} />, to: "/data-sources" },
  { label: "Agents", icon: <Bot size={18} />, to: "/agents" },
  { label: "Reports", icon: <BarChart2 size={18} />, to: "/reports" },
  { label: "Deployments", icon: <Cloud size={18} />, to: "/deployments" },
];

const adminNavItems: NavItem[] = [
  { label: "Admin", icon: <Shield size={18} />, to: "/admin" },
];

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const { user, workspaceId, logout } = useAuth();

  const shellUser = user
    ? {
        id: user.id,
        name: user.email ?? user.sub,
        email: user.email ?? "",
        role: "Viewer" as const,
        initials: (user.email ?? user.sub).split("@")[0].slice(0, 2).toUpperCase(),
      }
    : { id: "anon", name: "User", email: "", role: "Viewer" as const, initials: "U" };

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className={cn("flex h-14 items-center gap-2 border-b border-slate-200 px-3", collapsed && "justify-center")}> 
        <div className="flex size-7 items-center justify-center rounded-md bg-indigo-600">
          <Zap size={14} className="text-white" />
        </div>
        {!collapsed ? <span className="text-sm font-semibold text-slate-800">Insight Platform</span> : null}
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-2" aria-label="Main navigation">
        {navItems.map((item) => (
          <Tooltip key={item.to} delayDuration={300}>
            <TooltipTrigger asChild>
              <NavLink
                to={item.to}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100",
                    collapsed && "justify-center px-1",
                  )
                }
              >
                {item.icon}
                <span className={cn("truncate", collapsed && "sr-only")}>{item.label}</span>
              </NavLink>
            </TooltipTrigger>
            {collapsed && (
              <TooltipContent side="right" sideOffset={10}>
                {item.label}
              </TooltipContent>
            )}
          </Tooltip>
        ))}
      </nav>

      <div className="space-y-1 border-t border-slate-200 p-2">
        {adminNavItems.map((item) => (
          <Tooltip key={item.to} delayDuration={300}>
            <TooltipTrigger asChild>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100",
                    collapsed && "justify-center px-1",
                  )
                }
              >
                {item.icon}
                <span className={cn("truncate", collapsed && "sr-only")}>{item.label}</span>
              </NavLink>
            </TooltipTrigger>
            {collapsed && (
              <TooltipContent side="right" sideOffset={10}>
                {item.label}
              </TooltipContent>
            )}
          </Tooltip>
        ))}
        <Tooltip delayDuration={300}>
          <TooltipTrigger asChild>
            <NavLink
              to="/settings"
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100",
                  collapsed && "justify-center px-1",
                )
              }
            >
              <Settings size={18} />
              <span className={cn(collapsed && "sr-only")}>Settings</span>
            </NavLink>
          </TooltipTrigger>
          {collapsed && (
            <TooltipContent side="right" sideOffset={10}>
              Settings
            </TooltipContent>
          )}
        </Tooltip>
        <Tooltip delayDuration={300}>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={() => setCollapsed((value) => !value)}
              className="hidden w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-500 hover:bg-slate-100 lg:flex"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
              {!collapsed ? <span>Collapse</span> : null}
            </button>
          </TooltipTrigger>
          {collapsed && (
            <TooltipContent side="right" sideOffset={10}>
              Expand
            </TooltipContent>
          )}
        </Tooltip>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50">
      {mobileOpen ? <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setMobileOpen(false)} /> : null}

      <aside
        className={cn(
          "hidden border-r border-slate-200 bg-white transition-all duration-150 lg:block",
          collapsed ? "w-16" : "w-60",
        )}
      >
        {sidebar}
      </aside>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 w-64 border-r border-slate-200 bg-white transition-transform lg:hidden",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-14 items-center justify-between border-b border-slate-200 px-3">
          <span className="text-sm font-semibold text-slate-800">Insight Platform</span>
          <button type="button" onClick={() => setMobileOpen(false)} className="rounded p-1 text-slate-500 hover:bg-slate-100" aria-label="Close navigation">
            <X size={16} />
          </button>
        </div>
        {sidebar}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4">
          <div className="flex items-center gap-2">
            <button type="button" className="rounded p-1 text-slate-500 hover:bg-slate-100 lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
              <Menu size={18} />
            </button>
            <button
              type="button"
              className="hidden items-center gap-2 rounded-md border border-slate-200 px-3 py-1 text-sm text-slate-700 sm:flex"
            >
              <span className="font-medium">{workspaceId ?? "Workspace"}</span>
              <ChevronsUpDown size={14} className="text-slate-400" />
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button type="button" className="hidden items-center gap-2 rounded-md border border-slate-200 px-3 py-1 text-sm text-slate-400 sm:flex" aria-label="Search">
              <Search size={14} /> Search
            </button>
            <button type="button" className="rounded p-2 text-slate-500 hover:bg-slate-100" aria-label="Notifications">
              <Bell size={16} />
            </button>
            <button type="button" onClick={() => navigate("/settings")} className="rounded-full">
              <Avatar user={shellUser} size={32} />
            </button>
            <button type="button" onClick={handleLogout} className="rounded p-2 text-slate-500 hover:bg-slate-100" aria-label="Sign out">
              <LogOut size={16} />
            </button>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}

