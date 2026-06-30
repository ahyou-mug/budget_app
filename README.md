# 💰 Budget App

A multi-user personal finance manager built with Streamlit + SQLite.

## Features

- 🔐 Multi-user — each user has fully isolated accounts, transactions, budgets
- 🏦 Asset & Liability accounts, with Savings tagging
- 💸 Income & Expense transactions with categories, editable in-place
- 🔄 Inter-account transfers
- 🔁 Recurring transactions, auto-posted on login
- 📈 Budgets — per-category rate (Weekly/Monthly/Yearly), auto-scaled to any viewport
- ⚖️ 50/30/20 analysis — Needs / Wants / Savings, with uncategorised spend drill-down
- 📊 Reports — net worth, income vs expenses, category breakdown, 12-month trend
- 📥 CSV import/export, database backup & restore
- ⚙️ Username, password, and full user management (add/remove users)

## Quick Install (Desktop App)

```bash
bash install.sh
```

This creates an isolated Python virtual environment, installs all dependencies,
and adds **Budget App** to your application menu (Office / Finance category).
Launch it like any other app — it opens in its own window.

## Manual Run (without installing)

```bash
pip install -r requirements.txt --break-system-packages
streamlit run app.py
```

## First Login

Default account: **admin** / **changeme123**
Change your password immediately in ⚙️ Settings, or create your own user
from the login screen's "➕ Create new user" option.

## Uninstall

```bash
bash uninstall.sh            # asks before deleting your data
bash uninstall.sh --purge    # removes everything without asking
bash uninstall.sh --keep-data # removes the app, keeps budget.db
```

## File Layout

```
budget_app/
├── app.py              # Entry point / router
├── db.py                # SQLite layer (multi-user)
├── auth.py              # Login / user creation
├── csv_io.py             # CSV import/export
├── launcher.py           # Desktop window launcher (pywebview)
├── install.sh            # One-shot installer
├── uninstall.sh           # Uninstaller
├── views/
│   ├── dashboard.py
│   ├── accounts.py
│   ├── transactions.py
│   ├── recurring.py
│   ├── budget.py
│   ├── reports.py
│   ├── import_export.py
│   └── settings.py
└── requirements.txt
```

## Environment Variables

| Variable          | Default      | Description                 |
|--------------------|--------------|------------------------------|
| `BUDGET_DB_PATH`   | `budget.db`  | Path to the SQLite database |
