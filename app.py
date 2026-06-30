"""
app.py — Entry point for the Budget App.
Handles config, multi-user auth gate, sidebar navigation, page routing.
Run with:  streamlit run app.py
"""
import streamlit as st
import db
import auth
from views.ui import inject_css
from views import dashboard, accounts, transactions, recurring, budget, reports, import_export, settings

st.set_page_config(
    page_title="Budget App",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={},
)

# ── Init ──────────────────────────────────────────────────────────────────────
db.init_db()
inject_css()

# ── Auth gate ─────────────────────────────────────────────────────────────────
if not auth.login_form():
    st.stop()

uid = st.session_state["user_id"]

# Post due recurring transactions once per session
if not st.session_state.get("recurring_posted"):
    count = db.post_due_recurring(uid)
    if count:
        st.toast(f"{count} recurring transaction(s) posted automatically.", icon="🔁")
    st.session_state["recurring_posted"] = True

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💰 Budget App")
    st.markdown(f"Logged in as **{st.session_state.get('username', 'admin')}**")
    st.divider()
    page = st.radio(
        "Navigate",
        [
            "🏠 Dashboard",
            "🏦 Accounts",
            "💸 Transactions",
            "🔁 Recurring",
            "📈 Budget",
            "📊 Reports",
            "📥 Import / Export",
            "⚙️ Settings",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    if st.button("🚪 Logout", width="stretch"):
        auth.logout()

# ── Page router ───────────────────────────────────────────────────────────────
PAGE_MAP = {
    "🏠 Dashboard":       dashboard.render,
    "🏦 Accounts":        accounts.render,
    "💸 Transactions":    transactions.render,
    "🔁 Recurring":       recurring.render,
    "📈 Budget":          budget.render,
    "📊 Reports":         reports.render,
    "📥 Import / Export": import_export.render,
    "⚙️ Settings":        settings.render,
}

PAGE_MAP[page]()
