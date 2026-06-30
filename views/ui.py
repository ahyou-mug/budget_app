"""
views/ui.py — Shared display helpers.

fmt_money() uses plain string formatting — callers must NOT embed the result
directly into markdown strings (use st.write / st.metric / escaped f-strings).
escape_md() sanitises any string before markdown interpolation.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import db

CURRENCY_SYMBOL = "NZ$"
CARD_HEIGHT_PX  = 340


# ── Formatting ────────────────────────────────────────────────────────────────

def fmt_money(value: float, symbol: str = CURRENCY_SYMBOL) -> str:
    return f"{symbol}{value:,.2f}"


def escape_md(text: str) -> str:
    """Escape characters that Streamlit/markdown would misinterpret."""
    for ch in ["$", "*", "_", "`", "#", "~", "|", "\\", "["]:
        text = text.replace(ch, "\\" + ch)
    return text


def fmt_money_md(value: float, symbol: str = CURRENCY_SYMBOL) -> str:
    """Money string safe for embedding in markdown ($ escaped)."""
    return escape_md(fmt_money(value, symbol))


# ── Net worth helpers ─────────────────────────────────────────────────────────

def signed_balance(acct: dict) -> float:
    bal = db.account_balance(acct["id"])
    return bal if acct["type"] == "Asset" else -bal


def net_worth(user_id: int) -> float:
    return sum(signed_balance(a) for a in db.get_accounts(user_id))


# ── Global CSS ────────────────────────────────────────────────────────────────

def inject_css():
    st.markdown(f"""
<style>
[data-testid="stSidebar"] {{ background: #1a1a2e; }}
[data-testid="stSidebar"] * {{ color: #e0e0e0 !important; }}
.panel-box {{
    height: {CARD_HEIGHT_PX}px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}}
</style>
""", unsafe_allow_html=True)


# ── Transaction table ─────────────────────────────────────────────────────────

TX_DISPLAY_COLS = ["id", "date", "account", "category", "description", "amount", "type"]


def render_tx_table(txs: list[dict], key: str = "tx_table",
                    show_delete: bool = True) -> list[int]:
    if not txs:
        st.info("No transactions found.")
        return []

    df    = pd.DataFrame(txs)[TX_DISPLAY_COLS].copy()
    event = st.dataframe(
        df, width="stretch", hide_index=True,
        on_select="rerun", selection_mode="single-row", key=key,
    )
    selected = event.selection.rows if event.selection else []

    if show_delete:
        col_del, col_info = st.columns([1, 5])
        with col_del:
            if st.button("🗑️ Delete selected", disabled=len(selected) == 0,
                         key=f"{key}_del", type="secondary"):
                tx_id = int(df.iloc[selected[0]]["id"])
                db.delete_transaction(tx_id)
                st.toast("Transaction deleted.", icon="🗑️")
                st.rerun()
        with col_info:
            if selected:
                row = df.iloc[selected[0]]
                st.caption(
                    f"Selected: {row['date']} · {row['account']} · "
                    f"{row['description'] or '—'} · {fmt_money(float(row['amount']))}"
                )
    return selected


# ── Budget health table ───────────────────────────────────────────────────────

def render_budget_health(user_id: int, viewport: str = "Monthly") -> None:
    rows = db.get_budget_actuals(user_id, viewport)
    if not rows:
        st.caption("No budgets set yet — add some in 📈 Budget.")
        return

    display = []
    for r in rows:
        pct       = r["pct_used"]
        is_income = r["budget_type"] == "Income"
        icon      = ("🟢" if pct >= 100 else ("🟡" if pct >= 75 else "🔴")
                     ) if is_income else (
                     "🟢" if pct < 75 else ("🟡" if pct < 100 else "🔴"))
        display.append({
            "":                     icon,
            "Type":                 r["budget_type"],
            "Category":             r["category"],
            "Defined Rate":         fmt_money(r["rate_amount"]) + f" / {r['rate_period'].lower()}",
            f"Budget ({viewport})": fmt_money(r["budget"]),
            "Actual":               fmt_money(r["actual"]),
            "Remaining":            fmt_money(r["remaining"]),
            "% Used":               f"{pct:.0f}%",
        })
    st.dataframe(pd.DataFrame(display), width="stretch", hide_index=True)


# ── Chart helpers ─────────────────────────────────────────────────────────────

def bar_chart(x, y, colors, title="", height=CARD_HEIGHT_PX,
              y_prefix=CURRENCY_SYMBOL) -> go.Figure:
    fig = go.Figure(go.Bar(x=x, y=y, marker_color=colors))
    fig.update_layout(
        title=title, height=height,
        margin=dict(t=36, b=8, l=8, r=8),
        yaxis=dict(tickprefix=y_prefix, tickformat=",.0f"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def grouped_bar_chart(months, income_vals, expense_vals, height=400) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Income",   x=months, y=income_vals,  marker_color="#2ecc71"))
    fig.add_trace(go.Bar(name="Expenses", x=months, y=expense_vals, marker_color="#e74c3c"))
    fig.update_layout(
        barmode="group", title="Monthly Trend (12 months)", height=height,
        margin=dict(t=36, b=8, l=8, r=8),
        yaxis=dict(tickprefix=CURRENCY_SYMBOL, tickformat=",.0f"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def pie_chart_with_pullout(labels, values, title="") -> go.Figure:
    """Pie chart where hovering pulls out the slice (explode on hover)."""
    n    = len(labels)
    pull = [0.0] * n          # start flat; JS hover updates handled by Plotly natively
    fig  = go.Figure(go.Pie(
        labels=labels, values=values,
        pull=pull,
        hoverinfo="label+percent+value",
        hoverlabel=dict(bgcolor="white", font_size=13),
        textinfo="label+percent",
    ))
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>",
    )
    # Plotly animates pull on hover natively when using the callback below
    fig.update_layout(
        title=title,
        margin=dict(t=36, b=8, l=8, r=8),
        hoverlabel=dict(bgcolor="white"),
    )
    return fig


def hbar_chart(df, x_col, y_col, title="", height=400) -> go.Figure:
    fig = px.bar(df, x=x_col, y=y_col, orientation="h", title=title,
                 color=x_col, color_continuous_scale="reds")
    fig.update_layout(
        height=height, margin=dict(t=36, b=8, l=8, r=8),
        xaxis=dict(tickprefix=CURRENCY_SYMBOL, tickformat=",.0f"),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
