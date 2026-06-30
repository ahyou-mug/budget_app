"""
auth.py — Multi-user authentication.
Login screen shows existing users + a 'New user' option.
Session state carries user_id and username.
"""
import streamlit as st
import db

DEFAULT_USER = "admin"
DEFAULT_PASS = "changeme123"


def _ensure_default_user():
    """Create the default admin user if no users exist at all."""
    if not db.get_all_users():
        db.create_user(DEFAULT_USER, DEFAULT_PASS)


def login_form() -> bool:
    """Render login UI. Returns True when authenticated."""
    if st.session_state.get("authenticated"):
        return True

    _ensure_default_user()

    st.markdown(
        "<h2 style='text-align:center; margin-bottom:0'>💰 Budget App</h2>"
        "<p style='text-align:center; color:grey; margin-top:4px'>"
        "Personal Finance Manager</p>",
        unsafe_allow_html=True,
    )

    col = st.columns([1, 2, 1])[1]
    with col:
        users     = db.get_all_users()
        usernames = [u["username"] for u in users] + ["➕ Create new user"]
        choice    = st.selectbox("Select user", usernames, key="login_user_select")

        if choice == "➕ Create new user":
            with st.form("create_user_form"):
                st.subheader("Create Account")
                new_user = st.text_input("Username")
                new_pw   = st.text_input("Password", type="password")
                new_pw2  = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Create & Sign In", width='stretch'):
                    if not new_user.strip():
                        st.error("Username cannot be blank.")
                    elif len(new_pw) < 8:
                        st.error("Password must be at least 8 characters.")
                    elif new_pw != new_pw2:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            uid = db.create_user(new_user.strip(), new_pw)
                            st.session_state["authenticated"] = True
                            st.session_state["user_id"]       = uid
                            st.session_state["username"]      = new_user.strip()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not create user: {e}")
        else:
            with st.form("login_form"):
                st.subheader(f"Sign In as {choice}")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Login", width='stretch'):
                    user = db.verify_user(choice, password)
                    if user:
                        st.session_state["authenticated"] = True
                        st.session_state["user_id"]       = user["id"]
                        st.session_state["username"]      = user["username"]
                        st.rerun()
                    else:
                        st.error("Incorrect password.")

            # First-run hint
            users_with_default = [
                u for u in users
                if db.verify_user(u["username"], DEFAULT_PASS)
            ]
            if any(u["username"] == choice for u in users_with_default):
                st.info(
                    f"Default password is `{DEFAULT_PASS}`. "
                    "Please change it in ⚙️ Settings after logging in."
                )
    return False


def logout():
    for key in ["authenticated", "user_id", "username", "recurring_posted"]:
        st.session_state.pop(key, None)
    st.rerun()
