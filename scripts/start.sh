#!/bin/bash
set -euo pipefail

echo "Starting Trace Agent API on port ${API_PORT:-8742}"
cd /app/server
python -m uvicorn api.main:app --host 0.0.0.0 --port "${API_PORT:-8742}" &
API_PID=$!

echo "Starting Trace Agent web UI on port ${WEB_PORT:-3847}"
cd /app/web-standalone
HOSTNAME=0.0.0.0 PORT="${WEB_PORT:-3847}" node server.js &
WEB_PID=$!

cleanup() {
  kill "$API_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait -n "$API_PID" "$WEB_PID"
exit_code=$?
cleanup
exit "$exit_code"
