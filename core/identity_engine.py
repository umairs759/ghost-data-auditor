"""Identity Engine - Resolves emails/phones/usernames to canonical identity IDs.

Builds a graph or dictionary resolver mapping any email/phone/username/user_id
to the full set of canonical identity IDs using user_identities.csv and historical
entries in user_audit_log.csv.
"""

import csv
import os
from typing import Dict, List, Set, Tuple


def load_user_identities(dataset_dir: str) -> List[dict]:
    """Load user_identities.csv into a list of dicts."""
    path = os.path.join(dataset_dir, "user_identities.csv")
    rows = []
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def load_user_audit_log(dataset_dir: str) -> List[dict]:
    """Load user_audit_log.csv into a list of dicts."""
    path = os.path.join(dataset_dir, "user_audit_log.csv")
    rows = []
    with open(path, encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def build_identity_resolver(dataset_dir: str) -> Tuple[
    Dict[str, Set[str]],  # email (current) -> set of user_ids
    Dict[str, Set[str]],  # email (historical/old) -> set of user_ids
    Dict[str, Set[str]],  # phone -> set of user_ids
    Dict[str, str],       # user_id -> current canonical user_id
    Dict[str, List[str]], # user_id -> set of historical user_ids (aliases)
]:
    """Build identity resolution indexes from user_identities.csv and user_audit_log.csv.

    Returns:
        current_email_to_uids: Maps current email to set of user_ids
        old_email_to_uids: Maps old/historical email to set of user_ids
        phone_to_uids: Maps phone number to set of user_ids
        user_id_to_canonical: Maps user_id to its canonical user_id
        user_id_aliases: Maps user_id to list of alias user_ids
    """
    identities = load_user_identities(dataset_dir)
    audit_log = load_user_audit_log(dataset_dir)

    # Current email -> user_ids
    current_email_to_uids: Dict[str, Set[str]] = {}
    # Old email -> user_ids (from audit log)
    old_email_to_uids: Dict[str, Set[str]] = {}
    # Phone -> user_ids
    phone_to_uids: Dict[str, Set[str]] = {}
    # user_id -> canonical user_id (by highest user_id or most recent)
    user_id_to_canonical: Dict[str, str] = {}
    # user_id -> list of alias user_ids
    user_id_aliases: Dict[str, List[str]] = {}

    # Build from user_identities.csv
    for ident in identities:
        uid = ident.get("user_id", "")
        email = ident.get("email", "")
        phone = ident.get("phone", "")

        if email:
            current_email_to_uids.setdefault(email, set()).add(uid)

        if phone:
            phone_to_uids.setdefault(phone, set()).add(uid)

        # Initialize canonical mapping
        if uid not in user_id_to_canonical:
            user_id_to_canonical[uid] = uid

        # Track aliases
        if uid not in user_id_aliases:
            user_id_aliases[uid] = []

    # Build from user_audit_log.csv - historical emails
    for log_entry in audit_log:
        uid = log_entry.get("user_id", "")
        field = log_entry.get("field_name", "")
        old_val = log_entry.get("old_value", "")
        new_val = log_entry.get("new_value", "")

        if field == "email" and old_val:
            old_email_to_uids.setdefault(old_val, set()).add(uid)
        if field == "email" and new_val:
            # New email becomes current for that point in time
            # We track it as an old email that resolved to the uid
            old_email_to_uids.setdefault(new_val, set()).add(uid)

    # Also add new_val emails to current mapping if they aren't already
    # (handled by user_identities.csv)

    return current_email_to_uids, old_email_to_uids, phone_to_uids, user_id_to_canonical, user_id_aliases


def resolve_identifiers(
    query: str,
    current_email_to_uids: Dict[str, Set[str]],
    old_email_to_uids: Dict[str, Set[str]],
    phone_to_uids: Dict[str, Set[str]],
) -> Set[str]:
    """Resolve a query (email, phone, or username) to a set of user_ids.

    Args:
        query: The email, phone, or user_id to resolve
        current_email_to_uids: Current email -> user_ids mapping
        old_email_to_uids: Old email -> user_ids mapping
        phone_to_uids: Phone -> user_ids mapping

    Returns:
        Set of user_ids matching the query
    """
    resolved: Set[str] = set()

    # Try as current email
    if query in current_email_to_uids:
        resolved.update(current_email_to_uids[query])
    # Try as old/historical email
    elif query in old_email_to_uids:
        resolved.update(old_email_to_uids[query])
    # Try as phone
    elif query in phone_to_uids:
        resolved.update(phone_to_uids[query])
    # Try as user_id directly (format user_XXX)
    else:
        # Check if it looks like a user_id
        if query.startswith("user_") or query.startswith("user"):
            resolved.add(query)

    return resolved


def get_all_identities_for_email(
    email: str,
    current_email_to_uids: Dict[str, Set[str]],
    old_email_to_uids: Dict[str, Set[str]],
    phone_to_uids: Dict[str, Set[str]],
) -> Set[str]:
    """Get all user_ids associated with an email across current and historical records."""
    resolved = set()
    if email in current_email_to_uids:
        resolved.update(current_email_to_uids[email])
    if email in old_email_to_uids:
        resolved.update(old_email_to_uids[email])
    return resolved