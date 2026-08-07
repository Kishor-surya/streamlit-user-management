# PeopleDesk (Streamlit User Management)

A full-stack user management app built with [Streamlit](https://streamlit.io/) and SQLite.

## Features

- **Create** — add new users with name, email, phone, age, department, role, status
- **Read** — searchable/filterable list of all users, gated behind an admin sign-in
- **Update** — edit any existing user's details
- **Delete** — remove a user
- **Bulk Upload** — import users in bulk from a CSV/Excel file, with per-row validation
- **Export** — download the full user list as CSV or Excel (.xlsx)
- **Welcome emails** — optionally notify new users by email when they're added (single or bulk)
- **GitHub Issues requests** — add/delete/bulk-import users by filing a GitHub issue; a bot
  validates and queues the request, and the app picks it up on its next restart
- Persistent storage via a local SQLite database (`users.db`, auto-created)
- Server-side validation (required fields, email format, duplicate email check)

## Project Structure

```
streamlit-user-management/
├── app.py                       # Streamlit UI (pages: List, Add, Bulk Upload, Edit/Delete, Export)
├── db.py                        # SQLite data access layer
├── utils.py                     # Pure helpers (validation, dataframe/excel export) — unit tested
├── email_service.py             # Builds/sends the welcome email via SMTP — unit tested
├── inbox_sync.py                # Applies queued GitHub-issue requests into the DB — unit tested
├── assets/                      # Logo and empty-state SVGs used by the UI
├── data/inbox/                  # pending_add.csv / pending_delete.csv — the issue-request queue
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # + test/lint/security tooling
├── tests/                       # pytest unit tests for db.py, utils.py, email_service.py, inbox_sync.py, ...
├── scripts/
│   ├── build_dashboard.py       # Builds the CI/CD metrics dashboard for GitHub Pages
│   └── process_user_issue.py    # Parses a user-management-request issue, queues it — unit tested
└── .github/
    ├── ISSUE_TEMPLATE/
    │   └── user-management-request.yml   # Add/Delete/Bulk Upload issue form
    ├── workflows/
    │   ├── ci.yml                # Lint (flake8) + unit tests + coverage (70% gate)
    │   ├── codeql.yml            # CodeQL static analysis (security)
    │   ├── security.yml          # Bandit (SAST) + pip-audit (dependency vulnerabilities)
    │   ├── pages.yml             # Publishes coverage / CodeQL / Dependabot metrics to GitHub Pages
    │   └── user-request.yml      # Processes user-management-request issues into data/inbox/
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

## Email Notifications (optional)

To send a welcome email when a user is added (individually or via bulk upload), add SMTP
credentials to `.streamlit/secrets.toml`:

```toml
[email]
sender_email = "you@example.com"
sender_password = "app-password"   # e.g. a Gmail App Password, not your account password
smtp_host = "smtp.gmail.com"       # optional, defaults shown
smtp_port = 587
use_tls = true
```

If `[email]` isn't configured, the app runs normally and simply skips sending emails.
`.streamlit/secrets.toml` is git-ignored — never commit real credentials.

## User List Access (admin-only)

The **User List** page is the only page that shows the full roster, so it's gated behind a
sign-in. Default credentials are `admin` / `admin`; override them via secrets:

```toml
[admin]
username = "your-admin-username"
password = "your-admin-password"
```

The sign-in is session-scoped (Streamlit `session_state`) — it resets when the browser tab is
closed or the app reruns from a fresh session. This is a lightweight gate suited to an internal
demo tool, not a substitute for real authentication (no hashing, no rate limiting); rotate the
default credentials via secrets before sharing the app's URL with anyone.

## Adding Users via GitHub Issues

Anyone with issue access can request a user change without opening the app: go to
**[Issues → New issue](../../issues/new/choose)** and pick **User Management Request**. Fill in
an **Action** (Add User / Delete User / Bulk Upload — for bulk, drag a CSV/Excel file into the
"Bulk Upload File" box) and submit.

What happens next, automatically:
1. `.github/workflows/user-request.yml` fires on the new issue, runs
   `scripts/process_user_issue.py` to parse and validate the request.
2. Valid requests are appended to `data/inbox/pending_add.csv` or `pending_delete.csv` and
   committed straight to `main` (these are automated data commits, not code changes, so they
   skip the usual PR review). Invalid requests are rejected with no commit.
3. The bot comments on the issue with the result and closes it on success.
4. `main`'s redeploy on Streamlit Community Cloud picks up the new commit; on startup the app
   calls `inbox_sync.sync_pending_users()`, which applies any inbox rows not already reflected
   in the database (skipping emails that already exist / deletes for users already gone, so
   re-running it on every restart is safe).

**Why the queue, instead of writing straight to the database:** GitHub Actions runs on GitHub's
own infrastructure and has no network path to the Streamlit app's process or its local SQLite
file, so it can't call `db.add_user()` directly. The repo itself — via this CSV inbox — is the
only thing both sides can reach.

**Known limitations:**
- There's a delay between the issue being processed and the change appearing live — typically
  a couple of minutes, however long Streamlit Cloud takes to redeploy after the `main` push.
- Duplicate-email checking during issue processing only catches duplicates *within the same
  request*; it can't see the live database from inside the GitHub Actions runner. The real
  guard is `db.add_user()`'s `UNIQUE` constraint on `email`, enforced when `inbox_sync` applies
  the row.
- The inbox is replayed once per app process (`st.cache_resource`), not on every rerun — deleting
  or editing a user in the app sticks normally for the rest of that process's life. But the CSVs
  are append-only and never pruned, so if the app process later restarts fresh (a new deploy, or
  Streamlit Cloud waking from sleep) while a since-deleted user's row is still sitting in
  `pending_add.csv`, that row gets replayed again and the user reappears. If you delete someone
  who arrived via an issue, also remove their row from `pending_add.csv` if you want that to be
  permanent.
- Symmetrically, a delete row left in `pending_delete.csv` is a harmless no-op on future restarts
  once the user is already gone. Trim both CSVs by hand periodically if that matters to you.
- Requires the repo's Actions to have **Read and write permissions** under **Settings → Actions
  → General → Workflow permissions** (needed to push the commit and comment/close the issue),
  and `main` must allow the `github-actions[bot]` to push directly if branch protection is on.

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

**`user-request.yml`** runs on a different trigger — a new issue labeled `user-management-request`
— rather than push/PR, and is the one workflow that commits directly to `main` (see
[Adding Users via GitHub Issues](#adding-users-via-github-issues)).

## Notes

- Change `DEPARTMENTS` / `ROLES` / `STATUSES` lists in `db.py` to customize dropdown options.
- `users.db` is git-ignored by default; delete it to reset all data.
