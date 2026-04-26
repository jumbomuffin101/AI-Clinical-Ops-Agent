import json
from pathlib import Path

from app.models.schemas import CPTCodeCandidate, ReimbursementEstimate


class ReimbursementEstimator:
    def __init__(self, fee_schedule_path: Path):
        self.fee_schedule_path = fee_schedule_path
        self.fee_schedule = self._load_fee_schedule()

    def _load_fee_schedule(self) -> dict:
        if not self.fee_schedule_path.exists():
            return {}
        return json.loads(self.fee_schedule_path.read_text(encoding="utf-8"))

    def run(self, candidates: list[CPTCodeCandidate]) -> list[ReimbursementEstimate]:
        estimates: list[ReimbursementEstimate] = []
        for candidate in candidates:
            row = self.fee_schedule.get(candidate.code, {})
            estimates.append(
                ReimbursementEstimate(
                    code=candidate.code,
                    allowed_amount=float(row.get("allowed_amount", 0)),
                    currency=row.get("currency", "USD"),
                    source=row.get("source", "No local fee schedule match"),
                )
            )
        return estimates
