# Deployment Guide

## Architecture

```text
Developer machine
  |
  +-- apps/web: Next.js dashboard
  +-- apps/api: FastAPI API
  +-- data/: synthetic reference docs and fee schedule
  |
  v
Local Docker Compose
  |
  +-- web container -> http://localhost:3000
  +-- api container -> http://localhost:8000
  +-- postgres container -> localhost:5432

Production
  |
  +-- Vercel: Next.js frontend
  +-- Render Web Service: FastAPI Docker container
  +-- Render PostgreSQL: managed database
```

## Local Dev Flow

```text
Edit code
  |
  +-- backend: pytest
  +-- frontend: npm run build
  |
  v
docker compose up --build
  |
  v
Paste synthetic note in dashboard
```

For API-only work, SQLite is acceptable:

```powershell
cd apps/api
$env:DATABASE_URL="sqlite:///./clinical_ops.db"
$env:LLM_PROVIDER="mock"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## Production Deployment Flow

```text
Push to GitHub
  |
  +-- Render builds apps/api/Dockerfile
  |     |
  |     +-- alembic upgrade head
  |     +-- uvicorn app.main:app --host 0.0.0.0 --port $PORT
  |
  +-- Vercel builds apps/web
        |
        +-- browser calls NEXT_PUBLIC_API_BASE_URL
```

Use production mode for the FastAPI container. Do not deploy `uvicorn --reload`; reload mode is for local development and watches files with extra processes.

## Environment Variables

| Variable | App | Required | Example | Notes |
| --- | --- | --- | --- | --- |
| `DATABASE_URL` | API | Yes | `postgresql+psycopg://user:pass@host:5432/db` | Managed Postgres connection string. |
| `LLM_PROVIDER` | API | Yes | `mock` | Keep `mock` for no-key MVP deployment. |
| `CORS_ORIGINS` | API | Yes | `https://app.vercel.app,http://localhost:3000` | Comma-separated allowed frontend origins. |
| `ENVIRONMENT` | API | Yes | `production` | Use `local`, `test`, or `production`. |
| `AUTO_CREATE_TABLES` | API | Recommended | `false` | Use Alembic in production. |
| `MAX_REQUEST_BYTES` | API | Optional | `262144` | Request body limit. |
| `NEXT_PUBLIC_API_BASE_URL` | Web | Yes | `https://api.onrender.com` | Must be prefixed with `NEXT_PUBLIC_` for browser access in Vercel. |

## Render Backend

1. Create a Render PostgreSQL database.
2. Create a Render Web Service from GitHub.
3. Choose Docker.
4. Set Dockerfile path:

```text
apps/api/Dockerfile
```

5. Set API environment variables:

```env
DATABASE_URL=postgresql+psycopg://...
LLM_PROVIDER=mock
ENVIRONMENT=production
AUTO_CREATE_TABLES=false
CORS_ORIGINS=https://your-vercel-app.vercel.app
```

6. Deploy and check:

```text
https://your-render-service.onrender.com/health
https://your-render-service.onrender.com/health/db
```

## Vercel Frontend

1. Import the GitHub repository.
2. Set root directory to `apps/web`.
3. Set:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-render-service.onrender.com
```

4. Deploy.
5. Add the Vercel domain to Render `CORS_ORIGINS`.

## Common Deployment Issues

- **CORS error in browser:** `CORS_ORIGINS` does not include the exact Vercel origin.
- **Database health degraded:** Render API service cannot reach Postgres, or `DATABASE_URL` is not in SQLAlchemy/psycopg format.
- **Tables missing:** migrations did not run; check Render logs for `alembic upgrade head`.
- **Frontend calls localhost in production:** `NEXT_PUBLIC_API_BASE_URL` is missing in Vercel or was added after build without redeploying.
- **Slow first API request:** free-tier services may cold start.
- **Validation error on note submit:** note is under 50 characters, blank, or over 20,000 characters.
