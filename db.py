"""SQLite data access layer for the User Management app."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "users.db"

DEPARTMENTS = ["Engineering", "Sales", "Marketing", "HR", "Finance", "Operations", "Support"]
ROLES = ["Admin", "Manager", "Employee", "Contractor", "Intern"]
STATUSES = ["Active", "Inactive"]


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                age INTEGER,
                department TEXT,
                role TEXT,
                status TEXT DEFAULT 'Active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def email_exists(email: str, exclude_id: int | None = None) -> bool:
    with get_connection() as conn:
        if exclude_id is not None:
            row = conn.execute(
                "SELECT 1 FROM users WHERE email = ? AND id != ?", (email, exclude_id)
            ).fetchone()
        else:
            row = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        return row is not None


def add_user(full_name, email, phone, age, department, role, status="Active"):
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (full_name, email, phone, age, department, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (full_name, email, phone, age, department, role, status, now, now),
        )


def update_user(user_id, full_name, email, phone, age, department, role, status):
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET full_name = ?, email = ?, phone = ?, age = ?, department = ?,
                role = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (full_name, email, phone, age, department, role, status, now, user_id),
        )


def delete_user(user_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def get_user(user_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_email(email):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_all_users():
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]
