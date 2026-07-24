# Installation Guide

## Option A — Docker (recommended)

Requirements: Docker Engine + Docker Compose plugin.

```bash
git clone <this-repo>
cd converter
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/api/docs

Data persists in the `backend_storage` Docker volume (SQLite DB + uploaded
configs + generated outputs). To reset state:

```bash
docker compose down -v
```

## Option B — Local (no Docker)

Requirements: Python 3.12, Node.js 20+.

### Backend

```bash
cd backend
python3.12 -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:3000. The Vite dev server proxies `/api/*` calls to
`http://localhost:8000` automatically (see `frontend/vite.config.js`).

## Environment variables (backend)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./storage/converter.db` | SQLAlchemy connection string |
| `MAX_UPLOAD_MB` | `25` | Upload size limit |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed origins |

## Verifying the install

```bash
curl http://localhost:8000/api/health
# {"status":"ok"}

curl http://localhost:8000/api/vendors
# [] until a vendor parser is registered (Phase 2+)
```
