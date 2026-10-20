#!/usr/bin/env bash
# One-click start. Fetches Hunyuan vendor + tsbuildinfo if missing, then boots
# FastAPI + Next.js (and optionally the Hunyuan3D API).
#
#   ./scripts/start.sh
#   ./scripts/start.sh --skip-hunyuan
#   ./scripts/start.sh --hunyuan          # also start :8080
#   ./scripts/start.sh --detach
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
LOGDIR="$ROOT/tmp/civsim-logs"
SKIP_HUNYUAN=0
START_HY3D=0
DETACH=0
PIDS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-hunyuan) SKIP_HUNYUAN=1; shift ;;
    --hunyuan|--with-hunyuan-server) START_HY3D=1; shift ;;
    --detach|-d) DETACH=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$LOGDIR"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing command: $1" >&2; exit 1; }
}
need python3
need npm

BOOTSTRAP=("$ROOT/scripts/bootstrap.sh")
if [[ "$SKIP_HUNYUAN" == "1" ]]; then
  BOOTSTRAP+=(--skip-hunyuan)
fi

if [[ ! -d "$ROOT/backend/.venv" || ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Dependencies missing — running bootstrap …"
  "${BOOTSTRAP[@]}"
elif [[ "$SKIP_HUNYUAN" != "1" ]] && ! "$ROOT/backend/scripts/hunyuan3d/fetch_vendor.sh" --check >/dev/null; then
  echo "Hunyuan source/weights missing — downloading (resume-safe, ~20–28 GB) …"
  "$ROOT/backend/scripts/hunyuan3d/fetch_vendor.sh"
  if [[ ! -d "$ROOT/backend/.venv-hunyuan3d" ]]; then
    "$ROOT/backend/scripts/hunyuan3d/setup_mac.sh" --skip-weights || \
      echo "WARN  setup_mac.sh failed; Hunyuan API may not start"
  fi
else
  if [[ "$SKIP_HUNYUAN" == "1" ]]; then
    echo "Skipping Hunyuan fetch (--skip-hunyuan)."
  else
    echo "OK  Hunyuan vendor present"
  fi
fi

if [[ ! -f "$ROOT/frontend/tsconfig.tsbuildinfo" ]]; then
  echo "tsbuildinfo missing — fetching/generating …"
  "$ROOT/scripts/fetch_tsbuildinfo.sh" || \
    echo "WARN  tsbuildinfo step failed; Next.js will still start"
else
  echo "OK  frontend/tsconfig.tsbuildinfo"
fi

[[ -f "$ROOT/backend/.env" ]] || cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
[[ -f "$ROOT/frontend/.env.local" ]] || cp "$ROOT/frontend/.env.example" "$ROOT/frontend/.env.local"

kill_tree() {
  local pid="$1"
  pkill -P "$pid" >/dev/null 2>&1 || true
  kill "$pid" >/dev/null 2>&1 || true
}

stop_all() {
  local pid
  for pid in $PIDS; do
    kill_tree "$pid"
  done
}
trap stop_all EXIT INT TERM

echo "Starting backend :8000 …"
# shellcheck disable=SC1091
source "$ROOT/backend/.venv/bin/activate"
(
  cd "$ROOT/backend"
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
) >"$LOGDIR/backend.log" 2>&1 &
BE_PID=$!
PIDS="$PIDS $BE_PID"
echo "  pid $BE_PID  log $LOGDIR/backend.log"

echo "Starting frontend :3000 …"
(
  cd "$ROOT/frontend"
  exec npm run dev -- --port 3000 --hostname 0.0.0.0
) >"$LOGDIR/frontend.log" 2>&1 &
FE_PID=$!
PIDS="$PIDS $FE_PID"
echo "  pid $FE_PID  log $LOGDIR/frontend.log"

if [[ "$START_HY3D" == "1" ]]; then
  echo "Starting Hunyuan3D API :8080 …"
  (
    exec "$ROOT/backend/scripts/hunyuan3d/start_server.sh"
  ) >"$LOGDIR/hunyuan3d.log" 2>&1 &
  HY_PID=$!
  PIDS="$PIDS $HY_PID"
  echo "  pid $HY_PID  log $LOGDIR/hunyuan3d.log"
fi

echo
echo "Open http://localhost:3000"
echo "API  http://127.0.0.1:8000"
[[ "$START_HY3D" == "1" ]] && echo "3D   http://127.0.0.1:8080"
echo "Logs $LOGDIR"
echo

if [[ "$DETACH" == "1" ]]; then
  trap - EXIT INT TERM
  echo "$PIDS" >"$LOGDIR/pids"
  echo "Detached. Stop with: kill \$(cat $LOGDIR/pids)"
  exit 0
fi

echo "Ctrl-C to stop."
wait
