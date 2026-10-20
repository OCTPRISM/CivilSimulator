#!/usr/bin/env bash
# Hunyuan3D-2 local setup for Apple Silicon (M-series).
# Fetches vendor source + weights, then installs the dedicated venv.
# Recommended for M5 Max: Hunyuan3D-2mini-Turbo — 0.6B, ~6 GB shape VRAM.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENDOR="$ROOT/third_party/Hunyuan3D-2"
VENV="$ROOT/backend/.venv-hunyuan3d"
SKIP_WEIGHTS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-weights) SKIP_WEIGHTS=1; shift ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

echo "== Hunyuan3D-2 Mac setup =="
echo "Project root: $ROOT"

FETCH=("$ROOT/backend/scripts/hunyuan3d/fetch_vendor.sh")
[[ "$SKIP_WEIGHTS" == "1" ]] && FETCH+=(--skip-weights)
"${FETCH[@]}"

if [[ ! -d "$VENDOR/.git" && ! -d "$VENDOR/hy3dgen" ]]; then
  echo "Hunyuan3D-2 source missing after fetch." >&2
  exit 1
fi

if [[ -x "$VENV/bin/python" ]] && "$VENV/bin/python" -c "import hy3dgen" >/dev/null 2>&1; then
  echo "OK  hunyuan venv already has hy3dgen ($VENV)"
else
  if [[ ! -d "$VENV" ]]; then
    echo "Creating venv: $VENV"
    python3 -m venv "$VENV"
  fi
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"

  pip install -U pip wheel setuptools
  pip install torch torchvision torchaudio
  pip install -r "$VENDOR/requirements.txt"
  pip install -e "$VENDOR"

  # Texture rasterizer extensions often need CUDA; skip on Mac unless build succeeds.
  if python3 -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
    echo "CUDA detected — building texture rasterizer …"
    (cd "$VENDOR/hy3dgen/texgen/custom_rasterizer" && python3 setup.py install)
    (cd "$VENDOR/hy3dgen/texgen/differentiable_renderer" && python3 setup.py install)
  else
    echo "No CUDA — shape-only mode on Mac MPS (texture pipeline skipped)."
  fi
fi

cat <<EOF

✓ Setup complete.

Start API server:
  ./backend/scripts/hunyuan3d/start_server.sh

Or with the rest of CivilSimulator:
  ./scripts/start.sh --hunyuan

Weights live under third_party/hy3d_models (HY3DGEN_MODELS) and
third_party/hy3d_mlx_weights/paint. They are not git-tracked.
EOF
