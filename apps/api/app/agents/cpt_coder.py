from app.models.schemas import CPTCodeCandidate, ExtractedProcedure
from app.rag.retriever import KeywordRetriever


class CPTCoder:
    CODEBOOK = {
        "AV fistula creation": ("36821", "Direct arteriovenous anastomosis for dialysis access"),
        "Laparoscopic cholecystectomy": ("47562", "Laparoscopy, surgical; cholecystectomy"),
        "Laparoscopic cholecystectomy with cholangiography": ("47563", "Laparoscopy, surgical; cholecystectomy with cholangiography"),
        "Femoral endarterectomy": ("35371", "Thromboendarterectomy, including patch graft, common femoral"),
        "Carotid endarterectomy": ("35301", "Thromboendarterectomy, including patch graft, carotid"),
        "Laparoscopic appendectomy": ("44970", "Laparoscopy, surgical, appendectomy"),
        "Appendectomy": ("44950", "Appendectomy"),
        "Open inguinal hernia repair": ("49505", "Repair initial inguinal hernia, age 5 years or older; reducible"),
        "Diagnostic colonoscopy": ("45378", "Diagnostic colonoscopy, including specimen collection when performed"),
        "Lower extremity angiogram": ("75710", "Angiography, extremity, unilateral, radiological supervision and interpretation"),
    }

    def __init__(self, retriever: KeywordRetriever):
        self.retriever = retriever

    def run(self, procedures: list[ExtractedProcedure]) -> list[CPTCodeCandidate]:
        candidates: list[CPTCodeCandidate] = []
        for procedure in procedures:
            code, description = self.CODEBOOK.get(procedure.name, ("99999", "Unsupported procedure in local codebook"))
            docs = self.retriever.retrieve(f"{procedure.name} {code} {description}")
            evidence_used = [
                {"source": str(doc["source"]), "snippet": str(doc["snippet"]), "score": int(doc["score"])}
                for doc in docs
            ]
            candidates.append(
                CPTCodeCandidate(
                    procedure_name=procedure.name,
                    code=code,
                    description=description,
                    modifiers=self._modifiers_for(procedure),
                    rationale=f"Matched local rule for {procedure.name}; retrieved {len(docs)} guideline snippet(s).",
                    confidence=min(procedure.confidence, 0.94) if code != "99999" else 0.25,
                    supported_by_docs=bool(docs) and code != "99999",
                    evidence_used=evidence_used,
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
