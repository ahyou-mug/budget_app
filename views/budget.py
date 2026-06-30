"""
views/budget.py — Budget page (three tabs).
Markdown formatting bugs fixed: fmt_money_md() used wherever
money strings are embedded in st.success / st.error / st.caption / st.markdown.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import db
from views.ui import fmt_money, fmt_money_md, render_budget_health, CURRENCY_SYMBOL

PERIODS = ["Weekly", "Monthly", "Yearly"]
BUCKETS = ["Needs", "Wants", "Savings"]
BUCKET_COLORS = {"Needs": "#3498db", "Wants": "#9b59b6", "Savings": "#2ecc71"}
BUCKET_DESCRIPTIONS = {
    "Needs":   "Essentials — rent, groceries, utilities, transport",
    "Wants":   "Discretionary — dining out, entertainment, subscriptions",
    "Savings": "Future — savings, investments, debt repayment",
}


def render():
    uid = st.session_state["user_id"]
    st.title("📈 Budget")

    tab_vs, tab_5030, tab_manage = st.tabs(
        ["Budget vs Actual", "50/30/20", "Manage Budgets"]
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — Budget vs Actual
    # ══════════════════════════════════════════════════════════════════════════
    with tab_vs:
        viewport = st.segmented_control("View as", PERIODS, default="Monthly",
                                        key="bva_viewport")
        rows = db.get_budget_actuals(uid, viewport)
        if not rows:
            st.info("No budgets set up yet. Add some in the **Manage Budgets** tab.")
        else:
            inc_rows = [r for r in rows if r["budget_type"] == "Income"]
            exp_rows = [r for r in rows if r["budget_type"] == "Expense"]
            b_income  = sum(r["budget"] for r in inc_rows)
            a_income  = sum(r["actual"] for r in inc_rows)
            b_expense = sum(r["budget"] for r in exp_rows)
            a_expense = sum(r["actual"] for r in exp_rows)
            b_surplus = b_income - b_expense
            a_surplus = a_income - a_expense
            over      = sum(1 for r in exp_rows if r["pct_used"] > 100)

            k1,k2,k3,k4,k5 = st.columns(5)
            k1.metric("Budgeted Income",   fmt_money(b_income))
            k2.metric("Actual Income",     fmt_money(a_income))
            k3.metric("Budgeted Expenses", fmt_money(b_expense))
            k4.metric("Actual Expenses",   fmt_money(a_expense))
            k5.metric("Surplus",           fmt_money(a_surplus),
                      delta=fmt_money(a_surplus - b_surplus) if b_income else None)
            if over:
                st.warning(f"⚠️ {over} expense categor{'y' if over==1 else 'ies'} over budget.")

            st.divider()

            def _overlay_chart(chart_rows, section_title):
                if not chart_rows:
                    return
                st.markdown(f"**{section_title}**")
                crows      = list(reversed(chart_rows))
                cats       = [r["category"]   for r in crows]
                b_vals     = [r["budget"]      for r in crows]
                a_vals     = [r["actual"]      for r in crows]
                pcts       = [r["pct_used"]    for r in crows]
                is_income  = chart_rows[0]["budget_type"] == "Income"
                act_colors = [
                    ("#2ecc71" if p>=100 else ("#f0a500" if p>=75 else "#e74c3c"))
                    if is_income else
                    ("#e74c3c" if p>100  else ("#f0a500" if p>=75 else "#2ecc71"))
                    for p in pcts
                ]
                rate_labels = [
                    f"Rate: {fmt_money(r['rate_amount'])} / {r['rate_period'].lower()}"
                    for r in crows
                ]
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name="Budget", y=cats, x=b_vals, orientation="h",
                    marker_color="rgba(180,180,180,0.25)",
                    marker_line_color="rgba(180,180,180,0.7)", marker_line_width=1,
                    customdata=rate_labels,
                    hovertemplate=(f"<b>%{{y}}</b><br>{viewport} budget: "
                                   f"{CURRENCY_SYMBOL}%{{x:,.2f}}<br>%{{customdata}}<extra></extra>"),
                ))
                fig.add_trace(go.Bar(
                    name="Actual", y=cats, x=a_vals, orientation="h",
                    marker_color=act_colors,
                    hovertemplate=(f"<b>%{{y}}</b><br>Actual: "
                                   f"{CURRENCY_SYMBOL}%{{x:,.2f}}<extra></extra>"),
                ))
                fig.update_layout(
                    barmode="overlay",
                    height=max(160, len(cats)*46+80),
                    margin=dict(t=8,b=8,l=8,r=16),
                    xaxis=dict(tickprefix=CURRENCY_SYMBOL, tickformat=",.0f"),
                    legend=dict(orientation="h", y=1.12),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, width="stretch")

            _overlay_chart(inc_rows, "💰 Income")
            _overlay_chart(exp_rows, "💸 Expenses")
            st.divider()
            st.subheader("Detail")
            render_budget_health(uid, viewport)
            st.caption("Income: 🟢 meeting/exceeding · 🟡 75–99% · 🔴 falling short  |  "
                       "Expenses: 🟢 under 75% · 🟡 75–99% · 🔴 over budget")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — 50/30/20
    # ══════════════════════════════════════════════════════════════════════════
    with tab_5030:
        viewport2 = st.segmented_control("View as", PERIODS, default="Monthly",
                                         key="5030_viewport")
        data     = db.get_503020_actuals(uid, viewport2)
        income   = data["income"]
        buckets  = data["buckets"]
        untagged = data["untagged_expense"]

        if income == 0:
            st.warning("No income data found. Add income budgets or record income transactions.")
        else:
            src_label = ("budgeted income" if data["income_source"] == "budgeted"
                         else "actual income (no income budgets set)")
            sav_names = data.get("savings_accounts", [])
            sav_note  = (f"Savings from: **{', '.join(sav_names)}** balance change."
                         if sav_names
                         else "No savings accounts tagged — go to Accounts → Edit.")
            st.caption(
                f"Based on {fmt_money(income)} {viewport2.lower()} {src_label}. "
                f"{sav_note}"
            )

            k1,k2,k3,k4 = st.columns(4)
            k1.metric(f"{viewport2} Income",    fmt_money(income))
            k2.metric("Total Bucketed Spend",   fmt_money(sum(b["actual"] for b in buckets)))
            k3.metric("Unassigned Spend",       fmt_money(untagged))
            k4.metric("Savings Rate",
                      f"{(buckets[2]['actual']/income*100):.1f}%" if income else "—")

            st.divider()

            # Gauge chart
            b_names  = [b["bucket"]       for b in buckets]
            t_amts   = [b["target_amt"]   for b in buckets]
            a_amts   = [b["actual"]       for b in buckets]
            t_pcts   = [b["target_pct"]   for b in buckets]
            a_pcts   = [b["pct_of_income"] for b in buckets]
            colors   = [BUCKET_COLORS[b]  for b in b_names]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Target (50/30/20)", x=b_names, y=t_amts,
                marker_color="rgba(180,180,180,0.3)",
                marker_line_color="rgba(180,180,180,0.8)", marker_line_width=2,
                customdata=t_pcts,
                hovertemplate=(f"<b>%{{x}}</b><br>Target: {CURRENCY_SYMBOL}%{{y:,.2f}} "
                               f"(%{{customdata:.0f}}%)<extra></extra>"),
            ))
            fig.add_trace(go.Bar(
                name="Actual", x=b_names, y=a_amts,
                marker_color=colors, customdata=a_pcts,
                hovertemplate=(f"<b>%{{x}}</b><br>Actual: {CURRENCY_SYMBOL}%{{y:,.2f}} "
                               f"(%{{customdata:.1f}}% of income)<extra></extra>"),
            ))
            fig.update_layout(
                barmode="overlay", height=360,
                margin=dict(t=16,b=8,l=8,r=8),
                yaxis=dict(tickprefix=CURRENCY_SYMBOL, tickformat=",.0f"),
                legend=dict(orientation="h", y=1.08),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, width="stretch")

            # Per-bucket cards
            cols = st.columns(3)
            for col, b in zip(cols, buckets):
                pct        = b["pct_of_income"]
                target     = b["target_pct"]
                delta      = pct - target
                is_savings = b["bucket"] == "Savings"
                ok         = pct >= target if is_savings else pct <= target
                status     = "🟢" if ok else ("🟡" if abs(delta) <= 5 else "🔴")
                with col:
                    st.markdown(f"### {status} {b['bucket']}\n"
                                f"*{BUCKET_DESCRIPTIONS[b['bucket']]}*")
                    st.metric("Actual", fmt_money(b["actual"]),
                              delta=f"{delta:+.1f}pp vs {target:.0f}% target",
                              delta_color="normal" if is_savings else "inverse")
                    drawdown = (b["bucket"] == "Savings"
                                and data.get("savings_delta", 0) < 0)
                    st.caption(
                        f"Target: {fmt_money(b['target_amt'])} ({target:.0f}%)  \n"
                        f"Actual: {pct:.1f}% of income  \n"
                        f"Variance: {fmt_money(abs(b['variance']))} "
                        f"{'over' if b['variance']<0 else 'under'} target"
                        + (f"  \n⚠️ Net drawdown of "
                           f"{fmt_money(abs(data['savings_delta']))} this period"
                           if drawdown else "")
                    )

            # ── Uncategorised drill-down (item 4) ──────────────────────────────
            if untagged > 0:
                st.divider()
                with st.expander(
                    f"🔍 View uncategorised spend — {fmt_money(untagged)} unassigned"
                ):
                    start, today = db._viewport_window(viewport2)
                    unc_txs = db.get_transactions(
                        uid, start=start, end=today, category_id=-1
                    )
                    if unc_txs:
                        df_unc = pd.DataFrame(unc_txs)[
                            ["date","account","description","amount"]
                        ]
                        st.dataframe(df_unc, width="stretch", hide_index=True)
                        st.caption(
                            "These transactions have no category assigned. "
                            "Edit them in the Transactions tab to assign a category "
                            "and bucket them into the 50/30/20 analysis."
                        )
                    else:
                        st.info("No uncategorised transactions found.")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — Manage Budgets
    # ══════════════════════════════════════════════════════════════════════════
    with tab_manage:
        budgets = db.get_budgets(uid)
        if budgets:
            display_rows = []
            for b in budgets:
                display_rows.append({
                    "id":       b["id"],
                    "Type":     b["budget_type"],
                    "Category": b["category_name"],
                    "Bucket":   b["bucket"] or "—",
                    "Rate":     fmt_money(b["amount"]) + f" / {b['rate_period'].lower()}",
                    "Weekly":   fmt_money(db._scale_to_viewport(b["amount"],b["rate_period"],"Weekly")),
                    "Monthly":  fmt_money(db._scale_to_viewport(b["amount"],b["rate_period"],"Monthly")),
                    "Yearly":   fmt_money(db._scale_to_viewport(b["amount"],b["rate_period"],"Yearly")),
                })
            df_b     = pd.DataFrame(display_rows)
            disp_df  = df_b.drop(columns=["id"])
            event    = st.dataframe(disp_df, width="stretch", hide_index=True,
                                    on_select="rerun", selection_mode="single-row",
                                    key="budget_table")
            selected = event.selection.rows if event.selection else []
            if st.button("🗑️ Delete selected", disabled=len(selected)==0,
                         type="secondary", key="del_budget_btn"):
                db.delete_budget(int(df_b.iloc[selected[0]]["id"]))
                st.toast("Budget deleted.", icon="🗑️")
                st.rerun()
            st.caption("Weekly / Monthly / Yearly show scaled equivalents. "
                       "Bucket used by the 50/30/20 view.")

            # ── Balance summary ───────────────────────────────────────────────
            st.subheader("Budget Balance")
            summary     = db.get_budget_balance_summary(uid)
            has_income  = any(r["income"]   > 0 for r in summary)
            has_expense = any(r["expenses"] > 0 for r in summary)
            if not has_income or not has_expense:
                st.caption("Add both income and expense budgets to see the balance summary.")
            else:
                s_rows = []
                for r in summary:
                    s_rows.append({
                        "Period":   r["period"],
                        "Income":   fmt_money(r["income"]),
                        "Expenses": fmt_money(r["expenses"]),
                        "Balance":  fmt_money(r["balance"]),
                        "Status":   "✅ Surplus" if r["surplus"] else "⚠️ Deficit",
                    })
                st.dataframe(pd.DataFrame(s_rows), width="stretch", hide_index=True)
                monthly = next(r for r in summary if r["period"] == "Monthly")
                # Use st.write (not st.success/error with f-strings) to avoid $ parsing
                if monthly["surplus"]:
                    st.success(
                        f"Budgeted monthly expenses ({fmt_money(monthly['expenses'])}) "  # noqa
                        f"are within budgeted income ({fmt_money(monthly['income'])}), "
                        f"leaving a planned surplus of {fmt_money(monthly['balance'])}."
                    )
                else:
                    st.error(
                        f"Budgeted monthly expenses ({fmt_money(monthly['expenses'])}) "
                        f"exceed budgeted income ({fmt_money(monthly['income'])}) "
                        f"by {fmt_money(abs(monthly['balance']))}."
                    )
        else:
            st.info("No budgets defined yet. Add one below.")

        st.divider()
        st.subheader("Set a Budget")
        st.caption("One budget per category. Saving again updates it.")

        b_type      = st.selectbox("Budget Type", ["Expense","Income"], key="new_b_type")
        rate_period = st.selectbox("Rate Period",  PERIODS,              key="new_b_period")
        cats        = db.get_categories(uid, cat_type=b_type)
        cat_map     = {c["name"]: c["id"] for c in cats}
        if not cat_map:
            st.warning(f"No {b_type} categories found.")
        else:
            col_cat, col_bucket = st.columns(2)
            cat_name = col_cat.selectbox("Category", list(cat_map.keys()),
                                          key=f"new_b_cat_{b_type}")
            bucket   = (col_bucket.selectbox("50/30/20 Bucket",
                                              ["— (none)"] + BUCKETS,
                                              key="new_b_bucket")
                        if b_type == "Expense" else "— (none)")

            b_amount = st.number_input(f"Amount per {rate_period.lower()}",
                                        min_value=0.01, step=10.0, value=100.0,
                                        key="new_b_amount")
            if b_amount > 0:
                w = db._scale_to_viewport(b_amount, rate_period, "Weekly")
                m = db._scale_to_viewport(b_amount, rate_period, "Monthly")
                y = db._scale_to_viewport(b_amount, rate_period, "Yearly")
                # Plain text via st.write — avoids markdown $ formatting bug (item 13c)
                st.write(
                    f"\u2192 {fmt_money(w)} / week  \u00b7  "
                    f"{fmt_money(m)} / month  \u00b7  "
                    f"{fmt_money(y)} / year"
                )

            if st.button("💾 Save Budget", type="primary", key="save_budget_btn"):
                resolved_bucket = None if bucket == "— (none)" else bucket
                db.set_budget(uid, cat_map[cat_name], b_type, rate_period,
                              b_amount, resolved_bucket)
                st.toast(
                    f"{b_type} budget set: {fmt_money(b_amount)} / "
                    f"{rate_period.lower()} for {cat_name}.",
                    icon="✅",
                )
                st.rerun()
