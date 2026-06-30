"""
views/settings.py — Account settings: username, password, user management.
Items 1 (username change), 8 (add user), 9 (remove user + data).
"""
import streamlit as st
import db
import auth


def render():
    uid      = st.session_state["user_id"]
    username = st.session_state["username"]
    st.title("⚙️ Settings")

    # ── Change Username (item 1) ──────────────────────────────────────────────
    st.subheader("Change Username")
    with st.form("change_username"):
        new_username = st.text_input("New Username", value=username)
        if st.form_submit_button("Update Username"):
            if not new_username.strip():
                st.error("Username cannot be blank.")
            elif new_username.strip() == username:
                st.info("That's already your current username.")
            else:
                ok, msg = db.change_username(uid, new_username.strip())
                if ok:
                    st.session_state["username"] = new_username.strip()
                    st.toast(msg, icon="✅")
                    st.rerun()
                else:
                    st.error(msg)

    st.divider()

    # ── Change Password ───────────────────────────────────────────────────────
    st.subheader("Change Password")
    with st.form("change_pw"):
        cur_pw  = st.text_input("Current Password",     type="password")
        new_pw  = st.text_input("New Password",         type="password")
        new_pw2 = st.text_input("Confirm New Password", type="password")
        if st.form_submit_button("Change Password"):
            if new_pw != new_pw2:
                st.error("New passwords do not match.")
            else:
                ok, msg = db.change_password(uid, cur_pw, new_pw)
                if ok:
                    st.toast(msg, icon="✅")
                else:
                    st.error(msg)

    st.divider()

    # ── User Management (items 8, 9) ──────────────────────────────────────────
    st.subheader("User Management")
    st.caption(
        "Each user has completely separate accounts, transactions, budgets, "
        "and categories. Adding a user creates an isolated workspace."
    )

    all_users = db.get_all_users()
    user_rows = [
        {"Username": u["username"],
         "You": "👤" if u["id"] == uid else "",
         "Created": u["created_at"][:10]}
        for u in all_users
    ]
    import pandas as pd
    st.dataframe(pd.DataFrame(user_rows), width="stretch", hide_index=True)

    tab_add, tab_remove = st.tabs(["➕ Add User", "🗑️ Remove User"])

    with tab_add:
        with st.form("add_user_form"):
            au_name = st.text_input("Username")
            au_pw   = st.text_input("Password", type="password")
            au_pw2  = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Create User", type="primary"):
                if not au_name.strip():
                    st.error("Username cannot be blank.")
                elif len(au_pw) < 8:
                    st.error("Password must be at least 8 characters.")
                elif au_pw != au_pw2:
                    st.error("Passwords do not match.")
                else:
                    try:
                        db.create_user(au_name.strip(), au_pw)
                        st.toast(f"User '{au_name.strip()}' created.", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not create user — username may already exist. ({e})")

    with tab_remove:
        other_users = [u for u in all_users if u["id"] != uid]
        if not other_users:
            st.info("No other users to remove. You cannot delete your own account here "
                    "while logged in — log in as another user to remove this one.")
        else:
            del_map  = {u["username"]: u["id"] for u in other_users}
            del_name = st.selectbox("Select user to remove", list(del_map.keys()))
            st.warning(
                f"⚠️ This will permanently delete **{del_name}** and **all** of their "
                f"accounts, transactions, budgets, and recurring rules. "
                f"This cannot be undone."
            )
            confirm = st.checkbox(f"I understand this will permanently delete {del_name}'s data.")
            if st.button("🗑️ Delete User Permanently", type="secondary", disabled=not confirm):
                db.delete_user(del_map[del_name])
                st.toast(f"User '{del_name}' deleted.", icon="🗑️")
                st.rerun()

    st.divider()

    # ── Database info ─────────────────────────────────────────────────────────
    st.subheader("Database")
    st.caption(f"Database file: `{db.DB_PATH}`")
    accounts = db.get_accounts(uid)
    txs      = db.get_transactions(uid)
    c1, c2, c3 = st.columns(3)
    c1.metric("Your Accounts",     len(accounts))
    c2.metric("Your Transactions", len(txs))
    c3.metric("Your Recurring",    len(db.get_recurring(uid)))

    st.divider()
    st.subheader("About")
    st.markdown("""
**Budget App** — Personal Finance Manager
Built with [Streamlit](https://streamlit.io) · SQLite · Plotly
    """)
