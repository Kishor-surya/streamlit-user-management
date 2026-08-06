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
├── app.py                       # Streamlit UI (pages: List, Add, Edit/Delete, Export)
├── db.py                        # SQLite data access layer
├── utils.py                     # Pure helpers (validation, dataframe/excel export) — unit tested
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # + test/lint/security tooling
├── tests/                       # pytest unit tests for db.py and utils.py
├── scripts/build_dashboard.py   # Builds the CI/CD metrics dashboard for GitHub Pages
└── .github/
    ├── workflows/
    │   ├── ci.yml                # Lint (flake8) + unit tests + coverage (70% gate)
    │   ├── codeql.yml            # CodeQL static analysis (security)
    │   ├── security.yml          # Bandit (SAST) + pip-audit (dependency vulnerabilities)
    │   └── pages.yml             # Publishes coverage / CodeQL / Dependabot metrics to GitHub Pages
    └── dependabot.yml            # Weekly dependency update PRs (pip + github-actions)
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

## Testing

```bash
pip install -r requirements-dev.txt
pytest --cov=db --cov=utils --cov-report=term-missing
```

## CI/CD

Every push/PR to `main` or `develop` runs:
- **CI** — flake8 lint, pytest unit tests, coverage report (fails under 70%)
- **CodeQL** — static security analysis
- **Security Scan** — Bandit (SAST) and pip-audit (dependency CVEs), published as build artifacts (non-blocking)
- **Pages** — rebuilds the [live CI/CD metrics dashboard](../../actions) with current coverage,
  CodeQL alert counts, and Dependabot alert counts

Dependabot opens weekly PRs against `develop` for outdated pip and GitHub Actions dependencies.

## Notes

- Change `DEPARTMENTS` / `ROLES` / `STATUSES` lists in `db.py` to customize dropdown options.
- `users.db` is git-ignored by default; delete it to reset all data.
