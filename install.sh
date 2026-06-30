#!/usr/bin/env bash
# install.sh — Install Budget App as a Linux desktop application (venv-based).
# Run once from the budget_app directory:  bash install.sh

set -euo pipefail

APP_NAME="budget-app"
DISPLAY_NAME="Budget App"
INSTALL_DIR="$HOME/.local/share/$APP_NAME"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
VENV_DIR="$INSTALL_DIR/venv"

echo "=== Budget App Installer ==="
echo ""

# ── 1. Python check ───────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found."
    exit 1
fi
PY=$(command -v python3)
echo "✔ Python: $($PY --version)"

if ! $PY -m venv --help &>/dev/null 2>&1; then
    echo "→ Installing python3-venv..."
    sudo apt-get install -y python3-venv python3-full
fi

# ── 2. Copy app files ──────────────────────────────────────────────────────────
echo "→ Copying app files to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR/views"

for f in app.py db.py auth.py csv_io.py launcher.py requirements.txt README.md icon.png; do
    [[ -f "$f" ]] && cp "$f" "$INSTALL_DIR/"
done
for f in views/*.py; do
    [[ -f "$f" ]] && cp "$f" "$INSTALL_DIR/views/"
done
echo "  ✔ Files copied."

# ── 3. Virtualenv + dependencies ──────────────────────────────────────────────
echo "→ Creating virtualenv at $VENV_DIR ..."
$PY -m venv "$VENV_DIR"
echo "  ✔ Virtualenv created."

echo "→ Installing Python dependencies (this may take a minute)..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet \
    streamlit pandas plotly bcrypt pyyaml python-dateutil pywebview
echo "  ✔ Dependencies installed."

# ── 4. WebKit2GTK check (for pywebview) ───────────────────────────────────────
echo "→ Checking for GTK WebKit (required by pywebview)..."
if dpkg -l 2>/dev/null | grep -q "libwebkit2gtk-4"; then
    echo "  ✔ WebKit2GTK found."
else
    echo "  ⚠ WebKit2GTK not detected — attempting to install..."
    if sudo apt-get install -y --no-install-recommends \
            libwebkit2gtk-4.1-0 gir1.2-webkit2-4.1 \
            python3-gi python3-gi-cairo gir1.2-gtk-3.0 2>/dev/null; then
        echo "  ✔ WebKit2GTK installed."
    elif sudo apt-get install -y --no-install-recommends \
            libwebkit2gtk-4.0-37 python3-gi python3-gi-cairo gir1.2-gtk-3.0 2>/dev/null; then
        echo "  ✔ WebKit2GTK installed."
    else
        echo "  ✘ Could not install WebKit2GTK automatically."
        echo "    Please run:  sudo apt install libwebkit2gtk-4.1-0"
        echo "    Then re-run this script."
        exit 1
    fi
fi

# ── 5. Icon ───────────────────────────────────────────────────────────────────
if [[ -f "$INSTALL_DIR/icon.png" ]]; then
    mkdir -p "$ICON_DIR"
    cp "$INSTALL_DIR/icon.png" "$ICON_DIR/$APP_NAME.png"
    ICON_PATH="$ICON_DIR/$APP_NAME.png"
else
    ICON_PATH="utilities-finance"
fi

# ── 6. Wrapper script ──────────────────────────────────────────────────────────
WRAPPER="$HOME/.local/bin/$APP_NAME"
mkdir -p "$HOME/.local/bin"
cat > "$WRAPPER" << WRAPPER_EOF
#!/usr/bin/env bash
exec "$VENV_DIR/bin/python" "$INSTALL_DIR/launcher.py" "\$@"
WRAPPER_EOF
chmod +x "$WRAPPER"

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    echo "  ✔ Added ~/.local/bin to PATH in .bashrc"
fi
echo "  ✔ Launcher wrapper: $WRAPPER"

# ── 7. .desktop file ──────────────────────────────────────────────────────────
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/$APP_NAME.desktop" << DESKTOP_EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$DISPLAY_NAME
GenericName=Personal Finance Manager
Comment=Track accounts, transactions, budgets and reports
Exec=$WRAPPER
Icon=$ICON_PATH
Terminal=false
Categories=Office;Finance;
Keywords=budget;finance;money;accounts;
StartupNotify=true
StartupWMClass=Budget App
DESKTOP_EOF
chmod +x "$DESKTOP_DIR/$APP_NAME.desktop"
echo "  ✔ Desktop entry: $DESKTOP_DIR/$APP_NAME.desktop"

command -v update-desktop-database &>/dev/null && \
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

# ── 8. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "=== ✅ Installation complete! ==="
echo ""
echo "  Launch from terminal : $APP_NAME"
echo "  Or find 'Budget App' in your application menu (Office / Finance)"
echo ""
echo "  Data stored in       : $INSTALL_DIR"
echo "  Default login        : admin / changeme123"
echo "  Change password in   : ⚙️ Settings after first login"
echo ""
echo "  To uninstall later, run: bash uninstall.sh"
echo ""
