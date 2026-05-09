# AI Clinical Ops Agent

AI Clinical Ops Agent is a synthetic-demo healthcare revenue cycle tool that turns a surgical operative note into likely CPT billing-code candidates, documentation and billing risk flags, reimbursement estimates, and a plain-English claim readiness report. It is built to feel like a real healthcare operations dashboard rather than a chatbot: users choose or paste a synthetic note, run billing analysis, review what needs attention, and export a structured report for operational review.

## Why It Matters

Surgical coding and revenue-cycle workflows depend on precise operative-note interpretation, modifier validation, payer-style audit checks, and reimbursement estimation. Missing laterality, unsupported codes, low-confidence documentation, or bundled-code conflicts can delay claims or create compliance risk. This project demonstrates how an AI-assisted workflow can support billing and operations teams while keeping outputs structured, auditable, and testable.

## Who It Is For

This demo is intended for healthcare operations, revenue cycle, billing, and product/engineering audiences evaluating how AI agents can assist with clinical documentation review. It uses only synthetic notes so the workflow can be shown publicly without exposing protected health information.

## What The Demo Proves

The app proves that a multi-agent system can process a note end to end without relying on a generic chat interface: procedure extraction, CPT candidate generation, RAG-backed evidence retrieval, billing audit checks, reimbursement estimation, claim readiness scoring, analysis history, and JSON export all work locally with deterministic mock logic before real LLM APIs are added.

## Key Features

- Guided synthetic operative-note workflow with a persistent no-PHI warning.
- Multi-agent backend pipeline for procedure extraction, CPT candidate generation, billing audit, reimbursement estimation, and report generation.
- Local keyword RAG over coding guideline snippets, with retrieved evidence shown in the dashboard.
- Deterministic claim readiness score from `0-100` with `Ready`, `Needs Review`, and `High Risk` statuses.
- Analysis history and structured JSON export endpoints.
- Synthetic dataset evaluation with CPT match, audit finding, claim readiness, and confidence metrics.
- Next.js dashboard with step-by-step guidance, plain-English claim summary, CPT table, audit table, expandable evidence, recent analyses, and export controls.
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

## System Evaluation

The dashboard includes a collapsible `View system evaluation` section that runs the synthetic demo dataset against `data/evaluation/gold_standard.json`.

Metrics shown:

- **CPT match accuracy:** whether the primary generated CPT matches the expected demo CPT.
- **Audit finding accuracy:** whether expected audit categories such as missing laterality or bundling conflict are detected.
- **Claim readiness accuracy:** whether the system assigns the expected `Ready`, `Needs Review`, or `High Risk` status.
- **Average confidence:** average confidence of the primary CPT candidate across synthetic notes.

This evaluation is intentionally limited. It measures consistency on known synthetic cases only; it does not prove clinical correctness, payer-specific compliance, or performance on real patient records.

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
- System evaluation dashboard

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
