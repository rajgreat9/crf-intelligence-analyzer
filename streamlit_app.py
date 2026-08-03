"""
CRF Intelligence Analyzer — WUSS 2026
"""

import streamlit as st
import tempfile
import os
from datetime import datetime

from pdf_parser import parse_crf_pdf, forms_to_summary_text
from gap_analyzer import run_gap_analysis, run_portfolio_analysis, run_cdash_analysis, run_protocol_analysis
from usage_limiter import get_usage_today, get_daily_limit, is_limit_reached, increment_usage
from cdash_reference import list_available_domains, domains_to_reference_text, custom_reference_to_text, CDASH_VERSION_LABEL

st.set_page_config(page_title="CRF Intelligence Analyzer", page_icon="\U0001F9EC", layout="wide")

SEVERITY_ICONS = {"critical": "\U0001F534", "high": "\U0001F7E0", "moderate": "\U0001F7E1"}

MODE_PAIRWISE = "Pairwise Comparison (2 documents)"
MODE_PORTFOLIO = "Portfolio Scan (3+ documents)"
MODE_CDASH = "CDASH Alignment Check"
MODE_PROTOCOL = "Protocol Alignment Check"


def inject_custom_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@500&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, sans-serif;
        }

        /* Header */
        .cia-hero {
            display: flex;
            align-items: baseline;
            gap: 0.6rem;
            margin-bottom: 0.15rem;
        }
        .cia-hero-mark {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.75rem;
            font-weight: 500;
            letter-spacing: 0.08em;
            color: #B45309;
            background: #FDF3E7;
            border: 1px solid #F3D9B4;
            border-radius: 4px;
            padding: 0.15rem 0.5rem;
            text-transform: uppercase;
        }
        .cia-hero-author {
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
            color: #6B7280;
            font-weight: 500;
        }
        .cia-title {
            font-family: 'Source Serif 4', Georgia, serif;
            font-weight: 700;
            font-size: 2.1rem;
            color: #1B4B4F;
            letter-spacing: -0.01em;
        }
        .cia-subtitle {
            font-size: 1rem;
            color: #4B5563;
            max-width: 62ch;
            line-height: 1.55;
            margin-top: 0.35rem;
        }

        /* Section dividers use a hairline rather than default streamlit divider */
        .cia-rule {
            border: none;
            border-top: 1px solid #E2DFD5;
            margin: 1.1rem 0 1.3rem 0;
        }

        /* Cards for findings — subtle depth, no harsh shadow */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 10px !important;
            border-color: #E2DFD5 !important;
            transition: border-color 0.15s ease;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            border-color: #C9C4B4 !important;
        }

        /* Metric cards */
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #E2DFD5;
            border-radius: 8px;
            padding: 0.75rem 0.9rem;
        }
        div[data-testid="stMetricValue"] {
            font-family: 'Source Serif 4', Georgia, serif;
            font-weight: 700;
        }

        /* Radio pills for mode selection */
        div[role="radiogroup"] label {
            font-family: 'Inter', sans-serif;
        }

        /* Buttons */
        button[kind="primary"] {
            font-weight: 600;
            letter-spacing: 0.01em;
        }

        /* Sidebar polish */
        section[data-testid="stSidebar"] {
            background-color: #F5F3EC;
            border-right: 1px solid #E2DFD5;
        }
        section[data-testid="stSidebar"] h3 {
            font-family: 'Source Serif 4', Georgia, serif;
            color: #1B4B4F;
        }

        /* Monospace treatment for CDASH variable codes and file names in captions */
        code {
            font-family: 'IBM Plex Mono', monospace;
            background: #F0EEE5;
            color: #1B4B4F;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_api_key() -> str:
    if "ANTHROPIC_API_KEY" in st.secrets:
        return st.secrets["ANTHROPIC_API_KEY"]
    return os.environ.get("ANTHROPIC_API_KEY", "")


def render_header():
    st.markdown(
        """
        <div class="cia-hero">
            <span class="cia-hero-mark">WUSS 2026</span>
            <span class="cia-hero-author">Built by Raj Sharma</span>
        </div>
        <div class="cia-title">CRF Intelligence Analyzer</div>
        <div class="cia-subtitle">
            Automated CRF gap analysis, powered by AI. Compare two CRFs, scan a
            portfolio of three or more, check alignment against the official
            CDASHIG v2.3 standard, or verify a CRF against its source protocol —
            get a structured, severity-ranked report in seconds instead of days.
        </div>
        <hr class="cia-rule" />
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(mode: str):
    with st.sidebar:
        st.markdown("### About")
        st.markdown(
            """
            An AI-powered tool for automated CRF gap analysis, built around
            four common clinical data management scenarios:

            **Legacy portfolio review** — assess whether historical CRFs
            can be reused for a new study.

            **Vendor transition comparison** — catch gaps when a CRF is
            rebuilt by a new EDC vendor.

            **Protocol amendment impact** — check whether a CRF still
            captures what an amended protocol requires.

            **Cross-study harmonization** — find naming and structure
            inconsistencies across a program's CRFs before pooling data.

            **CDASH alignment** — check a CRF against the official
            CDASHIG v2.3 standard, domain by domain.
            """
        )
        st.divider()
        st.caption(
            "Try it with real public oncology CRFs from NCI's Human Cancer "
            "Models Initiative (HCMI) — Lung Cancer Enrollment vs Follow-Up "
            "forms work well as a first example."
        )
        if mode == MODE_CDASH:
            st.divider()
            st.caption(f"CDASH reference: {CDASH_VERSION_LABEL}")
            st.caption(
                "This reference is extracted directly from the official "
                "CDASHIG v2.3 Metadata Table published by CDISC — the "
                "authoritative standard, not a reconstruction."
            )
        st.divider()
        used = get_usage_today()
        limit = get_daily_limit()
        st.caption(f"Demo usage today: {used} / {limit} analyses")
        st.caption(
            "⚠️ This tool produces a first-pass AI-generated analysis intended "
            "to accelerate human review — not replace it."
        )


def render_pairwise_findings(report: dict):
    summary = report.get("summary", {})
    findings = report.get("findings", [])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Findings", summary.get("total_findings", len(findings)))
    col2.metric("\U0001F534 Critical", summary.get("critical_count", 0))
    col3.metric("\U0001F7E0 High", summary.get("high_count", 0))
    col4.metric("\U0001F7E1 Moderate", summary.get("moderate_count", 0))
    st.divider()

    severity_order = {"critical": 0, "high": 1, "moderate": 2}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.get("severity", "moderate"), 3))

    selected_filter = st.radio("Filter by severity:", ["All", "Critical", "High", "Moderate"], horizontal=True, key="pairwise_filter")

    for finding in sorted_findings:
        sev = finding.get("severity", "moderate")
        if selected_filter != "All" and sev != selected_filter.lower():
            continue
        with st.container(border=True):
            icon = SEVERITY_ICONS.get(sev, "\u26AA")
            st.markdown(f"{icon} **{sev.upper()}** &mdash; **{finding.get('form_name', 'Unknown Form')}**")
            st.markdown(f"**Type:** {finding.get('finding_type', 'other').replace('_', ' ').title()}")
            st.markdown(f"**What changed:** {finding.get('description', '')}")
            st.markdown(f"**Why it matters:** {finding.get('clinical_rationale', '')}")


def render_portfolio_findings(report: dict):
    summary = report.get("summary", {})
    findings = report.get("findings", [])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Documents Reviewed", summary.get("documents_reviewed", "-"))
    col2.metric("\U0001F534 Critical", summary.get("critical_count", 0))
    col3.metric("\U0001F7E0 High", summary.get("high_count", 0))
    col4.metric("\U0001F7E1 Moderate", summary.get("moderate_count", 0))
    st.divider()

    severity_order = {"critical": 0, "high": 1, "moderate": 2}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.get("severity", "moderate"), 3))

    selected_filter = st.radio("Filter by severity:", ["All", "Critical", "High", "Moderate"], horizontal=True, key="portfolio_filter")

    for finding in sorted_findings:
        sev = finding.get("severity", "moderate")
        if selected_filter != "All" and sev != selected_filter.lower():
            continue
        with st.container(border=True):
            icon = SEVERITY_ICONS.get(sev, "\u26AA")
            docs = ", ".join(finding.get("documents_involved", []) or ["(unspecified)"])
            st.markdown(f"{icon} **{sev.upper()}** &mdash; **{finding.get('finding_type', 'other').replace('_', ' ').title()}**")
            st.markdown(f"**Documents involved:** {docs}")
            st.markdown(f"**Pattern found:** {finding.get('description', '')}")
            st.markdown(f"**Why it matters:** {finding.get('clinical_rationale', '')}")


def render_cdash_findings(report: dict):
    summary = report.get("summary", {})
    findings = report.get("findings", [])

    domains_checked = ", ".join(summary.get("domains_checked", []) or ["-"])
    st.caption(f"Domains checked: {domains_checked}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Findings", summary.get("total_findings", len(findings)))
    col2.metric("\U0001F534 Critical", summary.get("critical_count", 0))
    col3.metric("\U0001F7E0 High", summary.get("high_count", 0))
    col4.metric("\U0001F7E1 Moderate", summary.get("moderate_count", 0))
    st.divider()

    severity_order = {"critical": 0, "high": 1, "moderate": 2}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.get("severity", "moderate"), 3))

    selected_filter = st.radio("Filter by severity:", ["All", "Critical", "High", "Moderate"], horizontal=True, key="cdash_filter")

    for finding in sorted_findings:
        sev = finding.get("severity", "moderate")
        if selected_filter != "All" and sev != selected_filter.lower():
            continue
        with st.container(border=True):
            icon = SEVERITY_ICONS.get(sev, "\u26AA")
            domain = finding.get("domain", "-")
            variable = finding.get("cdash_variable", "N/A")
            st.markdown(f"{icon} **{sev.upper()}** &mdash; **{domain}** / `{variable}`")
            st.markdown(f"**Type:** {finding.get('finding_type', 'other').replace('_', ' ').title()}")
            st.markdown(f"**Finding:** {finding.get('description', '')}")
            st.markdown(f"**Why it matters:** {finding.get('clinical_rationale', '')}")


def render_protocol_findings(report: dict):
    summary = report.get("summary", {})
    findings = report.get("findings", [])

    st.caption(f"Endpoints/requirements identified from protocol: {summary.get('endpoints_identified', '-')}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Findings", summary.get("total_findings", len(findings)))
    col2.metric("\U0001F534 Critical", summary.get("critical_count", 0))
    col3.metric("\U0001F7E0 High", summary.get("high_count", 0))
    col4.metric("\U0001F7E1 Moderate", summary.get("moderate_count", 0))
    st.divider()

    severity_order = {"critical": 0, "high": 1, "moderate": 2}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.get("severity", "moderate"), 3))

    selected_filter = st.radio("Filter by severity:", ["All", "Critical", "High", "Moderate"], horizontal=True, key="protocol_filter")

    for finding in sorted_findings:
        sev = finding.get("severity", "moderate")
        if selected_filter != "All" and sev != selected_filter.lower():
            continue
        with st.container(border=True):
            icon = SEVERITY_ICONS.get(sev, "\u26AA")
            req = finding.get("protocol_requirement", "Unspecified requirement")
            st.markdown(f"{icon} **{sev.upper()}** &mdash; **{req}**")
            st.markdown(f"**Type:** {finding.get('finding_type', 'other').replace('_', ' ').title()}")
            st.markdown(f"**Finding:** {finding.get('description', '')}")
            st.markdown(f"**Why it matters:** {finding.get('clinical_rationale', '')}")


def pairwise_report_to_markdown(report: dict, doc_a_name: str, doc_b_name: str) -> str:
    summary = report.get("summary", {})
    findings = report.get("findings", [])
    lines = [
        "# CRF Gap Analysis Report", "",
        f"**Document A:** {doc_a_name}  ",
        f"**Document B:** {doc_b_name}  ",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ", "",
        "## Summary", "",
        f"- Total findings: {summary.get('total_findings', len(findings))}",
        f"- Critical: {summary.get('critical_count', 0)}",
        f"- High: {summary.get('high_count', 0)}",
        f"- Moderate: {summary.get('moderate_count', 0)}", "",
        "## Findings", "",
    ]
    severity_order = {"critical": 0, "high": 1, "moderate": 2}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.get("severity", "moderate"), 3))
    for i, f in enumerate(sorted_findings, 1):
        lines += [
            f"### {i}. [{f.get('severity', 'moderate').upper()}] {f.get('form_name', 'Unknown Form')}", "",
            f"**Type:** {f.get('finding_type', 'other').replace('_', ' ').title()}", "",
            f"**What changed:** {f.get('description', '')}", "",
            f"**Why it matters:** {f.get('clinical_rationale', '')}", "", "---", "",
        ]
    return "\n".join(lines)


def portfolio_report_to_markdown(report: dict, doc_names: list) -> str:
    summary = report.get("summary", {})
    findings = report.get("findings", [])
    lines = [
        "# CRF Portfolio Analysis Report", "",
        f"**Documents reviewed ({len(doc_names)}):**",
    ]
    for name in doc_names:
        lines.append(f"- {name}")
    lines += [
        "", f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ", "",
        "## Summary", "",
        f"- Documents reviewed: {summary.get('documents_reviewed', len(doc_names))}",
        f"- Critical: {summary.get('critical_count', 0)}",
        f"- High: {summary.get('high_count', 0)}",
        f"- Moderate: {summary.get('moderate_count', 0)}", "",
        "## Findings", "",
    ]
    severity_order = {"critical": 0, "high": 1, "moderate": 2}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.get("severity", "moderate"), 3))
    for i, f in enumerate(sorted_findings, 1):
        docs = ", ".join(f.get("documents_involved", []) or ["(unspecified)"])
        lines += [
            f"### {i}. [{f.get('severity', 'moderate').upper()}] {f.get('finding_type', 'other').replace('_', ' ').title()}", "",
            f"**Documents involved:** {docs}", "",
            f"**Pattern found:** {f.get('description', '')}", "",
            f"**Why it matters:** {f.get('clinical_rationale', '')}", "", "---", "",
        ]
    return "\n".join(lines)


def cdash_report_to_markdown(report: dict, doc_name: str, domains: list) -> str:
    summary = report.get("summary", {})
    findings = report.get("findings", [])
    lines = [
        "# CDASH Alignment Report", "",
        f"**Document:** {doc_name}  ",
        f"**CDASH domains checked:** {', '.join(domains)}  ",
        f"**Reference:** {CDASH_VERSION_LABEL}  ",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ", "",
        "## Summary", "",
        f"- Total findings: {summary.get('total_findings', len(findings))}",
        f"- Critical: {summary.get('critical_count', 0)}",
        f"- High: {summary.get('high_count', 0)}",
        f"- Moderate: {summary.get('moderate_count', 0)}", "",
        "## Findings", "",
    ]
    severity_order = {"critical": 0, "high": 1, "moderate": 2}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.get("severity", "moderate"), 3))
    for i, f in enumerate(sorted_findings, 1):
        lines += [
            f"### {i}. [{f.get('severity', 'moderate').upper()}] {f.get('domain', '-')} / {f.get('cdash_variable', 'N/A')}", "",
            f"**Type:** {f.get('finding_type', 'other').replace('_', ' ').title()}", "",
            f"**Finding:** {f.get('description', '')}", "",
            f"**Why it matters:** {f.get('clinical_rationale', '')}", "", "---", "",
        ]
    return "\n".join(lines)


def protocol_report_to_markdown(report: dict, protocol_name: str, crf_name: str) -> str:
    summary = report.get("summary", {})
    findings = report.get("findings", [])
    lines = [
        "# Protocol Alignment Report", "",
        f"**Protocol:** {protocol_name}  ",
        f"**CRF:** {crf_name}  ",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ", "",
        "## Summary", "",
        f"- Endpoints/requirements identified: {summary.get('endpoints_identified', '-')}",
        f"- Total findings: {summary.get('total_findings', len(findings))}",
        f"- Critical: {summary.get('critical_count', 0)}",
        f"- High: {summary.get('high_count', 0)}",
        f"- Moderate: {summary.get('moderate_count', 0)}", "",
        "## Findings", "",
    ]
    severity_order = {"critical": 0, "high": 1, "moderate": 2}
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.get("severity", "moderate"), 3))
    for i, f in enumerate(sorted_findings, 1):
        lines += [
            f"### {i}. [{f.get('severity', 'moderate').upper()}] {f.get('protocol_requirement', 'Unspecified')}", "",
            f"**Type:** {f.get('finding_type', 'other').replace('_', ' ').title()}", "",
            f"**Finding:** {f.get('description', '')}", "",
            f"**Why it matters:** {f.get('clinical_rationale', '')}", "", "---", "",
        ]
    return "\n".join(lines)


def parse_uploaded_pdf(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        path = tmp.name
    try:
        forms = parse_crf_pdf(path)
        content = forms_to_summary_text(forms)
    finally:
        os.unlink(path)
    return forms, content


def main():
    inject_custom_css()
    render_header()

    mode = st.radio("Analysis mode:", [MODE_PAIRWISE, MODE_PORTFOLIO, MODE_CDASH, MODE_PROTOCOL], horizontal=True)

    render_sidebar(mode)

    api_key = get_api_key()
    if not api_key:
        st.error("No Anthropic API key found. Set ANTHROPIC_API_KEY as an environment variable or Space secret.")
        st.stop()

    limit_reached = is_limit_reached()
    if limit_reached:
        st.warning(
            f"This demo has reached its limit of {get_daily_limit()} analyses for today. "
            "Please check back tomorrow, or run the tool locally with your own API key. "
            "See the GitHub repo linked in the sidebar for instructions."
        )

    if mode == MODE_PAIRWISE:
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Document A")
            file_a = st.file_uploader("Upload CRF PDF", type=["pdf"], key="file_a")
        with col_b:
            st.subheader("Document B")
            file_b = st.file_uploader("Upload CRF PDF", type=["pdf"], key="file_b")

        run_button = st.button(
            "\U0001F50D Run Gap Analysis",
            type="primary",
            disabled=not (file_a and file_b) or limit_reached,
        )

        if run_button and file_a and file_b and not is_limit_reached():
            with st.spinner("Parsing CRF documents..."):
                forms_a, content_a = parse_uploaded_pdf(file_a)
                forms_b, content_b = parse_uploaded_pdf(file_b)

            st.success(f"Parsed {len(forms_a)} form section(s) from A, {len(forms_b)} from B.")

            with st.spinner("Running AI-powered gap analysis..."):
                try:
                    report = run_gap_analysis(file_a.name, content_a, file_b.name, content_b, api_key)
                    increment_usage()
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
                    st.stop()

            st.session_state["last_report"] = report
            st.session_state["last_mode"] = "pairwise"
            st.session_state["last_doc_a_name"] = file_a.name
            st.session_state["last_doc_b_name"] = file_b.name

        if "last_report" in st.session_state and st.session_state.get("last_mode") == "pairwise":
            st.divider()
            st.header("\U0001F4CB Gap Analysis Results")
            render_pairwise_findings(st.session_state["last_report"])
            st.divider()
            md_report = pairwise_report_to_markdown(
                st.session_state["last_report"],
                st.session_state["last_doc_a_name"],
                st.session_state["last_doc_b_name"],
            )
            st.download_button(
                "\U0001F4E5 Download Report (Markdown)", data=md_report,
                file_name=f"crf_gap_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md", mime="text/markdown",
            )
            with st.expander("View raw JSON output"):
                st.json(st.session_state["last_report"])

    elif mode == MODE_PORTFOLIO:
        st.subheader("Upload 3 or more CRF documents")
        uploaded_files = st.file_uploader(
            "Upload CRF PDFs (legacy studies, protocol versions, vendor builds, etc.)",
            type=["pdf"],
            accept_multiple_files=True,
            key="portfolio_files",
        )

        num_files = len(uploaded_files) if uploaded_files else 0
        if uploaded_files:
            st.caption(f"{num_files} file(s) selected.")

        run_button = st.button(
            "\U0001F50D Run Portfolio Scan",
            type="primary",
            disabled=num_files < 3 or limit_reached,
        )
        if 0 < num_files < 3:
            st.info("Portfolio mode requires at least 3 documents. Use Pairwise Comparison for 2.")

        if run_button and num_files >= 3 and not is_limit_reached():
            documents = []
            with st.spinner(f"Parsing {num_files} CRF documents..."):
                for f in uploaded_files:
                    forms, content = parse_uploaded_pdf(f)
                    documents.append((f.name, content))

            st.success(f"Parsed {num_files} documents.")

            with st.spinner("Running AI-powered portfolio analysis..."):
                try:
                    report = run_portfolio_analysis(documents, api_key)
                    increment_usage()
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
                    st.stop()

            st.session_state["last_report"] = report
            st.session_state["last_mode"] = "portfolio"
            st.session_state["last_doc_names"] = [name for name, _ in documents]

        if "last_report" in st.session_state and st.session_state.get("last_mode") == "portfolio":
            st.divider()
            st.header("\U0001F4CB Portfolio Analysis Results")
            render_portfolio_findings(st.session_state["last_report"])
            st.divider()
            md_report = portfolio_report_to_markdown(
                st.session_state["last_report"],
                st.session_state["last_doc_names"],
            )
            st.download_button(
                "\U0001F4E5 Download Report (Markdown)", data=md_report,
                file_name=f"crf_portfolio_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md", mime="text/markdown",
            )
            with st.expander("View raw JSON output"):
                st.json(st.session_state["last_report"])

    elif mode == MODE_CDASH:
        st.subheader("Upload one CRF document to check against CDASH")
        file_c = st.file_uploader("Upload CRF PDF", type=["pdf"], key="file_cdash")

        st.divider()
        st.markdown("**CDASH reference source**")
        ref_source = st.radio(
            "Which CDASH reference should be used?",
            [
                "Use built-in CDASHIG v2.3 reference (all 42 official domains)",
                "Upload my own CDASH reference (e.g., a different version, or internal standard)",
            ],
            key="cdash_ref_source",
        )
        use_custom_ref = ref_source.startswith("Upload")

        selected_codes = []
        custom_ref_file = None
        custom_ref_text = None

        if not use_custom_ref:
            available = list_available_domains()
            domain_labels = [f"{code} — {name}" for code, name in available]
            selected_labels = st.multiselect(
                "CDASH domains to check against:",
                domain_labels,
                default=[l for l in domain_labels if l.startswith(("AE ", "RS ", "TU "))] or domain_labels[:2],
            )
            selected_codes = [label.split(" — ")[0] for label in selected_labels]
            st.caption(
                "Reference source: official CDASHIG v2.3 Metadata Table. "
                "CDASH revises periodically — if you need to check against a "
                "different version, use the upload option above instead."
            )
        else:
            custom_ref_file = st.file_uploader(
                "Upload your CDASH reference (PDF or .txt — e.g., a CDASHIG Metadata Table export, "
                "an internal standards document, or a specific version extract)",
                type=["pdf", "txt"],
                key="cdash_custom_ref",
            )
            if custom_ref_file:
                st.caption(f"Using uploaded reference: {custom_ref_file.name}")

        ready_to_run = file_c and (
            (not use_custom_ref and selected_codes) or (use_custom_ref and custom_ref_file)
        )

        run_button = st.button(
            "\U0001F50D Run CDASH Check",
            type="primary",
            disabled=not ready_to_run or limit_reached,
        )

        if run_button and ready_to_run and not is_limit_reached():
            with st.spinner("Parsing CRF document..."):
                forms_c, content_c = parse_uploaded_pdf(file_c)

            st.success(f"Parsed {len(forms_c)} form section(s).")

            if use_custom_ref:
                with st.spinner("Reading uploaded CDASH reference..."):
                    if custom_ref_file.name.lower().endswith(".pdf"):
                        _, ref_raw_text = parse_uploaded_pdf(custom_ref_file)
                    else:
                        ref_raw_text = custom_ref_file.read().decode("utf-8", errors="ignore")
                    ref_text = custom_reference_to_text(ref_raw_text, source_label=custom_ref_file.name)
                domains_used = [f"custom: {custom_ref_file.name}"]
            else:
                ref_text = domains_to_reference_text(selected_codes)
                domains_used = selected_codes

            with st.spinner("Checking against CDASH reference..."):
                try:
                    report = run_cdash_analysis(file_c.name, content_c, ref_text, api_key)
                    increment_usage()
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
                    st.stop()

            st.session_state["last_report"] = report
            st.session_state["last_mode"] = "cdash"
            st.session_state["last_doc_c_name"] = file_c.name
            st.session_state["last_cdash_domains"] = domains_used

        if "last_report" in st.session_state and st.session_state.get("last_mode") == "cdash":
            st.divider()
            st.header("\U0001F4CB CDASH Alignment Results")
            render_cdash_findings(st.session_state["last_report"])
            st.divider()
            md_report = cdash_report_to_markdown(
                st.session_state["last_report"],
                st.session_state["last_doc_c_name"],
                st.session_state["last_cdash_domains"],
            )
            st.download_button(
                "\U0001F4E5 Download Report (Markdown)", data=md_report,
                file_name=f"crf_cdash_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md", mime="text/markdown",
            )
            with st.expander("View raw JSON output"):
                st.json(st.session_state["last_report"])

    else:  # MODE_PROTOCOL
        st.subheader("Upload a protocol and a CRF to check alignment")
        st.caption(
            "Upload the full protocol PDF and the CRF you want to check against it. "
            "Large documents (100+ pages) are automatically read in full and condensed "
            "to the clinically relevant content before analysis — this takes longer but "
            "covers the entire document, not just the beginning."
        )
        col_p, col_r = st.columns(2)
        with col_p:
            st.markdown("**Protocol document**")
            file_protocol = st.file_uploader("Upload protocol PDF", type=["pdf"], key="file_protocol")
        with col_r:
            st.markdown("**CRF document**")
            file_crf = st.file_uploader("Upload CRF PDF", type=["pdf"], key="file_protocol_crf")

        run_button = st.button(
            "\U0001F50D Run Protocol Alignment Check",
            type="primary",
            disabled=not (file_protocol and file_crf) or limit_reached,
        )

        if run_button and file_protocol and file_crf and not is_limit_reached():
            with st.spinner("Parsing protocol and CRF documents... this may take a moment for long protocols"):
                _, protocol_content = parse_uploaded_pdf(file_protocol)
                forms_crf, crf_content = parse_uploaded_pdf(file_crf)

            st.success(f"Parsed protocol ({len(protocol_content)} chars) and CRF ({len(forms_crf)} form section(s)).")

            progress_placeholder = st.empty()

            def show_progress(doc_type, i, n):
                label = "protocol" if doc_type == "protocol" else "CRF"
                progress_placeholder.info(f"Reading {label} document — section {i} of {n}...")

            with st.spinner("Identifying endpoints and checking CRF alignment..."):
                try:
                    report = run_protocol_analysis(
                        file_protocol.name, protocol_content, file_crf.name, crf_content, api_key,
                        progress_callback=show_progress,
                    )
                    increment_usage()
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
                    st.stop()

            progress_placeholder.empty()

            st.session_state["last_report"] = report
            st.session_state["last_mode"] = "protocol"
            st.session_state["last_protocol_name"] = file_protocol.name
            st.session_state["last_protocol_crf_name"] = file_crf.name

        if "last_report" in st.session_state and st.session_state.get("last_mode") == "protocol":
            st.divider()
            st.header("\U0001F4CB Protocol Alignment Results")

            condensation_info = st.session_state["last_report"].get("_condensation_info", {})
            if condensation_info.get("protocol_condensed") or condensation_info.get("crf_condensed"):
                parts = []
                if condensation_info.get("protocol_condensed"):
                    parts.append("protocol")
                if condensation_info.get("crf_condensed"):
                    parts.append("CRF")
                st.caption(
                    f"ℹ️ The {' and '.join(parts)} document was large and was read in full, "
                    "then condensed to clinically relevant content before analysis."
                )

            render_protocol_findings(st.session_state["last_report"])
            st.divider()
            md_report = protocol_report_to_markdown(
                st.session_state["last_report"],
                st.session_state["last_protocol_name"],
                st.session_state["last_protocol_crf_name"],
            )
            st.download_button(
                "\U0001F4E5 Download Report (Markdown)", data=md_report,
                file_name=f"crf_protocol_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md", mime="text/markdown",
            )
            with st.expander("View raw JSON output"):
                st.json(st.session_state["last_report"])


if __name__ == "__main__":
    main()
