#!/usr/bin/env bash
set -euo pipefail

BACKEND_PORT=${1:-5002}
FRONTEND_PORT=${2:-5173}

# Unique ngrok API ports per deployment (offset by backend port)
OFFSET=$(( BACKEND_PORT - 5000 ))
NGROK_B_API=$(( 4040 + OFFSET * 2 ))
NGROK_F_API=$(( 4041 + OFFSET * 2 ))

ROOT="$(cd "$(dirname "$0")" && pwd)"
PIDS_FILE="/tmp/trading_pids_${BACKEND_PORT}"

# Wait for ngrok tunnel URL on the given API port
get_ngrok_url() {
  local api=$1
  for i in $(seq 1 15); do
    local url
    url=$(curl -s "http://localhost:${api}/api/tunnels" 2>/dev/null \
      | python3 -c "
import sys, json
d = json.load(sys.stdin)
hits = [t['public_url'] for t in d.get('tunnels', []) if t['proto'] == 'https']
print(hits[0] if hits else '')
" 2>/dev/null || true)
    if [ -n "$url" ]; then
      echo "$url"
      return 0
    fi
    sleep 1
  done
  echo ""
  return 1
}

echo ""
echo "Deploying book  backend=$BACKEND_PORT  frontend=$FRONTEND_PORT"
echo "------------------------------------------------------------"

# 1. Backend
echo "[1/5] Starting backend on port $BACKEND_PORT..."
cd "$ROOT"
PORT=$BACKEND_PORT python app.py >> "/tmp/trading_backend_${BACKEND_PORT}.log" 2>&1 &
BACKEND_PID=$!
sleep 2

# 2. Ngrok backend
echo "[2/5] Tunnelling backend..."
ngrok http "$BACKEND_PORT" \
  --api-port "$NGROK_B_API" \
  --log stdout \
  >> "/tmp/trading_ngrok_b_${BACKEND_PORT}.log" 2>&1 &
NGROK_B_PID=$!
sleep 3

BACKEND_URL=$(get_ngrok_url "$NGROK_B_API")
if [ -z "$BACKEND_URL" ]; then
  echo "ERROR: could not get backend ngrok URL. Check /tmp/trading_ngrok_b_${BACKEND_PORT}.log"
  kill "$BACKEND_PID" "$NGROK_B_PID" 2>/dev/null || true
  exit 1
fi
echo "       backend  -> $BACKEND_URL"

# 3. Frontend (inject backend URL inline so multiple books don't clobber .env)
echo "[3/5] Starting frontend on port $FRONTEND_PORT..."
cd "$ROOT/frontend"
VITE_BACKEND_URL="$BACKEND_URL" npx vite --port "$FRONTEND_PORT" \
  >> "/tmp/trading_frontend_${FRONTEND_PORT}.log" 2>&1 &
FRONTEND_PID=$!
sleep 4

# 4. Ngrok frontend
echo "[4/5] Tunnelling frontend..."
ngrok http "$FRONTEND_PORT" \
  --api-port "$NGROK_F_API" \
  --log stdout \
  >> "/tmp/trading_ngrok_f_${FRONTEND_PORT}.log" 2>&1 &
NGROK_F_PID=$!
sleep 3

FRONTEND_URL=$(get_ngrok_url "$NGROK_F_API")
if [ -z "$FRONTEND_URL" ]; then
  echo "ERROR: could not get frontend ngrok URL. Check /tmp/trading_ngrok_f_${FRONTEND_PORT}.log"
  kill "$BACKEND_PID" "$NGROK_B_PID" "$FRONTEND_PID" "$NGROK_F_PID" 2>/dev/null || true
  exit 1
fi
echo "       frontend -> $FRONTEND_URL"

# 5. Save PIDs
echo "$BACKEND_PID $NGROK_B_PID $FRONTEND_PID $NGROK_F_PID" > "$PIDS_FILE"

echo ""
echo "============================================================"
echo "  Book ready!"
echo "  Backend:  $BACKEND_URL"
echo "  Frontend: $FRONTEND_URL"
echo "============================================================"
echo "  Logs:"
echo "    backend   /tmp/trading_backend_${BACKEND_PORT}.log"
echo "    frontend  /tmp/trading_frontend_${FRONTEND_PORT}.log"
echo "  Stop: ./stop.sh $BACKEND_PORT"
echo ""
