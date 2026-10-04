"""Text prompt → reference image for Hunyuan3D shape generation."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ..config import get_settings


ROOT = Path(__file__).resolve().parents[2]
HUNYUAN_VENV = ROOT / ".venv-hunyuan3d"
CLI = ROOT / "scripts" / "hunyuan3d" / "text_to_image_cli.py"


def _python() -> Path:
    py = HUNYUAN_VENV / "bin" / "python3"
    if py.is_file():
        return py
    return Path(sys.executable)


def prompt_for_kind(prompt: str, kind: str) -> str:
    p = prompt.strip()
    if kind == "character":
        return f"全身人物角色,{p},白色背景,3D风格,最佳质量,完整身体,单人"
    if kind == "prop":
        return f"单个道具物体,{p},白色背景,3D风格,最佳质量,孤立展示"
    return p


def text_to_image_bytes(
    prompt: str,
    *,
    kind: str = "character",
    seed: int = 42,
) -> bytes:
    """Run HunyuanDiT in hunyuan venv; return PNG bytes."""
    cfg = get_settings()
    out_dir = Path(cfg.generator_output_dir) / "text2img"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"t2i-{abs(hash(prompt + kind)) % 10**8}.png"

    full_prompt = prompt_for_kind(prompt, kind)
    env = {
        **os.environ,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTORCH_ENABLE_MPS_FALLBACK": "1",
    }
    cmd = [
        str(_python()),
        str(CLI),
        full_prompt,
        "-o",
        str(out_path),
        "--device",
        cfg.hunyuan3d_device,
        "--seed",
        str(seed),
    ]
    # DiT on CPU can take 20–40+ minutes for first/cold run
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=env)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "text2image failed")[:600]
        raise RuntimeError(err)
    if not out_path.is_file():
        raise RuntimeError("text2image produced no output")
    return out_path.read_bytes()
