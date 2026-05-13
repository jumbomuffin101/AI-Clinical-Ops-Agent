import re

from app.models.schemas import StructuredOperativeNote


class OperativeNoteParser:
    SECTION_ALIASES = {
        "procedure": "Procedure",
        "procedures performed": "Procedure",
        "operation": "Procedure",
        "indication": "Indication",
        "indications": "Indication",
        "findings": "Findings",
        "operative findings": "Findings",
        "technique": "Technique",
        "operative note": "Technique",
        "description of procedure": "Technique",
        "implants": "Implants",
        "implant": "Implants",
        "complications": "Complications",
        "closure": "Closure",
        "postoperative diagnosis": "Postoperative diagnosis",
        "post-op diagnosis": "Postoperative diagnosis",
        "postop diagnosis": "Postoperative diagnosis",
    }
    CRITICAL_SECTIONS = ["Procedure", "Findings", "Postoperative diagnosis"]

    PROCEDURE_PATTERNS = [
        ("AV fistula creation", ["av fistula", "arteriovenous fistula"]),
        ("Laparoscopic cholecystectomy with cholangiography", ["cholecystectomy with cholangiogram", "cholecystectomy with cholangiography"]),
        ("Laparoscopic cholecystectomy", ["laparoscopic cholecystectomy", "gallbladder"]),
        ("Femoral endarterectomy", ["femoral endarterectomy"]),
        ("Carotid endarterectomy", ["carotid endarterectomy"]),
        ("Laparoscopic appendectomy", ["laparoscopic appendectomy"]),
        ("Appendectomy", ["appendectomy", "appendix"]),
        ("Open inguinal hernia repair", ["open inguinal hernia repair", "inguinal hernia repair"]),
        ("Diagnostic colonoscopy", ["diagnostic colonoscopy", "colonoscopy"]),
        ("Lower extremity angiogram", ["lower extremity angiogram", "leg angiogram"]),
    ]
    ANATOMY_PATTERNS = [
        ("upper extremity", ["upper extremity", "arm", "wrist"]),
        ("gallbladder", ["gallbladder", "cystic duct"]),
        ("common femoral artery", ["common femoral", "femoral artery"]),
        ("carotid artery", ["carotid"]),
        ("appendix", ["appendix"]),
        ("inguinal region", ["inguinal", "groin"]),
        ("colon", ["colon", "cecum"]),
        ("lower extremity arteries", ["lower extremity", "leg"]),
    ]

    def parse(self, note_text: str) -> StructuredOperativeNote:
        sections = self._extract_sections(note_text)
        section_text = self._analysis_text(sections, note_text)
        detection_text = f"{section_text} {note_text}"
        missing_sections = [section for section in self.CRITICAL_SECTIONS if section not in sections]
        confidence = self._confidence(sections)
        return StructuredOperativeNote(
            raw_text=note_text,
            parsed_sections=sections,
            detected_procedure_name=self._detect_from_patterns(detection_text, self.PROCEDURE_PATTERNS),
            detected_anatomy=self._detect_from_patterns(detection_text, self.ANATOMY_PATTERNS),
            detected_laterality=self._laterality(sections, note_text),
            missing_sections=missing_sections,
            parsing_confidence=confidence,
            structure_quality=self._quality(confidence),
        )

    def _extract_sections(self, note_text: str) -> dict[str, str]:
        sections: dict[str, list[str]] = {}
        current: str | None = None

        for raw_line in note_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            header, inline_text = self._header(line)
            if header:
                current = header
                sections.setdefault(current, [])
                if inline_text:
                    sections[current].append(inline_text)
                continue
            if current:
                sections[current].append(line)

        if sections:
            return {section: " ".join(lines).strip() for section, lines in sections.items() if " ".join(lines).strip()}

        inferred: dict[str, str] = {}
        lowered = note_text.lower()
        if "procedure" in lowered:
            inferred["Procedure"] = self._sentence_containing(note_text, "procedure")
        if "indication" in lowered:
            inferred["Indication"] = self._sentence_containing(note_text, "indication")
        return {key: value for key, value in inferred.items() if value}

    def _header(self, line: str) -> tuple[str | None, str | None]:
        match = re.match(r"^([A-Za-z][A-Za-z /-]{2,45})(?::|-)\s*(.*)$", line)
        if not match:
            return None, None
        candidate = re.sub(r"\s+", " ", match.group(1).strip().lower())
        return self.SECTION_ALIASES.get(candidate), match.group(2).strip() or None

    @staticmethod
    def _sentence_containing(text: str, keyword: str) -> str:
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if keyword in sentence.lower():
                return sentence.strip()
        return ""

    @staticmethod
    def _analysis_text(sections: dict[str, str], note_text: str) -> str:
        preferred = " ".join(sections.get(section, "") for section in ["Procedure", "Findings", "Technique"])
        return preferred if preferred.strip() else note_text

    @staticmethod
    def _detect_from_patterns(text: str, patterns: list[tuple[str, list[str]]]) -> str | None:
        lowered = text.lower()
        for label, keywords in patterns:
            if any(keyword in lowered for keyword in keywords):
                return label
        return None

    def _laterality(self, sections: dict[str, str], note_text: str) -> str | None:
        for section in ["Procedure", "Findings"]:
            laterality = self._laterality_from_text(sections.get(section, ""))
            if laterality:
                return laterality
        return self._laterality_from_text(self._analysis_text(sections, note_text))

    @staticmethod
    def _laterality_from_text(text: str) -> str | None:
        lowered = text.lower()
        if any(phrase in lowered for phrase in ["left or right", "right or left", "laterality is missing", "does not clearly document left or right"]):
            return None
        has_left = bool(re.search(r"\bleft\b", lowered))
        has_right = bool(re.search(r"\bright\b", lowered))
        if has_left and not has_right:
            return "left"
        if has_right and not has_left:
            return "right"
        return None

    @staticmethod
    def _confidence(sections: dict[str, str]) -> float:
        if not sections:
            return 0.25
        critical_present = sum(1 for section in OperativeNoteParser.CRITICAL_SECTIONS if section in sections)
        return min(0.95, 0.35 + (len(sections) * 0.08) + (critical_present * 0.14))

    @staticmethod
    def _quality(confidence: float) -> str:
        if confidence >= 0.75:
            return "Strong structure"
        if confidence >= 0.5:
            return "Partial structure"
        return "Poorly structured note"
