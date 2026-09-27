#!/usr/bin/env bash
set -euo pipefail

# Start the frontend from its project directory and use cert files from there
FRONTEND_DIR="/home/rodolfo_danese/AI_compliance2/checkpoint1912NEEDTESTS/frontend"
cd "$FRONTEND_DIR"

SSL_CRT_FILE="$FRONTEND_DIR/192.168.41.54+1.pem"
SSL_KEY_FILE="$FRONTEND_DIR/192.168.41.54+1-key.pem"

if [[ ! -f "$SSL_CRT_FILE" ]]; then
  echo "SSL certificate not found: $SSL_CRT_FILE" >&2
  exit 1
fi
if [[ ! -f "$SSL_KEY_FILE" ]]; then
  echo "SSL key not found: $SSL_KEY_FILE" >&2
  exit 1
fi

# Start in background via nohup and capture PID. Log name includes a human-friendly name + PID.
LOG_DIR="$FRONTEND_DIR/logs"
mkdir -p "$LOG_DIR"

TMP_LOG="$(mktemp "$LOG_DIR/frontend.XXXXXX.log.tmp")"

nohup env HTTPS=true \
  SSL_CRT_FILE="$SSL_CRT_FILE" \
  SSL_KEY_FILE="$SSL_KEY_FILE" \
  npm start > "$TMP_LOG" 2>&1 &

PID=$!
LOG_FILE="$LOG_DIR/frontend-$PID.log"
mv "$TMP_LOG" "$LOG_FILE"

PID_FILE="$LOG_DIR/frontend-$PID.pid"
echo "$PID" > "$PID_FILE"
ln -sf "$PID_FILE" "$LOG_DIR/frontend.pid"

echo "Started frontend with PID $PID"
echo "Log: $LOG_FILE"
echo "To stop: kill $PID"