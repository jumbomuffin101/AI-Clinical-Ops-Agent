import re


PHI_PATTERNS = [
    re.compile(r"\bMRN[:\s#-]*\d{4,}\b", re.IGNORECASE),
    re.compile(r"\bDOB[:\s-]*(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b", re.IGNORECASE),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,6}\s+[A-Za-z0-9.\s]{2,40}\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b", re.IGNORECASE),
]


def contains_phi_like_identifier(text: str) -> bool:
    return any(pattern.search(text) for pattern in PHI_PATTERNS)
