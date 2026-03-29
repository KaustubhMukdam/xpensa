import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import api from "@/lib/axios";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ApprovalRecord {
    id: string;
    approver_id: string;
    approver_name: string | null;
    action: "approve" | "reject" | null;
    comment: string | null;
    step_order: number;
    acted_at: string | null;
}

// What GET /api/v1/expenses/ returns — NO approval_trail
interface ExpenseOut {
    id: string;
    employee_id: string;
    amount: number;
    currency: string;
    converted_amount: number | null;
    base_currency: string | null;
    exchange_rate_snapshot: number | null;
    category: string;
    description: string;
    expense_date: string;
    paid_by: string;
    status: "draft" | "pending" | "approved" | "rejected";
    receipt_url: string | null;
    created_at: string;
    updated_at: string;
}

// What GET /api/v1/approvals/ and GET /api/v1/approvals/{id} return — WITH trail
interface ExpenseDetail extends ExpenseOut {
    approval_trail: ApprovalRecord[];
}

type ManagerTab = "queue" | "all";

// ── Safe helper — works whether trail is present or not ────────────────────
function findPendingApprover(trail: ApprovalRecord[] | undefined): ApprovalRecord | undefined {
    return (trail ?? []).find((r) => r.action === null);
}

// ── Formatters ────────────────────────────────────────────────────────────────
function formatCurrency(amount: number, currency: string): string {
    try {
        return new Intl.NumberFormat("en-IN", {
            style: "currency", currency, maximumFractionDigits: 2,
        }).format(amount);
    } catch {
        return `${currency} ${amount.toFixed(2)}`;
    }
}

function formatDate(dateStr: string): string {
    try {
        return new Date(dateStr + "T00:00:00").toLocaleDateString("en-IN", {
            day: "2-digit", month: "short", year: "numeric",
        });
    } catch {
        return dateStr;
    }
}

function timeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}

function displayAmount(exp: ExpenseOut): string {
    return exp.converted_amount && exp.base_currency
        ? formatCurrency(exp.converted_amount, exp.base_currency)
        : formatCurrency(exp.amount, exp.currency);
}

// ── Icons ─────────────────────────────────────────────────────────────────────
const Icons = {
    queue: (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" /></svg>),
    all: (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /></svg>),
    logout: (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>),
    x: (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>),
    check: (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>),
    xmark: (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>),
    eye: (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>),
    receipt: (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>),
    clock: (<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>),
    spin: (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ animation: "mgr-spin 0.8s linear infinite", display: "inline-block" }}><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" opacity=".25" /><path d="M21 12a9 9 0 00-9-9" /></svg>),
    refresh: (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" /><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" /></svg>),
};

// ── Status Badge ───────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
    const map: Record<string, { cls: string; label: string }> = {
        draft: { cls: "badge-draft", label: "Draft" },
        pending: { cls: "badge-pending", label: "Pending" },
        approved: { cls: "badge-approved", label: "Approved" },
        rejected: { cls: "badge-rejected", label: "Rejected" },
    };
    const { cls, label } = map[status] ?? { cls: "badge-draft", label: status };
    return <span className={`badge ${cls}`}>{label}</span>;
}

// ── Action Modal ───────────────────────────────────────────────────────────────
function ActionModal({
    expense, action, onClose, onDone,
}: {
    expense: ExpenseOut;
    action: "approve" | "reject";
    onClose: () => void;
    onDone: () => void;
}) {
    const [comment, setComment] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const isApprove = action === "approve";

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!isApprove && !comment.trim()) { setError("Please provide a reason for rejection."); return; }
        setLoading(true); setError("");
        try {
            await api.post(`/api/v1/approvals/${expense.id}/${action}`, {
                comment: comment.trim() || undefined,
            });
            onDone(); onClose();
        } catch (err: unknown) {
            const e = err as { response?: { data?: { detail?: string } } };
            setError(e?.response?.data?.detail ?? `Failed to ${action} expense.`);
        } finally { setLoading(false); }
    };

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2 className="modal-title" style={{ color: isApprove ? "hsl(160 84% 60%)" : "hsl(0 72% 65%)" }}>
                        {isApprove ? "Approve Expense" : "Reject Expense"}
                    </h2>
                    <button className="icon-btn" onClick={onClose}>{Icons.x}</button>
                </div>

                {/* Summary */}
                <div style={{ background: "hsl(222 40% 7%)", border: "1px solid hsl(222 30% 14%)", borderRadius: "0.625rem", padding: "1rem", marginBottom: "1.25rem", display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem" }}>
                    <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: "0.73rem", color: "hsl(215 15% 40%)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.25rem" }}>{expense.category}</div>
                        <div style={{ fontSize: "0.9rem", color: "var(--color-foreground)", marginBottom: "0.2rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{expense.description}</div>
                        <div style={{ fontSize: "0.77rem", color: "hsl(215 15% 45%)" }}>{formatDate(expense.expense_date)}</div>
                    </div>
                    <div style={{ textAlign: "right", flexShrink: 0 }}>
                        <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--color-foreground)" }}>{displayAmount(expense)}</div>
                        {expense.converted_amount && expense.base_currency && expense.base_currency !== expense.currency && (
                            <div style={{ fontSize: "0.75rem", color: "hsl(215 15% 45%)" }}>({formatCurrency(expense.amount, expense.currency)})</div>
                        )}
                    </div>
                </div>

                <form onSubmit={handleSubmit} className="auth-form">
                    <div className="form-group">
                        <label className="form-label">{isApprove ? "Comment (optional)" : "Reason for rejection *"}</label>
                        <textarea
                            className="form-textarea"
                            placeholder={isApprove ? "Add a note (optional)…" : "Why is this being rejected?…"}
                            value={comment}
                            onChange={(e) => setComment(e.target.value)}
                            rows={3}
                        />
                    </div>
                    {error && <div className="form-error">{error}</div>}
                    <div className="modal-actions">
                        <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
                        <button type="submit" className="btn-primary-sm" disabled={loading}
                            style={!isApprove ? { background: "linear-gradient(135deg,hsl(0 72% 50%),hsl(0 72% 42%))", boxShadow: "0 2px 12px hsl(0 72% 50%/0.25)" } : {}}>
                            {loading ? <>{Icons.spin} {isApprove ? "Approving…" : "Rejecting…"}</>
                                : <>{isApprove ? Icons.check : Icons.xmark} {isApprove ? "Approve" : "Reject"}</>}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// ── Expense Detail Sheet ───────────────────────────────────────────────────────
// Always fetches from API — never assumes trail exists in list data
function ExpenseDetailSheet({
    expenseId, currentUserId, onClose, onAction,
}: {
    expenseId: string;
    currentUserId: string;
    onClose: () => void;
    onAction: (expense: ExpenseOut, action: "approve" | "reject") => void;
}) {
    const [detail, setDetail] = useState<ExpenseDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        setLoading(true); setError("");
        // Approvals endpoint first (manager-scoped with trail), fallback to expenses
        api.get<ExpenseDetail>(`/api/v1/approvals/${expenseId}`)
            .then(({ data }) => setDetail(data))
            .catch(() =>
                api.get<ExpenseDetail>(`/api/v1/expenses/${expenseId}`)
                    .then(({ data }) => setDetail(data))
                    .catch(() => setError("Failed to load expense details."))
            )
            .finally(() => setLoading(false));
    }, [expenseId]);

    const trail = detail?.approval_trail ?? [];
    const pendingRecord = findPendingApprover(trail);
    const isCurrentApprover = pendingRecord?.approver_id === currentUserId;

    const dotColor = (action: string | null) =>
        action === "approve" ? "hsl(160 84% 50%)" : action === "reject" ? "hsl(0 72% 55%)" : "hsl(35 90% 55%)";

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal modal-lg" style={{ maxWidth: 560, maxHeight: "90vh", overflowY: "auto" }}
                onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2 className="modal-title">Expense Detail</h2>
                    <button className="icon-btn" onClick={onClose}>{Icons.x}</button>
                </div>

                {loading && <div className="loading-rows">{[1, 2, 3].map(i => <div key={i} className="skeleton-row" />)}</div>}
                {error && <div className="form-error">{error}</div>}

                {detail && !loading && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                        {/* Status + actions */}
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
                            <StatusBadge status={detail.status} />
                            {isCurrentApprover && detail.status === "pending" && (
                                <div style={{ display: "flex", gap: "0.5rem" }}>
                                    <button className="btn-row-danger" style={{ padding: "0.4rem 0.875rem", fontSize: "0.83rem" }}
                                        onClick={() => { onClose(); onAction(detail, "reject"); }}>
                                        {Icons.xmark} Reject
                                    </button>
                                    <button className="btn-primary-sm" onClick={() => { onClose(); onAction(detail, "approve"); }}>
                                        {Icons.check} Approve
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Fields */}
                        <div className="detail-panel">
                            <div className="detail-row">
                                <div className="detail-field">
                                    <span className="detail-label">Amount</span>
                                    <span className="amount-primary">{displayAmount(detail)}</span>
                                    {detail.converted_amount && detail.base_currency && detail.base_currency !== detail.currency && (
                                        <span className="amount-converted">
                                            Originally {formatCurrency(detail.amount, detail.currency)}
                                            {detail.exchange_rate_snapshot ? ` @ ${detail.exchange_rate_snapshot.toFixed(4)}` : ""}
                                        </span>
                                    )}
                                </div>
                                <div className="detail-field">
                                    <span className="detail-label">Category</span>
                                    <span className="detail-value" style={{ textTransform: "capitalize" }}>{detail.category}</span>
                                </div>
                            </div>
                            <div className="detail-row">
                                <div className="detail-field">
                                    <span className="detail-label">Date</span>
                                    <span className="detail-value">{formatDate(detail.expense_date)}</span>
                                </div>
                                <div className="detail-field">
                                    <span className="detail-label">Paid By</span>
                                    <span className="detail-value">
                                        {detail.paid_by === "employee" ? "Out of pocket" : "Company Card"}
                                    </span>
                                </div>
                            </div>
                            <div className="detail-field">
                                <span className="detail-label">Description</span>
                                <span className="detail-value">{detail.description}</span>
                            </div>
                            {detail.receipt_url && (
                                <div className="detail-field">
                                    <span className="detail-label">Receipt</span>
                                    <a href={detail.receipt_url} target="_blank" rel="noopener noreferrer"
                                        style={{ display: "inline-flex", alignItems: "center", gap: "0.375rem", color: "hsl(160 84% 55%)", fontSize: "0.875rem", textDecoration: "none" }}>
                                        {Icons.receipt} View Receipt ↗
                                    </a>
                                </div>
                            )}
                        </div>

                        {/* Approval trail */}
                        {trail.length > 0 && (
                            <div>
                                <div className="detail-label" style={{ marginBottom: "0.75rem" }}>Approval Trail</div>
                                {trail.map((record) => (
                                    <div key={record.id} className="trail-item">
                                        <div className="trail-dot" style={{ background: dotColor(record.action), boxShadow: record.action === null ? `0 0 5px ${dotColor(null)}/0.5` : "none" }} />
                                        <div style={{ flex: 1 }}>
                                            <div className="trail-name">
                                                {record.approver_name ?? "Approver"}
                                                <span style={{ marginLeft: "0.5rem", fontSize: "0.78rem", color: "hsl(215 15% 45%)" }}>
                                                    {record.step_order === 0 ? "(Manager)" : `(Step ${record.step_order})`}
                                                </span>
                                            </div>
                                            <div className="trail-action">
                                                {record.action
                                                    ? `${record.action === "approve" ? "✓ Approved" : "✗ Rejected"} · ${record.acted_at
                                                        ? new Date(record.acted_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : ""}`
                                                    : "⏳ Waiting for action"}
                                            </div>
                                            {record.comment && <div className="trail-comment">"{record.comment}"</div>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

// ── Approval Queue Tab ─────────────────────────────────────────────────────────
// GET /api/v1/approvals/ → ExpenseDetail[] (trail always included by backend)
function ApprovalQueueTab({ currentUserId }: { currentUserId: string }) {
    const [expenses, setExpenses] = useState<ExpenseDetail[]>([]);
    const [loading, setLoading] = useState(true);
    const [viewId, setViewId] = useState<string | null>(null);
    const [actionModal, setActionModal] = useState<{ expense: ExpenseOut; action: "approve" | "reject" } | null>(null);

    const fetchQueue = useCallback(async () => {
        setLoading(true);
        try {
            const { data } = await api.get<ExpenseDetail[]>("/api/v1/approvals/");
            setExpenses(data);
        } catch { setExpenses([]); }
        finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchQueue(); }, [fetchQueue]);

    // Trail IS guaranteed on queue items — backend always builds it
    const isCurrentApprover = (exp: ExpenseDetail) =>
        findPendingApprover(exp.approval_trail)?.approver_id === currentUserId;

    const dotColor = (action: string | null) =>
        action === "approve" ? "hsl(160 84% 50%)" : action === "reject" ? "hsl(0 72% 55%)" : "hsl(35 90% 55%)";

    return (
        <div className="tab-content">
            <div className="content-header">
                <div>
                    <h2 className="content-title">Approval Queue</h2>
                    <p className="content-subtitle">
                        {loading ? "Loading…" : expenses.length === 0
                            ? "All caught up!"
                            : `${expenses.length} expense${expenses.length !== 1 ? "s" : ""} pending review`}
                    </p>
                </div>
                <button className="btn-ghost" onClick={fetchQueue}
                    style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
                    {Icons.refresh} Refresh
                </button>
            </div>

            {loading ? (
                <div className="loading-rows">{[1, 2, 3].map(i => <div key={i} className="skeleton-row" />)}</div>
            ) : expenses.length === 0 ? (
                <div className="empty-state">
                    <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>✓</div>
                    <p className="empty-title">All caught up!</p>
                    <p className="empty-sub">No expenses are pending your approval right now.</p>
                </div>
            ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    {expenses.map((exp) => {
                        const mine = isCurrentApprover(exp);
                        return (
                            <div key={exp.id} style={{
                                background: "hsl(222 40% 8%)",
                                border: mine ? "1px solid hsl(160 84% 39% / 0.35)" : "1px solid hsl(222 30% 13%)",
                                borderRadius: "0.875rem", padding: "1.25rem", transition: "border-color 0.15s",
                            }}>
                                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "1rem" }}>
                                    {/* Left */}
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.375rem" }}>
                                            <span className="mgr-category-pill">{exp.category}</span>
                                            {mine && (
                                                <span className="mgr-your-turn-pill">
                                                    {Icons.clock} Your turn
                                                </span>
                                            )}
                                        </div>
                                        <div style={{ fontSize: "0.9rem", fontWeight: 500, color: "var(--color-foreground)", marginBottom: "0.25rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                            {exp.description}
                                        </div>
                                        <div style={{ fontSize: "0.78rem", color: "hsl(215 15% 45%)" }}>
                                            Submitted {timeAgo(exp.created_at)} · {formatDate(exp.expense_date)}
                                        </div>
                                    </div>
                                    {/* Right */}
                                    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "0.625rem", flexShrink: 0 }}>
                                        <div style={{ textAlign: "right" }}>
                                            <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--color-foreground)", letterSpacing: "-0.02em" }}>
                                                {displayAmount(exp)}
                                            </div>
                                            {exp.converted_amount && exp.base_currency && exp.base_currency !== exp.currency && (
                                                <div style={{ fontSize: "0.75rem", color: "hsl(215 15% 45%)" }}>{formatCurrency(exp.amount, exp.currency)}</div>
                                            )}
                                        </div>
                                        <div style={{ display: "flex", gap: "0.375rem" }}>
                                            <button className="icon-btn" title="View details" onClick={() => setViewId(exp.id)}>{Icons.eye}</button>
                                            {mine && exp.status === "pending" && (
                                                <>
                                                    <button className="btn-row-danger" onClick={() => setActionModal({ expense: exp, action: "reject" })}>Reject</button>
                                                    <button className="btn-row-success" onClick={() => setActionModal({ expense: exp, action: "approve" })}>Approve</button>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                {/* Trail dots */}
                                {exp.approval_trail.length > 0 && (
                                    <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.875rem", paddingTop: "0.875rem", borderTop: "1px solid hsl(222 30% 12%)", flexWrap: "wrap" }}>
                                        {exp.approval_trail.map((r) => (
                                            <div key={r.id} style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
                                                <div style={{ width: 8, height: 8, borderRadius: "50%", background: dotColor(r.action), boxShadow: r.action === null ? `0 0 5px ${dotColor(null)}` : "none" }} />
                                                <span style={{ fontSize: "0.73rem", color: "hsl(215 15% 48%)" }}>
                                                    {r.approver_name ?? "Approver"}{r.step_order === 0 ? " (Mgr)" : ""}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {viewId && (
                <ExpenseDetailSheet expenseId={viewId} currentUserId={currentUserId}
                    onClose={() => setViewId(null)}
                    onAction={(exp, action) => { setViewId(null); setActionModal({ expense: exp, action }); }} />
            )}
            {actionModal && (
                <ActionModal expense={actionModal.expense} action={actionModal.action}
                    onClose={() => setActionModal(null)} onDone={fetchQueue} />
            )}
        </div>
    );
}

// ── All Team Expenses Tab ─────────────────────────────────────────────────────
// GET /api/v1/expenses/ → ExpenseOut[] — NO approval_trail field, never access it here
function AllExpensesTab({ currentUserId }: { currentUserId: string }) {
    const [expenses, setExpenses] = useState<ExpenseOut[]>([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setFilter] = useState("all");
    const [viewId, setViewId] = useState<string | null>(null);
    const [actionModal, setActionModal] = useState<{ expense: ExpenseOut; action: "approve" | "reject" } | null>(null);

    const fetchExpenses = useCallback(async () => {
        setLoading(true);
        try {
            const params = statusFilter !== "all" ? { status: statusFilter } : {};
            const { data } = await api.get<ExpenseOut[]>("/api/v1/expenses/", { params });
            setExpenses(data);
        } catch { setExpenses([]); }
        finally { setLoading(false); }
    }, [statusFilter]);

    useEffect(() => { fetchExpenses(); }, [fetchExpenses]);

    const totalApproved = expenses.filter(e => e.status === "approved")
        .reduce((s, e) => s + (e.converted_amount ?? e.amount), 0);
    const baseCurrency = expenses.find(e => e.base_currency)?.base_currency ?? "INR";

    const summaryCards = [
        { label: "Pending", value: String(expenses.filter(e => e.status === "pending").length), sub: "awaiting approval", accent: "hsl(35 90% 65%)" },
        { label: "Approved", value: formatCurrency(totalApproved, baseCurrency), sub: `${expenses.filter(e => e.status === "approved").length} expenses`, accent: "hsl(160 84% 60%)" },
        { label: "Total", value: String(expenses.length), sub: "records shown", accent: "hsl(215 20% 60%)" },
    ];

    const STATUS_TABS = ["all", "pending", "approved", "rejected"];

    return (
        <div className="tab-content">
            <div className="content-header">
                <div>
                    <h2 className="content-title">Team Expenses</h2>
                    <p className="content-subtitle">All expenses in your company</p>
                </div>
                <button className="btn-ghost" onClick={fetchExpenses} style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
                    {Icons.refresh} Refresh
                </button>
            </div>

            {/* Summary */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: "1rem" }}>
                {summaryCards.map(c => (
                    <div key={c.label} style={{ background: "hsl(222 40% 8%)", border: "1px solid hsl(222 30% 13%)", borderRadius: "0.875rem", padding: "1.25rem 1.5rem" }}>
                        <div style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "hsl(215 15% 40%)", marginBottom: "0.375rem" }}>{c.label}</div>
                        <div style={{ fontSize: "1.375rem", fontWeight: 700, color: c.accent, letterSpacing: "-0.02em" }}>{c.value}</div>
                        <div style={{ fontSize: "0.78rem", color: "hsl(215 15% 40%)", marginTop: "0.125rem" }}>{c.sub}</div>
                    </div>
                ))}
            </div>

            {/* Filter tabs */}
            <div style={{ display: "flex", gap: "0.375rem", background: "hsl(222 40% 7%)", border: "1px solid hsl(222 30% 13%)", borderRadius: "0.625rem", padding: "0.25rem", width: "fit-content" }}>
                {STATUS_TABS.map(t => (
                    <button key={t} onClick={() => setFilter(t)}
                        style={{
                            padding: "0.4rem 0.875rem", border: "none", fontFamily: "inherit", borderRadius: "0.375rem", fontSize: "0.83rem", fontWeight: 500, cursor: "pointer", transition: "background 0.15s, color 0.15s",
                            background: statusFilter === t ? "hsl(222 35% 14%)" : "transparent",
                            color: statusFilter === t ? "var(--color-foreground)" : "hsl(215 20% 50%)"
                        }}>
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                    </button>
                ))}
            </div>

            {/* Table */}
            {loading ? (
                <div className="loading-rows">{[1, 2, 3, 4].map(i => <div key={i} className="skeleton-row" />)}</div>
            ) : expenses.length === 0 ? (
                <div className="empty-state">
                    <div className="empty-icon">🧾</div>
                    <p className="empty-title">No expenses found</p>
                    <p className="empty-sub">Try a different status filter.</p>
                </div>
            ) : (
                <div className="table-wrap">
                    <table className="data-table">
                        <thead>
                            <tr><th>Description</th><th>Category</th><th>Amount</th><th>Date</th><th>Status</th><th>Actions</th></tr>
                        </thead>
                        <tbody>
                            {expenses.map(exp => (
                                <tr key={exp.id}>
                                    <td className="td-name" style={{ maxWidth: 220 }}>
                                        <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{exp.description}</span>
                                    </td>
                                    <td><span className="mgr-category-pill">{exp.category}</span></td>
                                    <td>
                                        <div style={{ fontWeight: 500 }}>{displayAmount(exp)}</div>
                                        {exp.converted_amount && exp.base_currency && exp.base_currency !== exp.currency && (
                                            <div style={{ fontSize: "0.77rem", color: "hsl(160 84% 55%)" }}>{formatCurrency(exp.amount, exp.currency)}</div>
                                        )}
                                    </td>
                                    <td className="td-muted">{formatDate(exp.expense_date)}</td>
                                    <td><StatusBadge status={exp.status} /></td>
                                    <td>
                                        <div style={{ display: "flex", gap: "0.375rem" }}>
                                            {/* Detail modal handles trail + approver check safely */}
                                            <button className="icon-btn" title="View details" onClick={() => setViewId(exp.id)}>{Icons.eye}</button>
                                            {exp.status === "pending" && (
                                                <>
                                                    <button className="btn-row-danger" onClick={() => setActionModal({ expense: exp, action: "reject" })}>Reject</button>
                                                    <button className="btn-row-success" onClick={() => setActionModal({ expense: exp, action: "approve" })}>Approve</button>
                                                </>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {viewId && (
                <ExpenseDetailSheet expenseId={viewId} currentUserId={currentUserId}
                    onClose={() => setViewId(null)}
                    onAction={(exp, action) => { setViewId(null); setActionModal({ expense: exp, action }); }} />
            )}
            {actionModal && (
                <ActionModal expense={actionModal.expense} action={actionModal.action}
                    onClose={() => setActionModal(null)} onDone={fetchExpenses} />
            )}
        </div>
    );
}

// ── Main ───────────────────────────────────────────────────────────────────────
export default function ManagerDashboard() {
    const { user, logout } = useAuthStore();
    const navigate = useNavigate();
    const [tab, setTab] = useState<ManagerTab>("queue");
    const handleLogout = () => { logout(); navigate("/login"); };

    return (
        <>
            <style>{MANAGER_CSS}</style>
            <div className="app-shell">
                <aside className="sidebar">
                    <div className="sidebar-logo">
                        <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
                            <rect width="32" height="32" rx="8" fill="url(#mgrG)" />
                            <path d="M8 20L14 12L19 17L23 11" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                            <circle cx="23" cy="11" r="2" fill="white" />
                            <defs><linearGradient id="mgrG" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse"><stop stopColor="#10b981" /><stop offset="1" stopColor="#059669" /></linearGradient></defs>
                        </svg>
                        <span className="sidebar-brand">xpensa</span>
                    </div>
                    <div className="sidebar-section-label">Manager</div>
                    <nav className="sidebar-nav">
                        <button className={`nav-item ${tab === "queue" ? "nav-item-active" : ""}`} onClick={() => setTab("queue")}>{Icons.queue} Approvals Queue</button>
                        <button className={`nav-item ${tab === "all" ? "nav-item-active" : ""}`} onClick={() => setTab("all")}>{Icons.all} Team Expenses</button>
                    </nav>
                    <div className="sidebar-footer">
                        <div className="sidebar-user">
                            <div className="avatar">{user?.full_name?.[0] ?? "M"}</div>
                            <div className="sidebar-user-info">
                                <span className="sidebar-user-name">{user?.full_name}</span>
                                <span className="sidebar-user-role">Manager</span>
                            </div>
                        </div>
                        <button className="icon-btn" onClick={handleLogout} title="Log out">{Icons.logout}</button>
                    </div>
                </aside>
                <main className="main-content">
                    {tab === "queue" && <ApprovalQueueTab currentUserId={user?.id ?? ""} />}
                    {tab === "all" && <AllExpensesTab currentUserId={user?.id ?? ""} />}
                </main>
            </div>
        </>
    );
}

const MANAGER_CSS = `
@keyframes mgr-spin { to { transform: rotate(360deg); } }
.mgr-category-pill {
    display: inline-block; padding: 0.15rem 0.5rem; border-radius: 99px;
    font-size: 0.75rem; font-weight: 500; text-transform: capitalize;
    background: hsl(222 35% 14%); color: hsl(215 20% 65%);
    border: 1px solid hsl(222 30% 20%);
}
.mgr-your-turn-pill {
    display: inline-flex; align-items: center; gap: 0.25rem;
    font-size: 0.72rem; font-weight: 600; color: hsl(160 84% 60%);
    background: hsl(160 84% 39% / 0.1); border: 1px solid hsl(160 84% 39% / 0.25);
    padding: 0.15rem 0.5rem; border-radius: 99px;
}
`;