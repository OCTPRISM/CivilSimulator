#!/usr/bin/env bash
# Hunyuan3D-2 local setup for Apple Silicon (M-series).
# Recommended for M5 Max: Hunyuan3D-2mini-Turbo — 0.6B, ~6 GB shape VRAM, fastest inference.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
VENDOR="$ROOT/third_party/Hunyuan3D-2"
VENV="$ROOT/backend/.venv-hunyuan3d"

echo "== Hunyuan3D-2 Mac setup =="
echo "Project root: $ROOT"

mkdir -p "$ROOT/third_party"
if [[ ! -d "$VENDOR/.git" ]]; then
  echo "Cloning Tencent-Hunyuan/Hunyuan3D-2 …"
  git clone --depth 1 https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git "$VENDOR"
else
  echo "Repo already present: $VENDOR"
fi

if [[ ! -d "$VENV" ]]; then
  echo "Creating venv: $VENV"
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

pip install -U pip wheel setuptools

# PyTorch with MPS (Apple Silicon)
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

cat <<EOF

✓ Setup complete.

Start API server (shape + optional texture):
  source backend/.venv-hunyuan3d/bin/activate
  cd third_party/Hunyuan3D-2
  python3 gradio_app.py \\
    --model_path tencent/Hunyuan3D-2mini \\
    --subfolder hunyuan3d-dit-v2-mini-turbo \\
    --texgen_model_path tencent/Hunyuan3D-2 \\
    --low_vram_mode \\
    --enable_flashvdm \\
    --port 8080

Or use the wrapper:
  ./backend/scripts/hunyuan3d/start_server.sh

First run downloads ~4–8 GB model weights from Hugging Face.
EOF
