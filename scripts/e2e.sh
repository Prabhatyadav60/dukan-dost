#!/usr/bin/env bash
# Browser regression on isolated servers (API :8001 on database dukan_dost_e2e, web :5174),
# so the app you are using on :8000/:5173 and its data are never touched.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="$ROOT/apps/api"; WEB="$ROOT/apps/web"
export MONGO_DB=dukan_dost_e2e
LOG="$(mktemp -d)"

(cd "$API" && .venv/bin/uvicorn app.main:app --port 8001 >"$LOG/api.log" 2>&1) & API_PID=$!
(cd "$WEB" && API_PROXY_TARGET=http://localhost:8001 npx vite --port 5174 --strictPort >"$LOG/web.log" 2>&1) & WEB_PID=$!
trap 'kill $API_PID $WEB_PID 2>/dev/null; pkill -f "vite --port 5174" 2>/dev/null; pkill -f "uvicorn app.main:app --port 8001" 2>/dev/null' EXIT

for _ in $(seq 1 60); do
  curl -sf localhost:8001/healthz >/dev/null && curl -sf localhost:5174 >/dev/null && break; sleep 0.5
done

status=0
for spec in ${@:-demo chat voice-question home-sales}; do
  (cd "$API" && .venv/bin/python -m app.seed >/dev/null) || { echo "seed failed"; exit 1; }
  echo "== $spec"
  (cd "$WEB" && WEB_URL=http://localhost:5174 npx playwright test "e2e/$spec.spec.ts" --reporter=line) || status=1
done
[ $status -ne 0 ] && echo "server logs: $LOG"
exit $status
