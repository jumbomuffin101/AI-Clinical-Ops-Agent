from pathlib import Path


class KeywordRetriever:
    def __init__(self, docs_path: Path):
        self.docs_path = docs_path
        self.documents = self._load_documents()

    def _load_documents(self) -> list[dict[str, str]]:
        if not self.docs_path.exists():
            return []
        docs: list[dict[str, str]] = []
        for path in sorted(self.docs_path.glob("*.md")):
            docs.append({"source": path.name, "content": path.read_text(encoding="utf-8")})
        return docs

    def retrieve(self, query: str, limit: int = 3) -> list[dict[str, str | int]]:
        terms = {term.strip(".,:;()").lower() for term in query.split() if len(term) > 2}
        scored: list[dict[str, str | int]] = []
        for doc in self.documents:
            content = doc["content"].lower()
            score = sum(content.count(term) for term in terms)
            if score:
                scored.append({"source": doc["source"], "snippet": self._snippet(doc["content"], terms), "score": score})
        return sorted(scored, key=lambda item: int(item["score"]), reverse=True)[:limit]

    @staticmethod
    def _snippet(content: str, terms: set[str], size: int = 280) -> str:
        lower = content.lower()
        first_hit = min((lower.find(term) for term in terms if lower.find(term) >= 0), default=0)
        start = max(first_hit - 80, 0)
        snippet = content[start : start + size].replace("\n", " ").strip()
        return snippet
