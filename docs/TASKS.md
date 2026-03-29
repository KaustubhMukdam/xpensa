# TASKS.md — xpensa Hackathon Task Board

> Priority: P0 = must have | P1 = should have | P2 = nice to have
> Each task is 30min–2hr estimated. Tackle Phase 0–4 first to have a working demo core.

---

## Phase 0 — Project Setup & Scaffolding

- [ ] **[P0]** Create GitHub repo (`xpensa`), add `README.md`, `.gitignore` (Python + Node)
- [ ] **[P0]** Scaffold backend: `backend/` with FastAPI + SQLModel + Alembic structure
  - `app/main.py`, `app/core/config.py`, `app/core/database.py`, `app/core/security.py`
  - `requirements.txt` with pinned versions
- [ ] **[P0]** Scaffold frontend: `npx create-vite@latest frontend -- --template react-ts`
  - Install: `tailwindcss`, `shadcn/ui` (init), `lucide-react`, `react-router-dom`, `@tanstack/react-query`, `zustand`, `react-hook-form`, `zod`, `axios`, `framer-motion`
- [ ] **[P0]** Set up Supabase project — copy DB connection string + anon key
- [ ] **[P0]** Configure `backend/.env` with `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY`, `SECRET_KEY`
- [ ] **[P0]** Configure `frontend/.env` with `VITE_API_BASE_URL=http://localhost:8000`
- [ ] **[P0]** Create `docker-compose.yml` for local dev (FastAPI + Vite containers)
- [ ] **[P0]** First Alembic migration: `alembic init alembic` + configure `env.py` to use SQLModel metadata
- [ ] **[P1]** Set up `render.yaml` for backend deployment config
- [ ] **[P1]** Connect frontend repo to Vercel (auto-deploy on push to `main`)

---

## Phase 1 — Auth & Company Onboarding

### Backend
- [ ] **[P0]** Define SQLModel models: `Company`, `User` (with `role` enum: admin/manager/employee)
- [ ] **[P0]** Run Alembic migration to create tables in Supabase DB
- [ ] **[P0]** `POST /auth/signup` — create Company + Admin user in one transaction
  - Call restcountries API to resolve country → currency on signup
  - Hash password with bcrypt, return JWT
- [ ] **[P0]** `POST /auth/login` — verify credentials, return JWT (role + company_id in claims)
- [ ] **[P0]** JWT auth dependency (`get_current_user`) — decode token, inject user into routes
- [ ] **[P1]** `POST /auth/forgot-password` — generate reset token, send email via SendGrid
- [ ] **[P1]** `POST /auth/reset-password` — validate token, set new password

### Frontend
- [ ] **[P0]** Build Signup page — company name, admin name, email, password, country dropdown
  - Fetch country list from `restcountries.com` on page load, show currency label next to selected country
- [ ] **[P0]** Build Login page — email, password, "Forgot password?" link
- [ ] **[P0]** Zustand `authStore` — store `{ token, user: { id, role, company_id, name } }`
- [ ] **[P0]** Axios instance in `src/lib/api.ts` — base URL from env, JWT injected via interceptor, 401 → redirect to login
- [ ] **[P0]** Role-based route guards — `ProtectedRoute` component that checks `authStore.user.role`
  - `/admin/*` → admin only | `/employee/*` → employee only | `/manager/*` → manager only
- [ ] **[P1]** Persist auth to `sessionStorage` (note: localStorage blocked on some sandboxed iframes — sessionStorage is fine for Vercel/Render)

---

## Phase 2 — Admin: User Management

### Backend
- [ ] **[P0]** `POST /users` — Admin creates employee or manager (auto-generates temp password, sends email)
- [ ] **[P0]** `GET /users` — list all users in company (admin only)
- [ ] **[P0]** `PATCH /users/{id}` — update role, assign/change manager relationship
- [ ] **[P1]** `POST /users/{id}/resend-password` — resend temp password email

### Frontend
- [ ] **[P0]** Admin layout with sidebar nav: Users | Approval Rules | All Expenses
- [ ] **[P0]** Users page — table: Name | Role | Manager | Email | Actions
- [ ] **[P0]** "New Employee" + "New Manager" buttons → modal form (name, email, role, manager dropdown)
- [ ] **[P0]** "Send password" action per row — triggers resend API call
- [ ] **[P1]** Inline role/manager edit in table rows

---

## Phase 3 — Admin: Approval Rule Configuration

### Backend
- [ ] **[P0]** Define SQLModel models: `ApprovalRule`, `ApprovalStep`
  - `ApprovalRule`: company_id, category, manager_is_approver (bool), rule_type, min_approval_pct, specific_approver_id
  - `ApprovalStep`: rule_id, approver_id (FK to User), sequence_order, is_required
- [ ] **[P0]** Run migration for new tables
- [ ] **[P0]** `POST /approval-rules` — create rule with steps (nested create)
- [ ] **[P0]** `GET /approval-rules` — list rules for company
- [ ] **[P0]** `PATCH /approval-rules/{id}` — update rule + steps (upsert steps)
- [ ] **[P0]** `DELETE /approval-rules/{id}` — soft-delete

### Frontend
- [ ] **[P0]** Approval Rules page — list cards per category
- [ ] **[P0]** Rule config form:
  - Category input
  - "Manager is approver" toggle
  - Ordered approver list (drag-to-reorder is P2) — add/remove approvers with "Required" checkbox per row
  - Conditional rule section: radio between "Percentage", "Specific Approver", "Hybrid"
  - Min approval % numeric input (shown when Percentage or Hybrid selected)
  - Specific approver dropdown (shown when Specific or Hybrid selected)
- [ ] **[P1]** Drag-to-reorder approver steps (use `@dnd-kit/core`)

---

## Phase 4 — Expense Submission (Employee)

### Backend
- [ ] **[P0]** Define SQLModel models: `Expense`, `ApprovalRecord`
  - `Expense`: company_id, employee_id, amount, currency, converted_amount, base_currency, exchange_rate_snapshot, category, description, date, paid_by, status (draft/pending/approved/rejected), receipt_url
  - `ApprovalRecord`: expense_id, approver_id, action, comment, timestamp, exchange_rate_snapshot
- [ ] **[P0]** Run migration
- [ ] **[P0]** Currency service (`app/services/currency.py`):
  - `TTLCache` (1-hour) keyed by base currency
  - `async def get_exchange_rate(from_currency, to_currency)` using httpx + exchangerate-api
- [ ] **[P0]** `POST /expenses` — create expense (status=draft), auto-convert amount to company base currency
- [ ] **[P0]** `GET /expenses` — list employee's own expenses (with status filter)
- [ ] **[P0]** `GET /expenses/{id}` — expense detail + approval trail
- [ ] **[P0]** `POST /expenses/{id}/submit` — change status draft→pending, trigger approval chain initialization
- [ ] **[P1]** `PATCH /expenses/{id}` — edit draft expense

### Frontend
- [ ] **[P0]** Employee layout with sidebar: My Expenses | New Expense
- [ ] **[P0]** Expense list page — table: Description | Category | Amount | Currency | Status (pill) | Date
  - Status pills: Draft (gray) | Waiting Approval (amber) | Approved (green) | Rejected (red)
- [ ] **[P0]** New Expense form — Description, Category (links to rule), Amount, Currency dropdown (all world currencies), Date, Paid By
  - Show live converted amount in company's base currency below the amount field
- [ ] **[P0]** Expense detail page — form fields (read-only after submit) + Approval Trail table (Approver | Status | Time)
- [ ] **[P0]** "Submit" button — calls `/expenses/{id}/submit`, transitions status pill with Framer Motion
- [ ] **[P0]** TanStack Query hooks: `useExpenses()`, `useExpense(id)`, `useCreateExpense()`, `useSubmitExpense()`
- [ ] **[P1]** Empty state for expense list: animated receipt icon + "Submit your first expense" CTA

---

## Phase 5 — Approval Engine (Core Backend Logic)

- [ ] **[P0]** `app/services/approval_engine.py` — the heart of the system:
  ```
  async def initialize_chain(expense_id):
    → find ApprovalRule for expense.category
    → if manager_is_approver: create pending record for manager (step 0)
    → else: create pending record for first step approver
    → notify first approver via email

  async def process_action(expense_id, approver_id, action, comment):
    → validate approver is current pending approver
    → record ApprovalRecord with timestamp + exchange_rate_snapshot
    → if action == REJECT: mark expense rejected, notify employee, end chain
    → check conditional rules:
        - percentage rule: if approved_count/total_approvers >= min_pct → approve
        - specific approver rule: if this approver == specific_approver_id → approve
    → if rule triggered: mark expense approved, notify employee, end
    → else: advance to next step approver
    → if no more steps: mark approved, notify employee
  ```
- [ ] **[P0]** `POST /approvals/{expense_id}/approve` — calls `process_action(action=APPROVE)`
- [ ] **[P0]** `POST /approvals/{expense_id}/reject` — calls `process_action(action=REJECT)`
- [ ] **[P0]** `GET /approvals` — manager's pending approval queue (expenses where current pending approver = current user)

---

## Phase 6 — Manager View

### Backend
- [ ] **[P0]** `GET /approvals` already done in Phase 5 — ensure it returns converted amount in company base currency
- [ ] **[P0]** `GET /approvals/{expense_id}` — expense detail for manager (same as employee detail + full trail)

### Frontend
- [ ] **[P0]** Manager layout with sidebar: Approvals Queue | Team Expenses
- [ ] **[P0]** Approvals page — table: Subject | Request Owner | Category | Status | Total Amount (base currency) | Approve | Reject
  - Amounts always show in company currency with flag/symbol
- [ ] **[P0]** Click row → Expense detail sheet/modal — full form + approval trail + Approve/Reject buttons + comment input
- [ ] **[P0]** "Approve" / "Reject" buttons with optimistic update (remove from queue immediately, undo on error)
- [ ] **[P1]** Empty state for approvals queue: "All caught up!" with a checkmark animation

---

## Phase 7 — OCR Receipt Scanning (Additional Feature)

### Backend
- [ ] **[P1]** Install `easyocr` and `supabase-py` in requirements.txt
- [ ] **[P1]** `POST /ocr/extract` — accept multipart image upload:
  - Upload file to Supabase Storage (`receipts/{company_id}/{uuid}.jpg`), get public URL
  - Launch `BackgroundTask`: run EasyOCR → parse amount, date, vendor, line items
  - Return `{ task_id, receipt_url }` immediately
- [ ] **[P1]** In-memory task store: `{ task_id: { status, result } }` (dict with TTL)
- [ ] **[P1]** `GET /ocr/status/{task_id}` — return `{ status: processing|done|error, data: {...} }`
- [ ] **[P1]** OCR parser (`ocr_service.py`): regex patterns to extract currency amounts, dates (DD/MM/YYYY, MM/DD/YYYY), merchant name from first line of receipt

### Frontend
- [ ] **[P1]** "Upload Receipt" button on expense form → file picker → POST to `/ocr/extract`
- [ ] **[P1]** Show spinner "Reading receipt..." → poll `/ocr/status/{task_id}` every 2s
- [ ] **[P1]** On done: auto-fill Description, Amount, Currency, Date from OCR result (user can override)
- [ ] **[P1]** Receipt thumbnail preview in form with "Remove" option

---

## Phase 8 — Deployment

- [ ] **[P0]** Backend: push to GitHub → connect Render → add all env vars from `PLANNING.md`
  - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - Add `GET /health` route returning `{"status": "ok"}` (prevents Render cold starts with an uptime monitor)
- [ ] **[P0]** Frontend: connect Vercel to GitHub repo → set `VITE_API_BASE_URL` to Render URL
- [ ] **[P0]** Run Alembic migrations against production Supabase DB: `alembic upgrade head`
- [ ] **[P0]** Test full signup → expense submission → approval flow on production URLs
- [ ] **[P1]** Set up UptimeRobot (free) to ping `/health` every 5 min — prevents Render free tier sleep

---

## Phase 9 — Polish & Demo Prep

- [ ] **[P1]** Add loading skeletons to all data-fetching pages (expense list, approvals queue)
- [ ] **[P1]** Toast notifications (Sonner) for: expense submitted, approved, rejected
- [ ] **[P1]** Status pill animations with Framer Motion (spring transition between states)
- [ ] **[P1]** Responsive mobile layout (sidebar → hamburger menu)
- [ ] **[P1]** Dark mode toggle (Shadcn ships it — just wire up `ThemeProvider`)
- [ ] **[P2]** Admin "All Expenses" page with filters (status, category, employee, date range)
- [ ] **[P2]** Simple analytics: expense total by category (Recharts donut chart) on admin dashboard
- [ ] **[P2]** Confetti animation when an expense gets final approval (react-confetti)
- [ ] **[P0]** Seed demo data script (`seed.py`): create demo company + users + 3-level approval rule + sample expenses in various states

---

## Suggested Build Order (Hackathon Sprint)

```
Hour 1–2:   Phase 0 (setup) + Phase 1 backend (auth)
Hour 3–4:   Phase 1 frontend (login/signup) + Phase 2 (user management)
Hour 5–6:   Phase 3 (approval rules) + Phase 4 backend (expenses)
Hour 7–8:   Phase 4 frontend (expense list + form) + Phase 5 (approval engine ← most critical)
Hour 9–10:  Phase 6 (manager view) + basic Phase 8 (deploy)
Hour 11–12: Phase 7 (OCR) + Phase 9 (polish + seed data + demo prep)
```
