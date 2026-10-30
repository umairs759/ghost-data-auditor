"""Interactive Dashboard for Ghost Data Still Exists Auditor.

Build a clean Streamlit dashboard to visualize:
- Case Search & Selector with status badges
- Identity Tree breakdown
- Ghost Data Radar
- Steps JSON Viewer
- Live Audit Sandbox
"""

import streamlit as st
import json
import csv
import os
import sys
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.insert(0, r'C:\Users\usamah\Desktop\Hackerrank_hackathon')

import code.main as main_mod

# --------------------------------------------------------------------------- #
# Page Configuration
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Ghost Data Still Exists - Auditor",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
OUTPUT_CSV = os.path.join(r'C:\Users\usamah\Desktop\Hackerrank_hackathon', 'output.csv')
DATASET_DIR = os.path.join(r'C:\Users\usamah\Desktop\Hackerrank_hackathon', 'dataset')

# Status badge colors
STATUS_BADGES = {
    'COMPLETE': ('✅ COMPLETE', '#2Ecc71'),
    'INCOMPLETE': ('⚠️ INCOMPLETE', '#f1c40f'),
    'NOT_APPLICABLE': ('ℹ️ NOT_APPLICABLE', '#95a5a6'),
}


# --------------------------------------------------------------------------- #
# Data Loading
# --------------------------------------------------------------------------- #
@st.cache_data
def load_output_data() -> List[Dict[str, any]]:
    """Load and parse the output.csv file."""
    results = []
    try:
        with open(OUTPUT_CSV, encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                case_id = row.get('case_id', '')
                deletion_status = row.get('deletion_status', '')
                steps_json = row.get('steps_json', '[]')
                try:
                    steps = json.loads(steps_json) if steps_json else []
                except json.JSONDecodeError:
                    steps = []
                results.append({
                    'case_id': case_id,
                    'deletion_status': deletion_status,
                    'steps_json': steps,
                })
    except FileNotFoundError:
        st.error(f"Output file not found: {OUTPUT_CSV}")
    return results


@st.cache_data
def load_dataset_identities() -> Dict[str, any]:
    """Load identity data for the identity tree visualization."""
    # Load user identities
    identities = {}
    try:
        identities_path = os.path.join(DATASET_DIR, 'user_identities.csv')
        with open(identities_path, encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                uid = row.get('user_id', '')
                identities[uid] = {
                    'name': row.get('name', ''),
                    'email': row.get('email', ''),
                    'phone': row.get('phone', ''),
                }
    except FileNotFoundError:
        st.warning("user_identities.csv not found")
    return identities


@st.cache_data
def load_evidence_files() -> List[Dict[str, any]]:
    """Load evidence file manifest."""
    evidence = []
    try:
        evidence_path = os.path.join(DATASET_DIR, 'evidence_files.csv')
        with open(evidence_path, encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                evidence.append({
                    'file_id': row.get('file_id', ''),
                    'file_path': row.get('file_path', ''),
                    'origin': row.get('origin', ''),
                    'captured_at': row.get('captured_at', ''),
                })
    except FileNotFoundError:
        st.warning("evidence_files.csv not found")
    return evidence


# --------------------------------------------------------------------------- #
# UI Components
# --------------------------------------------------------------------------- #
def status_badge(status: str) -> str:
    """Render a status badge for the given status."""
    badge_text, badge_color = STATUS_BADGES.get(
        status, ('? UNKNOWN', '#95a5a6')
    )
    st.markdown(
        f"<span style='"
        f"background-color: {badge_color}; "
        f"color: white; "
        f"padding: 4px 8px; "
        f"border-radius: 4px; "
        f"font-size: 0.8em;'>"
        f"{badge_text}</span>",
        unsafe_allow_html=True,
    )


def steps_json_viewer(steps: List[Dict[str, any]]) -> None:
    """Interactive visual timeline showing Phase -> Operation -> Evidence link."""
    if not steps:
        st.info("No steps to display")
        return

    # Group steps by phase
    phases = {'FINDING': [], 'REMEDIATION': [], 'VERIFICATION': []}
    for step in steps:
        phase = step.get('phase', '')
        if phase in phases:
            phases[phase].append(step)

    for phase_name, phase_steps in phases.items():
        if not phase_steps:
            continue
        st.markdown(f"### {phase_name}")
        for step in phase_steps:
            with st.expander(
                f"Step {step.get('step_no', '?')}: {step.get('operation', '?')}",
                expanded=False,
            ):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**System ID:** {step.get('system_id', 'N/A')}")
                with col2:
                    st.write(f"**Resource ID:** {step.get('resource_id', 'N/A')}")
                with col3:
                    st.write(f"**State:** {step.get('state', 'N/A')}")
                evidence_id = step.get('evidence_id', '')
                if evidence_id:
                    st.write(f"**Evidence ID:** {evidence_id}")
                else:
                    st.write(f"**Evidence ID:** *(none)*")


def render_sidebar() -> Dict[str, any]:
    """Render sidebar with case search and filters."""
    results = load_output_data()
    identities = load_dataset_identities()

    st.sidebar.title("🔍 Case Search")

    # Get unique case IDs sorted
    case_ids = sorted([r['case_id'] for r in results])

    # Search box
    search_term = st.sidebar.text_input(
        "Search case ID or email:",
        placeholder="Enter case ID (e.g., case_33) or email",
    )

    # Filter cases
    filtered_cases = case_ids
    if search_term:
        filtered_cases = [
            cid for cid in case_ids
            if search_term.lower() in cid.lower()
            or search_term.lower()
            in next(
                (r.get('email', '') for r in results if r.get('case_id') == cid),
                '',
            ).lower()
        ]

    # Case selector
    selected_case = st.sidebar.selectbox(
        "Select a case:",
        options=[""] + filtered_cases,
        format_func=lambda x: "Select a case" if not x else x,
    )

    # Summary stats
    status_counts = {}
    for r in results:
        s = r['deletion_status']
        status_counts[s] = status_counts.get(s, 0) + 1

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Summary:**")
    for status, count in sorted(status_counts.items()):
        status_badge(status)
        st.sidebar.write(f"  {status}: {count}")

    return {
        'selected_case': selected_case,
        'filtered_cases': filtered_cases,
        'status_counts': status_counts,
        'identities': identities,
    }


# --------------------------------------------------------------------------- #
# Main Dashboard Pages
# --------------------------------------------------------------------------- #
def main():
    """Main dashboard entry point."""
    st.title("👻 Ghost Data Still Exists - Auditor")
    st.markdown(
        "Interactive pipeline for detecting and auditing ghost data across 518 deletion requests."
    )

    # Sidebar
    sidebar_data = render_sidebar()
    selected_case = sidebar_data['selected_case']

    # Main content area
    if not selected_case:
        # Show overview
        st.markdown("### Overview")
        results = load_output_data()
        status_counts = sidebar_data['status_counts']

        col1, col2, col3, col4 = st.columns(4)
        total = len(results)
        col1.metric("Total Cases", total)
        col2.metric("COMPLETE", status_counts.get('COMPLETE', 0))
        col3.metric("INCOMPLETE", status_counts.get('INCOMPLETE', 0))
        col4.metric("NOT_APPLICABLE", status_counts.get('NOT_APPLICABLE', 0))

        st.markdown("---")
        st.markdown(
            "Use the sidebar to select a specific case for detailed analysis, "
            "or browse all 518 cases with their deletion statuses."
        )
        return

    # Display selected case details
    case_result = None
    for r in results:
        if r['case_id'] == selected_case:
            case_result = r
            break

    if case_result is None:
        st.error(f"Case {selected_case} not found")
        return

    # Case header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"# {selected_case}")
        status_badge(case_result['deletion_status'])
    with col2:
        if st.button("Refresh Data"):
            st.rerun()

    # Step JSON Viewer
    st.markdown("### Steps JSON Viewer")
    steps_json_viewer(case_result['steps_json'])

    # Identity Tree (simple display)
    st.markdown("### Identity Information")
    results = load_output_data()
    case_identities = {
        r['case_id']: next(
            (identities.get(r.get('email', ''), {}).get('email', 'N/A') for r in results if r['case_id'] == selected_case),
            'N/A',
        )
    }
    st.write(f"Associated email: {case_identities.get(selected_case, 'N/A')}")

    # Additional case details
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("Request Text"):
            st.write(
                "Request details would be loaded from dataset/deletion_requests.csv"
            )
    with col2:
        with expander("Deletion Status"):
            st.write(f"Status: {case_result['deletion_status']}")

    # Export button
    st.markdown("---")
    st.download_button(
        label="Download steps JSON",
        data=json.dumps(case_result['steps_json'], indent=2),
        file_name=f"{selected_case}_steps.json",
        mime_type="application/json",
    )


if __name__ == "__main__":
    main()