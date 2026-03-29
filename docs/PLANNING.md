# PLANNING.md — Expense Reimbursement Management

## Project Overview

A multi-role, multi-currency expense reimbursement platform built for a hackathon. Companies sign up, configure approval workflows, and employees submit expense claims that route through structured, rule-based approval chains — with OCR receipt scanning and real-time currency conversion.

---

## Repo Name Suggestion

**`xpensa`** — short, memorable, professional. Suggests "expense" without being generic.
Alternative: `claimflow` (describes the approval chain), `reimbify` (reimbursement + simplify)

---

## Goals

- Multi-role auth (Admin / Manager / Employee) with JWT
- Company onboarding with auto-currency detection by country
- Configurable approval rules (sequential, percentage-based, specific-approver, hybrid)
- Expense submission in any currency with auto-conversion to company base currency
- OCR receipt scanning to auto-fill expense forms
- Full approval trail per expense
- Clean, production-grade UI (Shadcn + Tailwind)

## Non-Goals (for Hackathon Scope)

- Mobile native app
- Multi-company admin panel (each company is siloed)
- Real payment processing / bank integration
- Custom SMTP server (use SendGrid free tier)
- Fine-grained analytics dashboard (basic charts only)

---

## Tech Stack

### Frontend
| Layer | Tool |
|-------|------|
| Framework | React 18 + TypeScript |
| Build Tool | Vite 5 |
| Styling | Tailwind CSS v4 + Shadcn/UI |
| Icons | Lucide React |
| Server State | TanStack Query v5 |
| Client State | Zustand |
| Forms | React Hook Form + Zod |
| Routing | React Router v6 |
| Animations | Framer Motion |
| HTTP Client | Axios (with JWT interceptor) |
| Charts | Recharts |

### Backend
| Layer | Tool |
|-------|------|
| Framework | FastAPI 0.115+ (Python 3.11+) |
| ORM | SQLModel + Alembic |
| Database | Supabase PostgreSQL (free tier) |
| File Storage | Supabase Storage (free tier, 1GB) |
| Auth | JWT (python-jose) + OAuth2PasswordBearer + passlib (bcrypt) |
| OCR | EasyOCR (runs as BackgroundTask) |
| Currency Cache | In-memory cache (TTLCache from cachetools) — no Redis needed |
| HTTP Client | httpx (async, for currency + countries APIs) |
| Email | FastAPI-Mail + SendGrid free tier |
| Settings | pydantic-settings (reads from .env) |

### Why Supabase over Local Storage
Local storage on Render's free tier uses an **ephemeral filesystem** — files vanish on every redeploy or dyno restart. Supabase Storage is free (1GB), persistent, and provides a Python SDK (`supabase-py`). The Supabase PostgreSQL also replaces Render's expiring 90-day free DB with a more stable free tier.

### Why No Redis
For the hackathon, currency rates are cached in-memory using `cachetools.TTLCache` (1-hour TTL). This avoids spinning up Redis and works fine for a single-process Render deployment. If scaling is needed post-hackathon, swap to Redis.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        VERCEL                           │
│  React + TypeScript + Vite                              │
│  Tailwind CSS + Shadcn/UI                               │
│  Role-based routing (/admin, /employee, /manager)       │
└───────────────────┬─────────────────────────────────────┘
                    │ HTTPS (Axios + JWT Bearer)
┌───────────────────▼─────────────────────────────────────┐
│                        RENDER                           │
│  FastAPI (Python 3.11)                                  │
│  - /auth  - /users  - /expenses                         │
│  - /approvals  - /rules  - /ocr                         │
│  approval_engine.py (core chain logic)                  │
│  ocr_service.py (EasyOCR BackgroundTask)                │
│  currency.py (TTLCache + httpx)                         │
└─────────┬────────────────────┬───────────────────────────┘
          │                    │
┌─────────▼──────┐   ┌─────────▼──────────────────────────┐
│ Supabase       │   │ External APIs                       │
│ PostgreSQL DB  │   │ restcountries.com (country/currency)│
│ Supabase       │   │ exchangerate-api.com (FX rates)     │
│ Storage        │   │ SendGrid (email)                    │
│ (receipts)     │   └─────────────────────────────────────┘
└────────────────┘
```

---

## Deployment Strategy

### Frontend → Vercel (Zero-config)
- Connect GitHub repo → Vercel auto-detects Vite
- Set `VITE_API_BASE_URL=https://your-render-app.onrender.com` in Vercel env vars
- Build command: `npm run build` | Output: `dist/`
- No Docker needed — Vercel handles static asset deployment natively

### Backend → Render
Two deployment options (choose one):

**Option A — Native Python (Recommended for simplicity)**
```
# render.yaml
services:
  - type: web
    name: xpensa-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        value: <supabase_connection_string>
      - key: SUPABASE_URL
        value: <your_supabase_url>
      - key: SUPABASE_KEY
        value: <your_supabase_anon_key>
      - key: SECRET_KEY
        generateValue: true
      - key: SENDGRID_API_KEY
        value: <your_key>
```

**Option B — Docker (Same image as local)**
- Add `Dockerfile` to `backend/`
- Render detects Dockerfile automatically
- Note: EasyOCR model downloads (~200MB) add to cold start time — pre-download in Dockerfile

### Docker Compose (Local Development Only)
```yaml
# docker-compose.yml — LOCAL ONLY, not used in production
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    env_file: ./backend/.env
    volumes: ["./backend:/app"]
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    volumes: ["./frontend:/app"]
    command: npm run dev -- --host
```
> Note: In local dev, point `VITE_API_BASE_URL=http://localhost:8000`. In production (Vercel), point to the Render URL.

---

## Environment Variables

### Backend (.env)
```
DATABASE_URL=postgresql+asyncpg://...  # Supabase connection string
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
SECRET_KEY=your-jwt-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
SENDGRID_API_KEY=SG.xxx
FROM_EMAIL=noreply@xpensa.app
FRONTEND_URL=https://your-app.vercel.app
EXCHANGE_RATE_BASE_URL=https://api.exchangerate-api.com/v4/latest
```

### Frontend (.env)
```
VITE_API_BASE_URL=http://localhost:8000       # local
# VITE_API_BASE_URL=https://xpensa.onrender.com  # production (set in Vercel dashboard)
```

---

## Free Tier Limits

| Service | Free Tier Limits | Risk |
|---------|-----------------|------|
| Render (Web Service) | 512MB RAM, spins down after 15min inactivity | Cold start ~30s. Mitigate: add a `/health` ping |
| Render (PostgreSQL) | Expires after 90 days ⚠️ | **Use Supabase DB instead** |
| Supabase | 500MB DB, 1GB storage, 50MB file uploads | Plenty for hackathon |
| Vercel | 100GB bandwidth, unlimited deploys | No risk |
| exchangerate-api.com | 1,500 requests/month free | Cache aggressively (1hr TTL) |
| SendGrid | 100 emails/day free | Fine for demo |

---

## Key Design Decisions

1. **Supabase as DB + Storage**: Single free-tier service replaces both Render's ephemeral DB and a paid S3. The `supabase-py` SDK handles storage; SQLModel still connects directly to the Postgres connection string.

2. **No Redis**: `cachetools.TTLCache` for in-process currency rate caching. Acceptable for single-process Render deployment. No extra service to manage.

3. **EasyOCR as BackgroundTask**: Receipt OCR returns a `task_id` immediately; frontend polls `/ocr/status/{task_id}`. Keeps the API snappy during demo.

4. **SQLModel over raw SQLAlchemy**: One class = DB model + Pydantic schema. Halves boilerplate, critical for hackathon speed.

5. **Role in JWT**: User role (`admin`/`manager`/`employee`) + `company_id` are embedded in JWT claims. No extra DB call per request for auth checks.

6. **Approval Engine as a service**: `approval_engine.py` is isolated from routers. Takes `(expense_id, approver_id, action)` and handles all chain logic, conditional rules, and notifications. Testable in isolation.
