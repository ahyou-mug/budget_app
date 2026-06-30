"""
views/transactions.py — Transaction list with:
  - Category filter (items 5)
  - Inline edit form (item 6)
  - No CSV export button (item 12)
  - Fixed caption formatting (item 13a)
"""
import streamlit as st
from datetime import date
import pandas as pd
import db
from views.ui import fmt_money, render_tx_table

TX_DISPLAY_COLS = ["id", "date", "account", "category", "description", "amount", "type"]


def _account_map(uid):
    return {a["name"]: a["id"] for a in db.get_accounts(uid)}


def _category_map(uid, tx_type):
    return {c["name"]: c["id"] for c in db.get_categories(uid, cat_type=tx_type)}


def render():
    uid      = st.session_state["user_id"]
    accounts = db.get_accounts(uid)
    st.title("💸 Transactions")

    if not accounts:
        st.warning("Add at least one account before recording transactions.")
        return

    acct_map   = _account_map(uid)
    acct_names = list(acct_map.keys())
    all_cats   = db.get_categories(uid)

    # ── Filters ───────────────────────────────────────────────────────────────
    f1, f2, f3, f4, f5 = st.columns(5)
    acct_filter  = f1.selectbox("Account",  ["All"] + acct_names,   key="tx_f_acct")
    type_filter  = f2.selectbox("Type",     ["All","Income","Expense","Transfer"],
                                key="tx_f_type")
    # Category filter — options depend on selected type
    if type_filter != "All":
        cat_options = ["All"] + [c["name"] for c in all_cats if c["type"] == type_filter]
    else:
        cat_options = ["All"] + [c["name"] for c in all_cats]
    cat_filter   = f3.selectbox("Category", cat_options, key="tx_f_cat")
    start_filter = f4.date_input("From", value=date.today().replace(day=1), key="tx_f_start")
    end_filter   = f5.date_input("To",   value=date.today(),                key="tx_f_end")

    acct_id_f = acct_map.get(acct_filter) if acct_filter != "All" else None
    type_f    = None if type_filter == "All" else type_filter
    cat_id_f  = None
    if cat_filter != "All":
        matched = [c for c in all_cats if c["name"] == cat_filter]
        if matched:
            cat_id_f = matched[0]["id"]

    txs = db.get_transactions(
        uid, account_id=acct_id_f, start=start_filter,
        end=end_filter, tx_type=type_f, category_id=cat_id_f,
    )

    # ── Transaction table ─────────────────────────────────────────────────────
    selected = render_tx_table(txs, key="tx_main")

    if txs:
        income_total  = sum(t["amount"]      for t in txs if t["type"] == "Income")
        expense_total = sum(abs(t["amount"]) for t in txs if t["type"] == "Expense")
        # Plain text caption — no markdown interpolation to avoid $ formatting bugs
        st.caption(
            f"{len(txs)} transactions  \u00b7  "
            f"Income: {fmt_money(income_total)}  \u00b7  "
            f"Expenses: {fmt_money(expense_total)}"
        )

    # ── Edit selected transaction ─────────────────────────────────────────────
    if selected and txs:
        st.divider()
        st.subheader("✏️ Edit Transaction")
        row = txs[selected[0]]

        # Only allow editing non-transfer legs independently
        if row["type"] == "Transfer":
            st.info("Transfers cannot be edited directly. Delete and re-enter if needed.")
        else:
            cats_for_type = db.get_categories(uid, cat_type=row["type"])
            cat_names     = [c["name"] for c in cats_for_type]
            cat_id_map    = {c["name"]: c["id"] for c in cats_for_type}
            current_cat   = row.get("category") or ""
            cat_index     = cat_names.index(current_cat) if current_cat in cat_names else 0

            with st.form("edit_tx_form"):
                ec1, ec2 = st.columns(2)
                new_date  = ec1.date_input("Date",
                                            value=date.fromisoformat(row["date"]))
                new_acct  = ec2.selectbox("Account", acct_names,
                                           index=acct_names.index(row["account"])
                                           if row["account"] in acct_names else 0)
                ec3, ec4  = st.columns(2)
                new_cat   = ec3.selectbox("Category", cat_names, index=cat_index)
                new_amt   = ec4.number_input("Amount", value=abs(float(row["amount"])),
                                              min_value=0.01, step=0.01)
                new_desc  = st.text_input("Description", value=row.get("description") or "")
                if st.form_submit_button("💾 Save Changes", type="primary"):
                    db.update_transaction(
                        row["id"], new_date, acct_map[new_acct],
                        cat_id_map.get(new_cat), new_desc, new_amt,
                    )
                    st.toast("Transaction updated.", icon="✅")
                    st.rerun()

    # ── Add Transaction ───────────────────────────────────────────────────────
    st.divider()
    st.subheader("Add Transaction")

    tx_type   = st.selectbox("Type", ["Expense", "Income", "Transfer"], key="new_tx_type")
    col_date, col_acct = st.columns(2)
    tx_date   = col_date.date_input("Date", value=date.today(), key="new_tx_date")
    from_acct = col_acct.selectbox(
        "From Account" if tx_type == "Transfer" else "Account",
        acct_names, key="new_tx_acct",
    )

    to_acct  = None
    cat_name = None
    cat_map_cur = {}

    if tx_type == "Transfer":
        to_options = [n for n in acct_names if n != from_acct]
        to_acct    = st.selectbox("To Account", to_options, key="new_tx_to")
    else:
        cat_map_cur = _category_map(uid, tx_type)
        cat_name    = st.selectbox(
            "Category",
            list(cat_map_cur.keys()) if cat_map_cur else ["—"],
            key=f"new_tx_cat_{tx_type}",
        )

    col_amt, col_desc = st.columns([1, 2])
    amount      = col_amt.number_input("Amount",  min_value=0.01, step=0.01,
                                        value=0.01, key="new_tx_amount")
    description = col_desc.text_input("Description", key="new_tx_desc")

    if st.button("➕ Add", type="primary", key="new_tx_submit"):
        if amount <= 0:
            st.error("Amount must be greater than zero.")
        elif tx_type == "Transfer":
            if not to_acct or from_acct == to_acct:
                st.error("From and To accounts must be different.")
            else:
                db.add_transfer(uid, tx_date, acct_map[from_acct],
                                acct_map[to_acct], amount,
                                description or "Transfer")
                st.toast(
                    f"Transfer of {fmt_money(amount)} from {from_acct} to {to_acct}.",
                    icon="✅",
                )
                st.rerun()
        else:
            cat_id = cat_map_cur.get(cat_name) if cat_name and cat_name != "—" else None
            db.add_transaction(uid, tx_date, acct_map[from_acct],
                               cat_id, description, amount, tx_type)
            st.toast(f"{tx_type} of {fmt_money(amount)} added.", icon="✅")
            st.rerun()
