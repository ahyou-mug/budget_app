#!/usr/bin/env python3
"""
launcher.py — Desktop launcher for Budget App.
Starts Streamlit on a free port, waits until ready, opens a pywebview window,
then shuts Streamlit down cleanly when the window closes.
"""
import os
import sys
import socket
import subprocess
import time
import webview

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_PY     = os.path.join(SCRIPT_DIR, "app.py")
ICON_PATH  = os.path.join(SCRIPT_DIR, "icon.png")


def find_free_port(start=8501, end=8600):
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found in range 8501-8600")


def wait_for_port(port, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect(("127.0.0.1", port))
                return True
            except (ConnectionRefusedError, OSError):
                time.sleep(0.2)
    return False


def main():
    port = find_free_port()
    url  = f"http://127.0.0.1:{port}"

    streamlit_cmd = [
        sys.executable, "-m", "streamlit", "run", APP_PY,
        "--server.port", str(port),
        "--server.address", "127.0.0.1",
        "--server.headless", "true",
        "--server.runOnSave", "false",
        "--global.developmentMode", "false",
        "--client.toolbarMode", "minimal",
        "--browser.gatherUsageStats", "false",
    ]

    env = os.environ.copy()
    env.setdefault("BUDGET_DB_PATH", os.path.join(SCRIPT_DIR, "budget.db"))

    proc = subprocess.Popen(
        streamlit_cmd, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=SCRIPT_DIR,
    )

    if not wait_for_port(port, timeout=30):
        proc.terminate()
        sys.exit("Streamlit failed to start within 30 seconds.")

    def on_closed():
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    window = webview.create_window(
        title="💰 Budget App",
        url=url,
        width=1280, height=820,
        min_size=(900, 600),
        resizable=True,
    )
    window.events.closed += on_closed

    webview.start(debug=False)

    if proc.poll() is None:
        proc.terminate()


if __name__ == "__main__":
    main()
