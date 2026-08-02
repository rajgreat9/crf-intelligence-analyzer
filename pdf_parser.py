"""
CRF PDF Parser
Extracts structured content (form names, field labels, tables) from CRF PDFs.
Handles both text-based and table-based CRF layouts using pdfplumber,
with a PyMuPDF fallback for PDFs where pdfplumber extraction is sparse.
"""

import pdfplumber
import fitz  # PyMuPDF
import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class CRFField:
    label: str
    page: int
    context: str = ""


@dataclass
class CRFForm:
    form_name: str
    page_start: int
    fields: List[CRFField] = field(default_factory=list)
    raw_text: str = ""


def _looks_like_form_header(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 80:
        return False
    patterns = [
        r"^[A-Z][A-Z\s/\-]{3,60}$",
        r"^\d+\.\d*\s+[A-Z][A-Za-z\s/\-]{3,60}$",
    ]
    return any(re.match(p, line) for p in patterns)


def _looks_like_field_label(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 120:
        return False
    if re.search(r"^[A-Z][A-Za-z0-9\s/\-,\.\(\)]{1,80}:\s*(_{2,}|\[.*\]|.{0,40})$", line):
        return True
    if re.search(r"\[\s?\]\s*[A-Za-z]", line):
        return True
    # Numbered question lines (real CRF style: "1 Gender: Male / Female")
    if re.match(r"^\d+[a-z]?\s+[A-Z].{2,100}", line):
        return True
    return False


def extract_with_pdfplumber(filepath: str) -> List[CRFForm]:
    forms: List[CRFForm] = []
    current_form = None

    with pdfplumber.open(filepath) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            lines = text.split("\n")

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                if _looks_like_form_header(stripped):
                    if current_form:
                        forms.append(current_form)
                    current_form = CRFForm(form_name=stripped, page_start=page_num)
                    continue

                if current_form is None:
                    current_form = CRFForm(form_name="Unlabeled Section", page_start=page_num)

                current_form.raw_text += stripped + "\n"

                if _looks_like_field_label(stripped):
                    current_form.fields.append(
                        CRFField(label=stripped, page=page_num, context=stripped)
                    )

            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    for cell in row:
                        if cell and _looks_like_field_label(str(cell)):
                            if current_form:
                                current_form.fields.append(
                                    CRFField(label=str(cell).strip(), page=page_num, context=str(row))
                                )

    if current_form:
        forms.append(current_form)

    return forms


def extract_with_pymupdf_fallback(filepath: str) -> List[CRFForm]:
    forms: List[CRFForm] = []
    doc = fitz.open(filepath)
    current_form = CRFForm(form_name="Document Content", page_start=1)

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text()
        if text.strip():
            current_form.raw_text += text + "\n"
            for line in text.split("\n"):
                if _looks_like_field_label(line):
                    current_form.fields.append(
                        CRFField(label=line.strip(), page=page_num, context=line.strip())
                    )
        widgets = page.widgets()
        if widgets:
            for w in widgets:
                if w.field_label or w.field_name:
                    label = w.field_label or w.field_name
                    current_form.fields.append(
                        CRFField(label=label, page=page_num, context=f"[form field] {label}")
                    )

    forms.append(current_form)
    doc.close()
    return forms


def parse_crf_pdf(filepath: str) -> List[CRFForm]:
    forms = extract_with_pdfplumber(filepath)
    total_fields = sum(len(f.fields) for f in forms)
    total_text = sum(len(f.raw_text) for f in forms)

    if total_fields < 3 or total_text < 200:
        fallback_forms = extract_with_pymupdf_fallback(filepath)
        fallback_fields = sum(len(f.fields) for f in fallback_forms)
        if fallback_fields > total_fields:
            return fallback_forms

    return forms


def forms_to_summary_text(forms: List[CRFForm], max_chars_per_form: int = 6000) -> str:
    output = []
    for f in forms:
        output.append(f"=== FORM: {f.form_name} (starts page {f.page_start}) ===")
        if f.fields:
            output.append(f"Fields detected ({len(f.fields)}):")
            for field_item in f.fields:
                output.append(f"  - {field_item.label}  [p.{field_item.page}]")
        else:
            output.append("Fields detected: none (raw text below)")
        raw = f.raw_text[:max_chars_per_form]
        output.append(f"Raw text excerpt:\n{raw}")
        output.append("")
    return "\n".join(output)
