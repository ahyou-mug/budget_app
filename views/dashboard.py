"""
views/dashboard.py — Dashboard page.
Savings metric added to KPI bar.
Savings shown as separate bar on the net worth chart.
Budget Health table removed; 50/30/20 compact summary retained.
"""
import streamlit as st
import pandas as pd
from datetime import date
import db
from views.ui import (fmt_money, net_worth, signed_balance,
                      bar_chart, render_tx_table, CARD_HEIGHT_PX)


def render():
    uid   = st.session_state["user_id"]
    st.title("🏠 Dashboard")

    accounts    = db.get_accounts(uid)
    nw          = net_worth(uid)
    today       = date.today()
    month_start = today.replace(day=1)

    txs     = db.get_transactions(uid, start=month_start, end=today)
    income  = sum(t["amount"]       for t in txs if t["type"] == "Income")
    expense = sum(abs(t["amount"])  for t in txs if t["type"] == "Expense")
    savings = db.get_savings_delta(uid, "Monthly")

    # ── KPI row ───────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Net Worth",            fmt_money(nw))
    k2.metric("Income (this month)",  fmt_money(income))
    k3.metric("Expenses (this month)",fmt_money(expense),
              delta=fmt_money(income - expense))
    k4.metric("Savings (this month)", fmt_money(savings),
              delta=None)
    k5.metric("Accounts",             len(accounts))

    st.divider()

    # ── Side-by-side panels ───────────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Account Balances")
        if accounts:
            rows = [
                {
                    "Account": a["name"],
                    "Type":    a["type"],
                    "Savings": "💰" if a.get("subtype") == "Savings" else "",
                    "Balance": fmt_money(db.account_balance(a["id"])),
                }
                for a in accounts
            ]
            st.dataframe(
                pd.DataFrame(rows),
                width="stretch",
                hide_index=True,
                height=CARD_HEIGHT_PX - 50,
            )
        else:
            st.info("No accounts yet — add one in Accounts.")

    with col_right:
        st.subheader("Net Worth Breakdown")
        if accounts:
            asset_total   = sum(db.account_balance(a["id"])
                                for a in accounts if a["type"] == "Asset"
                                and a.get("subtype") != "Savings")
            savings_total = sum(db.account_balance(a["id"])
                                for a in accounts if a.get("subtype") == "Savings")
            liab_total    = sum(db.account_balance(a["id"])
                                for a in accounts if a["type"] == "Liability")
            fig = bar_chart(
                x=["Assets", "Savings", "Liabilities"],
                y=[asset_total, savings_total, liab_total],
                colors=["#2ecc71", "#5b9bd5", "#e74c3c"],
                title="",
                height=CARD_HEIGHT_PX - 50,
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No accounts yet.")

    # ── Recent transactions ───────────────────────────────────────────────────
    st.subheader("Recent Transactions")
    recent = db.get_transactions(uid, limit=10)
    render_tx_table(recent, key="dash_tx", show_delete=False)

    # ── 50/30/20 compact ─────────────────────────────────────────────────────
    data_5030 = db.get_503020_actuals(uid, "Monthly")
    if data_5030["income"] > 0 and any(b["actual"] > 0 for b in data_5030["buckets"]):
        st.divider()
        st.subheader("⚖️ 50/30/20 — This Month")
        cols = st.columns(3)
        for col, b in zip(cols, data_5030["buckets"]):
            pct        = b["pct_of_income"]
            target     = b["target_pct"]
            is_savings = b["bucket"] == "Savings"
            ok         = pct >= target if is_savings else pct <= target
            delta      = pct - target
            icon       = "🟢" if ok else ("🟡" if abs(delta) <= 5 else "🔴")
            col.metric(
                f"{icon} {b['bucket']} (target {target:.0f}%)",
                f"{pct:.1f}%",
                delta=f"{delta:+.1f}pp",
                delta_color="normal" if is_savings else "inverse",
            )
