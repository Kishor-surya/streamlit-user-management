import csv
from pathlib import Path

from inbox_sync import sync_pending_users


def _write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


ADD_FIELDS = ["full_name", "email", "phone", "age", "department", "role", "status", "source_issue"]
DELETE_FIELDS = ["email", "source_issue"]


def test_sync_adds_new_users(temp_db, tmp_path):
    add_path = tmp_path / "pending_add.csv"
    delete_path = tmp_path / "pending_delete.csv"
    _write_csv(add_path, ADD_FIELDS, [{
        "full_name": "Jane Doe", "email": "jane@example.com", "phone": "", "age": "30",
        "department": "Engineering", "role": "Manager", "status": "Active", "source_issue": "5",
    }])
    _write_csv(delete_path, DELETE_FIELDS, [])

    result = sync_pending_users(add_path=add_path, delete_path=delete_path)

    assert result == {"added": 1, "deleted": 0, "notified": 0}
    users = temp_db.get_all_users()
    assert len(users) == 1
    assert users[0]["email"] == "jane@example.com"


def test_sync_skips_existing_email(temp_db, tmp_path):
    temp_db.add_user("Existing", "existing@example.com", "", 40, "HR", "Employee")
    add_path = tmp_path / "pending_add.csv"
    delete_path = tmp_path / "pending_delete.csv"
    _write_csv(add_path, ADD_FIELDS, [{
        "full_name": "Dup", "email": "existing@example.com", "phone": "", "age": "",
        "department": "", "role": "", "status": "", "source_issue": "6",
    }])
    _write_csv(delete_path, DELETE_FIELDS, [])

    result = sync_pending_users(add_path=add_path, delete_path=delete_path)

    assert result == {"added": 0, "deleted": 0, "notified": 0}
    assert len(temp_db.get_all_users()) == 1


def test_sync_defaults_unknown_department_role_status(temp_db, tmp_path):
    add_path = tmp_path / "pending_add.csv"
    delete_path = tmp_path / "pending_delete.csv"
    _write_csv(add_path, ADD_FIELDS, [{
        "full_name": "Alice", "email": "alice@example.com", "phone": "", "age": "not-a-number",
        "department": "Nope", "role": "Nope", "status": "Nope", "source_issue": "7",
    }])
    _write_csv(delete_path, DELETE_FIELDS, [])

    sync_pending_users(add_path=add_path, delete_path=delete_path)

    user = temp_db.get_all_users()[0]
    assert user["department"] == temp_db.DEPARTMENTS[0]
    assert user["role"] == temp_db.ROLES[0]
    assert user["status"] == "Active"
    assert user["age"] == 0


def test_sync_deletes_matching_user(temp_db, tmp_path):
    temp_db.add_user("To Remove", "remove@example.com", "", 22, "Sales", "Employee")
    add_path = tmp_path / "pending_add.csv"
    delete_path = tmp_path / "pending_delete.csv"
    _write_csv(add_path, ADD_FIELDS, [])
    _write_csv(delete_path, DELETE_FIELDS, [{"email": "remove@example.com", "source_issue": "8"}])

    result = sync_pending_users(add_path=add_path, delete_path=delete_path)

    assert result == {"added": 0, "deleted": 1, "notified": 0}
    assert temp_db.get_all_users() == []


def test_sync_delete_of_missing_user_is_noop(temp_db, tmp_path):
    add_path = tmp_path / "pending_add.csv"
    delete_path = tmp_path / "pending_delete.csv"
    _write_csv(add_path, ADD_FIELDS, [])
    _write_csv(delete_path, DELETE_FIELDS, [{"email": "ghost@example.com", "source_issue": "9"}])

    result = sync_pending_users(add_path=add_path, delete_path=delete_path)

    assert result == {"added": 0, "deleted": 0, "notified": 0}


def test_sync_handles_missing_files(temp_db, tmp_path):
    result = sync_pending_users(add_path=tmp_path / "missing_add.csv", delete_path=tmp_path / "missing_delete.csv")
    assert result == {"added": 0, "deleted": 0, "notified": 0}


def test_sync_calls_on_added_for_each_new_user(temp_db, tmp_path):
    add_path = tmp_path / "pending_add.csv"
    delete_path = tmp_path / "pending_delete.csv"
    _write_csv(add_path, ADD_FIELDS, [
        {
            "full_name": "Jane Doe", "email": "jane@example.com", "phone": "", "age": "30",
            "department": "Engineering", "role": "Manager", "status": "Active", "source_issue": "5",
        },
        {
            "full_name": "Bob Roe", "email": "bob@example.com", "phone": "", "age": "40",
            "department": "Sales", "role": "Employee", "status": "Active", "source_issue": "6",
        },
    ])
    _write_csv(delete_path, DELETE_FIELDS, [])

    notified_users = []

    def on_added(user):
        notified_users.append(user)
        return user["email"] == "jane@example.com"

    result = sync_pending_users(add_path=add_path, delete_path=delete_path, on_added=on_added)

    assert result == {"added": 2, "deleted": 0, "notified": 1}
    assert {u["email"] for u in notified_users} == {"jane@example.com", "bob@example.com"}


def test_sync_does_not_call_on_added_for_skipped_rows(temp_db, tmp_path):
    temp_db.add_user("Existing", "existing@example.com", "", 40, "HR", "Employee")
    add_path = tmp_path / "pending_add.csv"
    delete_path = tmp_path / "pending_delete.csv"
    _write_csv(add_path, ADD_FIELDS, [{
        "full_name": "Dup", "email": "existing@example.com", "phone": "", "age": "",
        "department": "", "role": "", "status": "", "source_issue": "6",
    }])
    _write_csv(delete_path, DELETE_FIELDS, [])

    calls = []
    result = sync_pending_users(add_path=add_path, delete_path=delete_path, on_added=lambda u: calls.append(u))

    assert result["notified"] == 0
    assert calls == []
