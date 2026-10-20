#!/usr/bin/env bash
# One-click Tech Preview deploy: Python + Node deps, env files,
# Hunyuan source/weights, and frontend tsbuildinfo.
#
#   ./scripts/bootstrap.sh
#   ./scripts/bootstrap.sh --skip-hunyuan
#   ./scripts/bootstrap.sh --skip-weights
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
SKIP_HUNYUAN=0
SKIP_WEIGHTS=0
SKIP_TSBUILD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-hunyuan) SKIP_HUNYUAN=1; shift ;;
    --skip-weights) SKIP_WEIGHTS=1; shift ;;
    --skip-tsbuildinfo) SKIP_TSBUILD=1; shift ;;
    -h|--help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

echo "== CivilSimulator bootstrap =="
echo "root: $ROOT"

# --- backend ---
if [[ ! -d "$ROOT/backend/.venv" ]]; then
  echo "Creating backend/.venv …"
  python3 -m venv "$ROOT/backend/.venv"
fi
# shellcheck disable=SC1091
source "$ROOT/backend/.venv/bin/activate"
pip install -U pip wheel setuptools
pip install -r "$ROOT/backend/requirements.txt"
if [[ ! -f "$ROOT/backend/.env" ]]; then
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
  echo "Wrote backend/.env from example"
fi

# --- frontend ---
if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "npm install …"
  (cd "$ROOT/frontend" && npm install)
fi
if [[ ! -f "$ROOT/frontend/.env.local" ]]; then
  cp "$ROOT/frontend/.env.example" "$ROOT/frontend/.env.local"
  echo "Wrote frontend/.env.local from example"
fi

# --- Hunyuan vendor (source + weights + dedicated venv) ---
if [[ "$SKIP_HUNYUAN" == "1" ]]; then
  echo "Skipping Hunyuan vendor (--skip-hunyuan)."
else
  SETUP=("$ROOT/backend/scripts/hunyuan3d/setup_mac.sh")
  [[ "$SKIP_WEIGHTS" == "1" ]] && SETUP+=(--skip-weights)
  "${SETUP[@]}"
fi

# --- tsbuildinfo ---
if [[ "$SKIP_TSBUILD" == "1" ]]; then
  echo "Skipping tsbuildinfo (--skip-tsbuildinfo)."
else
  "$ROOT/scripts/fetch_tsbuildinfo.sh"
fi

cat <<EOF

✓ Bootstrap complete.

Start:
  ./scripts/start.sh              # backend :8000 + frontend :3000
  ./scripts/start.sh --hunyuan    # also Hunyuan3D API :8080

Play-only (no Hunyuan download):
  ./scripts/bootstrap.sh --skip-hunyuan
  ./scripts/start.sh --skip-hunyuan
EOF
