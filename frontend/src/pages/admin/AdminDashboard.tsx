import { useState, useEffect } from "react";
import { useAuthStore } from "@/store/auth";
import api from "@/lib/axios";
import { useNavigate } from "react-router-dom";

// ── Types ──────────────────────────────────────────────────────────────────
interface User {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "manager" | "employee";
  is_active: boolean;
  created_at: string;
}

interface ApprovalStep {
  approver_id: string;
  step_order: number;
}

interface ApprovalRule {
  id: string;
  category: string;
  description?: string;
  manager_is_approver: boolean;
  specific_approver_id?: string;
  min_approval_percentage?: number;
  is_active: boolean;
  steps: ApprovalStep[];
}

type AdminTab = "users" | "rules";

// ── Icons ──────────────────────────────────────────────────────────────────
const Icons = {
  users: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
    </svg>
  ),
  rules: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
    </svg>
  ),
  plus: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  ),
  logout: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  ),
  trash: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6M14 11v6" /><path d="M9 6V4h6v2" />
    </svg>
  ),
  edit: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  ),
  x: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  ),
};

// ── Role Badge ─────────────────────────────────────────────────────────────
function RoleBadge({ role }: { role: string }) {
  const styles: Record<string, string> = {
    admin: "badge-admin",
    manager: "badge-manager",
    employee: "badge-employee",
  };
  return <span className={`badge ${styles[role] ?? "badge-employee"}`}>{role}</span>;
}

// ── Modal: Create User ─────────────────────────────────────────────────────
function CreateUserModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (user: User, tempPassword: string) => void;
}) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"manager" | "employee">("employee");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/api/v1/users/", { full_name: fullName, email, role });
      onCreated(data.user, data.temp_password);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to create user.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Add Team Member</h2>
          <button className="icon-btn" onClick={onClose}>{Icons.x}</button>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label className="form-label">Full name</label>
            <input className="form-input" placeholder="Jane Smith" value={fullName}
              onChange={(e) => setFullName(e.target.value)} required />
          </div>
          <div className="form-group">
            <label className="form-label">Work email</label>
            <input className="form-input" type="email" placeholder="jane@company.com" value={email}
              onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="form-group">
            <label className="form-label">Role</label>
            <select className="form-input form-select" value={role}
              onChange={(e) => setRole(e.target.value as "manager" | "employee")}>
              <option value="employee">Employee</option>
              <option value="manager">Manager</option>
            </select>
          </div>
          {error && <div className="form-error">{error}</div>}
          <div className="modal-actions">
            <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary-sm" disabled={loading}>
              {loading ? "Creating…" : "Create & Send Password"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Modal: Temp Password ───────────────────────────────────────────────────
function TempPasswordModal({ user, tempPassword, onClose }: { user: User; tempPassword: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(tempPassword);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Share Credentials</h2>
          <button className="icon-btn" onClick={onClose}>{Icons.x}</button>
        </div>
        <p className="modal-desc">
          Share these credentials with <strong>{user.full_name}</strong>. They'll be asked to change their password on first login.
        </p>
        <div className="cred-box">
          <div className="cred-row"><span className="cred-label">Email</span><span className="cred-value">{user.email}</span></div>
          <div className="cred-row"><span className="cred-label">Temp password</span>
            <span className="cred-value cred-mono">{tempPassword}</span>
          </div>
        </div>
        <div className="modal-actions">
          <button className="btn-ghost" onClick={onClose}>Close</button>
          <button className="btn-primary-sm" onClick={copy}>
            {copied ? "✓ Copied!" : "Copy to clipboard"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Users Tab ──────────────────────────────────────────────────────────────
function UsersTab() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creds, setCreds] = useState<{ user: User; pw: string } | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/api/v1/users/");
      setUsers(data);
    } catch { /* handled silently */ }
    setLoading(false);
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleCreated = (user: User, tempPassword: string) => {
    setShowCreate(false);
    setCreds({ user, pw: tempPassword });
    fetchUsers();
  };

  const toggleActive = async (user: User) => {
    await api.patch(`/api/v1/users/${user.id}`, { is_active: !user.is_active });
    fetchUsers();
  };

  return (
    <div className="tab-content">
      <div className="content-header">
        <div>
          <h2 className="content-title">Team Members</h2>
          <p className="content-subtitle">{users.length} members in your organisation</p>
        </div>
        <button className="btn-primary-sm" onClick={() => setShowCreate(true)}>
          {Icons.plus} Add member
        </button>
      </div>

      {loading ? (
        <div className="loading-rows">
          {[1,2,3].map(i => <div key={i} className="skeleton-row" />)}
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Joined</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td className="td-name">{u.full_name}</td>
                  <td className="td-muted">{u.email}</td>
                  <td><RoleBadge role={u.role} /></td>
                  <td>
                    <span className={u.is_active ? "status-active" : "status-inactive"}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="td-muted">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td>
                    {u.role !== "admin" && (
                      <button
                        className={u.is_active ? "btn-row-danger" : "btn-row-success"}
                        onClick={() => toggleActive(u)}
                      >
                        {u.is_active ? "Deactivate" : "Activate"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && <CreateUserModal onClose={() => setShowCreate(false)} onCreated={handleCreated} />}
      {creds && <TempPasswordModal user={creds.user} tempPassword={creds.pw} onClose={() => setCreds(null)} />}
    </div>
  );
}

// ── Approval Rules Tab ─────────────────────────────────────────────────────
function RulesTab() {
  const [rules, setRules] = useState<ApprovalRule[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editRule, setEditRule] = useState<ApprovalRule | null>(null);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [rulesRes, usersRes] = await Promise.all([
        api.get("/api/v1/approval-rules/"),
        api.get("/api/v1/users/"),
      ]);
      setRules(rulesRes.data);
      setUsers(usersRes.data);
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, []);

  const deleteRule = async (id: string) => {
    if (!confirm("Deactivate this rule?")) return;
    await api.delete(`/api/v1/approval-rules/${id}`);
    fetchAll();
  };

  const userName = (id?: string) => users.find((u) => u.id === id)?.full_name ?? id ?? "—";

  return (
    <div className="tab-content">
      <div className="content-header">
        <div>
          <h2 className="content-title">Approval Rules</h2>
          <p className="content-subtitle">Configure multi-step approval chains per expense category</p>
        </div>
        <button className="btn-primary-sm" onClick={() => { setEditRule(null); setShowForm(true); }}>
          {Icons.plus} New rule
        </button>
      </div>

      {loading ? (
        <div className="loading-rows">{[1,2].map(i => <div key={i} className="skeleton-row" />)}</div>
      ) : rules.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <p className="empty-title">No approval rules yet</p>
          <p className="empty-sub">Create a rule to define who approves expenses in each category.</p>
        </div>
      ) : (
        <div className="rules-grid">
          {rules.map((r) => (
            <div key={r.id} className="rule-card">
              <div className="rule-card-header">
                <div className="rule-category">{r.category}</div>
                <div className="rule-actions">
                  <button className="icon-btn" onClick={() => { setEditRule(r); setShowForm(true); }}>{Icons.edit}</button>
                  <button className="icon-btn icon-btn-danger" onClick={() => deleteRule(r.id)}>{Icons.trash}</button>
                </div>
              </div>
              {r.description && <p className="rule-desc">{r.description}</p>}
              <div className="rule-steps">
                {r.manager_is_approver && (
                  <div className="rule-step"><span className="step-num">0</span><span className="step-name">Manager (auto)</span></div>
                )}
                {r.steps.sort((a, b) => a.step_order - b.step_order).map((s) => (
                  <div key={s.step_order} className="rule-step">
                    <span className="step-num">{s.step_order}</span>
                    <span className="step-name">{userName(s.approver_id)}</span>
                  </div>
                ))}
                {r.steps.length === 0 && !r.manager_is_approver && (
                  <span className="td-muted">No steps — expenses auto-approved</span>
                )}
              </div>
              {r.min_approval_percentage && (
                <div className="rule-tag">Min {r.min_approval_percentage}% approval</div>
              )}
              {r.specific_approver_id && (
                <div className="rule-tag">Specific approver: {userName(r.specific_approver_id)}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <RuleFormModal
          existing={editRule}
          users={users}
          onClose={() => setShowForm(false)}
          onSaved={fetchAll}
        />
      )}
    </div>
  );
}

// ── Rule Form Modal ────────────────────────────────────────────────────────
function RuleFormModal({
  existing,
  users,
  onClose,
  onSaved,
}: {
  existing: ApprovalRule | null;
  users: User[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [category, setCategory] = useState(existing?.category ?? "");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [managerIsApprover, setManagerIsApprover] = useState(existing?.manager_is_approver ?? false);
  const [steps, setSteps] = useState<ApprovalStep[]>(existing?.steps ?? []);
  const [minPct, setMinPct] = useState<string>(existing?.min_approval_percentage?.toString() ?? "");
  const [specificId, setSpecificId] = useState(existing?.specific_approver_id ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const nonAdminUsers = users.filter((u) => u.role !== "admin" && u.is_active);

  const addStep = () => {
    const nextOrder = steps.length > 0 ? Math.max(...steps.map((s) => s.step_order)) + 1 : 1;
    setSteps([...steps, { approver_id: "", step_order: nextOrder }]);
  };
  const removeStep = (i: number) => setSteps(steps.filter((_, idx) => idx !== i));
  const updateStep = (i: number, approver_id: string) => {
    const updated = [...steps];
    updated[i] = { ...updated[i], approver_id };
    setSteps(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const validSteps = steps.filter((s) => s.approver_id);
    setLoading(true);
    try {
      const payload = {
        category,
        description: description || undefined,
        manager_is_approver: managerIsApprover,
        min_approval_percentage: minPct ? parseInt(minPct) : undefined,
        specific_approver_id: specificId || undefined,
        steps: validSteps,
      };
      if (existing) {
        await api.patch(`/api/v1/approval-rules/${existing.id}`, payload);
      } else {
        await api.post("/api/v1/approval-rules/", payload);
      }
      onSaved();
      onClose();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Failed to save rule.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{existing ? "Edit Rule" : "New Approval Rule"}</h2>
          <button className="icon-btn" onClick={onClose}>{Icons.x}</button>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Category</label>
              <input className="form-input" placeholder="e.g. travel, meals, equipment"
                value={category} onChange={(e) => setCategory(e.target.value)} required />
            </div>
            <div className="form-group">
              <label className="form-label">Description (optional)</label>
              <input className="form-input" placeholder="Short description"
                value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
          </div>

          <div className="form-group">
            <label className="toggle-label">
              <input type="checkbox" className="toggle-checkbox"
                checked={managerIsApprover} onChange={(e) => setManagerIsApprover(e.target.checked)} />
              <span className="toggle-text">Manager is always Step 1 approver</span>
            </label>
          </div>

          <div className="form-group">
            <div className="steps-header">
              <label className="form-label">Approver Chain</label>
              <button type="button" className="btn-ghost-sm" onClick={addStep}>{Icons.plus} Add step</button>
            </div>
            {steps.length === 0 ? (
              <p className="td-muted" style={{ fontSize: "0.82rem" }}>No steps — expenses will be auto-approved (unless manager toggle is on).</p>
            ) : (
              <div className="steps-list">
                {steps.map((s, i) => (
                  <div key={i} className="step-row">
                    <span className="step-num">{s.step_order}</span>
                    <select className="form-input form-select" value={s.approver_id}
                      onChange={(e) => updateStep(i, e.target.value)} required>
                      <option value="">Select approver…</option>
                      {nonAdminUsers.map((u) => (
                        <option key={u.id} value={u.id}>{u.full_name} ({u.role})</option>
                      ))}
                    </select>
                    <button type="button" className="icon-btn icon-btn-danger" onClick={() => removeStep(i)}>{Icons.trash}</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Min approval % (optional)</label>
              <input className="form-input" type="number" min="1" max="100"
                placeholder="e.g. 60" value={minPct} onChange={(e) => setMinPct(e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Specific approver shortcut (optional)</label>
              <select className="form-input form-select" value={specificId}
                onChange={(e) => setSpecificId(e.target.value)}>
                <option value="">None</option>
                {nonAdminUsers.map((u) => (
                  <option key={u.id} value={u.id}>{u.full_name}</option>
                ))}
              </select>
            </div>
          </div>

          {error && <div className="form-error">{error}</div>}
          <div className="modal-actions">
            <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary-sm" disabled={loading}>
              {loading ? "Saving…" : existing ? "Save changes" : "Create rule"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Admin Dashboard ───────────────────────────────────────────────────
export default function AdminDashboard() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const [tab, setTab] = useState<AdminTab>("users");

  const handleLogout = () => { logout(); navigate("/login"); };

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="8" fill="url(#sideLogoGrad)" />
            <path d="M8 20L14 12L19 17L23 11" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="23" cy="11" r="2" fill="white" />
            <defs>
              <linearGradient id="sideLogoGrad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                <stop stopColor="#10b981" /><stop offset="1" stopColor="#059669" />
              </linearGradient>
            </defs>
          </svg>
          <span className="sidebar-brand">xpensa</span>
        </div>

        <div className="sidebar-section-label">Admin</div>

        <nav className="sidebar-nav">
          <button className={`nav-item ${tab === "users" ? "nav-item-active" : ""}`} onClick={() => setTab("users")}>
            {Icons.users} Users
          </button>
          <button className={`nav-item ${tab === "rules" ? "nav-item-active" : ""}`} onClick={() => setTab("rules")}>
            {Icons.rules} Approval Rules
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <div className="avatar">{user?.full_name?.[0] ?? "A"}</div>
            <div className="sidebar-user-info">
              <span className="sidebar-user-name">{user?.full_name}</span>
              <span className="sidebar-user-role">Admin</span>
            </div>
          </div>
          <button className="icon-btn" onClick={handleLogout} title="Log out">{Icons.logout}</button>
        </div>
      </aside>

      {/* Main */}
      <main className="main-content">
        {tab === "users" && <UsersTab />}
        {tab === "rules" && <RulesTab />}
      </main>
    </div>
  );
}