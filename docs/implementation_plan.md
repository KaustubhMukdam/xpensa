# Xpensa Backend Completion Plan

## What already exists (Phase 0–2 ✅)
- FastAPI app, CORS, health check
- `Company`, `User`, `ApprovalRule`, `ApprovalStep` models
- Auth router: `POST /register`, `POST /login`, `GET /me`, `POST /change-password`
- Users router: `POST /users`, `GET /users`, `GET /users/{id}`, `PATCH /users/{id}`, `POST /users/{id}/reset-password`
- Security, JWT, password hashing, DB session, dependencies (CurrentUser/Admin/Manager)
- Alembic configured with all current models

## What needs to be built

---

### Phase 3 — Approval Rules CRUD
#### [NEW] `app/routers/approval_rules.py`
- `POST /approval-rules` — create rule + steps (nested)
- `GET /approval-rules` — list rules for company (admin)
- `GET /approval-rules/{id}` — get specific rule with steps
- `PATCH /approval-rules/{id}` — update rule + upsert steps
- `DELETE /approval-rules/{id}` — soft delete (set `is_active=False`)

#### [MODIFY] `app/models/approval_rule.py`
- Add `is_active: bool = Field(default=True)` to `ApprovalRule` for soft-delete

#### [NEW] `app/schemas/approval_rule.py`
- `ApprovalStepIn`, `ApprovalRuleCreate`, `ApprovalRuleUpdate`, `ApprovalStepOut`, `ApprovalRuleOut`

---

### Phase 4 — Expense Submission (Backend)
#### [NEW] `app/models/expense.py`
- `ExpenseStatus` enum: `draft | pending | approved | rejected`
- `Expense` model: company_id, employee_id, amount, currency, converted_amount, base_currency, exchange_rate_snapshot, category, description, date, paid_by, status, receipt_url
- `ApprovalRecord` model: expense_id, approver_id, action (approve/reject), comment, timestamp, exchange_rate_snapshot

#### [NEW] `app/services/currency.py`
- TTLCache (1h) for exchange rates
- `async get_exchange_rate(from_currency, to_currency)` using httpx + free exchangerate API (no key needed for basic)

#### [NEW] `app/schemas/expense.py`
- `ExpenseCreate`, `ExpenseOut`, `ExpenseDetail` (with approval trail)

#### [NEW] `app/routers/expenses.py`
- `POST /expenses` — create expense (draft), auto-convert currency
- `GET /expenses` — employee's own expenses (status filter)
- `GET /expenses/{id}` — detail + approval trail
- `POST /expenses/{id}/submit` — draft → pending, triggers approval chain
- `PATCH /expenses/{id}` — edit draft only

---

### Phase 5 — Approval Engine
#### [NEW] `app/services/approval_engine.py`
- `initialize_chain(expense_id, session)` — find rule, create pending ApprovalRecord for first approver
- `process_action(expense_id, approver_id, action, comment, session)` — validate, record, advance chain, check conditional rules (percentage, specific approver)

#### [NEW] `app/routers/approvals.py`
- `GET /approvals` — manager's pending approval queue
- `GET /approvals/{expense_id}` — expense detail for approver
- `POST /approvals/{expense_id}/approve` — calls `process_action(APPROVE)`
- `POST /approvals/{expense_id}/reject` — calls `process_action(REJECT)`

---

### Phase 8 — Seed Script
#### [NEW] `backend/seed.py`
- Creates demo company + admin + manager + employee
- Creates a 2-step approval rule for "travel"  
- Creates sample expenses in various states (draft, pending, approved, rejected)

---

### Alembic Migration
- New migration for: `expenses`, `approval_records`, `is_active` on `approval_rules`

---

### `app/main.py` updates
- Register new routers: `approval_rules`, `expenses`, `approvals`
- Import new models in alembic `env.py`

---

## Verification Plan
1. Start backend with `uvicorn app.main:app --reload`
2. Run `alembic upgrade head` to apply new migration
3. Hit `/docs` and test: register → login → create expense → submit → approve
4. Run `python seed.py` to populate demo data

> [!NOTE]
> White screen on frontend is a separate Tailwind v4 cache issue. The fix is already in place — the dev server just needs a clean restart (Ctrl+C then `npm run dev`). Focus is now on backend completion.
