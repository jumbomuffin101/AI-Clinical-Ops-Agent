# AI Clinical Ops Agent

AI Clinical Ops Agent is a full-stack healthcare operations project for reviewing operative notes before billing review. It identifies likely procedures, flags documentation risks, suggests coder confirmation steps, and keeps a clear separation between deterministic rules and optional AI-assisted interpretation.

The app is built for de-identified or synthetic notes only. It is not medical software and it is not billing advice. Human review is required before any billing decision.

## Why I Built This

I wanted to build something closer to a real healthcare workflow than a chatbot. Operative notes are messy, and small documentation gaps like missing laterality, unclear procedure intent, or bundled services can affect billing review. This project models that operational problem with a proper frontend, backend, database, migrations, tests, safety checks, and deployment path.

## What It Does

- Accepts a de-identified or synthetic operative note
- Parses the note into operative sections when possible
- Identifies likely procedures and anatomy
- Flags documentation and billing-review risks
- Suggests practical fixes for the note
- Shows a plain-English review summary
- Supports optional AI-assisted interpretation for vague or unsupported notes
- Keeps detailed metadata, evaluation, recent reviews, and revision history behind a details panel

## Architecture

```text
Next.js review UI
  -> FastAPI API
  -> structured note parser
  -> procedure extraction
  -> CPT-style candidate rules
  -> billing risk auditor
  -> optional Groq AI interpretation
  -> PostgreSQL / SQLAlchemy
  -> review report
```

The deterministic pipeline runs first. AI assistance is only used when the rules need help interpreting free text, such as an unsupported or ambiguous procedure. AI output is validated with Pydantic and does not override deterministic safety checks.

## Tech Stack

- Frontend: Next.js, TypeScript, Tailwind CSS
- Backend: FastAPI, Python, Pydantic
- Database: PostgreSQL, SQLAlchemy
- Migrations: Alembic
- AI provider: Groq optional, mock provider by default
- Retrieval: local keyword search over reference docs
- Infra: Docker, Render, Vercel
- Tests: Pytest

## Safety

This environment is for de-identified or synthetic notes only.

The app blocks likely identifiers before analysis, including MRNs, DOBs, SSNs, phone numbers, email addresses, names, and simple address patterns. The frontend disables review when identifiers are detected, and the backend rejects the request before saving or processing the note.

## Hybrid AI And Rules Workflow

Standard review handles known examples and confident deterministic cases. AI-assisted review is used only when additional note understanding is useful. The AI layer can help summarize procedure family, operative intent, documentation gaps, and clarification questions.

The rules layer remains responsible for:

- supported CPT-style mappings
- missing laterality checks
- bundled-code warnings
- unsupported-code handling
- review status
- reimbursement estimate from the local schedule

If AI assistance fails, the app still completes a standard review.

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

- Web app: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Groq Setup

Groq is optional. Local development works without an API key.

```env
LLM_PROVIDER=groq
GROQ_ENABLED=true
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

Default local mode:

```env
LLM_PROVIDER=mock
```

## Deployment

The deployed setup uses:

- Vercel for the Next.js frontend
- Render for the FastAPI backend
- Render PostgreSQL for the database
- Docker for the backend service

Required environment variables:

```env
DATABASE_URL=postgresql+psycopg://...
ENVIRONMENT=production
CORS_ORIGINS=https://your-vercel-app.vercel.app
LLM_PROVIDER=groq
GROQ_ENABLED=true
GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.3-70b-versatile
NEXT_PUBLIC_API_BASE_URL=https://your-render-api.onrender.com
```

More deployment notes:

- `docs/deployment.md`
- `docs/deployment_checklist.md`

## Tests

```powershell
cd apps/api
python -m pytest -q
```

```powershell
cd apps/web
npm run build
```

## Screenshots

### Main Review Workflow

![Main review workflow](docs/screenshots/main-dashboard.png)

### Ready Result

![Ready result](docs/screenshots/ready-result.png)

### Needs Review Result

![Needs Review result](docs/screenshots/needs-review.png)

### High Risk Result

![High Risk result](docs/screenshots/high-risk.png)

### PHI Blocked State

![PHI blocked state](docs/screenshots/phi-blocked.png)

### Detailed Review Panel

![Detailed review panel](docs/screenshots/detailed-review.png)

## Limitations

- Uses synthetic or de-identified notes only
- Not medical software
- Not billing advice
- CPT-style logic is simplified
- Retrieval is keyword-based, not embedding-based
- The evaluation set is small and synthetic
- Reimbursement estimates use a local sample fee schedule
- Real compliance deployment would require additional security, auditing, access control, and data handling controls

## Future Improvements

- Expand supported procedure families and modifier rules
- Improve note section parsing for more dictation styles
- Add stronger retrieval with embeddings
- Add reviewer comments and manual override workflow
- Add role-based views for coders, auditors, and operations teams
- Grow the synthetic gold-standard evaluation set
