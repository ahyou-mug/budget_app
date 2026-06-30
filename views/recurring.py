"""views/recurring.py — Recurring transaction rules."""
import streamlit as st
import pandas as pd
from datetime import date
import db
from views.ui import fmt_money


def render():
    uid = st.session_state["user_id"]
    st.title("🔁 Recurring Transactions")
    st.info("Recurring transactions are posted automatically when due, each time you open the app.")

    tab_list, tab_add = st.tabs(["Active Rules", "Add Rule"])

    with tab_list:
        recs = db.get_recurring(uid)
        if recs:
            df = pd.DataFrame(recs)[[
                "id","account_name","category_name","description",
                "amount","type","frequency","next_due",
            ]]
            df.columns = ["ID","Account","Category","Description",
                          "Amount","Type","Frequency","Next Due"]
            event    = st.dataframe(df, width="stretch", hide_index=True,
                                    on_select="rerun", selection_mode="single-row",
                                    key="rec_table")
            selected = event.selection.rows if event.selection else []
            if st.button("🗑️ Disable selected", disabled=len(selected)==0,
                         type="secondary", key="rec_del"):
                db.delete_recurring(int(df.iloc[selected[0]]["ID"]))
                st.toast("Recurring rule disabled.", icon="🗑️")
                st.rerun()
        else:
            st.info("No recurring rules yet.")

    with tab_add:
        accounts = db.get_accounts(uid)
        if not accounts:
            st.warning("Add an account first.")
            return
        with st.form("add_recurring"):
            tx_type  = st.selectbox("Type", ["Expense","Income"])
            acct_map = {a["name"]: a["id"] for a in accounts}
            acct     = st.selectbox("Account", list(acct_map.keys()))
            cats     = db.get_categories(uid, cat_type=tx_type)
            cat_map  = {c["name"]: c["id"] for c in cats}
            cat      = st.selectbox("Category", list(cat_map.keys()) if cat_map else ["—"])
            desc     = st.text_input("Description")
            amount   = st.number_input("Amount", min_value=0.01, step=0.01)
            freq     = st.selectbox("Frequency", ["Monthly","Weekly","Daily","Yearly"])
            next_due = st.date_input("First Due Date", value=date.today())
            if st.form_submit_button("Create Rule"):
                db.add_recurring(uid, acct_map[acct], cat_map.get(cat),
                                 desc, amount, tx_type, freq, next_due)
                st.toast("Recurring rule created!", icon="✅")
                st.rerun()
