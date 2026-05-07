#!/usr/bin/env bash
set -euo pipefail

SERVE=0
MID=""
POSITIONAL=()
args=("$@")
i=0
while [ $i -lt ${#args[@]} ]; do
  case "${args[$i]}" in
    --serve) SERVE=1 ;;
    --mid)   i=$(( i + 1 )); MID="${args[$i]}" ;;
    *)       POSITIONAL+=("${args[$i]}") ;;
  esac
  i=$(( i + 1 ))
done

BACKEND_PORT=${POSITIONAL[0]:-5002}
FRONTEND_PORT=${POSITIONAL[1]:-5173}

ROOT="$(cd "$(dirname "$0")" && pwd)"
PIDS_FILE="/tmp/trading_pids_${BACKEND_PORT}"

# Parse the tunnel URL from ngrok's JSON log output
get_ngrok_url() {
  local logfile=$1
  for i in $(seq 1 20); do
    local url
    url=$(grep -o '"url":"https://[^"]*"' "$logfile" 2>/dev/null | head -1 | sed 's/"url":"//;s/"//')
    if [ -n "$url" ]; then echo "$url"; return 0; fi
    sleep 1
  done
  echo ""; return 1
}

echo ""
if [ "$SERVE" = "1" ]; then
  echo "Deploying book (single server)  port=$BACKEND_PORT"
else
  echo "Deploying book (dev)  backend=$BACKEND_PORT  frontend=$FRONTEND_PORT"
fi
echo "------------------------------------------------------------"

PYTHON=${PYTHON:-$(command -v python3 || command -v python)}
echo "[0] Installing Python dependencies... ($PYTHON)"
cd "$ROOT"
"$PYTHON" -m pip install -r requirements.txt -q

# ── Single-server mode (--serve) ─────────────────────────────────────────────
if [ "$SERVE" = "1" ]; then

  # 1. Build frontend with backend URL = same origin (relative)
  echo "[1/3] Building frontend..."
  cd "$ROOT/frontend"
  npm install -q
  VITE_BACKEND_URL="" npx vite build >> "/tmp/trading_build_${BACKEND_PORT}.log" 2>&1
  echo "      built -> frontend/dist/"

  # 2. Start Flask serving frontend + API
  echo "[2/3] Starting server on port $BACKEND_PORT..."
  cd "$ROOT"
  PORT=$BACKEND_PORT SERVE_FRONTEND=1 ${MID:+INITIAL_MID=$MID} "$PYTHON" app.py \
    >> "/tmp/trading_backend_${BACKEND_PORT}.log" 2>&1 &
  BACKEND_PID=$!
  sleep 2

  # 3. Ngrok
  echo "[3/3] Tunnelling..."
  ngrok http "$BACKEND_PORT" \
    --log stdout --log-format json \
    >> "/tmp/trading_ngrok_b_${BACKEND_PORT}.log" 2>&1 &
  NGROK_B_PID=$!
  sleep 3

  URL=$(get_ngrok_url "/tmp/trading_ngrok_b_${BACKEND_PORT}.log")
  if [ -z "$URL" ]; then
    echo "ERROR: could not get ngrok URL. Check /tmp/trading_ngrok_b_${BACKEND_PORT}.log"
    kill "$BACKEND_PID" "$NGROK_B_PID" 2>/dev/null || true
    exit 1
  fi

  echo "$BACKEND_PID $NGROK_B_PID" > "$PIDS_FILE"

  echo ""
  echo "============================================================"
  echo "  Book ready!"
  echo "  URL: $URL"
  echo "============================================================"
  echo "  Logs:"
  echo "    server  /tmp/trading_backend_${BACKEND_PORT}.log"
  echo "  Stop: ./stop.sh $BACKEND_PORT"
  echo ""
  exit 0
fi

# ── Dev mode (separate Vite + Flask) ─────────────────────────────────────────

# 1. Backend
echo "[1/5] Starting backend on port $BACKEND_PORT..."
cd "$ROOT"
PORT=$BACKEND_PORT ${MID:+INITIAL_MID=$MID} "$PYTHON" app.py >> "/tmp/trading_backend_${BACKEND_PORT}.log" 2>&1 &
BACKEND_PID=$!
sleep 2

# 2. Ngrok backend
echo "[2/5] Tunnelling backend..."
ngrok http "$BACKEND_PORT" \
  --log stdout --log-format json \
  >> "/tmp/trading_ngrok_b_${BACKEND_PORT}.log" 2>&1 &
NGROK_B_PID=$!
sleep 3

BACKEND_URL=$(get_ngrok_url "/tmp/trading_ngrok_b_${BACKEND_PORT}.log")
if [ -z "$BACKEND_URL" ]; then
  echo "ERROR: could not get backend ngrok URL. Check /tmp/trading_ngrok_b_${BACKEND_PORT}.log"
  kill "$BACKEND_PID" "$NGROK_B_PID" 2>/dev/null || true
  exit 1
fi
echo "       backend  -> $BACKEND_URL"

# 3. Frontend
echo "[3/5] Starting frontend on port $FRONTEND_PORT..."
cd "$ROOT/frontend"
npm install -q
VITE_BACKEND_URL="$BACKEND_URL" npx vite --port "$FRONTEND_PORT" \
  >> "/tmp/trading_frontend_${FRONTEND_PORT}.log" 2>&1 &
FRONTEND_PID=$!
sleep 4

# 4. Ngrok frontend
echo "[4/5] Tunnelling frontend..."
ngrok http "$FRONTEND_PORT" \
  --log stdout --log-format json \
  >> "/tmp/trading_ngrok_f_${FRONTEND_PORT}.log" 2>&1 &
NGROK_F_PID=$!
sleep 3

FRONTEND_URL=$(get_ngrok_url "/tmp/trading_ngrok_f_${FRONTEND_PORT}.log")
if [ -z "$FRONTEND_URL" ]; then
  echo "ERROR: could not get frontend ngrok URL. Check /tmp/trading_ngrok_f_${FRONTEND_PORT}.log"
  kill "$BACKEND_PID" "$NGROK_B_PID" "$FRONTEND_PID" "$NGROK_F_PID" 2>/dev/null || true
  exit 1
fi
echo "       frontend -> $FRONTEND_URL"

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
