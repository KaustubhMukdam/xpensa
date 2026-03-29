/**
 * EmployeeDashboard.tsx
 *
 * Full employee experience:
 *  - Expense list with status filter tabs
 *  - New expense form (draft → submit)
 *  - Expense detail modal with approval trail
 *  - OCR receipt upload with live polling
 *  - Edit draft expense
 *
 * All state is managed locally with React state + TanStack Query.
 * API calls go through the shared axios instance (JWT auto-attached).
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import api from "@/lib/axios";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Expense {
    id: string;
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

interface ApprovalRecord {
    id: string;
    approver_id: string;
    approver_name: string | null;
    action: "approve" | "reject" | null;
    comment: string | null;
    step_order: number;
    acted_at: string | null;
}

interface ExpenseDetail extends Expense {
    approval_trail: ApprovalRecord[];
}

interface OcrResult {
    amount: number;
    currency: string;
    date: string;
    description: string;
    category: string;
}

type StatusFilter = "all" | "draft" | "pending" | "approved" | "rejected";

// ── World currencies (top 50) ─────────────────────────────────────────────────
const CURRENCIES = [
    "AED", "AUD", "BRL", "CAD", "CHF", "CNY", "COP", "CZK", "DKK", "EGP",
    "EUR", "GBP", "HKD", "HUF", "IDR", "ILS", "INR", "JPY", "KRW", "KWD",
    "MAD", "MXN", "MYR", "NGN", "NOK", "NZD", "PHP", "PKR", "PLN", "QAR",
    "RON", "RUB", "SAR", "SEK", "SGD", "THB", "TRY", "TWD", "UAH", "USD",
    "VND", "XAF", "XOF", "ZAR",
];

const CATEGORIES = ["travel", "meals", "equipment", "accommodation", "miscellaneous"];

// ── Icons ─────────────────────────────────────────────────────────────────────
const Icons = {
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
    x: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
        </svg>
    ),
    receipt: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
        </svg>
    ),
    upload: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="16 16 12 12 8 16" /><line x1="12" y1="12" x2="12" y2="21" />
            <path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3" />
        </svg>
    ),
    spin: (
        <svg className="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" opacity=".25" /><path d="M21 12a9 9 0 00-9-9" />
        </svg>
    ),
    eye: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
        </svg>
    ),
    edit: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
        </svg>
    ),
    send: (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
    ),
    check: (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
            <polyline points="20 6 9 17 4 12" />
        </svg>
    ),
    scan: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 7V5a2 2 0 012-2h2M17 3h2a2 2 0 012 2v2M21 17v2a2 2 0 01-2 2h-2M7 21H5a2 2 0 01-2-2v-2" />
            <line x1="3" y1="12" x2="21" y2="12" />
        </svg>
    ),
};

// ── Helpers ───────────────────────────────────────────────────────────────────

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

function today(): string {
    return new Date().toISOString().split("T")[0];
}

// ── Status Badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
    const map: Record<string, { cls: string; label: string }> = {
        draft: { cls: "badge-draft", label: "Draft" },
        pending: { cls: "badge-pending", label: "Waiting Approval" },
        approved: { cls: "badge-approved", label: "Approved" },
        rejected: { cls: "badge-rejected", label: "Rejected" },
    };
    const { cls, label } = map[status] ?? { cls: "badge-draft", label: status };
    return <span className={`badge ${cls}`}>{label}</span>;
}

// ── OCR Upload Panel ──────────────────────────────────────────────────────────
interface OcrPanelProps {
    onExtracted: (data: OcrResult) => void;
    onReceiptUrl: (url: string) => void;
}

function OcrPanel({ onExtracted, onReceiptUrl }: OcrPanelProps) {
    const [state, setState] = useState<"idle" | "uploading" | "processing" | "done" | "error">("idle");
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [errorMsg, setErrorMsg] = useState("");
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const fileRef = useRef<HTMLInputElement>(null);

    const stopPolling = () => {
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };

    useEffect(() => () => stopPolling(), []);

    const handleFile = async (file: File) => {
        if (!file.type.startsWith("image/")) {
            setErrorMsg("Please upload an image file (JPEG, PNG, WEBP).");
            return;
        }
        if (file.size > 5 * 1024 * 1024) {
            setErrorMsg("File too large. Maximum size is 5MB.");
            return;
        }

        // Preview
        const reader = new FileReader();
        reader.onload = (e) => setPreviewUrl(e.target?.result as string);
        reader.readAsDataURL(file);

        setState("uploading");
        setErrorMsg("");

        try {
            const formData = new FormData();
            formData.append("file", file);

            const { data } = await api.post("/api/v1/ocr/extract", formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });

            const { task_id, receipt_url } = data;
            if (receipt_url) onReceiptUrl(receipt_url);

            setState("processing");

            // Poll for result every 2 seconds
            pollRef.current = setInterval(async () => {
                try {
                    const { data: status } = await api.get(`/api/v1/ocr/status/${task_id}`);
                    if (status.status === "done") {
                        stopPolling();
                        setState("done");
                        onExtracted(status.result as OcrResult);
                    } else if (status.status === "error") {
                        stopPolling();
                        setState("error");
                        setErrorMsg(status.error ?? "OCR failed. Please fill in manually.");
                    }
                } catch {
                    stopPolling();
                    setState("error");
                    setErrorMsg("Could not reach OCR service.");
                }
            }, 2000);

        } catch (err: unknown) {
            const e = err as { response?: { data?: { detail?: string } } };
            setState("error");
            setErrorMsg(e?.response?.data?.detail ?? "Upload failed. Please try again.");
        }
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    };

    const reset = () => {
        stopPolling();
        setState("idle");
        setPreviewUrl(null);
        setErrorMsg("");
        if (fileRef.current) fileRef.current.value = "";
    };

    return (
        <div className="ocr-panel">
            <div className="ocr-label">
                {Icons.scan}
                <span>Scan Receipt</span>
                <span className="ocr-badge">AI</span>
            </div>

            {state === "idle" && (
                <div
                    className="ocr-dropzone"
                    onDrop={handleDrop}
                    onDragOver={(e) => e.preventDefault()}
                    onClick={() => fileRef.current?.click()}
                >
                    <div className="ocr-dropzone-icon">{Icons.upload}</div>
                    <p className="ocr-dropzone-text">Drop receipt here or <span className="ocr-link">browse</span></p>
                    <p className="ocr-dropzone-hint">JPEG, PNG, WEBP · max 5MB · Auto-fills form</p>
                    <input
                        ref={fileRef}
                        type="file"
                        accept="image/jpeg,image/png,image/webp,image/gif"
                        style={{ display: "none" }}
                        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
                    />
                </div>
            )}

            {(state === "uploading" || state === "processing") && (
                <div className="ocr-processing">
                    {previewUrl && <img src={previewUrl} alt="Receipt preview" className="ocr-preview" />}
                    <div className="ocr-status-row">
                        {Icons.spin}
                        <span>{state === "uploading" ? "Uploading receipt…" : "Reading receipt with AI…"}</span>
                    </div>
                    <div className="ocr-progress-bar">
                        <div className={`ocr-progress-fill ${state === "processing" ? "ocr-progress-animated" : ""}`} />
                    </div>
                </div>
            )}

            {state === "done" && (
                <div className="ocr-done">
                    {previewUrl && <img src={previewUrl} alt="Receipt" className="ocr-preview" />}
                    <div className="ocr-done-badge">
                        <span className="ocr-done-icon">{Icons.check}</span>
                        Form auto-filled from receipt
                    </div>
                    <button type="button" className="ocr-reset-btn" onClick={reset}>Scan different receipt</button>
                </div>
            )}

            {state === "error" && (
                <div className="ocr-error">
                    {previewUrl && <img src={previewUrl} alt="Receipt" className="ocr-preview" />}
                    <p className="ocr-error-msg">{errorMsg}</p>
                    <button type="button" className="ocr-reset-btn" onClick={reset}>Try again</button>
                </div>
            )}
        </div>
    );
}

// ── Expense Form Modal ────────────────────────────────────────────────────────
interface ExpenseFormProps {
    existing?: Expense | null; // if set → edit mode
    onClose: () => void;
    onSaved: () => void;
}

function ExpenseFormModal({ existing, onClose, onSaved }: ExpenseFormProps) {
    const [amount, setAmount] = useState(existing?.amount?.toString() ?? "");
    const [currency, setCurrency] = useState(existing?.currency ?? "INR");
    const [category, setCategory] = useState(existing?.category ?? "");
    const [description, setDesc] = useState(existing?.description ?? "");
    const [expenseDate, setDate] = useState(existing?.expense_date ?? today());
    const [paidBy, setPaidBy] = useState(existing?.paid_by ?? "employee");
    const [receiptUrl, setReceiptUrl] = useState(existing?.receipt_url ?? "");
    const [error, setError] = useState("");
    const [saving, setSaving] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    const isEdit = Boolean(existing);

    const handleOcrExtracted = (data: OcrResult) => {
        if (data.amount) setAmount(data.amount.toString());
        if (data.currency) setCurrency(data.currency);
        if (data.date) setDate(data.date);
        if (data.description) setDesc(data.description);
        if (data.category) setCategory(data.category);
    };

    const buildPayload = () => ({
        amount: parseFloat(amount),
        currency: currency.toUpperCase(),
        category,
        description,
        expense_date: expenseDate,
        paid_by: paidBy,
    });

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        if (!category) { setError("Please select a category."); return; }
        if (!amount || isNaN(parseFloat(amount)) || parseFloat(amount) <= 0) {
            setError("Please enter a valid amount."); return;
        }
        setSaving(true);
        try {
            if (isEdit && existing) {
                await api.patch(`/api/v1/expenses/${existing.id}`, buildPayload());
            } else {
                await api.post("/api/v1/expenses/", buildPayload());
            }
            onSaved();
            onClose();
        } catch (err: unknown) {
            const e = err as { response?: { data?: { detail?: string } } };
            setError(e?.response?.data?.detail ?? "Failed to save expense.");
        } finally {
            setSaving(false);
        }
    };

    const handleSaveAndSubmit = async () => {
        setError("");
        if (!category) { setError("Please select a category."); return; }
        if (!amount || isNaN(parseFloat(amount)) || parseFloat(amount) <= 0) {
            setError("Please enter a valid amount."); return;
        }
        setSubmitting(true);
        try {
            let expenseId = existing?.id;
            if (!isEdit) {
                const { data } = await api.post("/api/v1/expenses/", buildPayload());
                expenseId = data.id;
            } else {
                await api.patch(`/api/v1/expenses/${existing!.id}`, buildPayload());
            }
            await api.post(`/api/v1/expenses/${expenseId}/submit`);
            onSaved();
            onClose();
        } catch (err: unknown) {
            const e = err as { response?: { data?: { detail?: string } } };
            setError(e?.response?.data?.detail ?? "Failed to submit expense.");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal modal-lg" style={{ maxWidth: 620 }} onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2 className="modal-title">{isEdit ? "Edit Expense" : "New Expense"}</h2>
                    <button className="icon-btn" onClick={onClose}>{Icons.x}</button>
                </div>

                {/* OCR Panel — only for new expenses */}
                {!isEdit && (
                    <OcrPanel
                        onExtracted={handleOcrExtracted}
                        onReceiptUrl={(url) => setReceiptUrl(url)}
                    />
                )}

                <form onSubmit={handleSave} className="auth-form" style={{ marginTop: "1rem" }}>
                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">Amount</label>
                            <input
                                className="form-input"
                                type="number"
                                step="0.01"
                                min="0.01"
                                placeholder="0.00"
                                value={amount}
                                onChange={(e) => setAmount(e.target.value)}
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label className="form-label">Currency</label>
                            <select
                                className="form-input form-select"
                                value={currency}
                                onChange={(e) => setCurrency(e.target.value)}
                            >
                                {CURRENCIES.map((c) => (
                                    <option key={c} value={c}>{c}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label className="form-label">Category</label>
                            <select
                                className="form-input form-select"
                                value={category}
                                onChange={(e) => setCategory(e.target.value)}
                                required
                            >
                                <option value="">Select category…</option>
                                {CATEGORIES.map((c) => (
                                    <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                                ))}
                            </select>
                        </div>
                        <div className="form-group">
                            <label className="form-label">Expense Date</label>
                            <input
                                className="form-input"
                                type="date"
                                value={expenseDate}
                                max={today()}
                                onChange={(e) => setDate(e.target.value)}
                                required
                            />
                        </div>
                    </div>

                    <div className="form-group">
                        <label className="form-label">Description</label>
                        <input
                            className="form-input"
                            placeholder="e.g. Cab to client office, Team lunch at Barbeque Nation"
                            value={description}
                            onChange={(e) => setDesc(e.target.value)}
                            required
                            maxLength={300}
                        />
                    </div>

                    <div className="form-group">
                        <label className="form-label">Paid By</label>
                        <select
                            className="form-input form-select"
                            value={paidBy}
                            onChange={(e) => setPaidBy(e.target.value)}
                        >
                            <option value="employee">Employee (out of pocket)</option>
                            <option value="company">Company Card</option>
                        </select>
                    </div>

                    {receiptUrl && (
                        <div className="form-group">
                            <label className="form-label">Receipt</label>
                            <a href={receiptUrl} target="_blank" rel="noopener noreferrer" className="receipt-link">
                                {Icons.receipt} View uploaded receipt ↗
                            </a>
                        </div>
                    )}

                    {error && <div className="form-error">{error}</div>}

                    <div className="modal-actions" style={{ gap: "0.5rem" }}>
                        <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
                        <button type="submit" className="btn-ghost" disabled={saving || submitting}>
                            {saving ? "Saving…" : "Save Draft"}
                        </button>
                        <button
                            type="button"
                            className="btn-primary-sm"
                            onClick={handleSaveAndSubmit}
                            disabled={saving || submitting}
                        >
                            {submitting ? (
                                <>{Icons.spin} Submitting…</>
                            ) : (
                                <>{Icons.send} Submit for Approval</>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}

// ── Expense Detail Modal ──────────────────────────────────────────────────────
function ExpenseDetailModal({
    expenseId,
    onClose,
    onEdit,
}: {
    expenseId: string;
    onClose: () => void;
    onEdit: (expense: Expense) => void;
}) {
    const [detail, setDetail] = useState<ExpenseDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        api.get(`/api/v1/expenses/${expenseId}`)
            .then(({ data }) => setDetail(data))
            .catch(() => setError("Failed to load expense details."))
            .finally(() => setLoading(false));
    }, [expenseId]);

    const handleSubmit = async () => {
        if (!detail) return;
        setSubmitting(true);
        setError("");
        try {
            await api.post(`/api/v1/expenses/${detail.id}/submit`);
            // Reload detail
            const { data } = await api.get(`/api/v1/expenses/${expenseId}`);
            setDetail(data);
        } catch (err: unknown) {
            const e = err as { response?: { data?: { detail?: string } } };
            setError(e?.response?.data?.detail ?? "Failed to submit.");
        } finally {
            setSubmitting(false);
        }
    };

    const trailDotClass = (action: string | null) => {
        if (action === "approve") return "trail-dot trail-dot-approve";
        if (action === "reject") return "trail-dot trail-dot-reject";
        return "trail-dot trail-dot-pending";
    };

    return (
        <div className="modal-backdrop" onClick={onClose}>
            <div className="modal modal-lg" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2 className="modal-title">Expense Detail</h2>
                    <button className="icon-btn" onClick={onClose}>{Icons.x}</button>
                </div>

                {loading && (
                    <div className="loading-rows">
                        {[1, 2, 3].map(i => <div key={i} className="skeleton-row" />)}
                    </div>
                )}

                {error && <div className="form-error">{error}</div>}

                {detail && (
                    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                        {/* Status + actions */}
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                            <StatusBadge status={detail.status} />
                            <div style={{ display: "flex", gap: "0.5rem" }}>
                                {detail.status === "draft" && (
                                    <>
                                        <button className="btn-ghost-sm" onClick={() => { onClose(); onEdit(detail); }}>
                                            {Icons.edit} Edit
                                        </button>
                                        <button
                                            className="btn-primary-sm"
                                            onClick={handleSubmit}
                                            disabled={submitting}
                                        >
                                            {submitting ? Icons.spin : Icons.send}
                                            {submitting ? " Submitting…" : " Submit"}
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>

                        {/* Key fields */}
                        <div className="detail-panel">
                            <div className="detail-row">
                                <div className="detail-field">
                                    <span className="detail-label">Amount</span>
                                    <span className="amount-primary">{formatCurrency(detail.amount, detail.currency)}</span>
                                    {detail.converted_amount && detail.base_currency && detail.base_currency !== detail.currency && (
                                        <span className="amount-converted">
                                            ≈ {formatCurrency(detail.converted_amount, detail.base_currency)}
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
                                    <span className="detail-value" style={{ textTransform: "capitalize" }}>
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
                                    <a href={detail.receipt_url} target="_blank" rel="noopener noreferrer" className="receipt-link">
                                        {Icons.receipt} View Receipt ↗
                                    </a>
                                </div>
                            )}
                        </div>

                        {/* Approval trail */}
                        {detail.approval_trail.length > 0 && (
                            <div>
                                <div className="detail-label" style={{ marginBottom: "0.75rem" }}>Approval Trail</div>
                                {detail.approval_trail.map((record) => (
                                    <div key={record.id} className="trail-item">
                                        <div className={trailDotClass(record.action)} />
                                        <div style={{ flex: 1 }}>
                                            <div className="trail-name">
                                                {record.approver_name ?? "Approver"}
                                                <span style={{ marginLeft: "0.5rem", fontSize: "0.78rem" }}>
                                                    {record.step_order === 0 ? "(Manager)" : `(Step ${record.step_order})`}
                                                </span>
                                            </div>
                                            <div className="trail-action">
                                                {record.action
                                                    ? `${record.action === "approve" ? "✓ Approved" : "✗ Rejected"} · ${record.acted_at ? new Date(record.acted_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : ""}`
                                                    : "⏳ Waiting for action"}
                                            </div>
                                            {record.comment && (
                                                <div className="trail-comment">"{record.comment}"</div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {detail.status === "draft" && detail.approval_trail.length === 0 && (
                            <p style={{ fontSize: "0.85rem", color: "var(--color-muted-foreground)" }}>
                                Submit this expense to start the approval process.
                            </p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

// ── Main Employee Dashboard ───────────────────────────────────────────────────
export default function EmployeeDashboard() {
    const { user, logout } = useAuthStore();
    const navigate = useNavigate();

    const [expenses, setExpenses] = useState<Expense[]>([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

    const [showForm, setShowForm] = useState(false);
    const [editExpense, setEditExpense] = useState<Expense | null>(null);
    const [viewExpenseId, setViewExpenseId] = useState<string | null>(null);

    const fetchExpenses = useCallback(async () => {
        setLoading(true);
        try {
            const params = statusFilter !== "all" ? { status: statusFilter } : {};
            const { data } = await api.get("/api/v1/expenses/", { params });
            setExpenses(data);
        } catch {
            // silent
        } finally {
            setLoading(false);
        }
    }, [statusFilter]);

    useEffect(() => { fetchExpenses(); }, [fetchExpenses]);

    const handleLogout = () => { logout(); navigate("/login"); };

    const openEdit = (expense: Expense) => {
        setEditExpense(expense);
        setViewExpenseId(null);
        setShowForm(true);
    };

    // Status filter counts
    const counts: Record<StatusFilter, number> = {
        all: expenses.length,
        draft: 0, pending: 0, approved: 0, rejected: 0,
    };
    // We always show counts from the current fetched set
    expenses.forEach((e) => { counts[e.status as StatusFilter]++; });

    const TABS: { key: StatusFilter; label: string }[] = [
        { key: "all", label: "All" },
        { key: "draft", label: "Draft" },
        { key: "pending", label: "Pending" },
        { key: "approved", label: "Approved" },
        { key: "rejected", label: "Rejected" },
    ];

    // Summary cards
    const totalApproved = expenses
        .filter((e) => e.status === "approved")
        .reduce((sum, e) => sum + (e.converted_amount ?? e.amount), 0);
    const baseCurrency = expenses.find((e) => e.base_currency)?.base_currency ?? "INR";

    return (
        <>
            <style>{EMPLOYEE_CSS}</style>
            <div className="app-shell">
                {/* ── Sidebar ── */}
                <aside className="sidebar">
                    <div className="sidebar-logo">
                        <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
                            <rect width="32" height="32" rx="8" fill="url(#empLogoGrad)" />
                            <path d="M8 20L14 12L19 17L23 11" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                            <circle cx="23" cy="11" r="2" fill="white" />
                            <defs>
                                <linearGradient id="empLogoGrad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
                                    <stop stopColor="#10b981" /><stop offset="1" stopColor="#059669" />
                                </linearGradient>
                            </defs>
                        </svg>
                        <span className="sidebar-brand">xpensa</span>
                    </div>

                    <div className="sidebar-section-label">Employee</div>

                    <nav className="sidebar-nav">
                        <button className="nav-item nav-item-active">
                            {Icons.receipt} My Expenses
                        </button>
                    </nav>

                    <div className="sidebar-footer">
                        <div className="sidebar-user">
                            <div className="avatar">{user?.full_name?.[0] ?? "E"}</div>
                            <div className="sidebar-user-info">
                                <span className="sidebar-user-name">{user?.full_name}</span>
                                <span className="sidebar-user-role">Employee</span>
                            </div>
                        </div>
                        <button className="icon-btn" onClick={handleLogout} title="Log out">{Icons.logout}</button>
                    </div>
                </aside>

                {/* ── Main ── */}
                <main className="main-content">
                    <div className="tab-content">
                        {/* Header */}
                        <div className="content-header">
                            <div>
                                <h2 className="content-title">My Expenses</h2>
                                <p className="content-subtitle">Track and submit your reimbursement requests</p>
                            </div>
                            <button className="btn-primary-sm" onClick={() => { setEditExpense(null); setShowForm(true); }}>
                                {Icons.plus} New Expense
                            </button>
                        </div>

                        {/* Summary cards */}
                        <div className="summary-grid">
                            <div className="summary-card">
                                <div className="summary-label">Total Approved</div>
                                <div className="summary-value">{formatCurrency(totalApproved, baseCurrency)}</div>
                                <div className="summary-sub">{counts.approved} expense{counts.approved !== 1 ? "s" : ""}</div>
                            </div>
                            <div className="summary-card">
                                <div className="summary-label">Awaiting Approval</div>
                                <div className="summary-value summary-value-amber">{counts.pending}</div>
                                <div className="summary-sub">pending review</div>
                            </div>
                            <div className="summary-card">
                                <div className="summary-label">Drafts</div>
                                <div className="summary-value summary-value-muted">{counts.draft}</div>
                                <div className="summary-sub">not submitted yet</div>
                            </div>
                        </div>

                        {/* Filter tabs */}
                        <div className="filter-tabs">
                            {TABS.map((tab) => (
                                <button
                                    key={tab.key}
                                    className={`filter-tab ${statusFilter === tab.key ? "filter-tab-active" : ""}`}
                                    onClick={() => setStatusFilter(tab.key)}
                                >
                                    {tab.label}
                                    <span className="filter-tab-count">
                                        {tab.key === "all" ? expenses.length : counts[tab.key]}
                                    </span>
                                </button>
                            ))}
                        </div>

                        {/* Table */}
                        {loading ? (
                            <div className="loading-rows">
                                {[1, 2, 3, 4].map(i => <div key={i} className="skeleton-row" />)}
                            </div>
                        ) : expenses.length === 0 ? (
                            <div className="empty-state">
                                <div className="empty-icon">🧾</div>
                                <p className="empty-title">
                                    {statusFilter === "all" ? "No expenses yet" : `No ${statusFilter} expenses`}
                                </p>
                                <p className="empty-sub">
                                    {statusFilter === "all"
                                        ? "Click \"New Expense\" to submit your first reimbursement request."
                                        : "Try switching to a different filter."}
                                </p>
                            </div>
                        ) : (
                            <div className="table-wrap">
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Description</th>
                                            <th>Category</th>
                                            <th>Amount</th>
                                            <th>Date</th>
                                            <th>Status</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {expenses.map((exp) => (
                                            <tr key={exp.id}>
                                                <td className="td-name" style={{ maxWidth: 240 }}>
                                                    <span style={{ display: "block", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                                        {exp.description}
                                                    </span>
                                                </td>
                                                <td>
                                                    <span className="expense-category">{exp.category}</span>
                                                </td>
                                                <td>
                                                    <div>{formatCurrency(exp.amount, exp.currency)}</div>
                                                    {exp.converted_amount && exp.base_currency && exp.base_currency !== exp.currency && (
                                                        <div style={{ fontSize: "0.77rem", color: "hsl(160 84% 55%)" }}>
                                                            ≈ {formatCurrency(exp.converted_amount, exp.base_currency)}
                                                        </div>
                                                    )}
                                                </td>
                                                <td className="td-muted">{formatDate(exp.expense_date)}</td>
                                                <td><StatusBadge status={exp.status} /></td>
                                                <td>
                                                    <div style={{ display: "flex", gap: "0.375rem" }}>
                                                        <button
                                                            className="icon-btn"
                                                            title="View details"
                                                            onClick={() => setViewExpenseId(exp.id)}
                                                        >
                                                            {Icons.eye}
                                                        </button>
                                                        {exp.status === "draft" && (
                                                            <button
                                                                className="icon-btn"
                                                                title="Edit draft"
                                                                onClick={() => openEdit(exp)}
                                                            >
                                                                {Icons.edit}
                                                            </button>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </main>
            </div>

            {/* ── Modals ── */}
            {showForm && (
                <ExpenseFormModal
                    existing={editExpense}
                    onClose={() => { setShowForm(false); setEditExpense(null); }}
                    onSaved={fetchExpenses}
                />
            )}

            {viewExpenseId && (
                <ExpenseDetailModal
                    expenseId={viewExpenseId}
                    onClose={() => setViewExpenseId(null)}
                    onEdit={(exp) => { setViewExpenseId(null); openEdit(exp); }}
                />
            )}
        </>
    );
}

// ── Scoped CSS ────────────────────────────────────────────────────────────────
const EMPLOYEE_CSS = `
/* Summary cards */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}
.summary-card {
  background: hsl(222 40% 8%);
  border: 1px solid hsl(222 30% 13%);
  border-radius: 0.875rem;
  padding: 1.25rem 1.5rem;
}
.summary-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: hsl(215 15% 40%);
  margin-bottom: 0.375rem;
}
.summary-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: hsl(160 84% 60%);
  letter-spacing: -0.02em;
}
.summary-value-amber { color: hsl(35 90% 65%); }
.summary-value-muted { color: hsl(215 20% 60%); }
.summary-sub {
  font-size: 0.78rem;
  color: hsl(215 15% 40%);
  margin-top: 0.125rem;
}

/* Filter tabs */
.filter-tabs {
  display: flex;
  gap: 0.375rem;
  background: hsl(222 40% 7%);
  border: 1px solid hsl(222 30% 13%);
  border-radius: 0.625rem;
  padding: 0.25rem;
  width: fit-content;
}
.filter-tab {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.875rem;
  border: none;
  background: transparent;
  border-radius: 0.375rem;
  font-size: 0.83rem;
  font-weight: 500;
  color: hsl(215 20% 50%);
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s, color 0.15s;
}
.filter-tab:hover { color: var(--color-foreground); background: hsl(222 35% 12%); }
.filter-tab-active { background: hsl(222 35% 14%) !important; color: var(--color-foreground) !important; }
.filter-tab-count {
  font-size: 0.72rem;
  font-weight: 700;
  background: hsl(222 35% 18%);
  color: hsl(215 20% 60%);
  padding: 0.1rem 0.45rem;
  border-radius: 99px;
  min-width: 20px;
  text-align: center;
}
.filter-tab-active .filter-tab-count {
  background: hsl(160 84% 39% / 0.15);
  color: hsl(160 84% 60%);
}

/* Category pill */
.expense-category {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 99px;
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: capitalize;
  background: hsl(222 35% 14%);
  color: hsl(215 20% 65%);
  border: 1px solid hsl(222 30% 20%);
}

/* Receipt link */
.receipt-link {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.875rem;
  color: hsl(160 84% 55%);
  text-decoration: none;
  transition: opacity 0.15s;
}
.receipt-link:hover { opacity: 0.75; }

/* ── OCR Panel ── */
.ocr-panel {
  background: hsl(222 40% 7%);
  border: 1px solid hsl(222 30% 16%);
  border-radius: 0.75rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.ocr-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: hsl(215 20% 55%);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.ocr-badge {
  font-size: 0.65rem;
  font-weight: 700;
  background: linear-gradient(135deg, hsl(270 84% 55%), hsl(200 84% 50%));
  color: white;
  padding: 0.1rem 0.4rem;
  border-radius: 99px;
  letter-spacing: 0.04em;
}
.ocr-dropzone {
  border: 1.5px dashed hsl(222 30% 22%);
  border-radius: 0.625rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.375rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.ocr-dropzone:hover {
  border-color: hsl(160 84% 39% / 0.5);
  background: hsl(160 84% 39% / 0.03);
}
.ocr-dropzone-icon { color: hsl(215 15% 40%); }
.ocr-dropzone-text {
  font-size: 0.875rem;
  color: hsl(215 20% 60%);
  margin: 0;
}
.ocr-link { color: hsl(160 84% 55%); }
.ocr-dropzone-hint {
  font-size: 0.75rem;
  color: hsl(215 15% 38%);
  margin: 0;
}
.ocr-processing, .ocr-done, .ocr-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}
.ocr-preview {
  width: 100%;
  max-height: 120px;
  object-fit: contain;
  border-radius: 0.5rem;
  border: 1px solid hsl(222 30% 18%);
}
.ocr-status-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: hsl(215 20% 60%);
}
.ocr-progress-bar {
  width: 100%;
  height: 3px;
  background: hsl(222 30% 18%);
  border-radius: 99px;
  overflow: hidden;
}
.ocr-progress-fill {
  height: 100%;
  width: 40%;
  background: linear-gradient(90deg, hsl(160 84% 39%), hsl(200 84% 55%));
  border-radius: 99px;
}
.ocr-progress-animated {
  animation: ocr-sweep 1.8s ease-in-out infinite;
}
@keyframes ocr-sweep {
  0% { transform: translateX(-100%); width: 60%; }
  100% { transform: translateX(250%); width: 60%; }
}
.ocr-done-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: hsl(160 84% 60%);
  background: hsl(160 84% 39% / 0.1);
  border: 1px solid hsl(160 84% 39% / 0.2);
  padding: 0.4rem 0.875rem;
  border-radius: 99px;
}
.ocr-done-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  background: hsl(160 84% 39%);
  border-radius: 50%;
  color: white;
  flex-shrink: 0;
}
.ocr-reset-btn {
  background: transparent;
  border: 1px solid hsl(222 30% 22%);
  color: hsl(215 15% 50%);
  font-size: 0.8rem;
  font-family: inherit;
  padding: 0.3rem 0.75rem;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background 0.15s;
}
.ocr-reset-btn:hover { background: hsl(222 35% 14%); color: var(--color-foreground); }
.ocr-error-msg {
  font-size: 0.84rem;
  color: hsl(0 72% 65%);
  text-align: center;
  margin: 0;
}

/* Spin animation for icons */
.animate-spin {
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
`;