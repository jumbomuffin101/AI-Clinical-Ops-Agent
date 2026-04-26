from app.models.schemas import CPTCodeCandidate, ExtractedProcedure
from app.rag.retriever import KeywordRetriever


class CPTCoder:
    CODEBOOK = {
        "AV fistula creation": ("36821", "Direct arteriovenous anastomosis for dialysis access"),
        "Laparoscopic cholecystectomy": ("47562", "Laparoscopy, surgical; cholecystectomy"),
        "Femoral endarterectomy": ("35371", "Thromboendarterectomy, including patch graft, common femoral"),
    }

    def __init__(self, retriever: KeywordRetriever):
        self.retriever = retriever

    def run(self, procedures: list[ExtractedProcedure]) -> list[CPTCodeCandidate]:
        candidates: list[CPTCodeCandidate] = []
        for procedure in procedures:
            code, description = self.CODEBOOK.get(procedure.name, ("99999", "Unsupported procedure in local codebook"))
            docs = self.retriever.retrieve(f"{procedure.name} {code} {description}")
            candidates.append(
                CPTCodeCandidate(
                    procedure_name=procedure.name,
                    code=code,
                    description=description,
                    modifiers=self._modifiers_for(procedure),
                    rationale=f"Matched local rule for {procedure.name}; retrieved {len(docs)} guideline snippet(s).",
                    confidence=min(procedure.confidence, 0.94) if code != "99999" else 0.25,
                    supported_by_docs=bool(docs) and code != "99999",
                )
            )
        return candidates

    @staticmethod
    def _modifiers_for(procedure: ExtractedProcedure) -> list[str]:
        if procedure.laterality == "left":
            return ["LT"]
        if procedure.laterality == "right":
            return ["RT"]
        return []
