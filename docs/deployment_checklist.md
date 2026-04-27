# Deployment Checklist

## GitHub

1. Confirm tests and build pass.
2. Confirm `.env`, local databases, virtual environments, and build artifacts are ignored.
3. Commit the repository.
4. Push to GitHub.

## Render PostgreSQL

1. Create a new Render PostgreSQL database.
2. Copy the internal database URL.
3. Convert it to SQLAlchemy psycopg format:

```text
postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
```

## Render API Service

1. Create a Render Web Service from the GitHub repository.
2. Choose Docker deployment.
3. Set Dockerfile path:

```text
apps/api/Dockerfile
```

4. Set environment variables:

```env
DATABASE_URL=postgresql+psycopg://...
LLM_PROVIDER=mock
ENVIRONMENT=production
AUTO_CREATE_TABLES=false
CORS_ORIGINS=https://your-vercel-app.vercel.app
```

5. Deploy.
6. Confirm logs show `alembic upgrade head`.
7. Test:

```text
https://your-render-api.onrender.com/health
https://your-render-api.onrender.com/health/db
```

## Vercel Frontend

1. Import the GitHub repository.
2. Set root directory:

```text
apps/web
```

3. Set environment variable:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-render-api.onrender.com
```

4. Deploy.
5. Copy the Vercel production URL.
6. Update Render `CORS_ORIGINS` with the Vercel URL.
7. Redeploy or restart Render API.

## Production Smoke Test

1. Open the Vercel dashboard.
2. Submit `AV fistula` and verify a Ready or Needs Review result.
3. Submit `Bundled chole risk` and verify a High Risk result.
4. Confirm Recent Analyses updates.
5. Confirm Copy JSON and Download JSON work.
