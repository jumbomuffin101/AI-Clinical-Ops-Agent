# Clinical Operations Review Assistant

A documentation review system that simulates how a clinical operations or billing team evaluates operative notes before submission.

The application analyzes de-identified or synthetic operative notes, identifies potential documentation issues, surfaces coding-related risks, and provides structured review guidance. The goal is not to replace coders or clinical reviewers, but to support review workflows by highlighting areas that may require attention.

---

## Demo Workflow

1. Select an example operative note or enter a custom synthetic note
2. Run the review pipeline
3. Detect procedures and documentation issues
4. Generate a structured review summary
5. Surface potential coding risks and suggested fixes
6. Flag notes requiring human review

---

## Features

### Operative note analysis
- Procedure identification from operative note text
- Detection of incomplete or ambiguous documentation
- Structured extraction of note sections
- Support for custom synthetic notes

### Documentation review checks
- Missing laterality detection
- Bundling conflict detection
- Coding confidence evaluation
- Procedure ambiguity checks
- Conflicting documentation detection
- Unsupported procedure handling

### Safety features
- PHI detection and analysis blocking
- De-identified/synthetic note enforcement
- Prevention of stale results after blocked analyses

### Review workflow support
- Ready / Needs Review / High Risk classification
- Suggested next actions
- Structured coding recommendations
- Practical documentation fixes
- Revision history support
- Previous review history

---

## Example Review Outcomes

### Ready

Example:

- Procedure: Laparoscopic appendectomy
- Complete findings and postoperative diagnosis
- No significant documentation issues

Output:

- Status: Ready
- Suggested code: 44970
- Recommendation: Proceed with standard review

---

### Needs Review

Example:

- Open inguinal hernia repair without documented laterality

Output:

- Status: Needs Review
- Main issue: Missing laterality
- Recommendation: Clarify left vs right side

---

### High Risk

Example:

- Laparoscopic cholecystectomy with possible cholangiography documentation conflict

Output:

- Status: High Risk
- Main issue: Potential bundled procedure conflict
- Recommendation: Confirm supported procedure before submission

---

## System Architecture

```text
User Input
    ↓
Note Parsing Layer
    ↓
Documentation Analysis Engine
    ↓
Risk Classification Logic
    ↓
Procedure Detection
    ↓
Coding Recommendation Engine
    ↓
Review Summary + Suggested Fixes
```

---

## Tech Stack

### Frontend

- Next.js
- TypeScript
- React
- Tailwind CSS

### Backend

- Python
- FastAPI
- SQLAlchemy
- Alembic

### Database

- PostgreSQL

### Infrastructure / Development

- Docker
- Docker Compose
- Vercel
- Render

### AI Integration

- OpenRouter
- LLM-assisted interpretation pipeline
- Hybrid rules + AI workflow

---

## Project Structure

```text
apps/
├── web/                 # Next.js frontend
├── api/                 # FastAPI backend

docs/
├── architecture/
├── examples/

tests/

alembic/
```

---

## Local Setup

### Clone repository

```bash
git clone <repository-url>

cd <project-name>
```

### Install frontend dependencies

```bash
cd apps/web
npm install
```

### Install backend dependencies

```bash
cd apps/api
pip install -r requirements.txt
```

### Configure environment variables

Create:

```bash
.env
```

Example:

```env
DATABASE_URL=postgresql://...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=qwen/qwen-2.5-72b-instruct
```

### Run application

Frontend:

```bash
npm run dev
```

Backend:

```bash
uvicorn main:app --reload
```

---

## Design Notes

This project intentionally focuses on workflow support rather than autonomous medical decision making.

The system:

- does not make final coding decisions
- does not replace human review
- does not process real patient information
- only accepts synthetic or de-identified notes

---

## Future Improvements

- Expanded procedure support library
- Stronger coding confidence metrics
- Additional documentation quality checks
- Better explanation generation
- Evaluation datasets for broader testing
- Enhanced clinical workflow simulation

---

## Disclaimer

This project is intended for educational and engineering demonstration purposes only.

It is not a medical device and should not be used for clinical decision making, patient care, or production billing workflows.