# Architecture

```text
Frontend Dashboard (Next.js)
        |
        v
FastAPI API
        |
        v
AnalysisService orchestration layer
        |
        +--> ProcedureExtractor
        |
        +--> CPTCoder ----------------------+
        |                                   |
        +--> BillingAuditor ----------------+--> KeywordRetriever
        |                                         over data/reference_docs
        |
        +--> ReimbursementEstimator
        |         |
        |         v
        |   data/fee_schedule/fee_schedule.json
        |
        +--> ReportGenerator
                  |
                  v
          Claim readiness score
          Structured JSON report
                  |
                  v
PostgreSQL tables via SQLAlchemy + Alembic
        |
        v
History endpoint + export endpoint
```

## Runtime Flow

```text
1. User selects or pastes a synthetic operative note.
2. Frontend submits POST /api/notes.
3. FastAPI validates request size and note content.
4. AnalysisService runs the deterministic mock pipeline.
5. CPT coding and audit agents retrieve local guideline snippets.
6. ReportGenerator calculates claim readiness score and final report.
7. SQLAlchemy persists note, analysis, procedures, codes, findings, and estimates.
8. Frontend renders results and can call /api/analyses/{id}/export.
```

## Provider Strategy

The default provider is `MockLLMProvider`, which keeps outputs deterministic and runnable without API keys. `OpenAIProvider` is intentionally stubbed so a real LLM can be added later behind the same interface.
