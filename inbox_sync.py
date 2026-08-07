"""Applies queued user requests from data/inbox/*.csv into the live database.

The `user-management-request` GitHub Action can't reach the running Streamlit
process directly, so it queues validated rows into these CSVs and commits
them to the repo. This module replays that queue on every app startup.
Replays are idempotent: an add is skipped if the email already exists, and a
delete is a no-op if the user is already gone — so re-running it on every
restart is safe.
"""

import csv
from pathlib import Path

import db

INBOX_DIR = Path(__file__).parent / "data" / "inbox"
PENDING_ADD_PATH = INBOX_DIR / "pending_add.csv"
PENDING_DELETE_PATH = INBOX_DIR / "pending_delete.csv"


def _read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sync_pending_users(
    add_path: Path = PENDING_ADD_PATH,
    delete_path: Path = PENDING_DELETE_PATH,
    on_added=None,
) -> dict:
    """Apply queued adds/deletes. Returns {"added": int, "deleted": int, "notified": int}.

    `on_added`, if given, is called with each newly-added user's dict
    ({"full_name", "email", "department", "role", "status"}) and should
    return True if a notification was sent. Kept as an injected callback,
    not a direct email_service/Streamlit import, so this module stays
    testable without mocking SMTP or secrets.
    """
    added = 0
    notified = 0
    for row in _read_rows(add_path):
        email = (row.get("email") or "").strip().lower()
        full_name = (row.get("full_name") or "").strip()
        if not email or not full_name or db.email_exists(email):
            continue

        department = row.get("department") or ""
        if department not in db.DEPARTMENTS:
            department = db.DEPARTMENTS[0]
        role = row.get("role") or ""
        if role not in db.ROLES:
            role = db.ROLES[0]
        status = row.get("status") or ""
        if status not in db.STATUSES:
            status = "Active"
        age_raw = (row.get("age") or "").strip()
        age = int(age_raw) if age_raw.isdigit() else 0

        db.add_user(full_name, email, (row.get("phone") or "").strip(), age, department, role, status)
        added += 1

        if on_added and on_added(
            {"full_name": full_name, "email": email, "department": department, "role": role, "status": status}
        ):
            notified += 1

    deleted = 0
    for row in _read_rows(delete_path):
        email = (row.get("email") or "").strip().lower()
        if not email:
            continue
        existing = db.get_user_by_email(email)
        if existing:
            db.delete_user(existing["id"])
            deleted += 1

    return {"added": added, "deleted": deleted, "notified": notified}
