"""Step Builder - Builds fully ordered, schema-compliant steps_json array.

Takes evaluated findings and builds the fully ordered, schema-compliant steps_json
array adhering strictly to the phase, operation, system_id, and resource_id sort order
as defined in the Canonical Step Ordering Law.

The hierarchy is:
1. Phase Ordering: FINDING -> REMEDIATION -> VERIFICATION
2. Operation Ordering within each phase (strict order)
3. Secondary: system_id ascending, then resource_id ascending
4. Consecutive step_no starting at 1 and incrementing by 1
"""

from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------- #
# Phase constants - defines the strict ordering
# --------------------------------------------------------------------------- #
PHASE_FINDING = "FINDING"
PHASE_REMEDIATION = "REMEDIATION"
PHASE_VERIFICATION = "VERIFICATION"

PHASE_ORDER = [
    PHASE_FINDING,
    PHASE_REMEDIATION,
    PHASE_VERIFICATION,
]

# --------------------------------------------------------------------------- #
# FINDING phase operations - strict order within phase
# --------------------------------------------------------------------------- #
FINDING_OPS = [
    "REPORT_REMAINING_RECORD",
    "REPORT_EXPOSED_PII",
    "REPORT_ACTIVE_DATA_FLOW",
    "REPORT_RESTORE_RISK",
]

# --------------------------------------------------------------------------- #
# REMEDIATION phase operations - strict order within phase
# --------------------------------------------------------------------------- #
REMEDIATION_OPS = [
    "DISABLE_DATA_FLOW",
    "BLOCK_RESTORE",
    "DELETE_RECORD",
    "REDACT_RECORD",
    "ANONYMIZE_RECORD",
]

# --------------------------------------------------------------------------- #
# VERIFICATION phase operations - strict order within phase
# --------------------------------------------------------------------------- #
VERIFICATION_OPS = [
    "VERIFY_RECORD_ABSENT",
    "VERIFY_RECORD_PRESENT",
    "VERIFY_RECORD_REDACTED",
    "VERIFY_RECORD_ANONYMIZED",
    "VERIFY_DATA_FLOW_DISABLED",
    "VERIFY_RESTORE_BLOCKED",
]

# --------------------------------------------------------------------------- #
# Operation -> (phase, state) mapping
# --------------------------------------------------------------------------- #
OPERATION_PHASE_MAP = {}
OPERATION_STATE_MAP = {}

# Populate FINDING operations
for i, op in enumerate(FINDING_OPS, 1):
    OPERATION_PHASE_MAP[op] = PHASE_FINDING
    # State depends on context; we'll set it during step building
    # For FINDING ops, state is typically PRESENT for record/exposure/flow reports
    OPERATION_STATE_MAP[op] = "PRESENT"  # default, may be overridden

# Populate REMEDIATION operations
for i, op in enumerate(REMEDIATION_OPS, 1):
    OPERATION_PHASE_MAP[op] = PHASE_REMEDIATION
    # States are operation-specific
    if op == "DISABLE_DATA_FLOW":
        OPERATION_STATE_MAP[op] = "DISABLED"
    elif op == "BLOCK_RESTORE":
        OPERATION_STATE_MAP[op] = "BLOCKED"
    elif op == "DELETE_RECORD":
        OPERATION_STATE_MAP[op] = "ABSENT"
    elif op == "REDACT_RECORD":
        OPERATION_STATE_MAP[op] = "REDACTED"
    elif op == "ANONYMIZE_RECORD":
        OPERATION_STATE_MAP[op] = "ANONYMIZED"

# Populate VERIFICATION operations
for i, op in enumerate(VERIFICATION_OPS, 1):
    OPERATION_PHASE_MAP[op] = PHASE_VERIFICATION
    if op == "VERIFY_RECORD_ABSENT":
        OPERATION_STATE_MAP[op] = "ABSENT"
    elif op == "VERIFY_RECORD_PRESENT":
        OPERATION_STATE_MAP[op] = "PRESENT"
    elif op == "VERIFY_RECORD_REDACTED":
        OPERATION_STATE_MAP[op] = "REDACTED"
    elif op == "VERIFY_RECORD_ANONYMIZED":
        OPERATION_STATE_MAP[op] = "ANONYMIZED"
    elif op == "VERIFY_DATA_FLOW_DISABLED":
        OPERATION_STATE_MAP[op] = "DISABLED"
    elif op == "VERIFY_RESTORE_BLOCKED":
        OPERATION_STATE_MAP[op] = "BLOCKED"


def get_phase(operation: str) -> str:
    """Get the phase for a given operation."""
    return OPERATION_PHASE_MAP.get(operation, PHASE_VERIFICATION)


def get_state(operation: str) -> str:
    """Get the default state for a given operation."""
    return OPERATION_STATE_MAP.get(operation, "ABSENT")


def build_steps_json(
    case_id: str,
    deletion_status: str,
    findings: List[Dict[str, any]],
    remediations: List[Dict[str, any]],
    verifications: List[Dict[str, any]],
    evidence_id: str = "",
) -> List[Dict[str, any]]:
    """Build the fully ordered, schema-compliant steps_json array.
    
    Args:
        case_id: The case identifier
        deletion_status: COMPLETE, INCOMPLETE, or NOT_APPLICABLE
        findings: List of finding dicts with keys: operation, system_id, resource_id
        remediations: List of remediation dicts with keys: operation, system_id, resource_id
        verifications: List of verification dicts with keys: operation, system_id, resource_id
        evidence_id: Evidence file_id, activity_id, or audit_id for COMPLETE cases
    
    Returns:
        steps_json array sorted by phase -> operation -> system_id -> resource_id
        with consecutive step_no numbering starting at 1
    """
    
    steps = []
    step_no = 1
    
    # Handle NOT_APPLICABLE cases: steps_json must be empty list
    if deletion_status == "NOT_APPLICABLE":
        return []
    
    # Handle cases where steps should be empty (no findings/remediations/verifications)
    # But still need to generate appropriate steps based on state reconstruction
    
    # === PHASE 1: FINDING ===
    finding_steps = []
    for finding in findings:
        operation = finding.get("operation", "")
        system_id = finding.get("system_id", "")
        resource_id = finding.get("resource_id", "")
        
        if operation not in FINDING_OPS:
            continue
        
        # Get the state for this operation
        state = get_state(operation)
        
        # Determine evidence_id for FINDING steps
        # For COMPLETE cases with actual findings, cite valid evidence_id
        finding_evidence = evidence_id if evidence_id else ""
        
        step = {
            "step_no": step_no,
            "phase": PHASE_FINDING,
            "system_id": system_id,
            "resource_id": resource_id,
            "operation": operation,
            "state": state,
            "evidence_id": finding_evidence,
        }
        finding_steps.append(step)
        step_no += 1
    
    # === PHASE 2: REMEDIATION ===
    remediation_steps = []
    for remediation in remediations:
        operation = remediation.get("operation", "")
        system_id = remediation.get("system_id", "")
        resource_id = remediation.get("resource_id", "")
        
        if operation not in REMEDIATION_OPS:
            continue
        
        state = get_state(operation)
        
        # For REMEDIATION steps, evidence_id rules:
        # - COMPLETE cases: valid evidence_id
        # - INCOMPLETE cases: empty string ""
        if deletion_status == "COMPLETE":
            remediation_evidence = evidence_id if evidence_id else ""
        else:  # INCOMPLETE or other
            remediation_evidence = ""
        
        step = {
            "step_no": step_no,
            "phase": PHASE_REMEDIATION,
            "system_id": system_id,
            "resource_id": resource_id,
            "operation": operation,
            "state": state,
            "evidence_id": remediation_evidence,
        }
        remediation_steps.append(step)
        step_no += 1
    
    # === PHASE 3: VERIFICATION ===
    verification_steps = []
    for verification in verifications:
        operation = verification.get("operation", "")
        system_id = verification.get("system_id", "")
        resource_id = verification.get("resource_id", "")
        
        if operation not in VERIFICATION_OPS:
            continue
        
        state = get_state(operation)
        
        # For VERIFICATION steps evidence_id rules:
        # - COMPLETE cases: valid evidence_id
        # - INCOMPLETE cases: empty string ""
        if deletion_status == "COMPLETE":
            verification_evidence = evidence_id if evidence_id else ""
        else:
            verification_evidence = ""
        
        step = {
            "step_no": step_no,
            "phase": PHASE_VERIFICATION,
            "system_id": system_id,
            "resource_id": resource_id,
            "operation": operation,
            "state": state,
            "evidence_id": verification_evidence,
        }
        verification_steps.append(step)
        step_no += 1
    
    # Combine all steps in phase order: FINDING -> REMEDIATION -> VERIFICATION
    all_steps = finding_steps + remediation_steps + verification_steps
    
    # Now sort by the hierarchical order:
    # 1. Phase order (FINDING=0, REMEDIATION=1, VERIFICATION=2) - already handled by ordering
    # 2. Operation order within phase - already preserved from our lists
    # 3. system_id ascending
    # 4. resource_id ascending
    # 5. Consecutive step_no renumbering
    
    # Sort by (phase_order, operation_order, system_id, resource_id)
    # We need to map operations to their order within their phase
    operation_order_map = {}
    for i, op in enumerate(FINDING_OPS, 1):
        operation_order_map[op] = (0, i)  # (phase_order, operation_order)
    for i, op in enumerate(REMEDIATION_OPS, 1):
        operation_order_map[op] = (1, i)
    for i, op in enumerate(VERIFICATION_OPS, 1):
        operation_order_map[op] = (2, i)
    
    def sort_key(step):
        op = step.get("operation", "")
        phase_rank = PHASE_ORDER.index(step.get("phase", PHASE_VERIFICATION))
        op_rank = operation_order_map.get(op, (99, 99))
        return (phase_rank, op_rank, step.get("system_id", ""), step.get("resource_id", ""))
    
    # Sort all steps
    all_steps.sort(key=sort_key)
    
    # Renumber step_no consecutively starting at 1
    for i, step in enumerate(all_steps):
        step["step_no"] = i + 1
    
    return all_steps