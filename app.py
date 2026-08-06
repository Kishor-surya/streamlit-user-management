"""
Streamlit User Management Application
Create, Read, Update, Delete users, with list view, search, and export
(CSV / Excel) support. Data is persisted in a local SQLite database.
"""

import streamlit as st

import db
from utils import to_dataframe, to_excel_bytes, validate_user_form

st.set_page_config(page_title="User Management", page_icon="👤", layout="wide")
db.init_db()


# --------------------------------------------------------------------------- #
# Sidebar navigation
# --------------------------------------------------------------------------- #
st.sidebar.title("👤 User Management")
page = st.sidebar.radio(
    "Navigate",
    ["📋 User List", "➕ Add User", "✏️ Edit / Delete User", "⬇️ Export Data"],
)

st.sidebar.markdown("---")
all_users = db.get_all_users()
st.sidebar.metric("Total Users", len(all_users))
st.sidebar.metric("Active Users", sum(1 for u in all_users if u["status"] == "Active"))

# --------------------------------------------------------------------------- #
# Page: User List
# --------------------------------------------------------------------------- #
if page == "📋 User List":
    st.title("📋 User List")

    users = db.get_all_users()
    df = to_dataframe(users)

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search = st.text_input("🔍 Search by name or email")
    with col2:
        dept_filter = st.selectbox("Department", ["All"] + db.DEPARTMENTS)
    with col3:
        status_filter = st.selectbox("Status", ["All"] + db.STATUSES)

    filtered = df.copy()
    if not filtered.empty:
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

        submitted = st.form_submit_button("Add User", type="primary")

    if submitted:
        errors = validate_user_form(full_name, email, phone)
        if errors:
            for err in errors:
                st.error(err)
        else:
            db.add_user(full_name.strip(), email.strip(), phone.strip(), int(age), department, role, status)
            st.success(f"User '{full_name}' added successfully.")
            st.rerun()

# --------------------------------------------------------------------------- #
# Page: Edit / Delete User
# --------------------------------------------------------------------------- #
elif page == "✏️ Edit / Delete User":
    st.title("✏️ Edit / Delete User")

    users = db.get_all_users()
    if not users:
        st.info("No users available yet. Add a user first.")
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
            update_clicked = col_update.form_submit_button("💾 Update User", type="primary")
            delete_clicked = col_delete.form_submit_button("🗑️ Delete User")

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
                st.success("User updated successfully.")
                st.rerun()

        if delete_clicked:
            db.delete_user(selected_id)
            st.success("User deleted successfully.")
            st.rerun()

# --------------------------------------------------------------------------- #
# Page: Export Data
# --------------------------------------------------------------------------- #
elif page == "⬇️ Export Data":
    st.title("⬇️ Export User Data")

    users = db.get_all_users()
    df = to_dataframe(users)

    if df.empty:
        st.info("No users to export yet.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

        col1, col2 = st.columns(2)
        with col1:
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download as CSV",
                data=csv_bytes,
                file_name="users.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col2:
            excel_bytes = to_excel_bytes(df)
            st.download_button(
                "⬇️ Download as Excel",
                data=excel_bytes,
                file_name="users.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
