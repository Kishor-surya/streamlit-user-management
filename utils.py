"""Pure helper functions for the Streamlit User Management app.

Kept separate from app.py (which runs Streamlit UI code at import time)
so this logic can be unit tested in isolation.
"""

import io
import re

import pandas as pd

import db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+\-\s()]{6,20}$")

USER_COLUMNS = [
    "id", "full_name", "email", "phone", "age",
    "department", "role", "status", "created_at", "updated_at",
]


def to_dataframe(users: list[dict]) -> pd.DataFrame:
    if not users:
        return pd.DataFrame(columns=USER_COLUMNS)
    return pd.DataFrame(users)


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Users")
    return buffer.getvalue()


def validate_user_form(full_name, email, phone, exclude_id=None):
    errors = []
    if not full_name or not full_name.strip():
        errors.append("Full name is required.")
    if not email or not email.strip():
        errors.append("Email is required.")
    elif not EMAIL_RE.match(email.strip()):
        errors.append("Email format is invalid.")
    elif db.email_exists(email.strip(), exclude_id=exclude_id):
        errors.append("A user with this email already exists.")
    if phone and not PHONE_RE.match(phone.strip()):
        errors.append("Phone number format looks invalid.")
    return errors


# --------------------------------------------------------------------------- #
# Bulk upload (CSV / Excel)
# --------------------------------------------------------------------------- #
UPLOAD_REQUIRED_COLUMNS = ["full_name", "email"]
UPLOAD_OPTIONAL_COLUMNS = ["phone", "age", "department", "role", "status"]

UPLOAD_COLUMN_ALIASES = {
    "name": "full_name",
    "email_address": "email",
    "mobile": "phone",
    "phone_number": "phone",
    "dept": "department",
}

UPLOAD_TEMPLATE_ROW = {
    "full_name": "Jane Doe",
    "email": "jane.doe@example.com",
    "phone": "9876543210",
    "age": 28,
    "department": db.DEPARTMENTS[0],
    "role": db.ROLES[0],
    "status": "Active",
}


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def upload_template_bytes() -> bytes:
    return to_excel_bytes(pd.DataFrame([UPLOAD_TEMPLATE_ROW]))


def parse_upload(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Parse an uploaded CSV/Excel file into a raw DataFrame with normalized column names."""
    buffer = io.BytesIO(file_bytes)
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(buffer)
    else:
        df = pd.read_excel(buffer)

    normalized_columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    df.columns = [UPLOAD_COLUMN_ALIASES.get(c, c) for c in normalized_columns]
    return df


def validate_upload_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Validate each row of an uploaded users DataFrame.

    Returns a copy of df with two extra columns: `_valid` (bool) and `_error` (str),
    checking required fields, email/phone format, in-file duplicates, and DB duplicates.
    """
    missing_columns = [c for c in UPLOAD_REQUIRED_COLUMNS if c not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required column(s): {', '.join(missing_columns)}")

    valid_flags = []
    error_messages = []
    seen_emails = set()

    for _, row in df.iterrows():
        row_errors = []
        full_name = _clean(row.get("full_name"))
        email = _clean(row.get("email")).lower()
        phone = _clean(row.get("phone"))

        if not full_name:
            row_errors.append("Missing full name")
        if not email:
            row_errors.append("Missing email")
        elif not EMAIL_RE.match(email):
            row_errors.append("Invalid email format")
        elif email in seen_emails:
            row_errors.append("Duplicate email in file")
        elif db.email_exists(email):
            row_errors.append("Email already exists in database")
        if phone and not PHONE_RE.match(phone):
            row_errors.append("Invalid phone format")

        if email:
            seen_emails.add(email)

        valid_flags.append(len(row_errors) == 0)
        error_messages.append("; ".join(row_errors))

    result = df.copy()
    result["_valid"] = valid_flags
    result["_error"] = error_messages
    return result


def import_valid_rows(df: pd.DataFrame) -> list[dict]:
    """Insert every row marked `_valid` into the database. Returns the created user dicts."""
    created = []
    for _, row in df[df["_valid"]].iterrows():
        age_raw = row.get("age")
        try:
            age = int(age_raw) if _clean(age_raw) else 0
        except (ValueError, TypeError):
            age = 0

        department = _clean(row.get("department"))
        if department not in db.DEPARTMENTS:
            department = db.DEPARTMENTS[0]

        role = _clean(row.get("role"))
        if role not in db.ROLES:
            role = db.ROLES[0]

        status = _clean(row.get("status"))
        if status not in db.STATUSES:
            status = "Active"

        full_name = _clean(row.get("full_name"))
        email = _clean(row.get("email")).lower()
        db.add_user(
            full_name,
            email,
            _clean(row.get("phone")),
            age,
            department,
            role,
            status,
        )
        created.append(
            {"full_name": full_name, "email": email, "department": department, "role": role, "status": status}
        )

    return created
