#!/usr/bin/env python3
"""
migrate_to_multiuser.py — One-time migration from the old single-user
budget.db schema to the new multi-user schema.

What it does:
  1. Makes a timestamped backup of your existing budget.db before touching it.
  2. Creates a new user with the username and password you choose.
  3. Copies every account, category, transaction, recurring rule, and budget
     into the new schema, tagged with that user's user_id.
  4. Preserves all primary keys' relationships (transfer pairs, category
     links, account links) exactly as they were.
  5. Verifies row counts match between old and new data before finishing.

This script does NOT modify your old database — it reads from it and writes
a brand new database file in the new schema. Your original is left untouched
(besides the backup copy, which is just a safety net).

Usage:
    python3 migrate_to_multiuser.py --old budget_old.db --new budget.db \
        --username yourname --password yourpassword

If --new already exists and has data, the script will refuse to overwrite
it unless you pass --force.
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def detect_old_schema(old_conn) -> bool:
    """Return True if the old DB looks like the pre-multiuser schema
    (no users table, accounts has no user_id column)."""
    tables = {
        r["name"] for r in old_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "users" in tables:
        return False  # already migrated
    if "accounts" not in tables:
        return False  # not a recognisable budget app db
    cols = {r["name"] for r in old_conn.execute("PRAGMA table_info(accounts)").fetchall()}
    return "user_id" not in cols


def init_new_schema(new_conn):
    new_conn.executescript("""
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
    new_conn.commit()


def new_db_has_data(new_conn) -> bool:
    tables = {
        r["name"] for r in new_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "users" not in tables:
        return False
    count = new_conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return count > 0


def migrate(old_path: str, new_path: str, username: str, password: str, force: bool):
    import bcrypt

    if not os.path.exists(old_path):
        sys.exit(f"ERROR: old database not found at {old_path}")

    # ── Backup the old DB before doing anything ───────────────────────────────
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{old_path}.backup_{timestamp}"
    shutil.copy2(old_path, backup_path)
    print(f"✔ Backed up original database to: {backup_path}")

    old_conn = connect(old_path)
    if not detect_old_schema(old_conn):
        old_conn.close()
        sys.exit(
            "ERROR: this database does not look like the old single-user schema "
            "(it may already be migrated, or isn't a budget app database)."
        )

    # ── Prepare new DB ─────────────────────────────────────────────────────────
    new_db_existed = os.path.exists(new_path)
    new_conn = connect(new_path)
    init_new_schema(new_conn)

    if new_db_has_data(new_conn) and not force:
        new_conn.close()
        old_conn.close()
        sys.exit(
            f"ERROR: {new_path} already contains user data. "
            "Pass --force to proceed anyway (this will ADD to existing data, "
            "not overwrite it)."
        )

    # ── Create the user ────────────────────────────────────────────────────────
    existing = new_conn.execute(
        "SELECT id FROM users WHERE username=? COLLATE NOCASE", (username,)
    ).fetchone()
    if existing:
        user_id = existing["id"]
        print(f"→ User '{username}' already exists in new DB (id={user_id}); "
              f"migrating data into this existing user.")
    else:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur = new_conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?,?)",
            (username, hashed)
        )
        user_id = cur.lastrowid
        new_conn.commit()
        print(f"✔ Created user '{username}' (id={user_id})")

    # ── Migrate categories (preserve old_id -> new_id mapping) ────────────────
    cat_id_map = {}
    old_cats = old_conn.execute("SELECT * FROM categories").fetchall()
    for c in old_cats:
        cur = new_conn.execute(
            "INSERT INTO categories (user_id, name, type) VALUES (?,?,?) "
            "ON CONFLICT(user_id, name) DO UPDATE SET type=excluded.type "
            "RETURNING id",
            (user_id, c["name"], c["type"])
        )
        new_id = cur.fetchone()[0]
        cat_id_map[c["id"]] = new_id
    new_conn.commit()
    print(f"✔ Migrated {len(old_cats)} categories")

    # ── Migrate accounts (preserve old_id -> new_id mapping) ──────────────────
    acct_id_map = {}
    old_accts = old_conn.execute("SELECT * FROM accounts").fetchall()
    for a in old_accts:
        subtype = a["subtype"] if "subtype" in a.keys() else None
        cur = new_conn.execute(
            "INSERT INTO accounts (user_id,name,type,subtype,currency,note,"
            "opening_bal,created_at) VALUES (?,?,?,?,?,?,?,?) RETURNING id",
            (user_id, a["name"], a["type"], subtype, a["currency"],
             a["note"], a["opening_bal"], a["created_at"])
        )
        new_id = cur.fetchone()[0]
        acct_id_map[a["id"]] = new_id
    new_conn.commit()
    print(f"✔ Migrated {len(old_accts)} accounts")

    # ── Migrate transactions (preserve transfer_id pairing via id map) ────────
    tx_id_map = {}
    old_txs = old_conn.execute("SELECT * FROM transactions ORDER BY id").fetchall()
    for t in old_txs:
        new_cat_id = cat_id_map.get(t["category_id"]) if t["category_id"] else None
        cur = new_conn.execute(
            "INSERT INTO transactions (user_id,date,account_id,category_id,"
            "description,amount,type,created_at) VALUES (?,?,?,?,?,?,?,?) RETURNING id",
            (user_id, t["date"], acct_id_map[t["account_id"]], new_cat_id,
             t["description"], t["amount"], t["type"], t["created_at"])
        )
        new_id = cur.fetchone()[0]
        tx_id_map[t["id"]] = new_id
    new_conn.commit()

    # Second pass: fix up transfer_id links now that all new IDs exist
    transfer_links_fixed = 0
    for t in old_txs:
        if t["transfer_id"]:
            new_self_id  = tx_id_map[t["id"]]
            new_other_id = tx_id_map.get(t["transfer_id"])
            if new_other_id:
                new_conn.execute(
                    "UPDATE transactions SET transfer_id=? WHERE id=?",
                    (new_other_id, new_self_id)
                )
                transfer_links_fixed += 1
    new_conn.commit()
    print(f"✔ Migrated {len(old_txs)} transactions "
          f"({transfer_links_fixed} transfer links re-paired)")

    # ── Migrate recurring rules ────────────────────────────────────────────────
    old_recurring = old_conn.execute("SELECT * FROM recurring").fetchall()
    for r in old_recurring:
        new_cat_id = cat_id_map.get(r["category_id"]) if r["category_id"] else None
        new_conn.execute(
            "INSERT INTO recurring (user_id,account_id,category_id,description,"
            "amount,type,frequency,next_due,active) VALUES (?,?,?,?,?,?,?,?,?)",
            (user_id, acct_id_map[r["account_id"]], new_cat_id, r["description"],
             r["amount"], r["type"], r["frequency"], r["next_due"], r["active"])
        )
    new_conn.commit()
    print(f"✔ Migrated {len(old_recurring)} recurring rules")

    # ── Migrate budgets ────────────────────────────────────────────────────────
    old_budgets = old_conn.execute("SELECT * FROM budgets").fetchall()
    for b in old_budgets:
        new_cat_id = cat_id_map.get(b["category_id"])
        if new_cat_id is None:
            print(f"  ⚠ Skipping budget for missing category_id={b['category_id']}")
            continue
        bucket = b["bucket"] if "bucket" in b.keys() else None
        budget_type = b["budget_type"] if "budget_type" in b.keys() else "Expense"
        new_conn.execute(
            "INSERT INTO budgets (user_id,category_id,budget_type,rate_period,"
            "amount,bucket) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(user_id,category_id) DO UPDATE SET "
            "budget_type=excluded.budget_type, rate_period=excluded.rate_period, "
            "amount=excluded.amount, bucket=excluded.bucket",
            (user_id, new_cat_id, budget_type, b["rate_period"], b["amount"], bucket)
        )
    new_conn.commit()
    print(f"✔ Migrated {len(old_budgets)} budgets")

    # ── Verification ───────────────────────────────────────────────────────────
    print()
    print("=== Verification ===")
    checks = [
        ("accounts",     len(old_accts),     new_conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE user_id=?", (user_id,)).fetchone()[0]),
        ("categories",   len(old_cats),      new_conn.execute(
            "SELECT COUNT(*) FROM categories WHERE user_id=?", (user_id,)).fetchone()[0]),
        ("transactions", len(old_txs),       new_conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id=?", (user_id,)).fetchone()[0]),
        ("recurring",    len(old_recurring), new_conn.execute(
            "SELECT COUNT(*) FROM recurring WHERE user_id=?", (user_id,)).fetchone()[0]),
        ("budgets",      len(old_budgets),   new_conn.execute(
            "SELECT COUNT(*) FROM budgets WHERE user_id=?", (user_id,)).fetchone()[0]),
    ]
    all_ok = True
    for name, old_count, new_count in checks:
        status = "✔" if old_count == new_count else "✘ MISMATCH"
        if old_count != new_count:
            all_ok = False
        print(f"  {status}  {name}: old={old_count}  new={new_count}")

    # Sum check on transactions — money in = money in, not just row counts
    old_sum = old_conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM transactions"
    ).fetchone()[0]
    new_sum = new_conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=?", (user_id,)
    ).fetchone()[0]
    sum_ok = abs(old_sum - new_sum) < 0.01
    print(f"  {'✔' if sum_ok else '✘ MISMATCH'}  transaction amount sum: "
          f"old={old_sum:.2f}  new={new_sum:.2f}")
    if not sum_ok:
        all_ok = False

    old_conn.close()
    new_conn.close()

    print()
    if all_ok:
        print("=== ✅ Migration completed successfully — all counts and sums match ===")
        print(f"New database: {new_path}")
        print(f"Original backup: {backup_path}")
        print(f"Log in as: {username}")
    else:
        print("=== ⚠️ Migration finished but verification found mismatches ===")
        print("Please review the output above carefully before trusting the new database.")
        print(f"Your original data is safe and untouched at: {old_path}")
        print(f"(Backup copy also at: {backup_path})")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate old single-user budget.db to new multi-user schema."
    )
    parser.add_argument("--old", required=True, help="Path to existing (old schema) budget.db")
    parser.add_argument("--new", required=True, help="Path to write the new multi-user database")
    parser.add_argument("--username", required=True, help="Username to create for your migrated data")
    parser.add_argument("--password", required=True, help="Password for the new user account")
    parser.add_argument("--force", action="store_true",
                        help="Proceed even if --new already has user data")
    args = parser.parse_args()

    migrate(args.old, args.new, args.username, args.password, args.force)
