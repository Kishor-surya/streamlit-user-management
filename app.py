"""
PeopleDesk — User Management Application
Create, Read, Update, Delete users, with list view, search, bulk CSV/Excel
import, export, and automatic welcome-email notifications. Data is persisted
in a local SQLite database.
"""

from pathlib import Path

import streamlit as st

import db
from email_service import SmtpConfig, send_welcome_email
from inbox_sync import sync_pending_users
from utils import (
    import_valid_rows,
    parse_upload,
    to_dataframe,
    to_excel_bytes,
    upload_template_bytes,
    validate_upload_rows,
    validate_user_form,
)

APP_NAME = "PeopleDesk"
ASSETS_DIR = Path(__file__).parent / "assets"

st.set_page_config(page_title=APP_NAME, page_icon="🗂️", layout="wide")
db.init_db()
inbox_sync_result = sync_pending_users()

CUSTOM_CSS = """
<style>
  .pd-logo-row {
      display: flex;
      align-items: center;
      gap: 0.7rem;
      margin-bottom: 0.15rem;
  }
  .pd-logo-row h1 {
      font-size: 1.45rem;
      margin: 0;
      line-height: 1.1;
      background: linear-gradient(90deg, #6366f1, #22d3ee);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
  }
  .pd-tagline {
      color: #6b7280;
      font-size: 0.8rem;
      margin: 0 0 1rem 0;
  }
  div[data-testid="stMetric"] {
      background: rgba(99, 102, 241, 0.08);
      border-radius: 10px;
      padding: 0.6rem 0.8rem;
  }
  .stButton > button, .stDownloadButton > button {
      border-radius: 8px;
  }
  .pd-empty-state {
      text-align: center;
      padding: 1.5rem 0;
  }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def load_smtp_config():
    """Read SMTP credentials from Streamlit secrets, if configured. Returns None otherwise."""
    try:
        email_secrets = st.secrets["email"]
        return SmtpConfig(
            sender_email=email_secrets["sender_email"],
            sender_password=email_secrets["sender_password"],
            host=email_secrets.get("smtp_host", "smtp.gmail.com"),
            port=int(email_secrets.get("smtp_port", 587)),
            use_tls=bool(email_secrets.get("use_tls", True)),
        )
    except Exception:
        return None


def notify_new_user(config, to_email, full_name, department, role):
    """Send a welcome email. Returns (sent: bool, error_message: str | None)."""
    try:
        send_welcome_email(to_email, full_name, department, role, config)
        return True, None
    except Exception as e:
        return False, str(e)


def load_admin_credentials():
    """Read admin username/password from Streamlit secrets; falls back to admin/admin."""
    try:
        admin_secrets = st.secrets["admin"]
        return admin_secrets.get("username", "admin"), admin_secrets.get("password", "admin")
    except Exception:
        return "admin", "admin"


def render_empty_state(message: str):
    svg = (ASSETS_DIR / "empty_state.svg").read_text(encoding="utf-8")
    st.markdown(
        f'<div class="pd-empty-state">{svg}<p>{message}</p></div>',
        unsafe_allow_html=True,
    )


def flash(kind: str, message: str):
    """Queue a status message to survive the st.rerun() that follows it."""
    st.session_state.setdefault("_flash_messages", []).append((kind, message))


def render_flash_messages():
    for kind, message in st.session_state.pop("_flash_messages", []):
        getattr(st, kind)(message)


# --------------------------------------------------------------------------- #
# Sidebar navigation
# --------------------------------------------------------------------------- #
logo_svg = (ASSETS_DIR / "logo.svg").read_text(encoding="utf-8")
st.sidebar.markdown(
    f'<div class="pd-logo-row">{logo_svg}<h1>{APP_NAME}</h1></div>'
    '<p class="pd-tagline">Your team, organized.</p>',
    unsafe_allow_html=True,
)

page = st.sidebar.radio(
    "Navigate",
    ["📋 User List", "➕ Add User", "📤 Bulk Upload", "✏️ Edit / Delete User", "⬇️ Export Data"],
)

st.sidebar.markdown("---")
all_users = db.get_all_users()
st.sidebar.metric("Total Users", len(all_users))
st.sidebar.metric("Active Users", sum(1 for u in all_users if u["status"] == "Active"))

smtp_config = load_smtp_config()
st.sidebar.markdown("---")
if smtp_config is None:
    st.sidebar.caption("✉️ Welcome emails: not configured — see README.")
else:
    st.sidebar.caption(f"✉️ Welcome emails: enabled via {smtp_config.host}")

if inbox_sync_result["added"] or inbox_sync_result["deleted"]:
    st.sidebar.caption(
        f"🔄 Synced from GitHub Issues: +{inbox_sync_result['added']} added, "
        f"-{inbox_sync_result['deleted']} removed."
    )

render_flash_messages()

# --------------------------------------------------------------------------- #
# Page: User List
# --------------------------------------------------------------------------- #
if page == "📋 User List":
    st.title("📋 User List")

    if not st.session_state.get("user_list_authed", False):
        st.info("🔒 This page is restricted to admins. Sign in to view the user list.")
        with st.form("user_list_login"):
            login_user = st.text_input("Username")
            login_pass = st.text_input("Password", type="password")
            login_clicked = st.form_submit_button("Sign in", type="primary", icon=":material/lock_open:")

        if login_clicked:
            admin_user, admin_pass = load_admin_credentials()
            if login_user == admin_user and login_pass == admin_pass:
                st.session_state["user_list_authed"] = True
                st.rerun()
            else:
                st.error("Invalid username or password.")
    else:
        users = db.get_all_users()
        df = to_dataframe(users)

        if df.empty:
            render_empty_state("No users yet — add one from the **Add User** page.")
        else:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                search = st.text_input("🔍 Search by name or email")
            with col2:
                dept_filter = st.selectbox("Department", ["All"] + db.DEPARTMENTS)
            with col3:
                status_filter = st.selectbox("Status", ["All"] + db.STATUSES)

            filtered = df.copy()
            if search:
                mask = filtered["full_name"].str.contains(search, case=False, na=False) | \
                       filtered["email"].str.contains(search, case=False, na=False)
                filtered = filtered[mask]
            if dept_filter != "All":
                filtered = filtered[filtered["department"] == dept_filter]
            if status_filter != "All":
                filtered = filtered[filtered["status"] == status_filter]

            st.dataframe(filtered, use_container_width=True, hide_index=True)
            st.caption(f"Showing {len(filtered)} of {len(df)} user(s).")

# --------------------------------------------------------------------------- #
# Page: Add User
# --------------------------------------------------------------------------- #
elif page == "➕ Add User":
    st.title("➕ Add New User")

    with st.form("add_user_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            full_name = st.text_input("Full Name *")
            email = st.text_input("Email *")
            phone = st.text_input("Phone")
        with c2:
            age = st.number_input("Age", min_value=0, max_value=120, value=25, step=1)
            department = st.selectbox("Department", db.DEPARTMENTS)
            role = st.selectbox("Role", db.ROLES)
        status = st.radio("Status", db.STATUSES, horizontal=True)

        submitted = st.form_submit_button("Add User", type="primary", icon=":material/person_add:")

    if submitted:
        errors = validate_user_form(full_name, email, phone)
        if errors:
            for err in errors:
                st.error(err)
        else:
            db.add_user(full_name.strip(), email.strip(), phone.strip(), int(age), department, role, status)
            flash("success", f"User '{full_name}' added successfully.")

            if smtp_config:
                sent, error = notify_new_user(smtp_config, email.strip(), full_name.strip(), department, role)
                if sent:
                    flash("info", f"📧 Welcome email sent to {email.strip()}.")
                else:
                    flash("warning", f"User created, but the welcome email failed to send: {error}")

            st.rerun()

# --------------------------------------------------------------------------- #
# Page: Bulk Upload
# --------------------------------------------------------------------------- #
elif page == "📤 Bulk Upload":
    st.title("📤 Bulk Upload Users")
    st.caption(
        "Upload a CSV or Excel file with a `full_name` and `email` column "
        "(optionally `phone`, `age`, `department`, `role`, `status`)."
    )

    st.download_button(
        "Download template",
        data=upload_template_bytes(),
        file_name="user_upload_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        icon=":material/download:",
    )

    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx", "xls"])

    if uploaded_file is not None:
        try:
            raw_df = parse_upload(uploaded_file.getvalue(), uploaded_file.name)
            validated_df = validate_upload_rows(raw_df)
        except ValueError as e:
            st.error(str(e))
        except Exception:
            st.error("Could not read that file. Make sure it's a valid CSV or Excel file.")
        else:
            valid_count = int(validated_df["_valid"].sum())
            invalid_count = len(validated_df) - valid_count

            st.write(f"**{len(validated_df)} row(s) found** — {valid_count} valid, {invalid_count} with errors.")
            st.dataframe(
                validated_df.rename(columns={"_valid": "Valid", "_error": "Error"}),
                use_container_width=True,
                hide_index=True,
            )

            if valid_count > 0:
                import_clicked = st.button(
                    f"Import {valid_count} valid user(s)", type="primary", icon=":material/upload_file:"
                )
                if import_clicked:
                    created_users = import_valid_rows(validated_df)
                    flash("success", f"Imported {len(created_users)} user(s) successfully.")

                    if smtp_config:
                        sent_count = 0
                        failures = []
                        for u in created_users:
                            sent, error = notify_new_user(
                                smtp_config, u["email"], u["full_name"], u["department"], u["role"]
                            )
                            if sent:
                                sent_count += 1
                            else:
                                failures.append(f"{u['email']} ({error})")
                        summary = f"📧 Sent {sent_count} welcome email(s)."
                        if failures:
                            summary += f" {len(failures)} failed: " + "; ".join(failures)
                        flash("info", summary)

                    st.rerun()
            else:
                st.warning("No valid rows to import.")

# --------------------------------------------------------------------------- #
# Page: Edit / Delete User
# --------------------------------------------------------------------------- #
elif page == "✏️ Edit / Delete User":
    st.title("✏️ Edit / Delete User")

    users = db.get_all_users()
    if not users:
        render_empty_state("No users available yet. Add a user first.")
    else:
        options = {f"{u['full_name']} ({u['email']}) — id {u['id']}": u["id"] for u in users}
        selected_label = st.selectbox("Select a user", list(options.keys()))
        selected_id = options[selected_label]
        user = db.get_user(selected_id)

        with st.form("edit_user_form"):
            c1, c2 = st.columns(2)
            with c1:
                full_name = st.text_input("Full Name *", value=user["full_name"])
                email = st.text_input("Email *", value=user["email"])
                phone = st.text_input("Phone", value=user["phone"] or "")
            with c2:
                age = st.number_input(
                    "Age", min_value=0, max_value=120, value=user["age"] or 0, step=1
                )
                department = st.selectbox(
                    "Department", db.DEPARTMENTS,
                    index=db.DEPARTMENTS.index(user["department"]) if user["department"] in db.DEPARTMENTS else 0,
                )
                role = st.selectbox(
                    "Role", db.ROLES,
                    index=db.ROLES.index(user["role"]) if user["role"] in db.ROLES else 0,
                )
            status = st.radio(
                "Status", db.STATUSES, horizontal=True,
                index=db.STATUSES.index(user["status"]) if user["status"] in db.STATUSES else 0,
            )

            col_update, col_delete = st.columns(2)
            update_clicked = col_update.form_submit_button("Update User", type="primary", icon=":material/save:")
            delete_clicked = col_delete.form_submit_button("Delete User", icon=":material/delete:")

        if update_clicked:
            errors = validate_user_form(full_name, email, phone, exclude_id=selected_id)
            if errors:
                for err in errors:
                    st.error(err)
            else:
                db.update_user(
                    selected_id, full_name.strip(), email.strip(), phone.strip(),
                    int(age), department, role, status,
                )
                flash("success", "User updated successfully.")
                st.rerun()

        if delete_clicked:
            db.delete_user(selected_id)
            flash("success", "User deleted successfully.")
            st.rerun()

# --------------------------------------------------------------------------- #
# Page: Export Data
# --------------------------------------------------------------------------- #
elif page == "⬇️ Export Data":
    st.title("⬇️ Export User Data")

    users = db.get_all_users()
    df = to_dataframe(users)

    if df.empty:
        render_empty_state("No users to export yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download as CSV",
                data=csv_bytes,
                file_name="users.csv",
                mime="text/csv",
                use_container_width=True,
                icon=":material/download:",
            )
        with col2:
            excel_bytes = to_excel_bytes(df)
            st.download_button(
                "Download as Excel",
                data=excel_bytes,
                file_name="users.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                icon=":material/download:",
            )
