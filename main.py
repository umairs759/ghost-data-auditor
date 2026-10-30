"""
FastAPI live wrapper for the Northstar Deletion Audit Agent.

Endpoints:
    GET /               - Serves the ultra-clean Enterprise Security Console UI.
    GET /health         - Health check.
    GET /api/cases      - Returns paginated/filtered list of cases from output.csv and dataset/.
    GET /api/cases/{case_id} - Returns full identity, timeline, and steps details.
    POST /api/audit     - Live sandbox audit endpoint.
"""

from __future__ import annotations

import csv
import json
import os
from typing import List, Optional

# Increase CSV field size limit to handle large fields
csv.field_size_limit(100000000)

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

# ------------------------------------------------------------------
# Lazy auditor initialization - avoids failure when NVIDIA_API_KEY is absent
# ------------------------------------------------------------------

_auditor_instance = None

def get_auditor():
    global _auditor_instance
    if _auditor_instance is None:
        try:
            _auditor_instance = DeletionAuditor(
                corpus_path="dataset", rules_csv="deletion_rules.csv", sync_folder="scripts"
            )
        except Exception as e:
            logger.warning(f"Auditor could not be initialized: {e}")
            _auditor_instance = _AuditorFallback()
    return _auditor_instance


class _AuditorFallback:
    """Fallback when NVIDIA API key is not available."""
    def process_deletion_request(self, row):
        return {
            "request_id": row.get("request_id", "unknown"),
            "status": "UNKNOWN",
            "exposed_records": [],
            "active_sync_risks": [],
            "remediation_steps": [],
        }


# Import after the lazy init helpers to avoid early DeletionAgent failure
from app.auditor import DeletionAuditor as _DeletionAuditor
from app.logging import logger

# Reassign after the fallback class is defined
DeletionAuditor = _DeletionAuditor

# Now re-define get_auditor with the real class
def get_auditor_real():
    global _auditor_instance
    if _auditor_instance is None or isinstance(_auditor_instance, _AuditorFallback):
        try:
            _auditor_instance = DeletionAuditor(
                corpus_path="dataset", rules_csv="deletion_rules.csv", sync_folder="scripts"
            )
        except Exception as e:
            logger.warning(f"Auditor could not be initialized: {e}")
            _auditor_instance = _AuditorFallback()
    return _auditor_instance


# ------------------------------------------------------------------
# API models
# ------------------------------------------------------------------

class CaseSummary(BaseModel):
    case_id: str
    email: str
    deletion_status: str
    total_steps: int


class CaseDetailResponse(BaseModel):
    case_id: str
    email: str
    historical_emails: List[str]
    account_resources: List[str]
    steps: List[dict]
    deletion_status: str
    audit_at: str


class AuditSandboxRequest(BaseModel):
    request_text: str = Field(..., description="Custom audit request text")
    activity: str = Field(..., description="Simulated system activity")
    identifier: Optional[str] = Field(None, description="User identifier")


class HealthResponse(BaseModel):
    status: str
    service: str


# ------------------------------------------------------------------
# Data loading helpers
# ------------------------------------------------------------------

OUTPUT_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output.csv")
DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")

# Robust path resolution - check multiple possible locations
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
possible_output_paths = [
    os.path.join(BASE_DIR, "output.csv"),
    os.path.join(BASE_DIR, "..", "output.csv"),
    r"C:\Users\usamah\Desktop\Hackerrank_hackathon\output.csv",
]
possible_requests_paths = [
    os.path.join(BASE_DIR, "dataset", "deletion_requests.csv"),
    os.path.join(BASE_DIR, "..", "dataset", "deletion_requests.csv"),
    r"C:\Users\usamah\Desktop\Hackerrank_hackathon\dataset\deletion_requests.csv",
]

# Pre-load deletion requests data for email lookup
_deletion_requests_cache = None


def _get_deletion_requests():
    """Load and cache deletion_requests.csv data."""
    global _deletion_requests_cache
    if _deletion_requests_cache is not None:
        return _deletion_requests_cache

    requests_data = {}
    for path in possible_requests_paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    case_id = row.get("case_id", "")
                    if case_id:
                        requests_data[case_id] = {
                            "email": row.get("email", ""),
                            "requested_at": row.get("requested_at", ""),
                            "reported_status": row.get("reported_status", ""),
                            "reported_at": row.get("reported_at", ""),
                            "audit_at": row.get("audit_at", ""),
                            "request_text": row.get("request_text", ""),
                        }
            _deletion_requests_cache = requests_data
            break
        except FileNotFoundError:
            continue
    return _deletion_requests_cache


def load_output_data():
    """Load and parse the output.csv file with email lookup from deletion_requests.csv."""
    all_cases = _get_deletion_requests()
    if not all_cases:
        results = []
        try:
            with open(OUTPUT_CSV_PATH, encoding="utf-8", errors="replace") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    case_id = row.get("case_id", "")
                    deletion_status = row.get("deletion_status", "")
                    steps_json = row.get("steps_json", "[]")
                    try:
                        steps = json.loads(steps_json) if steps_json else []
                    except json.JSONDecodeError:
                        steps = []
                    results.append({
                        "case_id": case_id,
                        "email": "",
                        "deletion_status": deletion_status,
                        "steps_json": steps,
                        "total_steps": len(steps),
                    })
        except FileNotFoundError:
            pass
        return results

    # Build result set from deletion_requests data, supplementing with steps from output.csv
    # First, load output.csv steps and deletion_status data keyed by case_id
    steps_by_case = {}
    deletion_status_by_case = {}
    try:
        with open(OUTPUT_CSV_PATH, encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                case_id = row.get("case_id", "")
                steps_json = row.get("steps_json", "[]")
                deletion_status = row.get("deletion_status", "")
                try:
                    steps = json.loads(steps_json) if steps_json else []
                except json.JSONDecodeError:
                    steps = []
                steps_by_case[case_id] = steps
                deletion_status_by_case[case_id] = deletion_status
    except FileNotFoundError:
        pass

    # Build result set from deletion_requests data, supplemented with output.csv data
    results = []
    for case_id, req in all_cases.items():
        steps = steps_by_case.get(case_id, [])
        # Use output.csv deletion_status as the primary audit status
        audit_status = deletion_status_by_case.get(case_id, req["reported_status"])
        deletion_status = audit_status  # Use audit_status as deletion_status too
        
        results.append({
            "case_id": case_id,
            "email": req["email"],
            "deletion_status": deletion_status,
            "audit_status": audit_status,
            "step_count": len(steps),
            "steps": steps,
            "requested_at": req["requested_at"],
            "reported_at": req["reported_at"],
            "request_text": req["request_text"],
        })
    return results


def filter_cases(status_filter: Optional[str] = None, search: str = ""):
    """Load and optionally filter cases by status and search."""
    all_cases = load_output_data()

    # Apply status filter
    if status_filter and status_filter != "All":
        all_cases = [c for c in all_cases if c["deletion_status"] == status_filter]

    # Apply search filter
    if search:
        search_lower = search.lower()
        all_cases = [
            c for c in all_cases
            if search_lower in c["case_id"].lower()
            or search_lower in c["email"].lower()
        ]

    return all_cases


# ------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------

app = FastAPI(title="Northstar Deletion Auditor", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
async def get_home():
    """Serve the Enterprise Security Console UI."""
    return HTML_TEMPLATE


@app.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint."""
    return HealthResponse(status="ok", service="northstar-deletion-auditor")


@app.get("/api/cases", response_model=dict)
def get_cases(
    status: Optional[str] = None,
    search: str = "",
    page: int = 1,
    per_page: int = 50,
):
    """
    Returns paginated/filtered list of cases from output.csv and dataset/.
    
    Parameters:
        - status: Filter by ALL, COMPLETE, INCOMPLETE, NOT_APPLICABLE
        - search: Search by case_id, email, or keyword
        - page: Page number (1-indexed)
        - per_page: Items per page
    """
    all_cases = load_output_data()

    # Apply status filter
    if status and status != "ALL":
        all_cases = [c for c in all_cases if c["audit_status"] == status.upper()]
    
    # Apply search filter
    if search:
        search_lower = search.lower()
        all_cases = [
            c for c in all_cases
            if search_lower in c["case_id"].lower()
            or search_lower in c["email"].lower()
        ]

    # Compute counts
    total = len(all_cases)
    counts = {
        "total": total,
        "complete": sum(1 for c in all_cases if c["audit_status"] == "COMPLETE"),
        "incomplete": sum(1 for c in all_cases if c["audit_status"] == "INCOMPLETE"),
        "not_applicable": sum(1 for c in all_cases if c["audit_status"] == "NOT_APPLICABLE"),
    }

    # Pagination
    start = (page - 1) * per_page
    end = start + per_page
    paginated = all_cases[start:end]

    return {
        "total": counts["total"],
        "counts": counts,
        "cases": [
            {
                "case_id": c["case_id"],
                "email": c["email"] or "",
                "reported_status": c["deletion_status"],
                "audit_status": c["audit_status"],
                "step_count": c["step_count"],
                "steps": c["steps"],
            }
            for c in paginated
        ],
    }


@app.get("/api/cases/{case_id}", response_model=dict)
def get_case_detail(case_id: str):
    """
    Returns full identity, timeline, and steps details for a specific case.
    """
    case = None
    all_cases = load_output_data()
    for c in all_cases:
        if c["case_id"] == case_id:
            case = c
            break

    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    steps = case["steps"] if case["steps"] else []

    # Build identity info from deletion_requests email and user_id
    # The deletion_requests data already has the email
    email = case["email"] or ""
    user_id = case_id  # fallback

    # Try to get historical emails from user_audit_log.csv
    historical_emails = []
    try:
        audit_path = os.path.join(DATASET_DIR, "user_audit_log.csv")
        with open(audit_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if case_id in line:
                    parts = line.strip().split(",")
                    if len(parts) >= 2 and parts[1] not in historical_emails:
                        historical_emails.append(parts[1])
    except FileNotFoundError:
        pass

    # Get account resources from evidence files
    account_resources = []
    try:
        evidence_path = os.path.join(DATASET_DIR, "evidence_files.csv")
        with open(evidence_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if case_id in line:
                    parts = line.strip().split(",")
                    if len(parts) >= 1:
                        rid = parts[0].replace("account_", "").replace("evidence_", "")
                        if rid and rid not in account_resources:
                            account_resources.append(rid)
    except FileNotFoundError:
        pass

    # Build timeline from system activity
    timeline = []
    try:
        activity_path = os.path.join(DATASET_DIR, "system_activity.csv")
        with open(activity_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if case_id in line:
                    parts = line.strip().split(",")
                    if len(parts) >= 3:
                        timeline.append({
                            "event": parts[0] if parts else "activity",
                            "timestamp": parts[1] if len(parts) > 1 else "",
                            "detail": parts[2] if len(parts) > 2 else "",
                        })
    except FileNotFoundError:
        pass

    timeline.sort(key=lambda x: x.get("timestamp", ""))

    # Compute deletion_status and audit_status
    deletion_status = case["deletion_status"]
    audit_status = case["audit_status"]

    return {
        "case_id": case_id,
        "email": email,
        "historical_emails": historical_emails,
        "account_resources": account_resources,
        "steps": steps,
        "deletion_status": deletion_status,
        "audit_status": audit_status,
        "audit_at": timeline[-1].get("timestamp", "") if timeline else "",
        "timeline": timeline,
    }


@app.post("/api/audit")
def live_audit(request: dict):
    """
    Live sandbox audit endpoint.
    Accepts a custom request text, selects simulated system activities,
    and triggers a live audit evaluation displaying instant results and reasoning.
    """
    request_text = request.get("request_text", "")
    activity = request.get("activity", "")
    identifier = request.get("identifier", "")

    # Build a minimal request row from the sandbox input
    row = {"request_id": f"sandbox_{int(__import__('time').time() * 1000)}"}
    if identifier:
        row["identifier"] = identifier
    if request_text:
        row["request_text"] = request_text
    if activity:
        row["activity_context"] = activity

    auditor = get_auditor()
    try:
        result = auditor.process_deletion_request(row)
    except HTTPException:
        raise
    except Exception as exc:
        log_error(f"Live audit failed: {exc}")
        return JSONResponse(
            status_code=500,
            content={"status": "ERROR", "detail": str(exc), "request_id": row.get("request_id", "")}
        )

    return {
        "request_id": str(result.get("request_id", row.get("request_id", "unknown"))),
        "status": str(result.get("status", "UNKNOWN")),
        "exposed_records": result.get("exposed_records", []),
        "active_sync_risks": result.get("active_sync_risks", []),
        "remediation_steps": result.get("remediation_steps", []),
    }


# ------------------------------------------------------------------
# Static UI template (TailwindCSS from CDN, zero npm build overhead)
# ------------------------------------------------------------------

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Northstar Deletion Audit — Compliance Console</title>

    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap"
          rel="stylesheet">

    <style>
        :root {
            --bg: #0f0f0f;
            --bg-subtle: #18181b;
            --fg: #f0f0f0;
            --muted: #737373;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-crimson: #ef4444;
            --border: #3f3f46;
            --card: #1f1f23;
            --radius: 8px;
        }

        * { box-sizing: border-box; }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            color: var(--fg);
            margin: 0;
            min-height: 100vh;
        }

        .mono { font-family: 'SF Mono', 'Courier New', Courier, monospace; }

        .bg-zinc-950 { background-color: #0f0f0f !important; }
        .bg-zinc-800 { background-color: #18181b !important; }
        .bg-zinc-100 { background-color: #f0f0f0 !important; }
        .text-zinc-100 { color: #f0f0f0 !important; }
        .text-zinc-400 { color: #737373 !important; }
        .text-zinc-500 { color: #52525b !important; }
        .border-zinc-800 { border-color: #3f3f46 !important; }

        .pulse-emerald { animation: pulse-emerald 2s ease-in-out infinite; }
            @keyframes pulse-emerald { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

        .fade-in { animation: fade-in 0.5s ease-out forwards; }
            @keyframes fade-in { from { opacity: 0; transform: translateY(10px); }
                               to { opacity: 1; transform: translateY(0); } }

        .status-pill {
            padding: 2px 6px; border-radius: 10px; font-size: 0.7em; font-weight: 500;
        }
        .status-complete { background-color: #059669; color: white; }
        .status-incomplete { background-color: #d97706; color: white; }
        .status-not-applicable { background-color: #6b7280; color: white; }

        .search-input {
            @apply transition-all duration-200 w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2 text-zinc-100 mono focus-outline-none;
        }
        .search-input:focus {
            @apply outline-none border-emerald-500 shadow-emerald-glow;
        }
        .search-input::placeholder { @apply text-zinc-500; }

        .status-badge {
            @apply inline-flex items-center rounded-full px-3 py-1.5 text-sm font-medium;
        }
        .status-complete { @apply bg-emerald-600/20 text-emerald-400 border border-emerald-600; }
        .status-incomplete { @apply bg-amber-600/20 text-amber-400 border border-amber-600; }
        .status-not-applicable { @apply bg-zinc-700/50 text-zinc-400 border border-zinc-600; }

        .table-row:hover { @apply bg-zinc-900; }

        .drawer-panel {
            @apply fixed inset-0 z-50 flex fixed left-0 inset-y-0 w-80 bg-zinc-950 border-r border-zinc-800
                   transform translate-x-full transition-transform duration-300;
        }
        .drawer-panel.open { @apply translate-x-0; }

        *:focus-visible { @apply outline-none ring-2 ring-emerald-500/40; }

        .scale-in { animation: scale-in 0.3s ease-out forwards; opacity: 0; }
            @keyframes scale-in { from { transform: scale(0.95); opacity: 0; }
                                  to { transform: scale(1); opacity: 1; } }
        .fade-slide { animation: fade-slide 0.4s ease-out forwards; }
            @keyframes fade-slide { from { opacity: 0; transform: translateY(20px); }
                                    to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="antialiased">

<!-- Navigation / Top Metric Bar -->
<nav class="bg-zinc-950 border-zinc-800 border-b sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-6 py-3">
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
                <span class="text-zinc-400 text-sm font-medium">Northstar Deletion Audit</span>
                <span class="text-zinc-500 text-xs" id="compliance-engine">
                    Compliance Engine: Deterministic Replay + NVIDIA NIM Arbiter
                </span>
            </div>
            <div class="flex items-center gap-6">
                <div class="flex items-center gap-2">
                    <span class="text-zinc-400 text-xs">Total Monitored:</span>
                    <span class="status-pill status-complete pulse-emerald" id="total-count">0</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-zinc-400 text-xs">COMPLETE:</span>
                    <span class="status-pill status-complete" id="complete-count">0</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-zinc-400 text-xs">INCOMPLETE:</span>
                    <span class="status-pill status-incomplete" id="incomplete-count">0</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="text-zinc-400 text-xs">NOT_APPLICABLE:</span>
                    <span class="status-pill status-not-applicable" id="not-applicable-count">0</span>
                </div>
            </div>
        </div>
    </div>
</nav>

<!-- Main content -->
<main class="max-w-7xl mx-auto p-6 pb-12">

    <!-- Search & Filter Bar -->
    <div class="bg-zinc-800 rounded-xl p-4 mb-6 border-zinc-700 mb-8">
        <div class="flex gap-3">
            <div class="flex-1">
                <input 
                    type="text" 
                    id="case-search" 
                    placeholder="Search by case_id, email, or keyword..."
                    class="search-input w-full"
                >
            </div>
            <button id="filter-all" class="btn-filter px-4 py-2 rounded-lg text-zinc-400 
                       hover:text-zinc-100 hover:bg-zinc-700 transition-colors">
                All (<span id="filter-all-count">0</span>)
            </button>
        </div>
        <div class="mt-3 flex gap-1">
            <button class="filter-tab px-3 py-1 rounded text-xs text-zinc-400 hover:text-zinc-100
                       hover:bg-zinc-700 transition-colors bg-zinc-700 text-zinc-100 complete">COMPLETE</button>
            <button class="filter-tab px-3 py-1 rounded text-xs text-zinc-400 hover:text-zinc-100
                       hover:bg-zinc-700 transition-colors incomplete">INCOMPLETE</button>
            <button class="filter-tab px-3 py-1 rounded text-xs text-zinc-400 hover:text-zinc-100
                       hover:bg-zinc-700 transition-colors not-applicable">NOT_APPLICABLE</button>
        </div>
    </div>

    <!-- Cases Table -->
    <div class="bg-zinc-800 rounded-xl overflow-hidden border-zinc-700">
        <table class="w-full min-w-[800px]">
            <thead class="bg-zinc-950">
                <tr>
                    <th class="px-6 py-3 text-left text-zinc-400 text-xs font-medium uppercase tracking-wider">
                        Case ID
                    </th>
                    <th class="px-6 py-3 text-left text-zinc-400 text-xs font-medium uppercase tracking-wider">
                        Requester Email
                    </th>
                    <th class="px-6 py-3 text-left text-zinc-400 text-xs font-medium uppercase tracking-wider">
                        Reported Status vs Audit Status
                    </th>
                    <th class="px-6 py-3 text-left text-zinc-400 text-xs font-medium uppercase tracking-wider">
                        Total Steps
                    </th>
                    <th class="px-6 py-3 text-left text-zinc-400 text-xs font-medium uppercase tracking-wider">
                        Action
                    </th>
                </tr>
            </thead>
            <tbody id="cases-table">
                <!-- Rows injected by JS -->
            </tbody>
        </table>
    </div>

</main>

<!-- Case Inspector Drawer -->
<div id="case-drawer" class="drawer-panel" role="dialog" aria-modal="true">
    <div class="p-6 pt-8">
        <button
            id="close-drawer"
            class="absolute top-4 right-4 text-zinc-400 hover:text-zinc-100 transition-colors"
            aria-label="Close drawer"
        >
            ✕
        </button>
        <div id="drawer-content">
            <!-- Content injected by JS -->
        </div>
    </div>
</div>

<!-- Live Deletion Sandbox -->
<div id="sandbox-overlay" class="fixed inset-0 z-40 bg-black/60 hidden items-center justify-center">
    <div class="bg-zinc-800 rounded-xl p-8 max-w-lg w-full border-zinc-700">
        <h2 class="text-xl font-bold text-zinc-100 mb-4">Live Deletion Sandbox</h2>
        <form id="sandbox-form">
            <div class="mb-4">
                <textarea
                    id="sandbox-request"
                    rows="3"
                    placeholder="Paste custom audit request text..."
                    class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-zinc-100 mono resize-none
                           focus:outline-none focus:border-emerald-500"
                ></textarea>
            </div>
            <div class="mb-4">
                <select id="sandbox-activity" class="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2 text-zinc-100 mb-3">
                    <option value="REPORT_REMAINING_RECORD">REPORT_REMAINING_RECORD</option>
                    <option value="DELETE_RECORD">DELETE_RECORD</option>
                    <option value="VERIFY_RECORD_ABSENT">VERIFY_RECORD_ABSENT</option>
                    <option value="SYNC_JOB">SYNC_JOB</option>
                </select>
                <label class="text-sm text-zinc-400 mb-2">System Activity</label>
            </div>
            <button type="submit" class="w-full bg-emerald-600 text-white py-3 rounded-lg
                       hover:bg-emerald-700 transition-colors">
                Run Audit
            </button>
        </form>
        <div id="sandbox-results" class="mt-6 p-4 rounded-lg hidden"></div>
        <button
            id="close-sandbox"
            class="absolute top-4 right-4 text-zinc-400 hover:text-zinc-100 transition-colors"
            aria-label="Close sandbox"
        >
            ✕
        </button>
    </div>
</div>

<script>
    // Initial data load and rendering
    let allCases = [];
    let currentFilter = "All";
    let currentSearch = "";

    // Fetch cases from API
    async function fetchCases() {
        const statusParam = currentFilter !== "All" ? currentFilter : "ALL";
        const searchParam = currentSearch !== "" ? encodeURIComponent(currentSearch) : "";
        
        const url = `/api/cases?status=${statusParam}&search=${searchParam}&page=1&per_page=50`;
        const response = await fetch(url);
        const data = await response.json();
        
        allCases = data.cases || [];
        const counts = data.counts || { total: 0, complete: 0, incomplete: 0, not_applicable: 0 };
        
        // Update metric counters
        document.getElementById("total-count").textContent = counts.total || 0;
        document.getElementById("complete-count").textContent = counts.complete || 0;
        document.getElementById("incomplete-count").textContent = counts.incomplete || 0;
        document.getElementById("not-applicable-count").textContent = counts.not_applicable || 0;
        document.getElementById("filter-all-count").textContent = counts.total || 0;
        
        const tbody = document.getElementById("cases-table");
        tbody.innerHTML = "";
        
        allCases.forEach(caseItem => {
            const row = document.createElement("tr");
            row.className = "table-row border-b border-zinc-800 hover:bg-zinc-900 cursor-pointer";
            row.dataset.caseId = caseItem.case_id;
            // Convert audit_status to CSS class (replace underscores with hyphens)
            const statusClass = caseItem.audit_status.toLowerCase().replace(/_/g, "-");
            row.innerHTML = `
                <td class="px-6 py-3 font-medium text-zinc-100">${caseItem.case_id}</td>
                <td class="px-6 py-3 text-zinc-400 mono">${caseItem.email || "N/A"}</td>
                <td class="px-6 py-3">
                    <span class="status-badge status-${statusClass}">
                        ${caseItem.audit_status}
                    </span>
                </td>
                <td class="px-6 py-3 text-zinc-500 mono">${caseItem.step_count}</td>
                <td class="px-6 py-3">
                    <button class="view-case-btn text-emerald-400 text-sm hover:underline">Inspect</button>
                </td>
            `;
            tbody.appendChild(row);
        });
        
        updateFilterActiveStates();
    }

    function updateFilterActiveStates() {
        document.querySelectorAll(".filter-tab").forEach(btn => {
            btn.classList.remove("bg-zinc-700", "text-zinc-100");
        });
        // Highlight the active filter tab
        if (currentFilter === "All") {
            // Don't highlight any specific tab when "All" is selected
        } else {
            const activeBtn = document.querySelector(`.filter-tab.${currentFilter.toLowerCase()}`);
            if (activeBtn) {
                activeBtn.classList.add("bg-zinc-700", "text-zinc-100");
            }
        }
    }

    window.filterByStatus = function(status) {
        currentFilter = status;
        document.querySelectorAll(".filter-tab").forEach(btn => {
            btn.classList.remove("bg-zinc-700", "text-zinc-100");
            if (btn.textContent.trim().toLowerCase() === status.toLowerCase()) {
                btn.classList.add("bg-zinc-700", "text-zinc-100");
            }
        });
        fetchCases();
    };

    document.getElementById("case-search").addEventListener("input", (e) => {
        currentSearch = e.target.value;
        fetchCases();
    });

    document.querySelectorAll(".filter-tab").forEach(btn => {
        btn.addEventListener("click", function() {
            document.querySelectorAll(".filter-tab").forEach(b => {
                b.classList.remove("bg-zinc-700", "text-zinc-100");
            });
            this.classList.add("bg-zinc-700", "text-zinc-100");
            const statusText = this.textContent.trim();
            // Map tab text to status parameter
            if (statusText === "COMPLETE" || statusText === "INCOMPLETE" || statusText === "NOT_APPLICABLE") {
                currentFilter = statusText;
            } else {
                currentFilter = "All";
            }
            fetchCases();
        });
    });

    // Handle All filter button click
    document.getElementById("filter-all").addEventListener("click", function() {
        currentFilter = "All";
        document.querySelectorAll(".filter-tab").forEach(b => {
            b.classList.remove("bg-zinc-700", "text-zinc-100");
        });
        fetchCases();
    });

    // View case drawer
    document.getElementById("cases-table").addEventListener("click", (e) => {
        if (e.target.classList.contains("view-case-btn")) {
            const row = e.target.closest("tr");
            const caseId = row.dataset.caseId;
            openCaseDrawer(caseId);
        }
    });

    function openCaseDrawer(caseId) {
        fetch(`/api/cases/${caseId}`)
            .then(response => response.json())
            .then(caseDetail => {
                const drawer = document.getElementById("case-drawer");
                const content = document.getElementById("drawer-content");
                
                const stepsHtml = caseDetail.steps.map((step, idx) => {
                    const phase = step.phase || "FINDING";
                    const operation = step.operation || "unknown";
                    const resourceId = step.resource_id || "N/A";
                    const evidenceId = step.evidence_id || "N/A";
                    const state = step.state || "N/A";
                    return `
                        <details class="mt-3">
                            <summary class="text-sm text-zinc-300 cursor-pointer transition-colors">
                                Phase ${step.step_no || idx + 1}: ${phase} - ${operation}
                            </summary>
                            <div class="mt-2 text-zinc-400 text-sm">
                                <p><strong>System ID:</strong> ${step.system_id || "N/A"}</p>
                                <p><strong>Resource ID:</strong> ${resourceId}</p>
                                <p><strong>State:</strong> ${state}</p>
                                <p><strong>Evidence ID:</strong> ${evidenceId}</p>
                            </div>
                        </details>
                    `;
                }).join("");
                
                const accountResourcesHtml = caseDetail.account_resources.map((res, idx) => 
                    `<div class="mt-1 text-zinc-400 text-xs">${res}</div>`
                ).join("");
                
                const historicalEmailsHtml = caseDetail.historical_emails.map((email, idx) => 
                    `<div class="mt-1 text-zinc-400 text-xs">${email}</div>`
                ).join("");
                
                const timelineHtml = caseDetail.audit_at ?
                    `<div class="mt-3 text-zinc-500 text-sm">Audit completed: ${caseDetail.audit_at}</div>` : "";
                
                const evidenceChips = caseDetail.steps.map(step => {
                    const evidenceId = step.evidence_id || "N/A";
                    const resourceId = step.resource_id || "N/A";
                    return `<span class="bg-zinc-800 text-zinc-300 text-xs px-2 py-1 rounded">${evidenceId}</span>`;
                }).join("");
                
                content.innerHTML = `
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <h3 class="text-zinc-300 text-semibold mb-4">
                                Identity Resolution Card
                            </h3>
                            <div class="bg-zinc-900 rounded-lg p-4 mb-6">
                                <p class="text-zinc-400 text-sm mb-2">
                                    <strong>Canonical User ID:</strong> ${caseDetail.case_id}
                                </p>
                                <p class="text-zinc-400 text-sm mb-2">
                                    <strong>Current Email:</strong> ${caseDetail.email || "N/A"}
                                </p>
                                <p class="text-zinc-500 text-xs">
                                    <strong>Historical Emails:</strong>
                                </p>
                                <div>
                                    ${historicalEmailsHtml}
                                </div>
                                <p class="text-zinc-500 text-sm">
                                    <strong>Linked Account Resources:</strong>
                                </p>
                                <div>
                                    ${accountResourcesHtml}
                                </div>
                            </div>
                            
                            <div class="mt-6">
                                <h4 class="text-zinc-300 text-semibold mb-3">
                                    System Timeline Reconstruction
                                </h4>
                                <div class="space-y-2 text-zinc-400 text-sm">
                                    ${timelineHtml}
                                    ${caseDetail.steps.length > 0 ? `
                                        <p class="text-zinc-500 text-xs">
                                            Operational events up to audit completion.
                                        </p>
                                    ` : ""}
                                </div>
                            </div>
                        </div>
                        
                        <div>
                            <h3 class="text-zinc-300 text-semibold mb-4">
                                Canonical Step Sequence Tree
                            </h4>
                            <div class="space-y-3 text-zinc-400">
                                ${stepsHtml}
                            </div>
                            <div class="mt-6 p-4 bg-zinc-900 rounded-lg">
                                <h4 class="text-zinc-300 text-semibold mb-2">
                                    Evidence Link Chips
                                </h4>
                                <div class="flex flex-wrap gap-2">
                                    ${evidenceChips}
                                </div>
                                <button
                                    class="mt-3 w-full text-sm text-emerald-400 hover underline"
                                    onclick="copyCaseJSON()"
                                >
                                    Copy JSON
                                </button>
                            </div>
                        </div>
                    </div>
                `;
                
                drawer.classList.add("open");
                document.body.style.overflow = "hidden";
            })
            .catch(err => {
                console.error("Failed to load case details:", err);
                alert("Failed to load case details. Please try again.");
            });
    }

    function copyCaseJSON() {
        const searchBtn = event.target;
        const row = searchBtn.closest("tr");
        const caseId = row.dataset.caseId;
        
        fetch(`/api/cases/${caseId}`)
            .then(response => response.json())
            .then(data => {
                navigator.clipboard.writeText(JSON.stringify(data, null, 2))
                    .then(() => {
                        alert("Case JSON copied to clipboard!");
                    })
                    .catch(() => {
                        const textarea = document.createElement("textarea");
                        textarea.value = JSON.stringify(data, null, 2);
                        document.body.appendChild(textarea);
                        textarea.select();
                        document.execCommand("copy");
                        document.body.removeChild(textarea);
                        alert("Case JSON copied to clipboard!");
                    });
            })
            .catch(err => {
                console.error("Failed to copy JSON:", err);
                alert("Failed to copy case JSON.");
            });
    }

    document.getElementById("close-drawer").addEventListener("click", closeCaseDrawer);
    document.getElementById("case-drawer").addEventListener("click", (e) => {
        if (e.target === document.getElementById("case-drawer")) closeCaseDrawer();
    });

    function closeCaseDrawer() {
        const drawer = document.getElementById("case-drawer");
        drawer.classList.remove("open");
        document.body.style.overflow = "";
    }

    // Live Deletion Sandbox
    document.getElementById("sandbox-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        
        const requestText = document.getElementById("sandbox-request").value;
        const activity = document.getElementById("sandbox-activity").value;
        
        const submitBtn = e.target.querySelector("button[type='submit']");
        submitBtn.disabled = true;
        submitBtn.textContent = "Running...";
        
        const response = await fetch("/api/audit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ request_text: requestText, activity: activity })
        });
        
        const result = await response.json();
        submitBtn.disabled = false;
        submitBtn.textContent = "Run Audit";
        
        const resultsDiv = document.getElementById("sandbox-results");
        resultsDiv.classList.remove("hidden");
        
        if (result.status === "COMPLETE") {
            resultsDiv.classList.add("bg-emerald-600/20", "text-emerald-400");
            resultsDiv.classList.remove("bg-amber-600/20", "text-amber-400");
        } else {
            resultsDiv.classList.add("bg-amber-600/20", "text-amber-400");
            resultsDiv.classList.remove("bg-emerald-600/20", "text-emerald-400");
        }
        
        resultsDiv.innerHTML = `
            <p><strong>Status:</strong> 
                <span class="font-medium status-pill ${result.status.toLowerCase().replace(" ", "-")}">
                    ${result.status}
                </span>
            </strong></p>
            <p><strong>Exposed Records:</strong> ${JSON.stringify(result.exposed_records || [])}</p>
            <p><strong>Active Sync Risks:</strong> ${JSON.stringify(result.active_sync_risks || [])}</p>
            <p><strong>Remediation Steps:</strong> ${JSON.stringify(result.remediation_steps || [])}</p>
        `;
    });
    
    document.getElementById("close-sandbox").addEventListener("click", () => {
        document.getElementById("sandbox-overlay").classList.add("hidden");
    });

    // Initialize
    fetchCases();
</script>
</body>
</html>
"""

# ------------------------------------------------------------------
# Startup behavior
# ------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Log startup information and verify data integrity."""
    logger.info("Northstar Deletion Auditor starting up")
    logger.info("Compliance Engine: Deterministic Replay + NVIDIA NIM Arbiter")
    
    # Verify output.csv integrity
    try:
        with open(OUTPUT_CSV_PATH, encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
            logger.info(f"Verified output.csv: {len(rows)} cases loaded")
            deletation_count = sum(1 for row in rows if "DELETATION" in row.get("deletion_status", "").upper())
            logger.info(f"DELETATION occurrences in output.csv: {deletation_count}")
    except Exception as e:
        logger.warning(f"Could not verify output.csv: {e}")
    
    # Verify dataset accessibility
    if os.path.isdir(DATASET_DIR):
        logger.info(f"Dataset directory accessible: {DATASET_DIR}")
    else:
        logger.warning(f"Dataset directory not found: {DATASET_DIR}")


if __name__ == "__main__":
    import uvicorn
    import time
    uvicorn.run(app, host="127.0.0.1", port=8000)