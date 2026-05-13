from app.parsing.note_parser import OperativeNoteParser


def test_section_extraction_with_headers():
    note = """
Procedure: Left open inguinal hernia repair with mesh.
Indication: Symptomatic left inguinal hernia.
Findings: Indirect left inguinal hernia.
Technique: Mesh repair was completed.
Postoperative diagnosis: Left inguinal hernia.
"""
    parsed = OperativeNoteParser().parse(note)

    assert parsed.parsed_sections["Procedure"].startswith("Left open inguinal")
    assert parsed.parsed_sections["Findings"] == "Indirect left inguinal hernia."
    assert parsed.missing_sections == []
    assert parsed.structure_quality == "Strong structure"


def test_missing_section_detection():
    note = """
Procedure: Diagnostic colonoscopy.
Indication: Synthetic screening indication.
Technique: Scope advanced to the cecum.
"""
    parsed = OperativeNoteParser().parse(note)

    assert "Findings" in parsed.missing_sections
    assert "Postoperative diagnosis" in parsed.missing_sections


def test_anatomy_and_laterality_extraction_prioritizes_procedure_and_findings():
    note = """
Indication: Prior right-sided symptoms were discussed.
Procedure: Left lower extremity angiogram.
Findings: Left leg arterial images were obtained.
Postoperative diagnosis: Peripheral arterial disease.
"""
    parsed = OperativeNoteParser().parse(note)

    assert parsed.detected_anatomy == "lower extremity arteries"
    assert parsed.detected_laterality == "left"


def test_malformed_note_handling():
    note = "Short free text says an appendectomy was performed. No formal headings are present, and findings are not separated."
    parsed = OperativeNoteParser().parse(note)

    assert parsed.detected_procedure_name == "Appendectomy"
    assert parsed.structure_quality == "Poorly structured note"
    assert "Procedure" in parsed.missing_sections
