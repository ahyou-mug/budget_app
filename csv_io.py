"""
csv_io.py — CSV import / export utilities.
"""
import io
import pandas as pd
import db

EXPORT_COLUMNS = ["id", "date", "account", "category", "description", "amount", "type"]
IMPORT_REQUIRED = {"date", "account", "amount", "type"}


def export_transactions_csv(transactions: list[dict]) -> str:
    if not transactions:
        return ""
    rows = [{c: t.get(c, "") for c in EXPORT_COLUMNS} for t in transactions]
    return pd.DataFrame(rows, columns=EXPORT_COLUMNS).to_csv(index=False)


def import_transactions_csv(user_id: int, file_bytes: bytes) -> tuple[int, list[str]]:
    errors   = []
    imported = 0
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        return 0, [f"Could not parse CSV: {e}"]

    df.columns   = [c.strip().lower() for c in df.columns]
    missing      = IMPORT_REQUIRED - set(df.columns)
    if missing:
        return 0, [f"CSV is missing required columns: {', '.join(missing)}"]

    accounts   = {a["name"].lower(): a["id"] for a in db.get_accounts(user_id)}
    categories = {c["name"].lower(): c for c in db.get_categories(user_id)}

    for i, row in df.iterrows():
        lineno = i + 2
        try:
            tx_date = pd.to_datetime(row["date"]).date()
        except Exception:
            errors.append(f"Row {lineno}: invalid date '{row['date']}'"); continue

        acct_name = str(row["account"]).strip().lower()
        if acct_name not in accounts:
            errors.append(f"Row {lineno}: unknown account '{row['account']}'"); continue
        acct_id = accounts[acct_name]

        try:
            amount = float(
                str(row["amount"]).replace(",", "").replace("£", "")
                                  .replace("$", "").replace("NZ", "")
            )
        except Exception:
            errors.append(f"Row {lineno}: invalid amount '{row['amount']}'"); continue

        tx_type = str(row.get("type", "Expense")).strip().capitalize()
        if tx_type not in ("Income", "Expense"):
            errors.append(
                f"Row {lineno}: type must be Income or Expense, got '{tx_type}'"
            ); continue

        cat_name = str(row.get("category", "")).strip().lower()
        cat_id   = categories[cat_name]["id"] if cat_name in categories else None
        description = str(row.get("description", "")).strip()

        db.add_transaction(user_id, tx_date, acct_id, cat_id,
                           description, abs(amount), tx_type)
        imported += 1

    return imported, errors
