#!/usr/bin/env bash

BACKEND_PORT=${1:-5002}
PIDS_FILE="/tmp/trading_pids_${BACKEND_PORT}"

if [ -f "$PIDS_FILE" ]; then
  echo "Stopping deployment (backend port $BACKEND_PORT)..."
  for pid in $(cat "$PIDS_FILE"); do
    kill "$pid" 2>/dev/null && echo "  killed $pid" || true
  done
  rm "$PIDS_FILE"
else
  echo "No pids file found — falling back to pkill for port $BACKEND_PORT..."
  pkill -f "PORT=$BACKEND_PORT" 2>/dev/null || true
  pkill -f "app.py" 2>/dev/null || true
  pkill -f "ngrok http $BACKEND_PORT" 2>/dev/null || true
fi

echo "Done."
