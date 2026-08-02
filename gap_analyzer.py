"""
CRF Gap Analyzer — LLM comparison engine.
"""

import json
import re
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a clinical data management expert specializing in Case Report Form (CRF) review for clinical trials, with deep expertise in CDISC CDASH standards and oncology trial data collection (staging, biomarkers, treatment, response, and follow-up domains).

Your task is to compare two CRF documents (Document A and Document B) and produce a structured gap analysis, the way an experienced oncology clinical data manager would when assessing legacy form reuse, study-to-study comparison, or protocol amendment impact.

For each discrepancy, classify severity as:
- CRITICAL: Missing/altered fields affecting primary/secondary endpoints, safety data, survival/vital status, or required for regulatory submission.
- HIGH: Structural changes, renamed fields without clear equivalence, missing response categories/codelists, changes affecting SDTM mapping or CDASH alignment.
- MODERATE: Formatting differences, non-substantive label changes, or lower-risk ambiguous items.

Note: Document A and Document B here represent different stages of data collection (e.g., Enrollment vs Follow-Up), so some fields will legitimately differ by design — only flag differences that represent unexpected gaps, inconsistent standards, or genuine risk, not expected stage-specific content differences.

For each finding, explain the clinical rationale and downstream implication, using precise clinical data management language.

Respond ONLY with valid JSON, no preamble, no markdown fences:

{
  "summary": {
    "forms_compared_a": <int>,
    "forms_compared_b": <int>,
    "total_findings": <int>,
    "critical_count": <int>,
    "high_count": <int>,
    "moderate_count": <int>
  },
  "findings": [
    {
      "severity": "critical|high|moderate",
      "form_name": "<form this finding relates to>",
      "finding_type": "missing_field|renamed_field|structural_change|missing_codelist|new_field|other",
      "description": "<what changed>",
      "clinical_rationale": "<why this matters downstream>",
      "recommendation": "<what the reviewer should do next>"
    }
  ]
}
"""


def build_user_prompt(doc_a_name: str, doc_a_content: str, doc_b_name: str, doc_b_content: str) -> str:
    return f"""Compare the following two CRF documents and produce a gap analysis.

DOCUMENT A: {doc_a_name}
{doc_a_content}

---

DOCUMENT B: {doc_b_name}
{doc_b_content}

---

Produce the structured JSON gap report as instructed."""


def run_gap_analysis(doc_a_name: str, doc_a_content: str, doc_b_name: str, doc_b_content: str, api_key: str) -> dict:
    client = Anthropic(api_key=api_key)
    user_prompt = build_user_prompt(doc_a_name, doc_a_content, doc_b_name, doc_b_content)

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = "".join(block.text for block in response.content if block.type == "text")

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse model output as JSON: {e}\n\nRaw output:\n{raw_text[:2000]}")
