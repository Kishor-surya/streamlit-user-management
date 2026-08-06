# Streamlit User Management

A full-stack user management app built with [Streamlit](https://streamlit.io/) and SQLite.

## Features

- **Create** — add new users with name, email, phone, age, department, role, status
- **Read** — searchable/filterable list of all users
- **Update** — edit any existing user's details
- **Delete** — remove a user
- **Export** — download the full user list as CSV or Excel (.xlsx)
- Persistent storage via a local SQLite database (`users.db`, auto-created)
- Server-side validation (required fields, email format, duplicate email check)

## Project Structure

```
streamlit-user-management/
├── app.py             # Streamlit UI (pages: List, Add, Edit/Delete, Export)
├── db.py              # SQLite data access layer
├── requirements.txt   # Python dependencies
└── README.md
```

## Setup

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

The app opens at http://localhost:8501. A `users.db` SQLite file is created automatically
in the project directory on first run.

## Notes

- Change `DEPARTMENTS` / `ROLES` / `STATUSES` lists in `db.py` to customize dropdown options.
- `users.db` is git-ignored by default; delete it to reset all data.
