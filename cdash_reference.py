"""
CDASH Reference Data — bundled domain metadata for CDASH alignment checking.

IMPORTANT PROVENANCE NOTE:
This reference data was reconstructed from PUBLICLY AVAILABLE CDISC
documentation (cdisc.org domain overview pages, published tutorials,
conference papers, and public CDASHIG variable-naming-convention
descriptions) — NOT from the official, sign-in-gated CDASHIG Metadata
Table PDF/Excel files published by CDISC.

It is a best-effort, publicly-sourced approximation of core CDASH domain
structure for common oncology-relevant domains. It is suitable for
demonstrating the CDASH-alignment-checking capability of this tool, but
should NOT be treated as a verbatim or authoritative reproduction of the
official CDASHIG Metadata Table. Organizations using this tool for actual
regulatory-facing CRF design work should verify findings against their
licensed copy of the official CDASHIG.

Structure is designed so that this file can be swapped for a data
extract from the real, official CDASHIG Metadata Table (if obtained
through a CDISC membership) without changing any other application code
— see `load_cdash_domain()` at the bottom, which is the only function
the rest of the app calls.
"""

CDASH_VERSION_LABEL = "CDASHIG v2.1 (publicly-sourced reference reconstruction)"

# Each domain: CDASHIG-style variable name, plain-language field label,
# whether it's considered a "core" (commonly implemented) field, and a
# short note on why it matters when missing.
CDASH_DOMAINS = {
    "AE": {
        "domain_name": "Adverse Events",
        "fields": [
            {"variable": "AETERM", "label": "Adverse Event Term (verbatim)", "core": True,
             "note": "The reported term for the event; foundational for MedDRA coding."},
            {"variable": "AESTDAT", "label": "Start Date", "core": True,
             "note": "Required for onset timing and relationship to study drug exposure."},
            {"variable": "AEENDAT", "label": "End Date", "core": True,
             "note": "Required to determine event duration and ongoing status."},
            {"variable": "AESEV", "label": "Severity / Toxicity Grade", "core": True,
             "note": "Drives safety signal detection and CTCAE grading in oncology trials."},
            {"variable": "AESER", "label": "Serious Event (Y/N)", "core": True,
             "note": "Triggers expedited regulatory reporting obligations (e.g., 21 CFR 312.32)."},
            {"variable": "AEREL", "label": "Relationship to Study Treatment", "core": True,
             "note": "Required for causality assessment in safety analyses."},
            {"variable": "AEACN", "label": "Action Taken with Study Treatment", "core": True,
             "note": "Used to assess dose modifications due to toxicity."},
            {"variable": "AEOUT", "label": "Outcome", "core": True,
             "note": "Required to characterize event resolution (resolved, ongoing, fatal, etc.)."},
            {"variable": "AECONTRT", "label": "Concomitant/Additional Treatment Given", "core": False,
             "note": "Supports assessment of AE management."},
        ],
    },
    "CM": {
        "domain_name": "Concomitant Medications",
        "fields": [
            {"variable": "CMYN", "label": "Any Concomitant Medications Taken (Y/N)", "core": True,
             "note": "Gate question; commonly used to confirm negative/no-med pages."},
            {"variable": "CMTRT", "label": "Medication Name", "core": True,
             "note": "Required for WHO Drug coding and interaction assessment."},
            {"variable": "CMINDC", "label": "Indication", "core": True,
             "note": "Needed to distinguish concomitant illness treatment from AE treatment."},
            {"variable": "CMDOSFRQ", "label": "Dosing Frequency", "core": True,
             "note": "CDASH Model Interventions-class variable; supports dose regimen analysis."},
            {"variable": "CMDOSU", "label": "Dose Units", "core": False,
             "note": "Needed for standardized dose reporting."},
            {"variable": "CMROUTE", "label": "Route of Administration", "core": False,
             "note": "Supports drug interaction and PK-relevant assessments."},
            {"variable": "CMSTDAT", "label": "Start Date", "core": True,
             "note": "Required to assess temporal relationship to study treatment/AEs."},
            {"variable": "CMENDAT", "label": "End Date", "core": True,
             "note": "Required to determine ongoing status."},
            {"variable": "CMONGO", "label": "Ongoing (Y/N)", "core": False,
             "note": "Common CDASH field allowing omission of End Date when treatment continues."},
        ],
    },
    "VS": {
        "domain_name": "Vital Signs",
        "fields": [
            {"variable": "VSDAT", "label": "Vital Signs Date", "core": True,
             "note": "Required for timepoint alignment with visit schedule."},
            {"variable": "SYSBP / SYSBP_VSORRES", "label": "Systolic Blood Pressure", "core": True,
             "note": "Standard safety monitoring parameter."},
            {"variable": "DIABP / DIABP_VSORRES", "label": "Diastolic Blood Pressure", "core": True,
             "note": "Standard safety monitoring parameter."},
            {"variable": "PULSE / PULSE_VSORRES", "label": "Pulse/Heart Rate", "core": True,
             "note": "Standard safety monitoring parameter."},
            {"variable": "TEMP / TEMP_VSORRES", "label": "Temperature", "core": True,
             "note": "Standard safety monitoring parameter; relevant to infusion-reaction assessment."},
            {"variable": "WEIGHT / WEIGHT_VSORRES", "label": "Weight", "core": True,
             "note": "Often required for dosing calculations (e.g., mg/kg regimens)."},
            {"variable": "HEIGHT / HEIGHT_VSORRES", "label": "Height", "core": False,
             "note": "Typically collected at baseline for BSA/BMI-based dosing."},
            {"variable": "VSPERF", "label": "Vital Signs Performed (Y/N)", "core": False,
             "note": "CDASH data-cleaning prompt; not usually submitted in SDTM."},
        ],
    },
    "DM": {
        "domain_name": "Demographics",
        "fields": [
            {"variable": "BRTHDAT", "label": "Date of Birth / Age", "core": True,
             "note": "Required for eligibility verification and stratified analyses."},
            {"variable": "SEX", "label": "Sex", "core": True,
             "note": "Standard demographic and safety-stratification variable."},
            {"variable": "RACE", "label": "Race", "core": True,
             "note": "Required per most regulatory demographic reporting standards."},
            {"variable": "ETHNIC", "label": "Ethnicity", "core": False,
             "note": "Commonly required per FDA demographic subgroup reporting guidance."},
        ],
    },
    "RS": {
        "domain_name": "Disease Response (oncology)",
        "fields": [
            {"variable": "RSDAT", "label": "Assessment Date", "core": True,
             "note": "Required for time-to-event endpoint derivations (e.g., PFS)."},
            {"variable": "RSORRES", "label": "Overall Response Result", "core": True,
             "note": "Core efficacy endpoint field (CR/PR/SD/PD) in oncology trials."},
            {"variable": "RSEVAL", "label": "Method/Evaluator of Assessment", "core": False,
             "note": "Distinguishes investigator- vs. independent-review assessments."},
            {"variable": "RSSCAT", "label": "Response Category / Criteria Used", "core": False,
             "note": "Indicates RECIST 1.1 vs iRECIST vs other framework used."},
        ],
    },
    "LB": {
        "domain_name": "Laboratory Test Results",
        "fields": [
            {"variable": "LBDAT", "label": "Collection Date", "core": True,
             "note": "Required for timepoint alignment and trend analysis."},
            {"variable": "LBORRES", "label": "Result (original units)", "core": True,
             "note": "Core lab result value."},
            {"variable": "LBORNRLO / LBORNRHI", "label": "Reference Range (Low/High)", "core": True,
             "note": "Needed to flag clinically significant abnormalities and support AE triggering logic."},
            {"variable": "LBNRIND", "label": "Reference Range Indicator", "core": False,
             "note": "Normal/High/Low flag; commonly used for rapid abnormal-result review."},
        ],
    },
}


def list_available_domains() -> list:
    """Returns list of (code, domain_name) tuples for UI dropdowns."""
    return [(code, meta["domain_name"]) for code, meta in CDASH_DOMAINS.items()]


def load_cdash_domain(domain_code: str) -> dict:
    """
    Returns the reference field list for a given CDASH domain code
    (e.g., 'AE', 'CM', 'VS'). This is the single function the rest of
    the app calls — if a real CDASHIG extract becomes available, only
    this function's internals need to change, not any caller.
    """
    return CDASH_DOMAINS.get(domain_code.upper())


def domains_to_reference_text(domain_codes: list) -> str:
    """
    Formats selected CDASH domains into a text block suitable for
    inclusion in an LLM prompt as the comparison reference.
    """
    lines = [f"CDASH REFERENCE ({CDASH_VERSION_LABEL})", ""]
    for code in domain_codes:
        domain = load_cdash_domain(code)
        if not domain:
            continue
        lines.append(f"=== DOMAIN: {code} — {domain['domain_name']} ===")
        for f in domain["fields"]:
            core_tag = "CORE" if f["core"] else "supplemental"
            lines.append(f"  - [{f['variable']}] {f['label']} ({core_tag}): {f['note']}")
        lines.append("")
    return "\n".join(lines)


def custom_reference_to_text(raw_text: str, source_label: str = "User-uploaded CDASH reference") -> str:
    """
    Wraps a user-supplied CDASH reference (extracted text from their own
    CDASHIG PDF, Excel export, or other version-specific document) into
    the same kind of reference text block the LLM expects — without
    forcing it through our structured field format. This lets a user
    check against whatever CDASH version they actually have access to
    (e.g., a newer release than our bundled reconstruction), since CDASH
    itself revises periodically and our bundled data is necessarily a
    point-in-time, publicly-sourced approximation.
    """
    truncated = raw_text[:40000]  # keep prompt size reasonable
    note = ""
    if len(raw_text) > 40000:
        note = "\n[NOTE: reference text truncated to first 40,000 characters for length.]"
    return f"CDASH REFERENCE (source: {source_label})\n\n{truncated}{note}"
