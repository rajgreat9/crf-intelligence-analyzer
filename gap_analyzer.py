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

CDASH_SYSTEM_PROMPT = """You are a clinical data management expert with deep, specific expertise in CDISC CDASH (Clinical Data Acquisition Standards Harmonization) standards, evaluating a single CRF document for alignment with CDASH.

Your task is to assess how well the uploaded CRF aligns with the CDASH reference domain(s) provided below, the way an experienced CDASH implementation reviewer would during a CRF design review or standards compliance check.

For each CDASH reference field, determine whether the CRF:
- Has a clearly corresponding field (aligned)
- Has a field that may correspond but uses different terminology or structure (partial/ambiguous alignment — flag for review)
- Is missing the field entirely (gap)

Also flag any CRF fields that don't map to any CDASH reference field — these aren't necessarily wrong (some fields are legitimately study-specific), but are worth noting for completeness.

For each finding, classify severity as:
- CRITICAL: Missing a CORE CDASH field that has direct downstream impact on SDTM mapping, safety reporting, or regulatory submission-required domains.
- HIGH: Missing a core field with lower direct regulatory impact, or a significant terminology/structure mismatch likely to complicate SDTM mapping.
- MODERATE: Missing a supplemental (non-core) CDASH field, or a minor terminology variation.

Be precise and avoid false positives — if a CRF field plausibly corresponds to a CDASH field even with different wording, treat it as aligned rather than flagging a gap.

Respond ONLY with valid JSON, no preamble, no markdown fences:

{
  "summary": {
    "domains_checked": ["<domain codes checked, e.g. AE, CM>"],
    "total_findings": <int>,
    "critical_count": <int>,
    "high_count": <int>,
    "moderate_count": <int>
  },
  "findings": [
    {
      "severity": "critical|high|moderate",
      "domain": "<CDASH domain code, e.g. AE>",
      "cdash_variable": "<CDASH variable name this finding relates to, or 'N/A' if not applicable>",
      "finding_type": "missing_core_field|missing_supplemental_field|terminology_mismatch|unmapped_crf_field|other",
      "description": "<what was found or not found>",
      "clinical_rationale": "<why this matters for CDASH alignment and downstream standards compliance>"
    }
  ]
}
"""


PROTOCOL_SYSTEM_PROMPT = """You are a clinical data management expert specializing in protocol-to-CRF alignment review for clinical trials, with deep expertise in oncology trial design, endpoints, and Schedule of Assessments (SoA) structures.

Your task is to compare a clinical trial PROTOCOL document against a CRF document, the way an experienced clinical data manager would during CRF design review or study startup — checking whether the CRF actually captures what the protocol requires.

First, identify from the protocol:
- Primary and secondary endpoints
- Key safety assessments and their required frequency/timing
- Schedule of Assessments (SoA) entries — what is assessed at which visits
- Any explicitly named data collection requirements (e.g., specific biomarkers, specific response criteria like RECIST/iRECIST, specific lab panels)

Then assess whether the CRF has corresponding fields to capture each of these. For each protocol requirement, determine whether the CRF:
- Clearly captures it (aligned)
- Appears to partially or ambiguously capture it (flag for review)
- Does not appear to capture it at all (gap — this is the most important finding type)

Also note any CRF fields that don't seem to trace back to any protocol requirement — these may be reasonable operational fields, but are worth flagging for completeness review.

For each finding, classify severity as:
- CRITICAL: The CRF appears to be missing a field needed to capture a primary or secondary endpoint, or a required safety assessment explicitly specified in the protocol.
- HIGH: The CRF appears to be missing a field for a protocol-specified assessment that is not a primary/secondary endpoint but is still explicitly required (e.g., a named biomarker panel, a specific SoA timepoint).
- MODERATE: Ambiguous alignment, minor SoA timing mismatches, or CRF fields with no clear protocol traceability.

Be conservative — protocols are long and CRFs may reasonably summarize or restructure protocol language. Only flag genuine apparent gaps, not just differences in wording.

Respond ONLY with valid JSON, no preamble, no markdown fences:

{
  "summary": {
    "endpoints_identified": <int>,
    "total_findings": <int>,
    "critical_count": <int>,
    "high_count": <int>,
    "moderate_count": <int>
  },
  "findings": [
    {
      "severity": "critical|high|moderate",
      "protocol_requirement": "<the endpoint, assessment, or SoA item this finding relates to>",
      "finding_type": "missing_endpoint_field|missing_safety_assessment|soa_timing_mismatch|unmapped_crf_field|other",
      "description": "<what the protocol requires vs. what the CRF appears to capture>",
      "clinical_rationale": "<why this matters for endpoint derivation, safety monitoring, or data completeness>"
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


def build_cdash_prompt(doc_name: str, doc_content: str, cdash_reference_text: str) -> str:
    return f"""Assess the following CRF document for alignment with the CDASH reference domains provided below.

CRF DOCUMENT: {doc_name}
{doc_content}

---

{cdash_reference_text}

---

Produce the structured JSON CDASH alignment report as instructed."""


def build_protocol_prompt(protocol_name: str, protocol_content: str, crf_name: str, crf_content: str) -> str:
    return f"""Compare the following clinical trial protocol against the CRF document and assess whether the CRF captures what the protocol requires.

PROTOCOL DOCUMENT: {protocol_name}
{protocol_content}

---

CRF DOCUMENT: {crf_name}
{crf_content}

---

Produce the structured JSON protocol alignment report as instructed."""


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


def run_cdash_analysis(doc_name: str, doc_content: str, cdash_reference_text: str, api_key: str) -> dict:
    """
    Checks a single CRF document against selected CDASH reference domain(s).
    """
    user_prompt = build_cdash_prompt(doc_name, doc_content, cdash_reference_text)
    return _call_claude(CDASH_SYSTEM_PROMPT, user_prompt, api_key)


def run_protocol_analysis(protocol_name: str, protocol_content: str, crf_name: str, crf_content: str, api_key: str, progress_callback=None) -> dict:
    """
    Checks whether a CRF captures what a protocol requires (endpoints,
    safety assessments, Schedule of Assessments items). For large
    documents, condenses via chunked LLM extraction first so the full
    document is read even though only a distilled version reaches the
    final analysis call.
    """
    from doc_condenser import condense_document

    protocol_final, protocol_condensed, _ = condense_document(
        protocol_content, "protocol", api_key,
        progress_callback=lambda i, n: progress_callback("protocol", i, n) if progress_callback else None,
    )
    crf_final, crf_condensed, _ = condense_document(
        crf_content, "crf", api_key,
        progress_callback=lambda i, n: progress_callback("crf", i, n) if progress_callback else None,
    )

    user_prompt = build_protocol_prompt(protocol_name, protocol_final, crf_name, crf_final)
    result = _call_claude(PROTOCOL_SYSTEM_PROMPT, user_prompt, api_key)
    result["_condensation_info"] = {"protocol_condensed": protocol_condensed, "crf_condensed": crf_condensed}
    return result
