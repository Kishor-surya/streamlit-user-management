import io

import pandas as pd

from utils import (
    import_valid_rows,
    parse_upload,
    upload_template_bytes,
    validate_upload_rows,
)


def _csv_bytes(rows):
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def test_parse_upload_csv_normalizes_column_names():
    csv_bytes = "Full Name,Email,Phone\nAlice,alice@example.com,123\n".encode("utf-8")
    df = parse_upload(csv_bytes, "users.csv")
    assert list(df.columns) == ["full_name", "email", "phone"]
    assert df.iloc[0]["full_name"] == "Alice"


def test_parse_upload_applies_column_aliases():
    csv_bytes = "Name,Email Address,Mobile\nBob,bob@example.com,999\n".encode("utf-8")
    df = parse_upload(csv_bytes, "users.csv")
    assert list(df.columns) == ["full_name", "email", "phone"]


def test_parse_upload_excel():
    df_in = pd.DataFrame([{"full_name": "Carol", "email": "carol@example.com"}])
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_in.to_excel(writer, index=False)
    df = parse_upload(buffer.getvalue(), "users.xlsx")
    assert df.iloc[0]["full_name"] == "Carol"


def test_upload_template_bytes_is_valid_excel():
    template_bytes = upload_template_bytes()
    assert template_bytes[:2] == b"PK"
    df = pd.read_excel(io.BytesIO(template_bytes))
    assert "full_name" in df.columns
    assert "email" in df.columns


def test_validate_upload_rows_missing_required_column(temp_db):
    df = pd.DataFrame([{"full_name": "Alice"}])  # no email column
    try:
        validate_upload_rows(df)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "email" in str(e)


def test_validate_upload_rows_all_valid(temp_db):
    df = pd.DataFrame(
        [
            {"full_name": "Alice", "email": "alice@example.com", "phone": "1234567890"},
            {"full_name": "Bob", "email": "bob@example.com", "phone": ""},
        ]
    )
    result = validate_upload_rows(df)
    assert result["_valid"].all()
    assert (result["_error"] == "").all()


def test_validate_upload_rows_flags_missing_fields(temp_db):
    df = pd.DataFrame([{"full_name": "", "email": ""}])
    result = validate_upload_rows(df)
    assert result.iloc[0]["_valid"] == False  # noqa: E712 (numpy.bool_, not a Python bool)
    assert "Missing full name" in result.iloc[0]["_error"]
    assert "Missing email" in result.iloc[0]["_error"]


def test_validate_upload_rows_flags_bad_email_format(temp_db):
    df = pd.DataFrame([{"full_name": "Alice", "email": "not-an-email"}])
    result = validate_upload_rows(df)
    assert result.iloc[0]["_valid"] == False  # noqa: E712 (numpy.bool_, not a Python bool)
    assert "Invalid email format" in result.iloc[0]["_error"]


def test_validate_upload_rows_flags_bad_phone_format(temp_db):
    df = pd.DataFrame([{"full_name": "Alice", "email": "alice@example.com", "phone": "abc"}])
    result = validate_upload_rows(df)
    assert result.iloc[0]["_valid"] == False  # noqa: E712 (numpy.bool_, not a Python bool)
    assert "Invalid phone format" in result.iloc[0]["_error"]


def test_validate_upload_rows_flags_duplicate_within_file(temp_db):
    df = pd.DataFrame(
        [
            {"full_name": "Alice", "email": "dup@example.com"},
            {"full_name": "Alice Two", "email": "dup@example.com"},
        ]
    )
    result = validate_upload_rows(df)
    assert result.iloc[0]["_valid"] == True  # noqa: E712 (numpy.bool_, not a Python bool)
    assert result.iloc[1]["_valid"] == False  # noqa: E712 (numpy.bool_, not a Python bool)
    assert "Duplicate email in file" in result.iloc[1]["_error"]


def test_validate_upload_rows_flags_existing_in_db(temp_db):
    temp_db.add_user("Existing", "existing@example.com", "", 30, "Engineering", "Manager")
    df = pd.DataFrame([{"full_name": "New Name", "email": "existing@example.com"}])
    result = validate_upload_rows(df)
    assert result.iloc[0]["_valid"] == False  # noqa: E712 (numpy.bool_, not a Python bool)
    assert "already exists" in result.iloc[0]["_error"]


def test_import_valid_rows_inserts_only_valid(temp_db):
    df = pd.DataFrame(
        [
            {"full_name": "Alice", "email": "alice@example.com", "department": "Engineering", "role": "Manager"},
            {"full_name": "", "email": "bad"},
        ]
    )
    validated = validate_upload_rows(df)
    inserted = import_valid_rows(validated)

    assert inserted == 1
    users = temp_db.get_all_users()
    assert len(users) == 1
    assert users[0]["email"] == "alice@example.com"


def test_import_valid_rows_defaults_unknown_department_role_status(temp_db):
    df = pd.DataFrame(
        [{"full_name": "Alice", "email": "alice@example.com", "department": "Nope", "role": "Nope", "status": "Nope"}]
    )
    validated = validate_upload_rows(df)
    import_valid_rows(validated)

    user = temp_db.get_all_users()[0]
    assert user["department"] == temp_db.DEPARTMENTS[0]
    assert user["role"] == temp_db.ROLES[0]
    assert user["status"] == "Active"
