"""
views/accounts.py — Account and category management.
"""
import streamlit as st
import pandas as pd
import db
from views.ui import fmt_money

CURRENCIES = ["NZD", "USD", "GBP", "EUR", "AUD", "JPY"]


def render():
    uid = st.session_state["user_id"]
    st.title("🏦 Accounts")
    tab_list, tab_add, tab_edit, tab_cats = st.tabs(
        ["All Accounts", "Add Account", "Edit / Delete", "Categories"]
    )

    with tab_list:
        accounts = db.get_accounts(uid)
        if accounts:
            rows = [
                {
                    "Name":            a["name"],
                    "Type":            a["type"],
                    "Savings":         "💰" if a.get("subtype") == "Savings" else "",
                    "Currency":        a["currency"],
                    "Opening Balance": fmt_money(a["opening_bal"]),
                    "Current Balance": fmt_money(db.account_balance(a["id"])),
                    "Note":            a["note"] or "",
                }
                for a in accounts
            ]
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        else:
            st.info("No accounts yet.")

    with tab_add:
        with st.form("add_account"):
            name        = st.text_input("Account Name *")
            acct_type   = st.selectbox("Type *", ["Asset", "Liability"])
            opening_bal = st.number_input("Opening Balance", value=0.0, step=0.01)
            currency    = st.selectbox("Currency", CURRENCIES)
            is_savings  = st.checkbox(
                "Tag as Savings account",
                help="Savings accounts contribute to the Savings bucket in 50/30/20.",
            )
            note = st.text_input("Note (optional)")
            if st.form_submit_button("Add Account"):
                if not name.strip():
                    st.error("Account name is required.")
                else:
                    try:
                        db.add_account(uid, name.strip(), acct_type, opening_bal,
                                       currency, note,
                                       subtype="Savings" if is_savings else None)
                        st.toast(f"Account '{name.strip()}' added!", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab_edit:
        accounts = db.get_accounts(uid)
        if not accounts:
            st.info("No accounts to edit.")
        else:
            acct_map = {a["name"]: a for a in accounts}
            selected  = st.selectbox("Select account", list(acct_map.keys()))
            a = acct_map[selected]
            with st.form("edit_account"):
                new_name   = st.text_input("Name", value=a["name"])
                new_type   = st.selectbox("Type", ["Asset", "Liability"],
                                          index=0 if a["type"] == "Asset" else 1)
                new_bal    = st.number_input("Opening Balance",
                                             value=float(a["opening_bal"]), step=0.01)
                new_cur    = st.selectbox(
                    "Currency", CURRENCIES,
                    index=CURRENCIES.index(a["currency"])
                    if a["currency"] in CURRENCIES else 0,
                )
                is_savings = st.checkbox("Tag as Savings account",
                                         value=(a.get("subtype") == "Savings"))
                new_note   = st.text_input("Note", value=a["note"] or "")
                c1, c2     = st.columns(2)
                if c1.form_submit_button("💾 Save Changes"):
                    db.update_account(
                        a["id"], new_name, new_type, new_bal, new_cur, new_note,
                        subtype="Savings" if is_savings else None,
                    )
                    st.toast("Account updated.", icon="✅")
                    st.rerun()
                if c2.form_submit_button("🗑️ Delete Account", type="secondary"):
                    db.delete_account(a["id"])
                    st.toast("Account deleted.", icon="🗑️")
                    st.rerun()

    with tab_cats:
        st.subheader("Manage Categories")
        cats = db.get_categories(uid)
        if cats:
            st.dataframe(
                pd.DataFrame(cats)[["id", "name", "type"]],
                width="stretch", hide_index=True,
            )
        col1, col2 = st.columns(2)
        with col1:
            with st.form("add_cat"):
                cat_name = st.text_input("Category Name")
                cat_type = st.selectbox("Type", ["Income", "Expense"])
                if st.form_submit_button("Add Category"):
                    if cat_name.strip():
                        db.add_category(uid, cat_name.strip(), cat_type)
                        st.toast(f"Category '{cat_name.strip()}' added.", icon="✅")
                        st.rerun()
        with col2:
            with st.form("del_cat"):
                deletable = {
                    f"{c['name']} ({c['type']})": c["id"]
                    for c in cats if c["type"] != "Transfer"
                }
                if deletable:
                    del_cat = st.selectbox("Delete Category", list(deletable.keys()))
                    if st.form_submit_button("Delete", type="secondary"):
                        db.delete_category(deletable[del_cat])
                        st.toast("Category deleted.", icon="🗑️")
                        st.rerun()
