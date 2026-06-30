#!/usr/bin/env bash
# uninstall.sh — Remove Budget App entirely: app files, launcher, desktop entry,
# and (with --purge or by default prompt) all stored data.
#
# Usage:
#   bash uninstall.sh            # interactive — asks before deleting data
#   bash uninstall.sh --purge    # delete everything without asking
#   bash uninstall.sh --keep-data # remove app + launcher, keep budget.db

set -euo pipefail

APP_NAME="budget-app"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
DESKTOP_FILE="$HOME/.local/share/applications/$APP_NAME.desktop"
ICON_FILE="$HOME/.local/share/icons/hicolor/256x256/apps/$APP_NAME.png"
WRAPPER="$HOME/.local/bin/$APP_NAME"

PURGE=false
KEEP_DATA=false
for arg in "$@"; do
    case "$arg" in
        --purge)     PURGE=true ;;
        --keep-data) KEEP_DATA=true ;;
    esac
done

echo "=== Budget App Uninstaller ==="
echo ""

# ── Remove desktop integration ────────────────────────────────────────────────
[[ -f "$DESKTOP_FILE" ]] && rm "$DESKTOP_FILE" && echo "✔ Removed desktop entry"
[[ -f "$ICON_FILE"    ]] && rm "$ICON_FILE"    && echo "✔ Removed icon"
[[ -f "$WRAPPER"      ]] && rm "$WRAPPER"      && echo "✔ Removed launcher wrapper"

command -v update-desktop-database &>/dev/null && \
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

# ── Decide on data removal ────────────────────────────────────────────────────
if [[ ! -d "$INSTALL_DIR" ]]; then
    echo "No installation found at $INSTALL_DIR — nothing more to do."
    exit 0
fi

if $KEEP_DATA; then
    DO_PURGE=false
elif $PURGE; then
    DO_PURGE=true
else
    echo ""
    echo "⚠️  The app directory contains your financial data:"
    echo "    $INSTALL_DIR/budget.db"
    echo ""
    read -r -p "Delete ALL data permanently? Type 'yes' to confirm, anything else to keep it: " confirm
    if [[ "$confirm" == "yes" ]]; then
        DO_PURGE=true
    else
        DO_PURGE=false
    fi
fi

if $DO_PURGE; then
    rm -rf "$INSTALL_DIR"
    echo "✔ Removed application and all data ($INSTALL_DIR)"
else
    # Remove only code files, keep budget.db / auth-related data
    for f in app.py db.py auth.py csv_io.py launcher.py requirements.txt README.md icon.png; do
        [[ -f "$INSTALL_DIR/$f" ]] && rm "$INSTALL_DIR/$f"
    done
    rm -rf "$INSTALL_DIR/views" "$INSTALL_DIR/venv"
    echo "✔ Removed application code (data preserved in $INSTALL_DIR)"
    echo "  Your budget.db and any backups remain at: $INSTALL_DIR"
fi

echo ""
echo "=== Uninstall complete ==="
