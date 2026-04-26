# AI Clinical Ops Agent

End-to-end clinical operations demo system for synthetic surgical operative notes. The app extracts documented procedures, assigns CPT-style candidate codes, audits coding risks, estimates reimbursement from a local fee schedule, and renders a structured dashboard report.

This is designed as a production-style portfolio project, not a chatbot. The AI layer is modular, deterministic by default, and runnable locally without API keys.

## Why It Matters

Surgical coding and revenue-cycle workflows are expensive, detail-heavy, and error-prone. This project demonstrates how agent-style components can separate extraction, coding, auditing, and reporting while preserving testable outputs and human-review checkpoints.

## Architecture

```text
apps/web (Next.js dashboard)
        |
        v
apps/api (FastAPI)
        |
        +-> ProcedureExtractor agent
        +-> CPTCoder agent + keyword RAG
        +-> BillingAuditor agent + keyword RAG
        +-> ReimbursementEstimator agent
        +-> ReportGenerator agent
        |
        v
PostgreSQL via SQLAlchemy
```

## Repository Structure

```text
apps/
  api/        FastAPI backend, SQLAlchemy models, deterministic agent pipeline
  web/        Next.js App Router dashboard
packages/
  shared/     Placeholder for cross-app contracts
data/
  synthetic_notes/
  reference_docs/
  fee_schedule/
docs/
```

## No PHI

This repository must not use real patient data. All included notes are synthetic examples for local development and demos.

## Run Locally With Docker

1. Copy environment defaults:

```powershell
Copy-Item .env.example .env
```

2. Build and start the stack:

```powershell
docker compose up --build
```

3. Open the apps:

- Web dashboard: http://localhost:3000
- API health: http://localhost:8000/health
- API docs: http://localhost:8000/docs

The API creates tables automatically on startup for this first scaffold. Future production hardening should replace that with Alembic migrations.

## Run Without Docker

Start PostgreSQL locally and set `DATABASE_URL` to a reachable database, or use SQLite for quick API-only development:

```powershell
$env:DATABASE_URL="sqlite:///./clinical_ops.db"
cd apps/api
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```powershell
cd apps/web
npm install
npm run dev
```

## Example Workflow

1. Open one of the files in `data/synthetic_notes`.
2. Paste it into the dashboard textarea.
3. Submit the note.
4. Review extracted procedures, CPT candidates, audit findings, estimated reimbursement, and the generated claim-readiness report.

## Tests

```powershell
cd apps/api
pytest
```

## Resume Bullet Examples

- Built a multi-agent clinical revenue-cycle pipeline using FastAPI, SQLAlchemy, PostgreSQL, and deterministic mock AI providers.
- Implemented CPT-style coding, billing audit checks, local keyword RAG, and reimbursement estimation over synthetic surgical notes.
- Delivered a full-stack Next.js dashboard with structured analysis results and local Docker Compose deployment.
