"""views/import_export.py — CSV import/export + database backup/restore (item 7)."""
import streamlit as st
from datetime import date
import os
import db
import csv_io


def render():
    uid = st.session_state["user_id"]
    st.title("📥 Import / Export")

    tab_imp, tab_exp, tab_tmpl, tab_backup = st.tabs(
        ["Import CSV", "Export CSV", "CSV Template", "Backup / Restore"]
    )

    with tab_imp:
        st.markdown("""
Upload a CSV to bulk-import transactions.

**Required columns:** `date`, `account`, `amount`, `type`
**Optional columns:** `category`, `description`
- `type` must be `Income` or `Expense`
        """)
        uploaded = st.file_uploader("Choose CSV file", type=["csv"])
        if uploaded and st.button("Import", type="primary"):
            n, errors = csv_io.import_transactions_csv(uid, uploaded.read())
            if n:
                st.toast(f"{n} transaction(s) imported.", icon="✅")
            if errors:
                st.error("Some rows had errors:")
                for e in errors:
                    st.write(f"- {e}")

    with tab_exp:
        accounts = db.get_accounts(uid)
        c1,c2,c3 = st.columns(3)
        acct_f   = c1.selectbox("Account", ["All"]+[a["name"] for a in accounts], key="exp_acct")
        start_e  = c2.date_input("From", value=date.today().replace(day=1), key="exp_start")
        end_e    = c3.date_input("To",   value=date.today(),                key="exp_end")
        acct_id_e = next((a["id"] for a in accounts if a["name"]==acct_f), None)
        txs_e    = db.get_transactions(uid, account_id=acct_id_e, start=start_e, end=end_e)
        st.write(f"Found **{len(txs_e)}** transactions.")
        if txs_e:
            st.download_button(
                "📥 Download CSV",
                data=csv_io.export_transactions_csv(txs_e),
                file_name=f"budget_export_{start_e}_{end_e}.csv",
                mime="text/csv",
            )

    with tab_tmpl:
        template = (
            "date,account,category,description,amount,type\n"
            "2024-01-15,Cheque Account,Groceries,Weekly shop,52.30,Expense\n"
            "2024-01-20,Cheque Account,Salary,January salary,3500.00,Income\n"
        )
        st.code(template, language="text")
        st.download_button("Download Template", data=template,
                           file_name="budget_template.csv", mime="text/csv")

    with tab_backup:
        st.subheader("Backup Database")
        st.caption(f"Current database: `{db.DB_PATH}`")

        default_backup = os.path.join(
            os.path.expanduser("~"),
            f"budget_backup_{date.today().isoformat()}.db"
        )
        dest = st.text_input("Backup destination path", value=default_backup,
                             key="backup_dest")
        if st.button("💾 Create Backup", type="primary"):
            ok, msg = db.backup_db(dest)
            if ok:
                st.toast(msg, icon="✅")
            else:
                st.error(msg)

        st.divider()
        st.subheader("Restore Database")
        st.warning(
            "⚠️ Restoring will **replace** the current database entirely. "
            "Create a backup first if needed."
        )
        src = st.text_input("Backup file to restore from", key="restore_src")
        if st.button("♻️ Restore from Backup", type="secondary"):
            if not src.strip():
                st.error("Please enter the path to the backup file.")
            else:
                ok, msg = db.restore_db(src.strip())
                if ok:
                    st.toast(msg, icon="✅")
                    st.info("Please restart the app to use the restored database.")
                else:
                    st.error(msg)
