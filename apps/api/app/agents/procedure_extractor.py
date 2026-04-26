from app.models.schemas import ExtractedProcedure
from app.providers.base import BaseLLMProvider


class ProcedureExtractor:
    def __init__(self, llm_provider: BaseLLMProvider):
        self.llm_provider = llm_provider

    def run(self, note_text: str) -> list[ExtractedProcedure]:
        text = note_text.lower()
        procedures: list[ExtractedProcedure] = []

        if "av fistula" in text or "arteriovenous fistula" in text:
            procedures.append(
                ExtractedProcedure(
                    name="AV fistula creation",
                    body_site="upper extremity",
                    approach="open",
                    laterality="left" if "left" in text else "right" if "right" in text else None,
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
        if "femoral endarterectomy" in text or ("endarterectomy" in text and "femoral" in text):
            procedures.append(
                ExtractedProcedure(
                    name="Femoral endarterectomy",
                    body_site="common femoral artery",
                    approach="open",
                    laterality="left" if "left" in text else "right" if "right" in text else None,
                    evidence="Operative note describes plaque removal from the femoral artery.",
                    confidence=0.91,
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
