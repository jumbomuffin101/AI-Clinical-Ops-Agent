from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _active_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [finding for finding in report.get("audit_findings", []) if finding.get("category") != "clean_claim"]


def _issue_key(finding: dict[str, Any]) -> str:
    return str(finding.get("category") or finding.get("title") or finding.get("message") or "unknown_issue")


def _issue_title(finding: dict[str, Any]) -> str:
    return str(finding.get("title") or finding.get("message") or _issue_key(finding).replace("_", " ").title())


def _primary_cpt(report: dict[str, Any]) -> str | None:
    candidates = report.get("cpt_candidates", [])
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate.get("confidence", 0)).get("code")


def _average_confidence(report: dict[str, Any]) -> float:
    candidates = report.get("cpt_candidates", [])
    if not candidates:
        return 0.0
    return round(sum(candidate.get("confidence", 0) for candidate in candidates) / len(candidates), 3)


def compare_reports(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    previous_findings = {_issue_key(finding): _issue_title(finding) for finding in _active_findings(previous)}
    current_findings = {_issue_key(finding): _issue_title(finding) for finding in _active_findings(current)}

    previous_cpt = _primary_cpt(previous)
    current_cpt = _primary_cpt(current)
    previous_score = int(previous.get("report", {}).get("claim_readiness_score", 0))
    current_score = int(current.get("report", {}).get("claim_readiness_score", 0))

    cpt_changes = []
    if previous_cpt != current_cpt:
        cpt_changes.append({"from": previous_cpt, "to": current_cpt})

    return {
        "previous_claim_status": previous.get("report", {}).get("claim_readiness_status"),
        "new_claim_status": current.get("report", {}).get("claim_readiness_status"),
        "previous_readiness_score": previous_score,
        "new_readiness_score": current_score,
        "readiness_score_delta": current_score - previous_score,
        "resolved_issues": [previous_findings[key] for key in sorted(set(previous_findings) - set(current_findings))],
        "added_issues": [current_findings[key] for key in sorted(set(current_findings) - set(previous_findings))],
        "cpt_changes": cpt_changes,
        "previous_average_confidence": _average_confidence(previous),
        "new_average_confidence": _average_confidence(current),
    }


@dataclass
class RevisionHistory:
    items: list[dict[str, Any]] = field(default_factory=list)

    def add(self, original_note: str, revised_note: str, previous_report: dict[str, Any], new_report: dict[str, Any]) -> dict[str, Any]:
        item = {
            "created_at": datetime.now(UTC).isoformat(),
            "original_note": original_note,
            "revised_note": revised_note,
            "comparison": compare_reports(previous_report, new_report),
        }
        self.items.append(item)
        return item
