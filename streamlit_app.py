"""
CRF Intelligence Analyzer — WUSS 2026
"""

import streamlit as st
import tempfile
import os
from datetime import datetime

from pdf_parser import parse_crf_pdf, forms_to_summary_text
from gap_analyzer import run_gap_analysis
from usage_limiter import get_usage_today, get_daily_limit, is_limit_reached, increment_usage

st.set_page_config(page_title="CRF Intelligence Analyzer", page_icon="\U0001F9EC", layout="wide")

SEVERITY_ICONS = {"critical": "\U0001F534", "high": "\U0001F7E0", "moderate": "\U0001F7E1"}


def get_api_key() -> str:
    if "ANTHROPIC_API_KEY" in st.secrets:
        return st.secrets["ANTHROPIC_API_KEY"]
    return os.environ.get("ANTHROPIC_API_KEY", "")


def render_header():
    st.title("\U0001F9EC CRF Intelligence Analyzer")
    st.markdown(
        "**Automated protocol-to-CRF gap analysis, powered by AI.** "
        "Upload two CRF PDFs and get a structured, severity-ranked gap report in seconds."
    )
    st.divider()


def render_sidebar():
    with st.sidebar:
        st.header("About")
        st.markdown(
            """
            Common use cases:
            - Vendor transition CRF comparison
            - Protocol amendment impact review
            - Legacy study CRF reuse assessment
            - Cross-study harmonization checks

            Try it with real public oncology CRFs from NCI's
            Human Cancer Models Initiative (HCMI) — Lung Cancer
            Enrollment vs Follow-Up forms are preloaded as an example.
            """
        )
        st.divider()
        used = get_usage_today()
        limit = get_daily_limit()
        st.caption(f"Demo usage today: {used} / {limit} analyses")
        st.caption(
            "⚠️ This tool produces a first-pass AI-generated analysis intended "
            "to accelerate human review — not replace it."
        )


def render_findings(report: dict):
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

    selected_filter = st.radio("Filter by severity:", ["All", "Critical", "High", "Moderate"], horizontal=True)

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
            st.markdown(f"**Recommended action:** {finding.get('recommendation', '')}")


def report_to_markdown(report: dict, doc_a_name: str, doc_b_name: str) -> str:
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
            f"**Why it matters:** {f.get('clinical_rationale', '')}", "",
            f"**Recommended action:** {f.get('recommendation', '')}", "", "---", "",
        ]
    return "\n".join(lines)


def main():
    render_header()
    render_sidebar()

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
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_a:
                tmp_a.write(file_a.read())
                path_a = tmp_a.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_b:
                tmp_b.write(file_b.read())
                path_b = tmp_b.name
            try:
                forms_a = parse_crf_pdf(path_a)
                forms_b = parse_crf_pdf(path_b)
                content_a = forms_to_summary_text(forms_a)
                content_b = forms_to_summary_text(forms_b)
            finally:
                os.unlink(path_a)
                os.unlink(path_b)

        st.success(f"Parsed {len(forms_a)} form section(s) from A, {len(forms_b)} from B.")

        with st.spinner("Running AI-powered gap analysis..."):
            try:
                report = run_gap_analysis(file_a.name, content_a, file_b.name, content_b, api_key)
                increment_usage()
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                st.stop()

        st.session_state["last_report"] = report
        st.session_state["last_doc_a_name"] = file_a.name
        st.session_state["last_doc_b_name"] = file_b.name

    if "last_report" in st.session_state:
        st.divider()
        st.header("\U0001F4CB Gap Analysis Results")
        render_findings(st.session_state["last_report"])
        st.divider()
        md_report = report_to_markdown(
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


if __name__ == "__main__":
    main()
