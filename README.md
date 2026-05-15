# Nicogenoud — Investment Dashboard (IOL)

Personal investment dashboard. Connects to InvertirOnline (IOL) and tracks the
2026 portfolio: holdings, operations, P&L (realized / unrealized), portfolio
value evolution and asset-class distribution.

## Stack

- **Backend**: FastAPI + SQLAlchemy 2 + SQLite (WAL) + Alembic + APScheduler
- **Frontend**: Vite + React + Tailwind (dark by default) + Recharts + React Query
- **Auth**: single-user JWT (HS256) + bcrypt
- **IOL secrets**: encrypted at rest with Fernet
- **Deploy**: Docker Compose on CasaOS, Cloudflare Tunnel

## Layout

```
backend/   FastAPI app
frontend/  Vite + React SPA
data/      bind-mounted SQLite (rsync-friendly)
```

## Setup

```bash
cp backend/.env.example backend/.env
# fill JWT_SECRET (openssl rand -hex 32)
# fill FERNET_KEY  (python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
# fill ADMIN_PASSWORD
docker compose up -d --build
```

Open http://localhost:8080. Default admin user comes from `ADMIN_USERNAME`.

## Backups

`data/app.db` is a bind-mounted SQLite file — `rsync` it directly.
