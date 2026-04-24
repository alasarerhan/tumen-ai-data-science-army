import React, { useState } from "react";
import { AppShell } from "../components/layout/AppShell";
import { Avatar } from "../components/ui/avatar";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { useAuth } from "../context/AuthContext";
import { cn } from "../lib/utils";
import { toast } from "sonner";
import {
  User,
  Building,
  Users,
  Key,
  Bell,
  AlertTriangle,
  Eye,
  EyeOff,
  Plus,
  Trash2,
  RefreshCw,
  CheckCircle2,
  Copy,
} from "lucide-react";

const SETTINGS_NAV = [
  { id: "profile", label: "Profile", icon: <User size={16} /> },
  { id: "workspace", label: "Workspace", icon: <Building size={16} /> },
  { id: "members", label: "Members & RBAC", icon: <Users size={16} /> },
  { id: "api-keys", label: "API Keys", icon: <Key size={16} /> },
  { id: "notifications", label: "Notifications", icon: <Bell size={16} /> },
  { id: "danger", label: "Danger Zone", icon: <AlertTriangle size={16} /> },
];

function Toggle({ checked, onChange, "aria-label": ariaLabel }: { checked: boolean; onChange: () => void; "aria-label"?: string }) {
  return (
    <button
      onClick={onChange}
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      className={cn(
        "w-10 h-5 rounded-full transition-colors flex-shrink-0 relative",
        checked ? "bg-indigo-600" : "bg-slate-200 dark:bg-slate-700"
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 size-4 rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-5" : "translate-x-0.5"
        )}
      />
    </button>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="border-b border-slate-200 dark:border-slate-700 pb-3 mb-5">
      <h2 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "20px", fontWeight: 600 }}>{title}</h2>
    </div>
  );
}

export default function Settings() {
  const { user, workspaceId } = useAuth();
  const shellUser = user
    ? {
        id: user.id ?? "me",
        name: (user.email ?? user.sub ?? "user").split("@")[0],
        email: user.email ?? "",
        role: "Admin" as const,
        initials: (user.email ?? user.sub ?? "us").slice(0, 2).toUpperCase(),
      }
    : null;
  const [activeSection, setActiveSection] = useState("profile");

  // Profile state
  const [fullName, setFullName] = useState(user?.email?.split("@")[0] ?? "");
  const [jobTitle, setJobTitle] = useState("Senior Data Scientist");
  const [unsaved, setUnsaved] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isInviting, setIsInviting] = useState(false);

  // Notifications state
  const [notifToggles, setNotifToggles] = useState({
    runCompleted: true,
    runFailed: true,
    approvalRequired: true,
    deploymentSucceeded: false,
    newMemberJoined: false,
  });

  // API Keys
  const [showNewKey, setShowNewKey] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [apiKeys] = useState([
    { id: "k1", name: "Production Key", created: "Jan 15, 2026", lastUsed: "2h ago" },
    { id: "k2", name: "CI/CD Key", created: "Feb 1, 2026", lastUsed: "1d ago" },
  ]);

  // Delete workspace
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");

  const handleNotifToggle = (key: keyof typeof notifToggles) => {
    setNotifToggles((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const generateKey = () => {
    const key = "sk-" + Array.from({ length: 32 }, () => Math.random().toString(36)[2]).join("");
    setGeneratedKey(key);
  };

  return (
    <AppShell>
      <div className="flex h-full">
        {/* Sub-nav */}
        <aside className="w-52 flex-shrink-0 border-r border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 py-5 px-3 space-y-0.5">
          {SETTINGS_NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveSection(item.id)}
              aria-current={activeSection === item.id ? "page" : undefined}
              className={cn(
                "w-full flex items-center gap-2.5 px-3 py-2 rounded-[6px] text-sm transition-colors text-left",
                activeSection === item.id
                  ? "bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800",
                item.id === "danger" && "text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 mt-4"
              )}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </aside>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-xl">
            {/* Profile */}
            {activeSection === "profile" && (
              <div>
                <SectionHeader title="Profile" />
                {unsaved && (
                  <div className="mb-4 flex items-center gap-2 px-3 py-2 rounded bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 text-amber-700 dark:text-amber-400 text-sm">
                    <AlertTriangle size={14} />
                    Unsaved changes
                  </div>
                )}
                <div className="flex items-center gap-4 mb-6">
                  {shellUser && <Avatar user={shellUser} size={64} />}
                  <Button variant="ghost" size="sm">Change Photo</Button>
                </div>
                <div className="space-y-4">
                  {[
                    { label: "Full Name", value: fullName, setter: (v: string) => { setFullName(v); setUnsaved(true); } },
                    { label: "Email", value: user?.email ?? "", disabled: true },
                    { label: "Job Title", value: jobTitle, setter: (v: string) => { setJobTitle(v); setUnsaved(true); } },
                  ].map((field) => (
                    <div key={field.label} className="space-y-1.5">
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">{field.label}</label>
                      <input
                        value={field.value}
                        disabled={field.disabled}
                        onChange={(e) => field.setter?.(e.target.value)}
                        className={cn(
                          "w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500",
                          field.disabled && "bg-slate-50 dark:bg-slate-900 text-slate-400 cursor-not-allowed"
                        )}
                      />
                    </div>
                  ))}
                  <Button
                    variant="primary"
                    size="md"
                    loading={isSavingProfile}
                    onClick={() => {
                      setIsSavingProfile(true);
                      setTimeout(() => {
                        setUnsaved(false);
                        setIsSavingProfile(false);
                        toast.success("Profile updated successfully");
                      }, 800);
                    }}
                  >
                    Save Changes
                  </Button>
                </div>
              </div>
            )}

            {/* Workspace */}
            {activeSection === "workspace" && (
              <div>
                <SectionHeader title="Workspace" />
                <div className="space-y-4">
                  {[
                    { label: "Workspace Name", value: "ACME Analytics" },
                    { label: "Slug", value: "acme-analytics", mono: true },
                    { label: "Region", value: "us-east-1", disabled: true },
                  ].map((field) => (
                    <div key={field.label} className="space-y-1.5">
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">{field.label}</label>
                      <input
                        defaultValue={field.value}
                        disabled={field.disabled}
                        className={cn(
                          "w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500",
                          field.mono && "font-mono",
                          field.disabled && "bg-slate-50 dark:bg-slate-900 text-slate-400 cursor-not-allowed"
                        )}
                      />
                      {field.disabled && <p className="text-xs text-slate-400">Region cannot be changed after creation.</p>}
                    </div>
                  ))}
                  <Button variant="primary" size="md">Save</Button>
                </div>
              </div>
            )}

            {/* Members */}
            {activeSection === "members" && (
              <div>
                <SectionHeader title="Members & RBAC" />
                <div className="bg-white dark:bg-slate-900 rounded-[8px] border border-slate-200 dark:border-slate-700 overflow-hidden mb-5">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 dark:border-slate-800">
                        <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Member</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Role</th>
                        <th className="px-4 py-3 w-10" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {shellUser && (
                        <tr key={shellUser.id}>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <Avatar user={shellUser} size={32} />
                              <div>
                                <p className="font-medium text-slate-800 dark:text-slate-200">{shellUser.name}</p>
                                <p className="text-xs text-slate-400">{shellUser.email}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <select
                              defaultValue="Admin"
                              className="h-8 px-2 text-xs rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none"
                              aria-label={`Role for ${shellUser.name}`}
                            >
                              <option>Admin</option>
                              <option>Editor</option>
                              <option>Viewer</option>
                            </select>
                          </td>
                          <td className="px-4 py-3" />
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="bg-slate-50 dark:bg-slate-800 rounded-[8px] p-4 space-y-3">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Invite Member</p>
                  <div className="flex gap-2">
                    <input type="email" autoComplete="off" spellCheck={false} placeholder="email@company.com" className="flex-1 h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                    <select className="h-9 px-2 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none">
                      <option>Viewer</option>
                      <option>Editor</option>
                      <option>Admin</option>
                    </select>
                    <Button
                      variant="primary"
                      size="md"
                      loading={isInviting}
                      onClick={() => {
                        setIsInviting(true);
                        setTimeout(() => {
                          setIsInviting(false);
                          toast.success("Invitation sent");
                        }, 800);
                      }}
                    >
                      Send Invite
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* API Keys */}
            {activeSection === "api-keys" && (
              <div>
                <SectionHeader title="API Keys" />
                <div className="mb-4">
                  <Button variant="primary" size="md" leadingIcon={<Plus size={14} />} onClick={() => setShowNewKey(true)}>
                    Generate New Key
                  </Button>
                </div>
                {showNewKey && !generatedKey && (
                  <div className="mb-4 bg-white dark:bg-slate-900 rounded-[8px] border border-slate-200 dark:border-slate-700 p-4 space-y-3">
                    <p className="text-sm font-medium text-slate-800 dark:text-slate-200">New API Key</p>
                    <div className="flex gap-2">
                      <input
                        value={newKeyName}
                        onChange={(e) => setNewKeyName(e.target.value)}
                        placeholder="Key name…"
                        className="flex-1 h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                      <select className="h-9 px-2 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none">
                        <option>Never</option>
                        <option>30 days</option>
                        <option>90 days</option>
                        <option>1 year</option>
                      </select>
                    </div>
                    <Button variant="primary" size="sm" onClick={generateKey}>Generate</Button>
                  </div>
                )}
                {generatedKey && (
                  <div className="mb-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-[8px] p-4 space-y-2">
                    <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400 text-sm">
                      <AlertTriangle size={14} />
                      <strong>Copy your new key — it will not be shown again.</strong>
                    </div>
                    <div className="flex items-center gap-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded px-3 py-2">
                      <code className="flex-1 text-xs font-mono text-slate-700 dark:text-slate-300 break-all">{generatedKey}</code>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(generatedKey);
                          toast.success("API key copied to clipboard");
                        }}
                        className="text-slate-400 hover:text-slate-600"
                        aria-label="Copy key"
                      >
                        <Copy size={14} />
                      </button>
                    </div>
                    <Button variant="ghost" size="sm" onClick={() => { setGeneratedKey(null); setShowNewKey(false); setNewKeyName(""); }}>Done</Button>
                  </div>
                )}
                <div className="bg-white dark:bg-slate-900 rounded-[8px] border border-slate-200 dark:border-slate-700 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 dark:border-slate-800">
                        {["Name", "Created", "Last Used", ""].map((h) => (
                          <th key={h} className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {apiKeys.map((key) => (
                        <tr key={key.id}>
                          <td className="px-4 py-3 font-medium text-slate-800 dark:text-slate-200">{key.name}</td>
                          <td className="px-4 py-3 text-slate-500 text-xs">{key.created}</td>
                          <td className="px-4 py-3 text-slate-500 text-xs">{key.lastUsed}</td>
                          <td className="px-4 py-3">
                            <Button
                              variant="destructive"
                              size="xs"
                              onClick={() => toast.success("API key revoked")}
                            >
                              Revoke
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Notifications */}
            {activeSection === "notifications" && (
              <div>
                <SectionHeader title="Notifications" />
                <div className="bg-white dark:bg-slate-900 rounded-[8px] border border-slate-200 dark:border-slate-700 divide-y divide-slate-100 dark:divide-slate-800">
                  {[
                    { key: "runCompleted" as const, label: "Run completed" },
                    { key: "runFailed" as const, label: "Run failed" },
                    { key: "approvalRequired" as const, label: "Approval required" },
                    { key: "deploymentSucceeded" as const, label: "Deployment succeeded" },
                    { key: "newMemberJoined" as const, label: "New member joined" },
                  ].map((item) => (
                    <div key={item.key} className="flex items-center justify-between px-4 py-3.5">
                      <span className="text-sm text-slate-700 dark:text-slate-300">{item.label}</span>
                      <Toggle
                        checked={notifToggles[item.key]}
                        onChange={() => handleNotifToggle(item.key)}
                        aria-label={`Toggle ${item.label}`}
                      />
                    </div>
                  ))}
                </div>
                <div className="mt-5 space-y-3">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Channels</p>
                  <div className="flex gap-2">
                    <Badge variant="success" dot size="md">Email</Badge>
                    <Badge variant="neutral" size="md">Slack</Badge>
                  </div>
                </div>
              </div>
            )}

            {/* Danger Zone */}
            {activeSection === "danger" && (
              <div>
                <SectionHeader title="Danger Zone" />
                <div className="border-2 border-red-200 dark:border-red-800 rounded-[8px] p-5 bg-red-50 dark:bg-red-900/10">
                  <h3 className="text-sm font-semibold text-red-800 dark:text-red-400 mb-2">Delete Workspace</h3>
                  <p className="text-sm text-red-700 dark:text-red-300 mb-4">
                    This permanently deletes all runs, workflows, artifacts, and reports. <strong>This action cannot be undone.</strong>
                  </p>
                  <Button variant="destructive" size="md" onClick={() => setShowDeleteModal(true)}>
                    Delete Workspace
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Delete workspace confirmation modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div className="relative bg-white dark:bg-slate-900 rounded-[12px] shadow-xl w-full max-w-[448px] mx-4 p-6 space-y-4" role="dialog" aria-modal="true">
            <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">Delete Workspace</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Type <strong className="font-mono text-slate-800 dark:text-slate-200">ACME Analytics</strong> to confirm:
            </p>
            <input
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              className="w-full h-9 px-3 text-sm rounded-[6px] border border-red-300 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-red-500"
              placeholder="ACME Analytics"
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="md" onClick={() => { setShowDeleteModal(false); setDeleteConfirm(""); }}>Cancel</Button>
              <Button
                variant="destructive"
                size="md"
                disabled={deleteConfirm !== "ACME Analytics"}
                onClick={() => { setShowDeleteModal(false); setDeleteConfirm(""); }}
              >
                Delete Workspace
              </Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}


