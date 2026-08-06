import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.process_user_issue import parse_issue_body, process, queue_add, queue_delete  # noqa: E402

SAMPLE_ADD_BODY = """### Action

Add User

### Full Name

Jane Doe

### Email

jane@example.com

### Phone

_No response_

### Age

30

### Department

Engineering

### Role

Manager

### Status

Active

### Bulk Upload File

_No response_
"""


def test_parse_issue_body_extracts_fields_and_blanks_no_response():
    fields = parse_issue_body(SAMPLE_ADD_BODY)
    assert fields["Action"] == "Add User"
    assert fields["Full Name"] == "Jane Doe"
    assert fields["Email"] == "jane@example.com"
    assert fields["Phone"] == ""


def test_queue_add_appends_and_dedupes_case_insensitively():
    rows = []
    ok1, _ = queue_add(rows, 1, "Jane", "jane@example.com", "", "30", "Engineering", "Manager", "Active")
    ok2, msg2 = queue_add(rows, 2, "Jane Dup", "JANE@example.com", "", "", "", "", "")

    assert ok1 is True
    assert ok2 is False
    assert "duplicate" in msg2
    assert len(rows) == 1


def test_queue_delete_appends_and_dedupes():
    rows = []
    ok1, _ = queue_delete(rows, 1, "jane@example.com")
    ok2, _ = queue_delete(rows, 2, "jane@example.com")

    assert ok1 is True
    assert ok2 is False
    assert len(rows) == 1


def test_process_add_user_queues_row(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.process_user_issue.ADD_PATH", tmp_path / "pending_add.csv")
    monkeypatch.setattr("scripts.process_user_issue.DELETE_PATH", tmp_path / "pending_delete.csv")

    changed, success, comment = process(SAMPLE_ADD_BODY, 42)

    assert changed is True
    assert success is True
    assert "Queued" in comment
    assert (tmp_path / "pending_add.csv").exists()


def test_process_rejects_missing_required_fields(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.process_user_issue.ADD_PATH", tmp_path / "pending_add.csv")
    monkeypatch.setattr("scripts.process_user_issue.DELETE_PATH", tmp_path / "pending_delete.csv")

    body = "### Action\n\nAdd User\n\n### Full Name\n\n_No response_\n\n### Email\n\n_No response_\n"
    changed, success, comment = process(body, 43)

    assert changed is False
    assert success is False
    assert "requires" in comment


def test_process_delete_user_queues_row(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.process_user_issue.ADD_PATH", tmp_path / "pending_add.csv")
    monkeypatch.setattr("scripts.process_user_issue.DELETE_PATH", tmp_path / "pending_delete.csv")

    body = "### Action\n\nDelete User\n\n### Email\n\njane@example.com\n"
    changed, success, comment = process(body, 44)

    assert changed is True
    assert success is True
    assert (tmp_path / "pending_delete.csv").exists()


def test_process_unrecognized_action(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.process_user_issue.ADD_PATH", tmp_path / "pending_add.csv")
    monkeypatch.setattr("scripts.process_user_issue.DELETE_PATH", tmp_path / "pending_delete.csv")

    changed, success, comment = process("### Action\n\nDo Something Else\n", 45)

    assert changed is False
    assert success is False
    assert "Unrecognized" in comment


def test_process_bulk_upload_downloads_and_queues(temp_db, tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.process_user_issue.ADD_PATH", tmp_path / "pending_add.csv")
    monkeypatch.setattr("scripts.process_user_issue.DELETE_PATH", tmp_path / "pending_delete.csv")

    csv_bytes = b"full_name,email\nBulk One,bulk1@example.com\nBulk Two,bulk2@example.com\n"
    monkeypatch.setattr(
        "scripts.process_user_issue.download_attachment",
        lambda url: (csv_bytes, "users.csv"),
    )

    body = (
        "### Action\n\nBulk Upload\n\n"
        "### Bulk Upload File\n\n[users.csv](https://github.com/user-attachments/files/1/users.csv)\n"
    )
    changed, success, comment = process(body, 46)

    assert changed is True
    assert success is True
    assert "Queued **2**" in comment
