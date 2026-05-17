from app.models.schemas import ExtractedProcedure
from app.models.schemas import StructuredOperativeNote
from app.providers.base import BaseLLMProvider


class ProcedureExtractor:
    def __init__(self, llm_provider: BaseLLMProvider):
        self.llm_provider = llm_provider

    def run(self, note_text: str, structured_note: StructuredOperativeNote | None = None) -> list[ExtractedProcedure]:
        analysis_text = self._analysis_text(note_text, structured_note)
        text = analysis_text.lower()
        laterality = structured_note.detected_laterality if structured_note else self._laterality(text)
        procedures: list[ExtractedProcedure] = []

        if "av fistula" in text or "arteriovenous fistula" in text:
            procedures.append(
                ExtractedProcedure(
                    name="AV fistula creation",
                    body_site="upper extremity",
                    approach="open",
                    laterality=laterality,
                    evidence="Operative note describes an anastomosis between artery and vein for dialysis access.",
                    confidence=0.93,
                )
            )
        if "laparoscopic cholecystectomy" in text or ("gallbladder" in text and "laparoscopic" in text):
            procedures.append(
                ExtractedProcedure(
                    name="Laparoscopic cholecystectomy",
                    body_site="gallbladder",
                    approach="laparoscopic",
                    laterality=None,
                    evidence="Operative note describes laparoscopic removal of the gallbladder.",
                    confidence=0.95,
                )
            )
        if ("cholangiogram" in text or "cholangiography" in text) and not any(
            phrase in text for phrase in ["no cholangiogram", "without cholangiogram", "no cholangiography", "without cholangiography"]
        ):
            procedures.append(
                ExtractedProcedure(
                    name="Laparoscopic cholecystectomy with cholangiography",
                    body_site="gallbladder",
                    approach="laparoscopic",
                    laterality=None,
                    evidence="Operative note references gallbladder removal with cholangiogram documentation.",
                    confidence=0.82,
                )
            )
        if "femoral endarterectomy" in text or ("endarterectomy" in text and "femoral" in text):
            procedures.append(
                ExtractedProcedure(
                    name="Femoral endarterectomy",
                    body_site="common femoral artery",
                    approach="open",
                    laterality=laterality,
                    evidence="Operative note describes plaque removal from the femoral artery.",
                    confidence=0.91,
                )
            )
        if "carotid endarterectomy" in text or ("endarterectomy" in text and "carotid" in text):
            procedures.append(
                ExtractedProcedure(
                    name="Carotid endarterectomy",
                    body_site="carotid artery",
                    approach="open",
                    laterality=laterality,
                    evidence="Operative note describes plaque removal from the carotid artery.",
                    confidence=0.9,
                )
            )
        if "appendectomy" in text or "appendix" in text:
            procedures.append(
                ExtractedProcedure(
                    name="Laparoscopic appendectomy" if "laparoscopic" in text else "Appendectomy",
                    body_site="appendix",
                    approach="laparoscopic" if "laparoscopic" in text else "open",
                    laterality=None,
                    evidence="Operative note documents appendix removal.",
                    confidence=0.9 if "appendix" in text else 0.78,
                )
            )
        if "inguinal hernia" in text and "repair" in text:
            procedures.append(
                ExtractedProcedure(
                    name="Open inguinal hernia repair",
                    body_site="inguinal region",
                    approach="open",
                    laterality=laterality,
                    evidence="Operative note describes open inguinal hernia repair with mesh placement.",
                    confidence=0.88,
                )
            )
        if "colonoscopy" in text:
            procedures.append(
                ExtractedProcedure(
                    name="Diagnostic colonoscopy",
                    body_site="colon",
                    approach="endoscopic",
                    laterality=None,
                    evidence="Operative note documents diagnostic colonoscopy to the cecum.",
                    confidence=0.91 if "cecum" in text else 0.72,
                )
            )
        if "angiogram" in text and ("lower extremity" in text or "leg" in text):
            procedures.append(
                ExtractedProcedure(
                    name="Lower extremity angiogram",
                    body_site="lower extremity arteries",
                    approach="percutaneous",
                    laterality=laterality,
                    evidence="Operative note describes catheter-based lower extremity angiography.",
                    confidence=0.84,
                )
            )

        if not procedures:
            procedures.append(
                ExtractedProcedure(
                    name="Unclassified operative procedure",
                    body_site=None,
                    approach=None,
                    laterality=None,
                    evidence="No supported procedure pattern matched the synthetic ruleset.",
                    confidence=0.35,
                )
            )

        return procedures

    @staticmethod
    def _analysis_text(note_text: str, structured_note: StructuredOperativeNote | None) -> str:
        if not structured_note:
            return note_text
        sections = structured_note.parsed_sections
        preferred = " ".join(sections.get(section, "") for section in ["Procedure", "Findings", "Technique"])
        return f"{preferred} {note_text}" if preferred.strip() else note_text

    @staticmethod
    def _laterality(text: str) -> str | None:
        uncertainty_phrases = [
            "left or right",
            "right or left",
            "does not clearly document",
            "not clearly document",
            "missing laterality",
            "laterality is missing",
            "without laterality",
        ]
        if any(phrase in text for phrase in uncertainty_phrases):
            return None
        if "left" in text and "right" not in text:
            return "left"
        if "right" in text and "left" not in text:
            return "right"
        return None
