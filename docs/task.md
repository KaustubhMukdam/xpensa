# Xpensa Backend — Task Progress

## Phase 3 — Approval Rules ✅
- [x] Add `is_active` to `ApprovalRule` model
- [x] `app/schemas/approval_rule.py`
- [x] `app/routers/approval_rules.py` (CRUD + soft-delete)
- [x] Register router in `main.py`

## Phase 4 — Expenses ✅
- [x] `app/models/expense.py` (Expense + ApprovalRecord)
- [x] Add back-references to User model
- [x] Export new models from `models/__init__.py`
- [x] `app/schemas/expense.py`
- [x] `app/services/currency.py` (TTL-cached exchange rates)
- [x] `app/routers/expenses.py` (create, list, detail, update, submit)
- [x] Register router in `main.py`

## Phase 5 — Approval Engine ✅
- [x] `app/services/approval_engine.py` (initialize_chain + process_action)
- [x] `app/routers/approvals.py` (queue, detail, approve, reject)
- [x] Register router in `main.py`

## Seed Data ✅
- [x] `backend/seed.py` (company, 3 users, 2 rules, 4 expenses)

## Alembic Migration ← YOU NEED TO RUN THIS
- [ ] `cd backend`
- [ ] `alembic revision --autogenerate -m "add_expenses_approval_records_is_active"`
- [ ] `alembic upgrade head`

## Install Dependencies ← YOU NEED TO RUN THIS
- [ ] `pip install -r requirements.txt` (adds `cachetools==5.5.0`)

## Frontend — White Screen Fix ✅
- [x] `index.css` rewritten for Tailwind v4 (uses `@theme` + `--color-*`)
- [x] Vite cache cleared
- [ ] **Stop and restart `npm run dev`** (Ctrl+C → `npm run dev`)

## Remaining Frontend Phases
- [ ] Phase 1: Login + Register pages (full UI)
- [ ] Phase 2: Admin user management UI
- [ ] Phase 3: Approval rules config UI
- [ ] Phase 4: Expense list + new expense form
- [ ] Phase 6: Manager approval queue
