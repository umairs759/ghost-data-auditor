"""Reconstruction Engine - Replays system_activity.csv per user identity up to audit_at.

Replays system_activity.csv per user identity up to the timestamp audit_at.
Cross-references with deletion_rules.csv to evaluate whether each remaining record
is legally retained or an illegal leak. Detects restore risks from backups and active
data sync pipelines.
"""

import csv
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from .identity_engine import (
    resolve_identifiers,
    get_all_identities_for_email,
)


# --------------------------------------------------------------------------- #
# Event types we track
# --------------------------------------------------------------------------- #
TRACKED_EVENT_TYPES = {
    "DELETE_RECORD",
    "REDACT_RECORD",
    "ANONYMIZE_RECORD",
    "DISABLE_DATA_FLOW",
    "BLOCK_RESTORE",
    "SYNC_RECORD",
    "LINK_RESOURCE_IDENTITY",
}


def load_system_activity(dataset_dir: str) -> List[dict]:
    """Load system_activity.csv into a list of dicts."""
    path = os.path.join(dataset_dir, "system_activity.csv")
    rows = []
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def load_deletion_rules(dataset_dir: str) -> List[dict]:
    """Load deletion_rules.csv into a list of dicts."""
    path = os.path.join(dataset_dir, "deletion_rules.csv")
    rows = []
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def parse_event_time(time_str: str) -> datetime:
    """Parse an ISO-8601 timestamp string to a datetime object."""
    # Handle Z suffix
    time_str = time_str.strip()
    if time_str.endswith("Z"):
        time_str = time_str[:-1] + "+00:00"
    return datetime.fromisoformat(time_str)


def is_within_audit_at(event_time: datetime, audit_at: datetime) -> bool:
    """Check if event_time is <= audit_at."""
    return event_time <= audit_at


def evaluate_deletion_status(
    resource_id: str,
    event_type: str,
    system_id: str,
    audit_at: datetime,
    system_activity: List[dict],
    deletion_rules: List[dict],
) -> Tuple[str, str, str]:
    """Evaluate the deletion status of a resource at audit_at.

    Returns:
        (state, reason, applicable_rule)
        state: One of "PRESENT", "ABSENT", "REDACTED", "ANONYMIZED", "DISABLED", "BLOCKED"
    """
    # Find all relevant events for this resource up to audit_at
    relevant_events = []
    for evt in system_activity:
        # Must be related to this resource
        if evt.get("resource_id", "") == resource_id:
            evt_time = parse_event_time(evt.get("event_time", ""))
            if is_within_audit_at(evt_time, audit_at):
                if evt.get("event_type", "") == event_type:
                    relevant_events.append(evt)

    # Also check LINK_RESOURCE_IDENTITY events that might link to this resource
    # We'll handle that at a higher level

    if not relevant_events:
        # No deletion events found - record is still PRESENT
        # Check if there are any events at all
        any_events = False
        for evt in system_activity:
            if evt.get("resource_id", "") == resource_id:
                any_events = True
                break
        if any_events:
            # There are events but none are the specific type we're looking for
            # Check deletion rules
            for rule in deletion_rules:
                if rule.get("data_category", "") == resource_id.split("_")[-1] if "_" in resource_id else resource_id:
                    if rule.get("condition", "") == "Always":
                        if rule.get("required_action", "") == "DELETE":
                            # Rule says delete but no events found = leak
                            return "ABSENT", "No delete events found - potential leak", rule.get("rule_id", "")
        return "PRESENT", "No relevant deletion events found", ""


    # Sort events by time (chronological)
    relevant_events.sort(key=lambda e: parse_event_time(e.get("event_time", "")))

    # Find the latest DELETE_RECORD
    latest_delete = None
    latest_redact = None
    latest_anonymize = None
    latest_disable_flow = None
    latest_block_restore = None

    for evt in relevant_events:
        etype = evt.get("event_type", "")
        if etype == "DELETE_RECORD":
            latest_delete = evt
        elif etype == "REDACT_RECORD":
            latest_redact = evt
        elif etype == "ANONYMIZE_RECORD":
            latest_anonymize = evt
        elif etype == "DISABLE_DATA_FLOW":
            latest_disable_flow = evt
        elif etype == "BLOCK_RESTORE":
            latest_block_restore = evt

    # Determine state based on latest events
    # Priority: if DELETE_RECORD exists -> ABSENT
    if latest_delete:
        return "ABSENT", "Record deleted", latest_delete.get("rule_id", "")

    # If REDACT_RECORD exists -> REDACTED
    if latest_redact:
        return "REDACTED", "Record redacted", latest_redact.get("rule_id", "")

    # If ANONYMIZE_RECORD exists -> ANONYMIZED
    if latest_anonymize:
        return "ANONYMIZED", "Record anonymized", latest_anonymize.get("rule_id", "")

    # If DISABLE_DATA_FLOW exists -> DISABLED
    if latest_disable_flow:
        return "DISABLED", "Data flow disabled", latest_disable_flow.get("rule_id", "")

    # If BLOCK_RESTORE exists -> BLOCKED
    if latest_block_restore:
        return "BLOCKED", "Restore blocked", latest_block_restore.get("rule_id", "")

    # No deletion events found - record is still PRESENT
    return "PRESENT", "Record still present", ""


def detect_restore_risks(
    resource_id: str,
    audit_at: datetime,
    system_activity: List[dict],
) -> Dict[str, any]:
    """Detect restore risks from backups and active sync pipelines after deletion.

    Returns:
        dict with 'has_restore_risk', 'has_active_sync', 'restore_events', 'sync_events'
    """
    # Find all events for this resource up to audit_at
    relevant_events = []
    for evt in system_activity:
        if evt.get("resource_id", "") == resource_id:
            evt_time = parse_event_time(evt.get("event_time", ""))
            if is_within_audit_at(evt_time, audit_at):
                relevant_events.append(evt)

    # Sort by time
    relevant_events.sort(key=lambda e: parse_event_time(e.get("event_time", "")))

    has_active_sync = False
    sync_events = []
    restore_events = []

    for evt in relevant_events:
        etype = evt.get("event_type", "")
        if etype == "SYNC_RECORD":
            # Check if sync is active (not blocked/completed)
            reported_result = evt.get("reported_result", "")
            if reported_result in ("ACTIVE", "PENDING", "RUNNING"):
                has_active_sync = True
                sync_events.append(evt)
        elif etype == "BLOCK_RESTORE":
            restore_events.append(evt)
        elif etype == "DELETE_RECORD":
            # Found deletion, now check if there are restore/sync after it
            pass

    # Determine if there's a restore risk: deletion occurred but backup/restore
    # or active sync exists after deletion
    deletion_found = any(
        e.get("event_type", "") == "DELETE_RECORD"
        for e in relevant_events
    )

    has_restore_risk = deletion_found and (has_active_sync or len(restore_events) > 0)

    return {
        "has_restore_risk": has_restore_risk,
        "has_active_sync": has_active_sync,
        "sync_events": sync_events,
        "restore_events": restore_events,
    }


def replay_activities_for_user(
    user_id: str,
    audit_at: datetime,
    system_activity: List[dict],
    deletion_rules: List[dict],
    current_email_to_uids: Dict[str, Set[str]],
    old_email_to_uids: Dict[str, Set[str]],
    phone_to_uids: Dict[str, Set[str]],
) -> Dict[str, any]:
    """Replay all system activities for a given user up to audit_at.

    Returns comprehensive state information about all resources associated with
    this user at the audit timestamp.
    """
    # Find all user identifiers (email, phone, user_id)
    # We need to look up activities related to this user

    # Gather all resource_ids that this user interacts with
    user_resources = set()
    user_events = []

    for evt in system_activity:
        # Check if this event is related to this user
        # Event types that link user identities to resources
        if evt.get("event_type", "") == "LINK_RESOURCE_IDENTITY":
            details = evt.get("details", "")
            # Parse details to find user_id or email
            # Check if user_id appears in details, or if any of the user's current emails appear
            user_email_parts = []
            for eid, uids in current_email_to_uids.items():
                for uid in uids:
                    if uid == user_id:
                        user_email_parts.append(eid)
            # Also check direct user_id match
            if user_id in details or user_email_parts and any(uid in details for uid in user_email_parts) or (details and user_id.split('_')[-1] in details if '_' in user_id else False):
                rid = evt.get("resource_id", "")
                if rid:
                    user_resources.add(rid)
                    user_events.append(evt)

        # Also check source_system and target_system
        # Activities that directly involve this user's resources
        source = evt.get("source_system", "")
        target = evt.get("target_system", "")
        resource = evt.get("resource_id", "")

        # If resource belongs to this user (we'll track by resource patterns)
        if resource and (resource.startswith("user_") or resource.startswith("account_")):
            user_resources.add(resource)
            user_events.append(evt)

    # Also find resources by looking at events where this user's emails appear
    # in details or as target/source

    # Evaluate deletion status for each resource
    resource_states = {}
    restore_risks = {}

    for resource_id in user_resources:
        state, reason, rule = evaluate_deletion_status(
            resource_id, "DELETE_RECORD", "system", audit_at,
            system_activity, deletion_rules
        )
        resource_states[resource_id] = {
            "state": state,
            "reason": reason,
            "rule": rule,
        }

        # Detect restore risks
        risk_info = detect_restore_risks(
            resource_id, audit_at, system_activity
        )
        restore_risks[resource_id] = risk_info

    return {
        "user_id": user_id,
        "audit_at": audit_at.isoformat(),
        "resource_states": resource_states,
        "restore_risks": restore_risks,
        "user_events": user_events,
        "all_resources": user_resources,
    }