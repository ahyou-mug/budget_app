# Migrating from the old single-user version

If you've been using an earlier version of Budget App (before multi-user
support was added), use this script **once** to bring your existing data
across safely.

## What it does

- Makes a timestamped backup of your old `budget.db` automatically
- Creates a new user account with the username/password you choose
- Copies every account, category, transaction, recurring rule, and budget
  into the new multi-user database, tagged to that user
- Verifies the migration by comparing row counts and the total sum of all
  transaction amounts between old and new — if anything doesn't match,
  it tells you and stops, without touching your original file

Your original `budget.db` is **never modified** — the script only reads
from it. The new data is written to a separate file that you then use as
your live database going forward.

## Steps

1. **Locate your old database.** If you installed via `install.sh` previously,
   it's likely at:
   ```
   ~/.local/share/budget-app/budget.db
   ```
   If you ran the app manually, it's wherever you ran `streamlit run app.py`
   from (usually the `budget_app` folder itself).

2. **Run the migration**, pointing `--old` at that file and `--new` at
   wherever you want the new database to live (this can be the same
   filename — the script makes a timestamped backup first either way):

   ```bash
   python3 migrate_to_multiuser.py \
       --old ~/.local/share/budget-app/budget.db \
       --new ~/.local/share/budget-app/budget_new.db \
       --username yourname \
       --password yourpassword
   ```

3. **Check the output.** You should see a row-count match for every table
   plus a transaction-sum match, ending in:
   ```
   === ✅ Migration completed successfully — all counts and sums match ===
   ```
   If you instead see a mismatch warning, **do not delete your old file** —
   send the full output and we'll figure out what happened. The script's
   backup copy and your original are both still intact at this point.

4. **Swap in the new database.** Once verified, replace the app's live
   database with the migrated one:
   ```bash
   cp ~/.local/share/budget-app/budget_new.db ~/.local/share/budget-app/budget.db
   ```
   (Only do this after step 3 confirms success.)

5. **Restart the app and log in** with the username and password you chose
   in step 2. Your accounts, transactions, budgets, and recurring rules
   should all be exactly as you left them.

## If something looks wrong after migrating

Your original file is preserved in two places: the file you pointed `--old`
at (untouched), and a timestamped `.backup_YYYYMMDD_HHMMSS` copy next to it.
Nothing is lost even if the migrated copy has an issue — just let me know
and we'll dig into the specific row that didn't come across as expected.
