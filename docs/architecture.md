# Architecture

```text
Synthetic operative note
        |
        v
FastAPI route -> AnalysisService
        |
        +-> ProcedureExtractor
        +-> CPTCoder --------+
        |                    |
        +-> BillingAuditor <-+-- KeywordRetriever over /data/reference_docs
        |
        +-> ReimbursementEstimator over /data/fee_schedule
        |
        +-> ReportGenerator
        |
        v
PostgreSQL tables + dashboard response
```

The provider layer starts with `MockLLMProvider` so the system runs without API keys. `OpenAIProvider` is intentionally a stub until real LLM calls are introduced.
