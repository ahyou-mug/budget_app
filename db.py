"""
db.py — SQLite database layer.
Multi-user: every data table carries a user_id FK.
All query functions require a user_id parameter.
"""
import sqlite3
import os
import calendar
from datetime import date, datetime, timedelta
from contextlib import contextmanager

DB_PATH = os.environ.get("BUDGET_DB_PATH", "budget.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('Asset','Liability')),
                subtype     TEXT CHECK(subtype IN ('Savings') OR subtype IS NULL),
                currency    TEXT NOT NULL DEFAULT 'NZD',
                note        TEXT,
                opening_bal REAL NOT NULL DEFAULT 0.0,
                created_at  TEXT NOT NULL DEFAULT (date('now')),
                UNIQUE(user_id, name)
            );

            CREATE TABLE IF NOT EXISTS categories (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name    TEXT NOT NULL,
                type    TEXT NOT NULL CHECK(type IN ('Income','Expense','Transfer')),
                UNIQUE(user_id, name)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                date        TEXT NOT NULL,
                account_id  INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                description TEXT,
                amount      REAL NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('Income','Expense','Transfer')),
                transfer_id INTEGER,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS recurring (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                description  TEXT,
                amount       REAL NOT NULL,
                type         TEXT NOT NULL CHECK(type IN ('Income','Expense')),
                frequency    TEXT NOT NULL CHECK(frequency IN ('Daily','Weekly','Monthly','Yearly')),
                next_due     TEXT NOT NULL,
                active       INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category_id  INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                budget_type  TEXT NOT NULL DEFAULT 'Expense'
                             CHECK(budget_type IN ('Income','Expense')),
                rate_period  TEXT NOT NULL CHECK(rate_period IN ('Weekly','Monthly','Yearly')),
                amount       REAL NOT NULL CHECK(amount > 0),
                bucket       TEXT CHECK(bucket IN ('Needs','Wants','Savings') OR bucket IS NULL),
                UNIQUE(user_id, category_id)
            );
        """)


# ── Users ─────────────────────────────────────────────────────────────────────

def get_all_users() -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT id, username, created_at FROM users ORDER BY username"
        ).fetchall()]


def create_user(username: str, password: str) -> int:
    """Create a new user, seed default categories, return user_id."""
    import bcrypt
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?,?)",
            (username.strip(), hashed)
        )
        uid = cur.lastrowid
        _seed_categories(conn, uid)
    return uid


def _seed_categories(conn, user_id: int):
    defaults = [
        ("Salary", "Income"), ("Freelance", "Income"), ("Interest", "Income"),
        ("Other Income", "Income"),
        ("Groceries", "Expense"), ("Rent/Mortgage", "Expense"),
        ("Utilities", "Expense"), ("Transport", "Expense"),
        ("Dining Out", "Expense"), ("Entertainment", "Expense"),
        ("Healthcare", "Expense"), ("Clothing", "Expense"),
        ("Education", "Expense"), ("Subscriptions", "Expense"),
        ("Other Expense", "Expense"),
        ("Transfer", "Transfer"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO categories (user_id, name, type) VALUES (?,?,?)",
        [(user_id, name, typ) for name, typ in defaults]
    )


def verify_user(username: str, password: str) -> dict | None:
    """Return user dict if credentials match, else None."""
    import bcrypt
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? COLLATE NOCASE", (username,)
        ).fetchone()
    if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return dict(row)
    return None


def change_username(user_id: int, new_username: str) -> tuple[bool, str]:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username=? COLLATE NOCASE AND id!=?",
            (new_username.strip(), user_id)
        ).fetchone()
        if existing:
            return False, "That username is already taken."
        conn.execute(
            "UPDATE users SET username=? WHERE id=?",
            (new_username.strip(), user_id)
        )
    return True, "Username updated."


def change_password(user_id: int, current_pw: str, new_pw: str) -> tuple[bool, str]:
    import bcrypt
    with get_conn() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id=?", (user_id,)
        ).fetchone()
    if not row or not bcrypt.checkpw(current_pw.encode(), row["password_hash"].encode()):
        return False, "Current password is incorrect."
    if len(new_pw) < 8:
        return False, "New password must be at least 8 characters."
    hashed = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?", (hashed, user_id)
        )
    return True, "Password changed successfully."


def delete_user(user_id: int) -> None:
    """Delete user and all their data (CASCADE handles child rows)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))


# ── Accounts ──────────────────────────────────────────────────────────────────

def get_accounts(user_id: int) -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM accounts WHERE user_id=? ORDER BY type, name", (user_id,)
        ).fetchall()]


def add_account(user_id, name, acct_type, opening_bal=0.0,
                currency="NZD", note="", subtype=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO accounts (user_id,name,type,subtype,opening_bal,currency,note) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, name, acct_type, subtype, opening_bal, currency, note)
        )


def update_account(acct_id, name, acct_type, opening_bal,
                   currency, note, subtype=None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE accounts SET name=?,type=?,subtype=?,opening_bal=?,currency=?,note=? "
            "WHERE id=?",
            (name, acct_type, subtype, opening_bal, currency, note, acct_id)
        )


def delete_account(acct_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM accounts WHERE id=?", (acct_id,))


def account_balance(acct_id: int) -> float:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT opening_bal FROM accounts WHERE id=?", (acct_id,)
        ).fetchone()
        if row is None:
            return 0.0
        opening = row["opening_bal"]
        signed = conn.execute("""
            SELECT COALESCE(SUM(
                CASE WHEN type='Income'  THEN  amount
                     WHEN type='Expense' THEN -ABS(amount)
                     ELSE amount END
            ), 0) FROM transactions WHERE account_id=?
        """, (acct_id,)).fetchone()[0]
        return opening + signed


def account_balance_at(acct_id: int, as_of: date) -> float:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT opening_bal FROM accounts WHERE id=?", (acct_id,)
        ).fetchone()
        if row is None:
            return 0.0
        opening = row["opening_bal"]
        signed = conn.execute("""
            SELECT COALESCE(SUM(
                CASE WHEN type='Income'  THEN  amount
                     WHEN type='Expense' THEN -ABS(amount)
                     ELSE amount END
            ), 0) FROM transactions WHERE account_id=? AND date<=?
        """, (acct_id, str(as_of))).fetchone()[0]
        return opening + signed


# ── Categories ────────────────────────────────────────────────────────────────

def get_categories(user_id: int, cat_type=None) -> list[dict]:
    with get_conn() as conn:
        if cat_type:
            rows = conn.execute(
                "SELECT * FROM categories WHERE user_id=? AND type=? ORDER BY name",
                (user_id, cat_type)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM categories WHERE user_id=? ORDER BY type, name",
                (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]


def add_category(user_id: int, name: str, cat_type: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO categories (user_id,name,type) VALUES (?,?,?)",
            (user_id, name, cat_type)
        )


def delete_category(cat_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))


# ── Transactions ──────────────────────────────────────────────────────────────

def get_transactions(user_id: int, account_id=None, start=None, end=None,
                     tx_type=None, category_id=None, limit=None) -> list[dict]:
    sql = """
        SELECT t.id, t.date, a.name AS account, c.name AS category,
               t.description, t.amount, t.type, t.transfer_id,
               t.account_id, t.category_id
        FROM transactions t
        JOIN accounts a ON a.id = t.account_id
        LEFT JOIN categories c ON c.id = t.category_id
        WHERE t.user_id=?
    """
    params: list = [user_id]
    if account_id:
        sql += " AND t.account_id=?";   params.append(account_id)
    if start:
        sql += " AND t.date>=?";        params.append(str(start))
    if end:
        sql += " AND t.date<=?";        params.append(str(end))
    if tx_type:
        sql += " AND t.type=?";         params.append(tx_type)
    if category_id is not None:
        if category_id == -1:           # sentinel for "uncategorised"
            sql += " AND t.category_id IS NULL AND t.type='Expense'"
        else:
            sql += " AND t.category_id=?"; params.append(category_id)
    sql += " ORDER BY t.date DESC, t.id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def add_transaction(user_id, tx_date, account_id, category_id,
                    description, amount, tx_type):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transactions "
            "(user_id,date,account_id,category_id,description,amount,type) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, str(tx_date), account_id, category_id,
             description, amount, tx_type)
        )


def update_transaction(tx_id: int, tx_date, account_id: int,
                       category_id, description: str, amount: float):
    with get_conn() as conn:
        conn.execute(
            "UPDATE transactions SET date=?,account_id=?,category_id=?,"
            "description=?,amount=? WHERE id=?",
            (str(tx_date), account_id, category_id, description, amount, tx_id)
        )


def add_transfer(user_id, tx_date, from_id, to_id, amount, description="Transfer"):
    with get_conn() as conn:
        cat = conn.execute(
            "SELECT id FROM categories WHERE user_id=? AND type='Transfer' LIMIT 1",
            (user_id,)
        ).fetchone()
        cat_id = cat["id"] if cat else None
        cur = conn.execute(
            "INSERT INTO transactions "
            "(user_id,date,account_id,category_id,description,amount,type) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, str(tx_date), from_id, cat_id, description, -abs(amount), "Transfer")
        )
        from_row = cur.lastrowid
        cur2 = conn.execute(
            "INSERT INTO transactions "
            "(user_id,date,account_id,category_id,description,amount,type) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, str(tx_date), to_id, cat_id, description, abs(amount), "Transfer")
        )
        to_row = cur2.lastrowid
        conn.execute("UPDATE transactions SET transfer_id=? WHERE id=?", (to_row, from_row))
        conn.execute("UPDATE transactions SET transfer_id=? WHERE id=?", (from_row, to_row))


def delete_transaction(tx_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT transfer_id FROM transactions WHERE id=?", (tx_id,)
        ).fetchone()
        conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        if row and row["transfer_id"]:
            conn.execute("DELETE FROM transactions WHERE id=?", (row["transfer_id"],))


# ── Recurring ─────────────────────────────────────────────────────────────────

def get_recurring(user_id: int) -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT r.*, a.name AS account_name, c.name AS category_name
            FROM recurring r
            JOIN accounts a ON a.id = r.account_id
            LEFT JOIN categories c ON c.id = r.category_id
            WHERE r.user_id=? AND r.active=1 ORDER BY r.next_due
        """, (user_id,)).fetchall()]


def add_recurring(user_id, account_id, category_id, description,
                  amount, tx_type, frequency, next_due):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO recurring "
            "(user_id,account_id,category_id,description,amount,type,frequency,next_due) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, account_id, category_id, description,
             amount, tx_type, frequency, str(next_due))
        )


def delete_recurring(rec_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE recurring SET active=0 WHERE id=?", (rec_id,))


def post_due_recurring(user_id: int) -> int:
    from dateutil.relativedelta import relativedelta
    today   = date.today()
    posted  = 0
    with get_conn() as conn:
        due = conn.execute(
            "SELECT * FROM recurring WHERE user_id=? AND active=1 AND next_due<=?",
            (user_id, str(today))
        ).fetchall()
        for r in due:
            conn.execute(
                "INSERT INTO transactions "
                "(user_id,date,account_id,category_id,description,amount,type) "
                "VALUES (?,?,?,?,?,?,?)",
                (user_id, r["next_due"], r["account_id"], r["category_id"],
                 r["description"], r["amount"], r["type"])
            )
            nd   = datetime.strptime(r["next_due"], "%Y-%m-%d").date()
            freq = r["frequency"]
            if freq == "Daily":    nd += relativedelta(days=1)
            elif freq == "Weekly":  nd += relativedelta(weeks=1)
            elif freq == "Monthly": nd += relativedelta(months=1)
            elif freq == "Yearly":  nd += relativedelta(years=1)
            conn.execute(
                "UPDATE recurring SET next_due=? WHERE id=?", (str(nd), r["id"])
            )
            posted += 1
    return posted


# ── Budgets ───────────────────────────────────────────────────────────────────

def get_budgets(user_id: int) -> list[dict]:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT b.id, b.category_id, c.name AS category_name,
                   b.budget_type, b.rate_period, b.amount, b.bucket
            FROM budgets b
            JOIN categories c ON c.id = b.category_id
            WHERE b.user_id=?
            ORDER BY b.budget_type DESC, c.name
        """, (user_id,)).fetchall()]


def set_budget(user_id: int, category_id: int, budget_type: str,
               rate_period: str, amount: float, bucket=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO budgets (user_id,category_id,budget_type,rate_period,amount,bucket) "
            "VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(user_id,category_id) DO UPDATE SET "
            "budget_type=excluded.budget_type, rate_period=excluded.rate_period, "
            "amount=excluded.amount, bucket=excluded.bucket",
            (user_id, category_id, budget_type, rate_period, amount, bucket)
        )


def delete_budget(budget_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM budgets WHERE id=?", (budget_id,))


def _scale_to_viewport(amount: float, rate_period: str, viewport: str) -> float:
    today         = date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    wim           = days_in_month / 7.0

    if rate_period == "Weekly":   weekly = amount
    elif rate_period == "Monthly": weekly = amount / wim
    else:                          weekly = amount / 52.0

    if viewport == "Weekly":
        return amount if rate_period == "Weekly"  else weekly
    elif viewport == "Monthly":
        return amount if rate_period == "Monthly" else weekly * wim
    else:
        if rate_period == "Yearly":  return amount
        if rate_period == "Monthly": return amount * 12.0
        return weekly * 52.0


def _viewport_window(viewport: str) -> tuple[date, date]:
    today = date.today()
    if viewport == "Weekly":
        return today - timedelta(days=today.weekday()), today
    elif viewport == "Monthly":
        return today.replace(day=1), today
    else:
        return today.replace(month=1, day=1), today


def get_savings_delta(user_id: int, viewport: str) -> float:
    start, today      = _viewport_window(viewport)
    day_before        = start - timedelta(days=1)
    savings_accounts  = [a for a in get_accounts(user_id)
                         if a.get("subtype") == "Savings"]
    if not savings_accounts:
        return 0.0
    delta = 0.0
    for a in savings_accounts:
        delta += account_balance(a["id"]) - account_balance_at(a["id"], day_before)
    return delta


def get_budget_actuals(user_id: int, viewport: str) -> list[dict]:
    start, today = _viewport_window(viewport)
    all_budgets  = get_budgets(user_id)
    if not all_budgets:
        return []
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT t.category_id, t.type AS tx_type,
                   COALESCE(SUM(ABS(t.amount)), 0) AS total
            FROM transactions t
            WHERE t.user_id=? AND t.date>=? AND t.date<=?
              AND t.type IN ('Income','Expense')
            GROUP BY t.category_id, t.type
        """, (user_id, str(start), str(today))).fetchall()
    actuals = {(r["category_id"], r["tx_type"]): r["total"] for r in rows}
    result  = []
    for b in all_budgets:
        scaled    = _scale_to_viewport(b["amount"], b["rate_period"], viewport)
        actual    = actuals.get((b["category_id"], b["budget_type"]), 0.0)
        remaining = scaled - actual
        pct       = (actual / scaled * 100) if scaled else 0.0
        result.append({
            "category":    b["category_name"],
            "budget_type": b["budget_type"],
            "bucket":      b["bucket"],
            "rate_period": b["rate_period"],
            "rate_amount": b["amount"],
            "budget":      scaled,
            "actual":      actual,
            "remaining":   remaining,
            "pct_used":    pct,
        })
    result.sort(key=lambda r: (0 if r["budget_type"] == "Income" else 1, -r["pct_used"]))
    return result


BUCKET_TARGETS = {"Needs": 50.0, "Wants": 30.0, "Savings": 20.0}


def get_503020_actuals(user_id: int, viewport: str) -> dict:
    start, today = _viewport_window(viewport)
    all_budgets  = get_budgets(user_id)

    # Income baseline
    inc_budgets = [b for b in all_budgets if b["budget_type"] == "Income"]
    if inc_budgets:
        income_source = "budgeted"
        income = sum(_scale_to_viewport(b["amount"], b["rate_period"], viewport)
                     for b in inc_budgets)
    else:
        income_source = "actual"
        with get_conn() as conn:
            row = conn.execute("""
                SELECT COALESCE(SUM(amount),0) AS total FROM transactions
                WHERE user_id=? AND type='Income' AND date>=? AND date<=?
            """, (user_id, str(start), str(today))).fetchone()
        income = row["total"]

    # Expense buckets
    exp_budgets      = [b for b in all_budgets if b["budget_type"] == "Expense"]
    bucketed_cat_ids = {b["category_id"]: b["bucket"] for b in exp_budgets if b["bucket"]}

    with get_conn() as conn:
        rows = conn.execute("""
            SELECT category_id, COALESCE(SUM(ABS(amount)),0) AS spent
            FROM transactions
            WHERE user_id=? AND type='Expense' AND date>=? AND date<=?
            GROUP BY category_id
        """, (user_id, str(start), str(today))).fetchall()

    bucket_spent: dict[str, float] = {b: 0.0 for b in BUCKET_TARGETS}
    untagged = 0.0
    for r in rows:
        bucket = bucketed_cat_ids.get(r["category_id"])
        if bucket and bucket != "Savings":
            bucket_spent[bucket] += r["spent"]
        elif not bucket:
            untagged += r["spent"]

    savings_delta             = get_savings_delta(user_id, viewport)
    bucket_spent["Savings"]   = max(savings_delta, 0.0)
    savings_accounts          = [a["name"] for a in get_accounts(user_id)
                                  if a.get("subtype") == "Savings"]

    buckets = []
    for bucket, target_pct in BUCKET_TARGETS.items():
        target_amt = income * target_pct / 100 if income else 0.0
        actual     = bucket_spent[bucket]
        variance   = target_amt - actual
        pct_of_inc = (actual / income * 100) if income else 0.0
        buckets.append({
            "bucket": bucket, "target_pct": target_pct,
            "target_amt": target_amt, "actual": actual,
            "variance": variance, "pct_of_income": pct_of_inc,
        })

    return {
        "income_source": income_source, "income": income,
        "buckets": buckets, "untagged_expense": untagged,
        "savings_delta": savings_delta, "savings_accounts": savings_accounts,
    }


def get_budget_balance_summary(user_id: int) -> list[dict]:
    budgets = get_budgets(user_id)
    result  = []
    for period in ("Weekly", "Monthly", "Yearly"):
        income   = sum(_scale_to_viewport(b["amount"], b["rate_period"], period)
                       for b in budgets if b["budget_type"] == "Income")
        expenses = sum(_scale_to_viewport(b["amount"], b["rate_period"], period)
                       for b in budgets if b["budget_type"] == "Expense")
        balance  = income - expenses
        result.append({
            "period": period, "income": income,
            "expenses": expenses, "balance": balance,
            "surplus": balance >= 0,
        })
    return result


# ── Backup / Restore ──────────────────────────────────────────────────────────

def backup_db(dest_path: str) -> tuple[bool, str]:
    import shutil
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(DB_PATH, dest_path)
        return True, f"Backed up to {dest_path}"
    except Exception as e:
        return False, str(e)


def restore_db(src_path: str) -> tuple[bool, str]:
    import shutil
    try:
        if not os.path.exists(src_path):
            return False, "Backup file not found."
        shutil.copy2(src_path, DB_PATH)
        return True, "Database restored. Please restart the app."
    except Exception as e:
        return False, str(e)
