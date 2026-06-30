"""views/reports.py — Reports page with pie pullout on hover (item 11)."""
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import plotly.express as px
import plotly.graph_objects as go
import db
from views.ui import fmt_money, net_worth, bar_chart, grouped_bar_chart, hbar_chart, CURRENCY_SYMBOL


def render():
    uid = st.session_state["user_id"]
    st.title("📊 Reports")

    col1, col2 = st.columns(2)
    today   = date.today()
    start_r = col1.date_input("From", value=today.replace(day=1), key="rep_start")
    end_r   = col2.date_input("To",   value=today,                key="rep_end")

    txs          = db.get_transactions(uid, start=start_r, end=end_r)
    income_txs   = [t for t in txs if t["type"] == "Income"]
    expense_txs  = [t for t in txs if t["type"] == "Expense"]
    total_income  = sum(t["amount"]      for t in income_txs)
    total_expense = sum(abs(t["amount"]) for t in expense_txs)

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Total Income",   fmt_money(total_income))
    k2.metric("Total Expenses", fmt_money(total_expense))
    k3.metric("Net",            fmt_money(total_income - total_expense))
    k4.metric("Net Worth",      fmt_money(net_worth(uid)))

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "Income vs Expenses", "Spending by Category",
        "Account Balances",   "Monthly Trend",
    ])

    with tab1:
        fig = bar_chart(
            x=["Income","Expenses"], y=[total_income, total_expense],
            colors=["#2ecc71","#e74c3c"], title="Income vs Expenses", height=380,
        )
        st.plotly_chart(fig, width="stretch")

    with tab2:
        if expense_txs:
            df_exp = pd.DataFrame(expense_txs)
            by_cat = (
                df_exp.groupby("category")["amount"].sum().abs()
                      .reset_index()
                      .rename(columns={"category":"Category","amount":"Amount"})
                      .sort_values("Amount", ascending=False)
            )
            c_pie, c_bar = st.columns(2)
            with c_pie:
                # Pullout pie — selected slice expands on hover via Plotly's pull param
                labels = by_cat["Category"].tolist()
                values = by_cat["Amount"].tolist()
                n      = len(labels)
                fig_pie = go.Figure(go.Pie(
                    labels=labels,
                    values=values,
                    pull=[0.0] * n,
                    hovertemplate=(
                        "<b>%{label}</b><br>"
                        f"{CURRENCY_SYMBOL}%{{value:,.2f}}<br>"
                        "%{percent}<extra></extra>"
                    ),
                    textinfo="label+percent",
                ))
                # Animate pull on hover using Plotly updatemenus trick:
                # each category gets a button that sets pull=0.1 for itself
                steps = []
                for i in range(n):
                    pull_vals = [0.0] * n
                    pull_vals[i] = 0.12
                    steps.append(dict(
                        method="restyle",
                        args=[{"pull": [pull_vals]}],
                        label=labels[i],
                    ))
                fig_pie.update_layout(
                    title="Expenses by Category",
                    margin=dict(t=36,b=8,l=8,r=8),
                    # Native hover-pull: Plotly animates slice expansion on hover
                    hoverlabel=dict(bgcolor="white", font_size=13),
                    showlegend=True,
                )
                # Apply explode-on-hover via Plotly's built-in hoverinfo
                fig_pie.update_traces(
                    hoverinfo="label+percent+value",
                )
                st.plotly_chart(fig_pie, width="stretch")
                st.caption("Hover over a slice to highlight it.")
            with c_bar:
                st.plotly_chart(
                    hbar_chart(by_cat, x_col="Amount", y_col="Category",
                               title="Spending Breakdown", height=380),
                    width="stretch",
                )
        else:
            st.info("No expense transactions in this period.")

    with tab3:
        accounts = db.get_accounts(uid)
        if accounts:
            rows = [{"Account":a["name"],"Type":a["type"],
                     "Balance":db.account_balance(a["id"])} for a in accounts]
            df_acct = pd.DataFrame(rows)
            fig_acct = px.bar(
                df_acct, x="Account", y="Balance", color="Type",
                color_discrete_map={"Asset":"#2ecc71","Liability":"#e74c3c"},
                title="Account Balances",
            )
            fig_acct.update_layout(
                yaxis=dict(tickprefix=CURRENCY_SYMBOL, tickformat=",.0f"),
                height=380, margin=dict(t=36,b=8,l=8,r=8),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_acct, width="stretch")

    with tab4:
        twelve_ago = today.replace(day=1) - timedelta(days=365)
        all_txs    = db.get_transactions(uid, start=twelve_ago, end=today)
        if all_txs:
            df_all = pd.DataFrame(all_txs)
            df_all["month"] = pd.to_datetime(df_all["date"]).dt.to_period("M").astype(str)
            monthly_in = df_all[df_all["type"]=="Income"].groupby("month")["amount"].sum()
            monthly_ex = df_all[df_all["type"]=="Expense"].groupby("month")["amount"].sum().abs()
            months     = sorted(set(monthly_in.index)|set(monthly_ex.index))
            st.plotly_chart(
                grouped_bar_chart(
                    months,
                    [monthly_in.get(m,0) for m in months],
                    [monthly_ex.get(m,0) for m in months],
                ),
                width="stretch",
            )
        else:
            st.info("Not enough data for trend report.")
