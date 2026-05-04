#!/usr/bin/env bash

BACKEND_PORT=${1:-5002}
PIDS_FILE="/tmp/trading_pids_${BACKEND_PORT}"

if [ ! -f "$PIDS_FILE" ]; then
  echo "No deployment found for backend port $BACKEND_PORT"
  exit 1
fi

echo "Stopping deployment (backend port $BACKEND_PORT)..."
for pid in $(cat "$PIDS_FILE"); do
  kill "$pid" 2>/dev/null && echo "  killed $pid" || true
done
rm "$PIDS_FILE"
echo "Done."
