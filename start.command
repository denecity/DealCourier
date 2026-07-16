#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  DealCourier launcher for macOS (also works on Linux)
#  - creates/activates a .venv if missing
#  - installs the project into it
#  - starts the web dashboard
#  Close this Terminal window or press Ctrl+C to stop.
# ─────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

# Make sure this script is executable (it may lose the bit when zipped/emailed)
chmod +x "$0" 2>/dev/null || true

echo "DealCourier launcher"
echo "--------------------"

if [ ! -f "config.yaml" ]; then
    if [ -f "config_init.yaml" ]; then
        echo "[setup] config.yaml not found -- copying config_init.yaml to config.yaml"
        echo "[setup] Remember to edit config.yaml and set your api_key!"
        cp "config_init.yaml" "config.yaml"
        echo
    else
        echo "[error] Neither config.yaml nor config_init.yaml found in $(pwd)"
        echo "        Copy config_init.yaml to config.yaml and fill in your api_key."
        read -n 1 -s -r -p "Press any key to close."
        exit 1
    fi
fi

# Read port from config.yaml (default 8000) so we open the right URL
PORT=$(grep -E '^[[:space:]]*port:[[:space:]]*[0-9]+' config.yaml 2>/dev/null | head -1 | sed 's/[^0-9]*//g')
[ -z "$PORT" ] && PORT=8000
echo "[info] Dashboard will open at http://127.0.0.1:$PORT once the server is ready"

# Background waiter: poll /health, open default browser when ready, then exit.
# macOS uses `open`; fall back to `xdg-open` on Linux.
OPENER=open
if ! command -v open >/dev/null 2>&1; then OPENER=xdg-open; fi
(
    for _ in $(seq 1 60); do
        if curl -fs -o /dev/null --max-time 1 "http://127.0.0.1:$PORT/health" 2>/dev/null; then
            "$OPENER" "http://127.0.0.1:$PORT"
            exit 0
        fi
        sleep 1
    done
) &
WAITER_PID=$!

# Make sure the waiter doesn't outlive this script
trap 'kill "$WAITER_PID" 2>/dev/null || true' EXIT

# Prefer uv if present
if command -v uv >/dev/null 2>&1; then
    echo "[run] uv detected -- syncing dependencies"
    uv sync
    echo
    echo "[run] Starting DealCourier ...  (Ctrl+C to stop)"
    uv run python -m dealcourier.main
    exit 0
fi

# Otherwise use python3 + venv
if [ ! -d ".venv" ]; then
    echo "[setup] Creating virtual environment (.venv)"
    python3 -m venv .venv
fi

echo "[setup] Installing dependencies into .venv"
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip --quiet
pip install -e . --quiet
echo
echo "[run] Starting DealCourier ...  (Ctrl+C to stop)"
python -m dealcourier.main
deactivate 2>/dev/null || true
