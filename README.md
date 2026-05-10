# AI Clinical Ops Agent

AI Clinical Ops Agent is a full-stack healthcare revenue cycle demo that analyzes synthetic operative notes, suggests CPT-style billing codes, flags documentation risks, and generates claim readiness reports.

This is not a chatbot wrapper. The goal was to build a small but realistic workflow tool with a frontend, backend, database, migrations, tests, synthetic data, and deployment path.

## Why I Built This

I built this project because I am interested in the intersection of healthcare operations and backend systems. A lot of healthcare software is not just about showing information; it is about helping people make operational decisions from messy documentation.

Operative notes are a good example. If a note does not clearly document something like laterality, procedure intent, or whether two services should be billed together, that can affect coding, reimbursement, and claim review. I wanted to model that kind of workflow in a project that was more structured than a generic AI chat demo.

The project uses synthetic notes only. There is no patient data in this repository, and the app is not intended to be medical or billing advice. The point is to demonstrate how an AI-assisted operations system could be designed with deterministic outputs, audit checks, evidence snippets, revision tracking, and evaluation metrics.

## What The App Does

The app lets a user:

- choose or paste a synthetic operative note
- run a billing analysis
- identify likely CPT-style code candidates
- detect documentation or billing risks
- estimate reimbursement from a local fake fee schedule
- generate a claim readiness status
- see suggested documentation improvements
- revise the note and re-run the analysis
- compare the original and revised results
- review synthetic evaluation metrics across the demo dataset

The revision workflow is an important part of the project. If the system flags missing laterality or ambiguous documentation, the user can edit the note, reanalyze it, and see whether the claim readiness score improved.

## Example Workflow

A user selects a synthetic open inguinal hernia repair note where the note does not say whether the repair was on the left or right side.

The app flags:

- `Missing laterality`
- claim status: `Needs Review`
- suggested improvement: document whether the procedure was performed on the left or right side

The user updates the note to specify `left open inguinal hernia repair`, then reanalyzes it.

The app shows:

- the missing laterality issue was resolved
- the claim readiness score improved
- the CPT modifier is no longer ambiguous
- the revision history records the before/after result

## System Architecture

The project is organized as a monorepo:

```text
apps/
  api/    FastAPI backend
  web/    Next.js frontend

data/
  synthetic_notes/
  reference_docs/
  fee_schedule/
  evaluation/

docs/
```

### Frontend

The frontend is a Next.js app using TypeScript, React, the App Router, and Tailwind CSS. It is built as a workflow UI instead of a chat interface. The main dashboard includes:

- synthetic note input
- example note selector
- billing analysis stage
- claim readiness summary
- CPT candidates
- audit findings
- documentation improvement suggestions
- before/after revision impact
- recent analyses
- evaluation dashboard

### Backend

The backend is a FastAPI app with a modular analysis pipeline:

```text
Operative note
  -> procedure extractor
  -> CPT coder
  -> billing auditor
  -> reimbursement estimator
  -> report generator
```

Each step passes structured Pydantic models to the next step. The logic is intentionally deterministic where possible so it can be tested. The system uses lightweight keyword retrieval over local reference docs instead of pretending to be a fully autonomous medical AI system.

### Database

PostgreSQL is used for deployed environments, with SQLAlchemy models and Alembic migrations. Local development can also run against SQLite for quick testing.

Stored entities include:

- notes
- analyses
- extracted procedures
- CPT candidates
- audit findings
- reimbursement estimates

### Infrastructure

The backend is Dockerized and can run locally with Docker Compose or deploy to Render. The frontend is deployed separately on Vercel. Database migrations are handled with Alembic.

## Features

- CPT-style candidate generation from synthetic operative notes
- billing and documentation risk detection
- missing modifier and missing laterality checks
- bundled-code conflict detection
- claim readiness scoring
- recommended next action for each result
- evidence snippets from local reference docs
- documentation improvement suggestions
- note revision and reanalysis workflow
- before/after comparison for revised notes
- resolved issue tracking
- revision history in the UI
- recent analysis history
- JSON export support in the backend
- synthetic dataset evaluation dashboard
- Dockerized backend
- Alembic migrations
- Pytest coverage for pipeline, API, evaluation, and revision logic

## Evaluation

The app includes a small synthetic benchmark under `data/evaluation/gold_standard.json`.

Current evaluation results:

- 9 synthetic cases evaluated
- 100% CPT match accuracy
- 100% audit finding accuracy
- 100% claim readiness accuracy
- 90.6% average confidence

These numbers are only for the synthetic benchmark cases included in the repo. They should not be interpreted as real-world billing accuracy. The evaluation is useful because it checks that the deterministic pipeline produces the expected outputs for known demo cases and catches regressions when the rules change.

## Deployment

The deployed version uses:

- Vercel for the Next.js frontend
- Render for the FastAPI backend
- Render PostgreSQL for the database
- Docker for the backend service

Important environment variables:

```env
DATABASE_URL=postgresql+psycopg://...
LLM_PROVIDER=mock
ENVIRONMENT=production
CORS_ORIGINS=https://your-vercel-app.vercel.app
NEXT_PUBLIC_API_BASE_URL=https://your-render-api.onrender.com
```

The backend should run in production mode, not with Uvicorn reload enabled.

More deployment notes are in:

- `docs/deployment.md`
- `docs/deployment_checklist.md`

## Local Setup

### Backend

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

### Frontend

```powershell
cd apps/web
npm install
$env:NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
npm run dev
```

Open:

- frontend: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- health check: `http://localhost:8000/health`

### Tests

```powershell
cd apps/api
python -m pytest -q
```

```powershell
cd apps/web
npm run build
```

## Screenshots

### Main Dashboard

![Main dashboard screenshot placeholder](docs/screenshots/main-dashboard.png)

### Needs Review Result

![Needs Review screenshot placeholder](docs/screenshots/needs-review.png)

### High Risk Result

![High Risk screenshot placeholder](docs/screenshots/high-risk.png)

### Revision Workflow

![Revision workflow screenshot placeholder](docs/screenshots/revision-workflow.png)

### Evaluation Dashboard

![Evaluation dashboard screenshot placeholder](docs/screenshots/evaluation-dashboard.png)

## Limitations

This project has important limitations:

- It uses synthetic operative notes only.
- It is not production medical software.
- It is not billing advice and should not be used for real claims.
- CPT logic is simplified and only covers a small demo code set.
- Many decisions are deterministic and rule-based by design.
- The retrieval system is keyword-based, not embedding-based.
- The fee schedule is fake and only exists for demo purposes.
- The evaluation set is small and synthetic.
- The OpenAI provider is only a placeholder; the mock provider is the default.

I kept these limitations explicit because the goal is to show system design and workflow thinking, not to claim real clinical or billing correctness.

## Future Improvements

Some realistic next steps:

- improve retrieval with embeddings and better document chunking
- expand the synthetic gold-standard evaluation set
- add note section parsing for indication, procedure, findings, and conclusion
- support more CPT families and modifier rules
- make reimbursement logic more realistic
- add reviewer comments and manual override workflow
- expand the provider abstraction beyond the mock provider
- add frontend component tests for revision workflows
- add role-based views for coder, auditor, and operations reviewer
