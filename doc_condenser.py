"""
Document Condensation — for very large documents (100+ pages) that exceed
a reasonable single-request size, this module chunks the document and uses
an LLM extraction pass to pull out only the clinically meaningful content
(endpoints, Schedule of Assessments entries, safety requirements, CRF field
definitions) before the real gap/alignment analysis runs.

This is a genuine map-reduce style approach, not blind truncation: every
chunk of the document is read, and the condensation step is instructed to
preserve anything relevant rather than just keep the first N pages. This
means the final analysis sees a distilled version of the ENTIRE document,
not just its beginning.
"""

import re
from anthropic import Anthropic

MODEL = "claude-sonnet-4-6"

# Threshold above which we condense before running the real analysis.
# Below this, documents are sent as-is (no condensation overhead).
CONDENSE_THRESHOLD_CHARS = 40000

# Target chunk size for the map step. Kept well under typical context
# limits to leave room for the extraction instructions and output.
CHUNK_SIZE_CHARS = 30000
CHUNK_OVERLAP_CHARS = 1000

PROTOCOL_CONDENSE_PROMPT = """You are helping prepare a large clinical trial protocol document for a downstream protocol-to-CRF alignment review. You are looking at ONE CHUNK of a much larger document.

Extract and preserve, VERBATIM where possible, anything in this chunk that is relevant to:
- Primary, secondary, or exploratory objectives/endpoints
- Schedule of Assessments (SoA) / Schedule of Events entries — what is assessed, and when
- Safety assessment requirements (adverse event definitions, SAE criteria, reporting timelines, lab thresholds for stopping/dose modification)
- Named biomarkers, response criteria (e.g., RECIST, iRECIST), or specific data collection requirements
- Explicit mentions of Case Report Forms (CRFs) or what data they capture
- Visit/cycle schedule structure

Do NOT include: background/rationale narrative, drug pharmacology details, statistical methodology details, regulatory/administrative boilerplate, references, or content clearly irrelevant to what a CRF needs to capture.

If this chunk contains none of the above, respond with exactly: "NO RELEVANT CONTENT IN THIS CHUNK"

Otherwise, output the relevant content directly, preserving section numbers/headers where present. Do not add commentary or summarization framing — extract the actual relevant text."""

CRF_CONDENSE_PROMPT = """You are helping prepare a large Case Report Form (CRF) document for a downstream protocol-to-CRF alignment review. You are looking at ONE CHUNK of a much larger CRF document.

Extract and preserve a representative account of:
- Every distinct form/section name found in this chunk
- The field labels within each form (you do not need every single field if a form has dozens of repetitive fields of the same type — capture a representative sample plus the total count, e.g. "12 laboratory result fields including Hemoglobin, WBC, Platelets...")
- Any field related to endpoints, safety (AEs/SAEs), response assessment, or biomarkers should always be included individually, never summarized away

Do NOT include: page headers/footers, form instructions/boilerplate text, repeated confidentiality notices.

If this chunk contains no form/field content, respond with exactly: "NO RELEVANT CONTENT IN THIS CHUNK"

Otherwise, output the extracted structure directly. Do not add commentary."""


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list:
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        if end >= text_len:
            break
        start = end - overlap
    return chunks


def _condense_chunk(chunk: str, prompt: str, api_key: str) -> str:
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=prompt,
        messages=[{"role": "user", "content": chunk}],
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if text == "NO RELEVANT CONTENT IN THIS CHUNK":
        return ""
    return text


def condense_document(content: str, doc_type: str, api_key: str, progress_callback=None) -> tuple:
    """
    Condenses a large document by chunking and extracting relevant content
    from each chunk via LLM. Reads the ENTIRE document (all chunks), not
    just the beginning.

    doc_type: "protocol" or "crf" — selects the appropriate extraction prompt.
    progress_callback: optional callable(current_chunk, total_chunks) for UI feedback.

    Returns (condensed_text, was_condensed: bool, chunk_count: int).
    If content is under the condensation threshold, returns it unchanged.
    """
    if len(content) <= CONDENSE_THRESHOLD_CHARS:
        return content, False, 1

    prompt = PROTOCOL_CONDENSE_PROMPT if doc_type == "protocol" else CRF_CONDENSE_PROMPT
    chunks = _chunk_text(content)
    condensed_parts = []

    for i, chunk in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(i, len(chunks))
        extracted = _condense_chunk(chunk, prompt, api_key)
        if extracted:
            condensed_parts.append(f"[Extracted from document section {i}/{len(chunks)}]\n{extracted}")

    condensed_text = "\n\n".join(condensed_parts)
    if not condensed_text.strip():
        # Fallback: if condensation somehow extracted nothing, don't return empty --
        # fall back to a simple truncation so the analysis still has something to work with.
        condensed_text = content[:CONDENSE_THRESHOLD_CHARS] + "\n\n[NOTE: Condensation extracted no distinct content; showing truncated raw text as fallback.]"

    return condensed_text, True, len(chunks)
