# AI Clinical Ops Agent

AI Clinical Ops Agent is a full-stack healthcare operations platform that turns synthetic surgical operative notes into structured procedure extraction, CPT-style coding candidates, billing audit findings, reimbursement estimates, RAG-backed evidence, claim readiness scoring, and downloadable JSON reports. It is designed as a resume-grade systems project: modular, testable, locally runnable without API keys, and deployment-ready with Docker, FastAPI, Next.js, PostgreSQL, SQLAlchemy, and Alembic.

## Problem Statement

Surgical coding and revenue-cycle workflows depend on precise operative-note interpretation, modifier validation, payer-style audit checks, and reimbursement estimation. Manual review is expensive and error-prone, while naive chatbot workflows are hard to test. This project models a practical AI-assisted coding workflow with deterministic mock agents first, so the system can be validated locally before plugging in real LLM providers.

## Key Features

- Synthetic operative-note intake with strict no-PHI workflow.
- Multi-agent backend pipeline for procedure extraction, CPT candidate generation, billing audit, reimbursement estimation, and report generation.
- Local keyword RAG over coding guideline snippets, with retrieved evidence shown in the dashboard.
- Deterministic claim readiness score from `0-100` with `Ready`, `Needs Review`, and `High Risk` statuses.
- Analysis history and structured JSON export endpoints.
- Next.js dashboard with example note selector, CPT table, audit table, evidence panel, recent analyses, and export controls.
- Production-ready backend foundations: Alembic migrations, health checks, integration tests, Docker deployment, and provider abstraction.

## Architecture

```mermaid
flowchart LR
    A["Frontend Dashboard<br/>Next.js"] --> B["FastAPI API"]
    B --> C["Multi-Agent Pipeline"]
    C --> D["Procedure Extractor"]
    C --> E["CPT Coder"]
    C --> F["Billing Auditor"]
    C --> G["Reimbursement Estimator"]
    C --> H["Report Generator"]
    E --> I["RAG Retriever<br/>Reference Docs"]
    F --> I
    B --> J["PostgreSQL<br/>SQLAlchemy + Alembic"]
    H --> K["JSON Report / Export"]
```

Plain text architecture is also available in [docs/architecture.md](docs/architecture.md).

## Tech Stack

- **Frontend:** Next.js, TypeScript, App Router, Tailwind CSS
- **Backend:** FastAPI, Python, Pydantic
- **Database:** PostgreSQL, SQLAlchemy, Alembic
- **AI Layer:** Mock provider by default, OpenAI provider stub for future integration
- **RAG:** Local keyword retrieval over Markdown reference docs
- **Infra:** Docker Compose, Dockerfile deployment path for Render
- **Testing:** Pytest, FastAPI TestClient

## Local Setup

Backend:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL="sqlite:///./clinical_ops.db"
$env:ENVIRONMENT="local"
$env:LLM_PROVIDER="mock"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd apps/web
npm install
$env:NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
npm run dev
```

Open:

- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- DB health: http://localhost:8000/health/db

## Docker Setup

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The API container runs `alembic upgrade head` before starting Uvicorn.

## Deployment Guide

Recommended deployment:

```text
Vercel frontend
    -> Render FastAPI Docker service
        -> Render PostgreSQL
```

Required backend environment variables:

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
LLM_PROVIDER=mock
ENVIRONMENT=production
AUTO_CREATE_TABLES=false
CORS_ORIGINS=https://your-vercel-app.vercel.app
```

Required frontend environment variable:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-render-api.onrender.com
```

Detailed deployment steps are in [docs/deployment.md](docs/deployment.md) and [docs/deployment_checklist.md](docs/deployment_checklist.md).

## Synthetic Data And No PHI

This repository is for synthetic demo data only. Do not enter real patient information. The sample notes in `data/synthetic_notes` are fabricated for testing and portfolio demonstrations.

## Example Output

The API returns structured output with:

- Note metadata
- Extracted procedures
- CPT candidates with modifiers, confidence, rationale, and evidence snippets
- Audit findings with severity, category, recommendation, and evidence
- Reimbursement estimates from a fake local fee schedule
- Claim readiness score and explanation
- Final report object for JSON export

See [docs/sample_analysis_output.json](docs/sample_analysis_output.json).

## Demo Screenshots

Placeholder screenshots to capture after local run or deployment:

- Empty dashboard
- Example note selected
- Ready claim result
- High Risk claim result
- CPT evidence table
- Audit warning section
- Recent analyses panel
- JSON export section

See [docs/screenshot_checklist.md](docs/screenshot_checklist.md).

## Useful Commands

```powershell
make test-backend
make run-backend
make run-frontend
make build-frontend
make migrate
```

If `make` is unavailable on Windows, run the commands listed in the `Makefile` directly.

## Resume Bullets

- Built a full-stack AI clinical operations platform using FastAPI, Next.js, PostgreSQL, and Docker to process synthetic operative notes into structured CPT coding and reimbursement reports.
- Designed a modular multi-agent pipeline for procedure extraction, CPT code generation, billing audit, RAG-backed evidence retrieval, and claim readiness scoring.
- Implemented production-ready backend infrastructure with Alembic migrations, integration tests, health checks, Docker deployment, and mock/LLM provider abstraction.
