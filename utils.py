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
