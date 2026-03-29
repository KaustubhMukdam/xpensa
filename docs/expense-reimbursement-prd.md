# Expense Reimbursement Management — Hackathon PRD

---

## Executive Summary

This document covers the Product Requirements Document (PRD), Design Stack, and Tech Stack for a multi-role, multi-currency expense reimbursement platform. The system enables companies to define configurable approval workflows, manage multi-level expense approvals, and auto-read receipts via OCR — eliminating the manual, error-prone reimbursement processes that plague most organizations.

---

## 1. Product Requirements Document (PRD)

### 1.1 Problem Statement

Companies struggle with manual expense reimbursement workflows that are:
- Time-consuming with no structured approval sequencing
- Error-prone due to manual data entry from paper/PDF receipts
- Lacking transparency — employees cannot track approval status in real time
- Inflexible — unable to support multi-level, threshold-based, or conditional approval rules

---

### 1.2 User Roles & Permissions

| Role | Key Permissions |
|------|----------------|
| **Admin** | Auto-creates company on signup (country sets default currency); creates/manages employees & managers; assigns roles; defines approval rules per category; views all expenses; overrides approvals |
| **Manager** | Views team expenses pending approval; approves or rejects with comments; sees all amounts auto-converted to company's base currency |
| **Employee** | Submits expense claims in any currency; attaches/scans receipts via OCR; tracks approval status in real time; views full expense history |

---

### 1.3 Screen-by-Screen Feature Breakdown

#### Screen 1 — Admin (Company) Signup
- Fields: Company Name, Admin Name, Email, Password, Confirm Password
- **Country dropdown** auto-populated via `https://restcountries.com/v3.1/all?fields=name,currencies`
- Selecting a country auto-sets the company's default currency (e.g., India → INR)
- On submit: company entity + admin user are created simultaneously
- Redirect to Admin Dashboard

#### Screen 2 — Sign-In Page
- Email + Password login
- "Don't have an account? Sign up" link
- "Forgot password?" link (reset flow)
- JWT token issued on successful auth

#### Screen 3 — Admin: User Management
- Table view: User Name | Role | Manager | Email | Actions
- **"Employee" / "Manager" buttons** to create new users
- On creation, a temporary password is auto-generated and a **"Send password"** email is triggered
- Admin can reassign roles and manager relationships inline
- Role change propagates through active approval chains

#### Screen 4 — Admin: Approval Rule Configuration
- Rule applies per **Category** (e.g., "Miscellaneous Expenses")
- **Manager Approver toggle**: If checked, the assigned manager is always Step 1 in the chain
- **Sequential Approvers list**: Admin defines ordered list of approvers (User 1 → User 2 → User 3)
  - Each approver row has a "Required" checkbox to mark mandatory vs. optional approvers
- **Conditional Approval Rules** (at least one must apply):
  - **Percentage Rule**: e.g., If 60% of approvers approve → expense is auto-approved
  - **Specific Approver Rule**: e.g., If "Sarah (CFO)" approves → expense is auto-approved regardless of others
  - **Hybrid Rule**: Percentage OR Specific Approver — whichever fires first triggers approval
- **Minimum Approval Percentage** field: numeric input (0–100%)
- Rules can combine sequential flow + conditional logic simultaneously

#### Screen 5 — Employee: Expense List View
- Table columns: Employee | Description | Role | Reimbursed By | Paid By | Reports | Amount | **Status**
- Status pill follows the flow: **Draft → Waiting Approval → Approved / Rejected**
- **"Upload"** button: upload receipt image → OCR auto-fills expense form
- **"New"** button: create blank expense form manually
- Clicking a row opens the Expense Detail View

#### Screen 6 — Employee: Expense Detail / Submission Form
- **Attach Receipt** button (upload from computer; OCR triggers on upload)
- Status header: `Draft | Waiting Approval | Approved`
- Fields:
  - Description (text)
  - Category (dropdown, links to approval rules)
  - Total Amount — employee submits in **any currency** (dropdown with all world currencies)
  - **Auto-conversion note**: The system auto-converts to company's base currency using `https://api.exchangerate-api.com/v4/latest/{BASE_CURRENCY}`
  - Paid By (dropdown: Employee / Company Card)
  - Description (long text)
- **Approval Trail** at bottom (read-only, visible after submission):
  - Columns: Approver | Status | Time
  - e.g., `Sarah | Approved | 12:44 hrs, Oct 2025`
- **Submit** button: moves expense from Draft → Waiting Approval

#### Screen 7 — Manager: Approvals To Review
- Table columns: Approval Subject | Request Owner | Category | Request Status | **Total Amount (in company's currency)** | Approve | Reject
- Amounts are always shown in the company's base currency (auto-converted)
- **Approve button**: moves expense to next approver in chain (or marks Approved if final step)
- **Reject button**: terminates the chain; employee is notified immediately
- Exchange rate snapshot is logged at the time of each approval action

---

### 1.4 OCR Feature (Additional)

- Employee uploads/scans a receipt image
- Backend OCR pipeline extracts:
  - **Amount** (e.g., ₹850, $42.50)
  - **Date** of transaction
  - **Vendor/Merchant Name** (e.g., "McDonald's", "Uber")
  - **Expense Type** (inferred: Food, Travel, etc.)
  - **Line items** (individual items from the receipt)
- Extracted data pre-fills the submission form — employee reviews and submits
- OCR is non-blocking: form remains editable if extraction fails

---

### 1.5 Currency Handling Rules

| Scenario | Behavior |
|----------|----------|
| Employee submits in USD, company is INR | Amount stored in USD + INR equivalent at submission time |
| Manager views the expense | Always displayed in INR (company's base currency) |
| Approval finalized | Exchange rate snapshot is stored permanently for audit |
| Company currency set | Derived from country selected at signup via restcountries API |

---

### 1.6 Approval Flow Logic

```
Expense Submitted
        │
        ▼
[Is Manager Approver = true?] ──Yes──► Step 1: Manager Reviews
        │                                        │
        No                              Approve ─┤─ Reject → Notify Employee (end)
        │                                        │
        ▼                                        ▼
Step 1: First Defined Approver         Step 2: Next Approver in Sequence
        │
        ▼ (after each step)
[Conditional Rule Check]
   ├── Percentage Rule met? ──► Auto-Approve (end)
   ├── Specific Approver rule met? ──► Auto-Approve (end)
   └── Neither? ──► Continue to next approver
        │
        ▼ (all approvers processed)
Final Approval / Rejection → Notify Employee
```

---

### 1.7 Notifications & Status Updates

- **Email notifications** on: expense submission, approval/rejection at each step, final outcome
- **In-app status** updates via polling (or WebSocket for real-time)
- **Audit trail** stored immutably per expense (approver, action, timestamp, exchange rate used)

---

### 1.8 External APIs

| API | Purpose | Endpoint |
|-----|---------|----------|
| REST Countries | Country + currency list for signup | `https://restcountries.com/v3.1/all?fields=name,currencies` |
| Exchange Rate API | Real-time currency conversion | `https://api.exchangerate-api.com/v4/latest/{BASE_CURRENCY}` |

---

## 2. Design Stack

The design targets a clean, professional **SaaS/dashboard aesthetic** — think Linear or Vercel. Dense but breathable, neutral palette with one teal accent for CTAs.

### 2.1 Frontend Framework & Tooling

| Tool | Version | Role |
|------|---------|------|
| **React** | 18.x | Core UI framework (component model, hooks, concurrent features) |
| **TypeScript** | 5.x | Type safety across all components and API contracts |
| **Vite** | 5.x | Lightning-fast dev server + build tool; HMR out of the box |

### 2.2 Styling

| Tool | Role |
|------|------|
| **Tailwind CSS v4** | Utility-first styling; all spacing, color, and typography via design tokens |
| **Shadcn/UI** | Pre-built accessible components (Table, Dialog, Form, Select, Badge, Dropdown) built on Radix UI primitives — zero runtime overhead, fully customizable |
| **Lucide React** | Consistent icon set matching Shadcn aesthetic |

> **Why Shadcn?** It is copy-paste component code (not an NPM dependency), so it is fully customizable — critical for a hackathon where speed + bespoke UI matter. Components are accessible (WCAG AA) out of the box via Radix.

### 2.3 State & Data Management

| Tool | Role |
|------|------|
| **TanStack Query v5** | Server state: caching, background refetch, optimistic updates for expense lists and approval queues |
| **Zustand** | Lightweight client state: auth token, current user context, active company currency |
| **React Hook Form + Zod** | Form management + runtime schema validation (expense submission, approval rule config) |

### 2.4 Routing & Animation

| Tool | Role |
|------|------|
| **React Router v6** | Client-side routing with role-based route guards (`/admin/*`, `/employee/*`, `/manager/*`) |
| **Framer Motion** | Page transitions, status pill animations, approval trail entry animations |

### 2.5 Data Visualization

| Tool | Role |
|------|------|
| **Recharts** | Expense breakdown by category, monthly trends, approval turnaround time charts |

---

### 2.6 Design Token Reference

```
Color Palette:   Neutral warm surfaces + Teal (#01696f) as primary CTA accent
Typography:      General Sans (body) + Satoshi (headings/display) via Fontshare
Spacing:         4px base grid
Border Radius:   Small (inputs/cards) → Full (status badge pills)
Density:         Balanced — data-dense tables with generous section padding
Dark Mode:       Full light/dark toggle via CSS custom properties + data-theme attribute
```

---

## 3. Tech Stack

### 3.1 Backend — FastAPI (Python)

FastAPI is an excellent choice: async-first, auto-generates OpenAPI docs, and pairs perfectly with SQLModel for type-safe DB access.

| Layer | Tool | Rationale |
|-------|------|-----------|
| **API Framework** | FastAPI 0.115+ | Async, auto OpenAPI/Swagger docs, OAuth2 + JWT built-in, Pydantic v2 validation |
| **ORM / Models** | SQLModel | SQLAlchemy + Pydantic in one — single class defines both DB model and API schema |
| **Database** | PostgreSQL 16 | Relational integrity for approval chains; JSON columns for dynamic rule config; ACID compliance for financial data |
| **DB Migrations** | Alembic | Schema versioning; auto-generates migration files from SQLModel models |
| **Auth** | JWT (python-jose) + OAuth2PasswordBearer | FastAPI's built-in OAuth2 flow; role claims embedded in JWT payload |
| **Password Hashing** | passlib (bcrypt) | Industry-standard password security |
| **File Storage** | Cloudinary / AWS S3 | Receipt image storage; pre-signed URLs for secure upload/download |
| **OCR Engine** | EasyOCR (Python) | GPU-optional, multi-language receipt OCR; runs as a background task |
| **Background Tasks** | FastAPI BackgroundTasks (hackathon) / Celery + Redis (scale) | Async OCR processing + email dispatch |
| **Email** | FastAPI-Mail + SendGrid / SMTP | New user password emails, approval step notifications |
| **Currency Cache** | Redis (1-hr TTL) | Cache exchangerate-api.com responses to avoid rate limits |
| **HTTP Client** | httpx | Async calls to external APIs (currency, countries) |

### 3.2 Database Schema (Key Entities)

```sql
Company         → id, name, country, default_currency
User            → id, company_id, name, email, hashed_password, role, manager_id
Expense         → id, company_id, employee_id, amount, currency, converted_amount,
                   base_currency, category, description, date, status, receipt_url, created_at
ApprovalRule    → id, company_id, category, manager_is_approver, min_approval_percentage,
                   specific_approver_id, rule_type (sequential/percentage/specific/hybrid)
ApprovalStep    → id, rule_id, approver_id, sequence_order, is_required
ApprovalRecord  → id, expense_id, approver_id, action, comment, timestamp, exchange_rate_snapshot
```

### 3.3 Full Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend Framework | React 18 + TypeScript + Vite |
| Styling | Tailwind CSS v4 + Shadcn/UI + Lucide React |
| Client State | Zustand |
| Server State | TanStack Query v5 |
| Forms | React Hook Form + Zod |
| Routing | React Router v6 |
| Animations | Framer Motion |
| Charts | Recharts |
| HTTP Client (FE) | Axios (JWT interceptors + 401 redirect) |
| Backend | FastAPI (Python 3.11+) |
| ORM | SQLModel + Alembic |
| Database | PostgreSQL 16 |
| Cache / Broker | Redis |
| Auth | JWT + OAuth2 (python-jose + passlib) |
| OCR | EasyOCR |
| File Storage | Cloudinary / AWS S3 |
| Email | FastAPI-Mail + SendGrid |
| Containerization | Docker + Docker Compose |

### 3.4 Project Structure

```
expense-management/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app init, CORS, routers
│   │   ├── core/
│   │   │   ├── config.py            # Settings via pydantic-settings
│   │   │   ├── security.py          # JWT + password hashing
│   │   │   └── database.py          # SQLModel engine + session
│   │   ├── models/                  # SQLModel DB models
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── auth.py              # /auth/signup, /auth/login
│   │   │   ├── users.py             # /users CRUD (admin only)
│   │   │   ├── expenses.py          # /expenses (submit, list, detail)
│   │   │   ├── approvals.py         # /approvals (queue, approve, reject)
│   │   │   ├── rules.py             # /approval-rules (admin CRUD)
│   │   │   └── ocr.py               # /ocr/extract (receipt → parsed fields)
│   │   └── services/
│   │       ├── currency.py          # Exchange rate fetch + Redis cache
│   │       ├── ocr_service.py       # EasyOCR pipeline
│   │       └── approval_engine.py   # Core approval chain logic
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/              # Shadcn + custom components
│   │   ├── pages/
│   │   │   ├── auth/                # Signup, Login
│   │   │   ├── admin/               # User mgmt, Approval rules
│   │   │   ├── employee/            # Expense list, Submission form
│   │   │   └── manager/             # Approvals review queue
│   │   ├── hooks/                   # TanStack Query hooks
│   │   ├── store/                   # Zustand stores (auth, company)
│   │   ├── lib/
│   │   │   ├── api.ts               # Axios instance + interceptors
│   │   │   └── utils.ts             # Currency formatting, date helpers
│   │   └── types/                   # TypeScript interfaces
│   ├── vite.config.ts
│   └── Dockerfile
└── docker-compose.yml
```

---

## 4. Thoughts on the FastAPI Choice

FastAPI is an **excellent** pick for this hackathon, and here is why it aligns perfectly:

- **Auto-generated OpenAPI docs** (`/docs` and `/redoc`) act as instant API documentation — the frontend team can consume APIs without any extra communication overhead
- **Pydantic v2 + SQLModel** means one class definition covers both DB schema and API validation, cutting boilerplate dramatically
- **Async by default** — currency API calls, OCR processing, and email dispatch all run non-blocking without threading complexity
- **Built-in OAuth2** support means JWT role-based auth is ~20 lines of code
- **Python's EasyOCR library** integrates naturally into the same codebase — no separate microservice needed for the OCR feature
- The `approval_engine.py` service (the core technical differentiator) gets full focus without wrestling with infrastructure

**One optimization for the hackathon demo**: OCR on receipts can take 2–5 seconds. Use FastAPI's `BackgroundTasks` so the form response is immediate, and poll a `/ocr/status/{task_id}` endpoint to hydrate the form once extraction completes. This makes the demo feel snappy even with real OCR running.
