import io

import pandas as pd

from utils import EMAIL_RE, to_dataframe, to_excel_bytes, validate_user_form


def test_to_dataframe_empty_has_expected_columns():
    df = to_dataframe([])
    assert list(df.columns) == [
        "id", "full_name", "email", "phone", "age",
        "department", "role", "status", "created_at", "updated_at",
    ]
    assert df.empty


def test_to_dataframe_with_data():
    users = [{"id": 1, "full_name": "Alice", "email": "alice@example.com"}]
    df = to_dataframe(users)
    assert len(df) == 1
    assert df.iloc[0]["full_name"] == "Alice"


def test_to_excel_bytes_roundtrip():
    df = pd.DataFrame([{"full_name": "Alice", "email": "alice@example.com"}])
    excel_bytes = to_excel_bytes(df)

    assert excel_bytes[:2] == b"PK"  # xlsx files are zip archives

    roundtrip = pd.read_excel(io.BytesIO(excel_bytes))
    assert roundtrip.iloc[0]["full_name"] == "Alice"


def test_email_regex():
    assert EMAIL_RE.match("user@example.com")
    assert not EMAIL_RE.match("not-an-email")


def test_validate_user_form_requires_name_and_email(temp_db):
    errors = validate_user_form("", "", "")
    assert "Full name is required." in errors
    assert "Email is required." in errors


def test_validate_user_form_bad_email_format(temp_db):
    errors = validate_user_form("Alice", "not-an-email", "")
    assert any("invalid" in e for e in errors)


def test_validate_user_form_bad_phone_format(temp_db):
    errors = validate_user_form("Alice", "alice@example.com", "abc")
    assert any("Phone number" in e for e in errors)


def test_validate_user_form_duplicate_email(temp_db):
    temp_db.add_user("Alice", "alice@example.com", "", 30, "Engineering", "Manager")
    errors = validate_user_form("Bob", "alice@example.com", "")
    assert any("already exists" in e for e in errors)


def test_validate_user_form_duplicate_email_excluded_when_editing_self(temp_db):
    temp_db.add_user("Alice", "alice@example.com", "", 30, "Engineering", "Manager")
    user = temp_db.get_all_users()[0]
    errors = validate_user_form("Alice", "alice@example.com", "", exclude_id=user["id"])
    assert errors == []


def test_validate_user_form_valid(temp_db):
    errors = validate_user_form("Alice", "alice@example.com", "123-456-7890")
    assert errors == []
