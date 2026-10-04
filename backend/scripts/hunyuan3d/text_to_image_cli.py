#!/usr/bin/env python3
"""CLI: text prompt → PNG (HunyuanDiT, local cache)."""
from __future__ import annotations

import argparse
import os
import sys


def _resolve_device(requested: str) -> str:
    import torch

    if requested == "cuda":
        return "cuda" if torch.cuda.is_available() else (
            "mps" if torch.backends.mps.is_available() else "cpu"
        )
    if requested == "mps":
        # macOS 26+: MPS often crashes; prefer cpu unless explicitly forced
        if os.environ.get("HY3D_FORCE_MPS") == "1" and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    return requested or "cpu"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", help="text prompt")
    parser.add_argument("-o", "--output", required=True, help="output PNG path")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--steps", type=int, default=25, help="diffusion steps")
    parser.add_argument("--size", type=int, default=1024, help="square output size")
    parser.add_argument(
        "--kind",
        choices=("character", "map", "prop"),
        default="character",
        help="prompt suffix / length policy",
    )
    args = parser.parse_args()

    import torch
    from diffusers import HunyuanDiTPipeline

    # Prefer offline / local HF cache (already downloaded)
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    device = _resolve_device(args.device)
    dtype = torch.float16 if device in ("cuda", "mps") else torch.float32
    model_id = "Tencent-Hunyuan/HunyuanDiT-v1.1-Diffusers-Distilled"

    print(f"Loading HunyuanDiT on {device} ({dtype}) kind={args.kind}…", file=sys.stderr, flush=True)
    pipe = HunyuanDiTPipeline.from_pretrained(
        model_id,
        torch_dtype=dtype,
        local_files_only=True,
    )
    pipe = pipe.to(device)

    if args.kind == "map":
        pos = ",鸟瞰全图,俯视战略地图,游戏概念美术,鲜明地势植被分区,最佳质量"
        neg = (
            "人物特写,半身像,脸部,文本水印,logo,裁剪,出框,最差质量,低质量,"
            "JPEG伪影,重复,模糊,畸形"
        )
        prompt = (args.prompt[:180] + pos)[:220]
        size = max(512, min(int(args.size), 1024))
    else:
        pos = ",白色背景,3D风格,最佳质量"
        neg = (
            "文本,特写,裁剪,出框,最差质量,低质量,JPEG伪影,重复,病态,"
            "残缺,多余的手指,变异的手,画得不好的手,画得不好的脸,变异,畸形,模糊"
        )
        prompt = (args.prompt[:60] + pos)
        size = max(512, min(int(args.size), 1024))

    steps = max(4, min(int(args.steps), 50))
    generator = torch.Generator(device=device).manual_seed(int(args.seed))
    print(f"Infer steps={steps} size={size} seed={args.seed}", file=sys.stderr, flush=True)
    out = pipe(
        prompt=prompt,
        negative_prompt=neg,
        num_inference_steps=steps,
        width=size,
        height=size,
        generator=generator,
        return_dict=False,
    )[0][0]
    out.save(args.output)
    print(args.output, file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
