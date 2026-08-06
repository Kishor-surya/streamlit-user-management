"""Parses a "User Management Request" GitHub issue and queues the requested
change into data/inbox/*.csv for the running app to pick up (see
inbox_sync.py). Invoked by .github/workflows/user-request.yml with the issue
body and number in the environment.

GitHub Actions has no network path to the deployed Streamlit process, so this
script never touches the live app directly — it only validates the request
and queues it for the app to apply on its next restart.
"""

import csv
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
from utils import EMAIL_RE, PHONE_RE, parse_upload, validate_upload_rows  # noqa: E402

ADD_PATH = ROOT / "data" / "inbox" / "pending_add.csv"
DELETE_PATH = ROOT / "data" / "inbox" / "pending_delete.csv"
ADD_FIELDS = ["full_name", "email", "phone", "age", "department", "role", "status", "source_issue"]
DELETE_FIELDS = ["email", "source_issue"]

SECTION_RE = re.compile(r"^### (.+?)\n+(.*?)(?=\n### |\Z)", re.S | re.M)
ATTACHMENT_RE = re.compile(r"\((https?://\S+?)\)")


def parse_issue_body(body: str) -> dict:
    """Turn a GitHub issue-form body into {field label: submitted value}."""
    fields = {}
    for heading, content in SECTION_RE.findall(body or ""):
        value = content.strip()
        if value == "_No response_":
            value = ""
        fields[heading.strip()] = value
    return fields


def read_csv_rows(path: Path) -> list:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv_rows(path: Path, fieldnames: list, rows: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def queue_add(rows, issue_number, full_name, email, phone, age, department, role, status):
    email = email.strip().lower()
    if any((r.get("email") or "").strip().lower() == email for r in rows):
        return False, f"`{email}` is already queued — skipped as a duplicate."
    rows.append({
        "full_name": full_name.strip(),
        "email": email,
        "phone": phone.strip(),
        "age": age.strip(),
        "department": department.strip(),
        "role": role.strip(),
        "status": status.strip() or "Active",
        "source_issue": str(issue_number),
    })
    return True, f"Queued **{full_name.strip()}** (`{email}`) to be added."


def queue_delete(rows, issue_number, email):
    email = email.strip().lower()
    if any((r.get("email") or "").strip().lower() == email for r in rows):
        return False, f"`{email}` is already queued for deletion — skipped as a duplicate."
    rows.append({"email": email, "source_issue": str(issue_number)})
    return True, f"Queued `{email}` to be removed."


def download_attachment(url: str) -> tuple:
    headers = {"User-Agent": "peopledesk-bot"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    filename = url.rstrip("/").split("/")[-1]
    return resp.content, filename


def _cell(row, col) -> str:
    val = row.get(col)
    if val is None:
        return ""
    try:
        if val != val:  # NaN check without importing pandas here
            return ""
    except TypeError:
        pass
    return str(val).strip()


def process(body: str, issue_number) -> tuple:
    """Returns (changed: bool, success: bool, comment_markdown: str)."""
    db.init_db()
    fields = parse_issue_body(body)
    action = (fields.get("Action") or "").strip().lower()

    add_rows = read_csv_rows(ADD_PATH)
    delete_rows = read_csv_rows(DELETE_PATH)
    changed = False
    lines = []

    if action == "add user":
        full_name = fields.get("Full Name", "")
        email = fields.get("Email", "")
        if not full_name or not email:
            return False, False, "❌ **Add User** requires both **Full Name** and **Email**."
        if not EMAIL_RE.match(email.strip()):
            return False, False, f"❌ `{email}` doesn't look like a valid email address."
        phone = fields.get("Phone", "")
        if phone and not PHONE_RE.match(phone.strip()):
            return False, False, f"❌ `{phone}` doesn't look like a valid phone number."
        ok, msg = queue_add(
            add_rows, issue_number, full_name, email, phone,
            fields.get("Age", ""), fields.get("Department", ""), fields.get("Role", ""), fields.get("Status", ""),
        )
        changed = ok
        lines.append(("✅ " if ok else "⚠️ ") + msg)

    elif action == "delete user":
        email = fields.get("Email", "")
        if not email or not EMAIL_RE.match(email.strip()):
            return False, False, "❌ **Delete User** requires a valid **Email**."
        ok, msg = queue_delete(delete_rows, issue_number, email)
        changed = ok
        lines.append(("✅ " if ok else "⚠️ ") + msg)

    elif action == "bulk upload":
        raw = fields.get("Bulk Upload File", "")
        match = ATTACHMENT_RE.search(raw)
        if not match:
            return False, False, "❌ **Bulk Upload** needs a file attached in the **Bulk Upload File** box."
        try:
            content, filename = download_attachment(match.group(1))
            validated = validate_upload_rows(parse_upload(content, filename))
        except Exception as exc:
            return False, False, f"❌ Couldn't read the attached file: {exc}"

        queued, skipped = 0, 0
        for _, row in validated.iterrows():
            if not bool(row["_valid"]):
                skipped += 1
                continue
            ok, _ = queue_add(
                add_rows, issue_number,
                _cell(row, "full_name"), _cell(row, "email"), _cell(row, "phone"),
                _cell(row, "age"), _cell(row, "department"), _cell(row, "role"), _cell(row, "status"),
            )
            if ok:
                queued += 1
            else:
                skipped += 1
        changed = queued > 0
        lines.append(f"{'✅' if queued else '⚠️'} Queued **{queued}** user(s) for import, skipped **{skipped}**.")

    else:
        readable = fields.get("Action", "")
        return False, False, f"❌ Unrecognized action `{readable}`. Use Add User, Delete User, or Bulk Upload."

    if changed:
        write_csv_rows(ADD_PATH, ADD_FIELDS, add_rows)
        write_csv_rows(DELETE_PATH, DELETE_FIELDS, delete_rows)
        lines.append("\nThis will appear in the live app on its next restart (usually within a couple of minutes).")

    return changed, True, "\n".join(lines)


def main():
    body = os.environ.get("ISSUE_BODY", "")
    issue_number = os.environ.get("ISSUE_NUMBER", "0")

    changed, success, comment = process(body, issue_number)

    Path("issue_comment.md").write_text(comment, encoding="utf-8")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")
            f.write(f"success={'true' if success else 'false'}\n")


if __name__ == "__main__":
    main()
