# xpensa 💸

> A multi-role, multi-currency expense reimbursement platform with configurable approval workflows and OCR receipt scanning.

Built for a hackathon. Production-deployed on **Render** (backend) + **Vercel** (frontend).

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + Shadcn/UI |
| Backend | FastAPI (Python 3.11+) |
| ORM | SQLModel + Alembic |
| Database | Supabase (PostgreSQL) |
| File Storage | Supabase Storage |
| Auth | JWT (python-jose) + bcrypt |
| OCR | EasyOCR |

---

## User Roles

| Role | What they can do |
|------|-----------------|
| **Admin** | Create company on signup, manage users, configure approval rules |
| **Manager** | Approve or reject expenses assigned to them |
| **Employee** | Submit expense claims, track approval status |

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker + Docker Compose *(optional, for containerized local dev)*

### Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Copy and fill in your environment variables
cp .env.example .env

# Run database migrations
alembic upgrade head

# Start the dev server
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### Frontend (React + Vite)

```bash
cd frontend
npm install

# Copy and fill in your environment variables
cp .env.example .env

# Start the dev server
npm run dev
```

App available at: http://localhost:5173

### Docker (Full Stack — Local Only)

```bash
# From project root
docker-compose up --build
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase anon/service key |
| `SECRET_KEY` | JWT secret (min 32 chars) |
| `ALGORITHM` | JWT algorithm (use `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token TTL (default: 60) |
| `SENDGRID_API_KEY` | SendGrid API key for emails |
| `FROM_EMAIL` | Sender email address |
| `FRONTEND_URL` | Frontend URL for CORS |

### Frontend (`frontend/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend API URL |

---

## Deployment

- **Backend** → [Render](https://render.com) — see `render.yaml`
- **Frontend** → [Vercel](https://vercel.com) — connect GitHub repo, set `VITE_API_BASE_URL`

---

## Project Structure

```
xpensa/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── core/
│   │   │   ├── config.py       # Settings (pydantic-settings)
│   │   │   ├── database.py     # SQLModel engine + session
│   │   │   └── security.py     # JWT + password hashing
│   │   ├── models/             # SQLModel DB models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── routers/            # API route handlers
│   │   └── services/           # Business logic (approval engine, OCR, currency)
│   ├── alembic/                # Database migrations
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/         # Reusable UI components
│   │   ├── pages/              # Route-level page components
│   │   ├── hooks/              # TanStack Query hooks
│   │   ├── store/              # Zustand state stores
│   │   ├── lib/                # Axios instance, utilities
│   │   └── types/              # TypeScript interfaces
│   ├── .env.example
│   └── Dockerfile
├── docker-compose.yml
├── render.yaml
├── .gitignore
└── README.md
```