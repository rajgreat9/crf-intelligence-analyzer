"""
CRF Gap Analyzer — LLM comparison engine.
Supports pairwise (2-document) comparison and portfolio-mode (N-document)
comparison for legacy CRF library / cross-study scans.
"""

import json
import re
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

PAIRWISE_SYSTEM_PROMPT = """You are a clinical data management expert specializing in Case Report Form (CRF) review for clinical trials, with deep expertise in CDISC CDASH standards and oncology trial data collection (staging, biomarkers, treatment, response, and follow-up domains).

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
      "clinical_rationale": "<why this matters downstream>"
    }
  ]
}
"""

PORTFOLIO_SYSTEM_PROMPT = """You are a clinical data management expert specializing in Case Report Form (CRF) review for clinical trials, with deep expertise in CDISC CDASH standards and oncology trial data collection.

Your task is to review a PORTFOLIO of multiple CRF documents (three or more) from different studies, protocol versions, or vendor builds, and produce a structured cross-document analysis — the way an experienced data manager would when assessing a legacy CRF library for reuse, consistency, and standardization across a program.

Unlike a simple pairwise diff, your job here is to identify PATTERNS across the whole set:
- Fields/concepts that appear inconsistently across documents (e.g., same concept collected under different labels in different studies — a naming/standardization gap)
- Fields present in some documents but conspicuously absent in others, where the absence looks unintentional rather than stage-appropriate
- Opportunities for reuse: forms or field groups that are consistent enough across documents to be confidently reused as-is
- Structural or standards drift over time if document names/order suggest a chronological progression

For each finding, classify severity as:
- CRITICAL: Inconsistency affecting safety data, primary/secondary endpoints, or regulatory-required fields, that could compromise cross-study pooling or data integrity.
- HIGH: Structural or naming inconsistency likely to complicate SDTM mapping, CDASH alignment, or cross-study harmonization.
- MODERATE: Lower-risk inconsistency or cosmetic variation worth noting but unlikely to block reuse or pooling.

Respond ONLY with valid JSON, no preamble, no markdown fences:

{
  "summary": {
    "documents_reviewed": <int>,
    "total_findings": <int>,
    "critical_count": <int>,
    "high_count": <int>,
    "moderate_count": <int>
  },
  "findings": [
    {
      "severity": "critical|high|moderate",
      "finding_type": "inconsistent_naming|missing_in_subset|reuse_opportunity|structural_drift|other",
      "documents_involved": ["<document name(s) this finding relates to>"],
      "description": "<what pattern was found across the documents>",
      "clinical_rationale": "<why this matters for portfolio consistency, reuse, or pooling>"
    }
  ]
}
"""

# Kept for backward compatibility with any code still importing the old name
SYSTEM_PROMPT = PAIRWISE_SYSTEM_PROMPT


def build_user_prompt(doc_a_name: str, doc_a_content: str, doc_b_name: str, doc_b_content: str) -> str:
    return f"""Compare the following two CRF documents and produce a gap analysis.

DOCUMENT A: {doc_a_name}
{doc_a_content}

---

DOCUMENT B: {doc_b_name}
{doc_b_content}

---

Produce the structured JSON gap report as instructed."""


def build_portfolio_prompt(documents: list) -> str:
    """
    documents: list of (name, content) tuples, 3 or more.
    """
    sections = [f"Review the following {len(documents)} CRF documents as a portfolio and produce a cross-document analysis.\n"]
    for i, (name, content) in enumerate(documents, 1):
        sections.append(f"DOCUMENT {i}: {name}\n{content}\n")
        sections.append("---")
    sections.append("\nProduce the structured JSON portfolio analysis as instructed.")
    return "\n".join(sections)


def _call_claude(system_prompt: str, user_prompt: str, api_key: str) -> dict:
    client = Anthropic(api_key=api_key)

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=system_prompt,
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


def run_gap_analysis(doc_a_name: str, doc_a_content: str, doc_b_name: str, doc_b_content: str, api_key: str) -> dict:
    """Pairwise (2-document) comparison — original behavior, unchanged."""
    user_prompt = build_user_prompt(doc_a_name, doc_a_content, doc_b_name, doc_b_content)
    return _call_claude(PAIRWISE_SYSTEM_PROMPT, user_prompt, api_key)


def run_portfolio_analysis(documents: list, api_key: str) -> dict:
    """
    Portfolio (N-document, N>=3) cross-document analysis.
    documents: list of (name, content) tuples.
    """
    if len(documents) < 3:
        raise ValueError("Portfolio analysis requires at least 3 documents. Use run_gap_analysis for 2 documents.")
    user_prompt = build_portfolio_prompt(documents)
    return _call_claude(PORTFOLIO_SYSTEM_PROMPT, user_prompt, api_key)
