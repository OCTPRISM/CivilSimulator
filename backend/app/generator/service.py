"""Orchestrate generator jobs and asset storage."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ..config import get_settings
from . import hunyuan_client
from .map_service import generate_map
from .outfits import apply_outfit_to_prompt, list_outfits
from .text_to_image_lite import render_reference_png

ModelKind = Literal["character", "prop"]


def output_root() -> Path:
    p = Path(get_settings().generator_output_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_character_outfits(civilization: str | None = None) -> list[dict[str, Any]]:
    return list_outfits(civilization)


def _reference_image_bytes(prompt: str, kind: ModelKind) -> bytes:
    cfg = get_settings()
    if cfg.hunyuan3d_text2img_mode == "dit":
        from .text_to_image import text_to_image_bytes
        return text_to_image_bytes(prompt, kind=kind)
    return render_reference_png(prompt, kind=kind)


def _save_model_job(
    glb: bytes,
    *,
    kind: ModelKind,
    prompt: str | None,
    source: str,
    with_texture: bool,
    job_id: str | None = None,
    outfit: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    job_id = job_id or uuid.uuid4().hex[:12]
    out_dir = output_root() / "models" / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    glb_path = out_dir / "model.glb"
    hunyuan_client.save_glb(glb, glb_path)
    meta: dict[str, Any] = {
        "job_id": job_id,
        "kind": kind,
        "prompt": prompt,
        "source": source,
        "with_texture": with_texture,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if outfit:
        meta["outfit_id"] = outfit.get("id")
        meta["outfit"] = {
            "id": outfit.get("id"),
            "label": outfit.get("label"),
            "era": outfit.get("era"),
            "occupation": outfit.get("occupation"),
            "clothing": outfit.get("clothing"),
            "props": outfit.get("props"),
        }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if user_id:
        (out_dir / "owner.json").write_text(
            json.dumps({"user_id": user_id}),
            encoding="utf-8",
        )
    else:
        _write_model_owner(out_dir, job_id)
    return {
        **meta,
        "status": "done",
        "error": None,
        "glb_url": f"/api/generator/models/{job_id}/model.glb",
    }


def create_model_job_from_image(
    image_bytes: bytes,
    *,
    kind: ModelKind = "character",
    prompt: str | None = None,
    with_texture: bool = False,
    job_id: str | None = None,
    outfit_id: str | None = None,
    civilization: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    outfit = None
    full_prompt = prompt
    if kind == "character" and outfit_id:
        full_prompt, outfit = apply_outfit_to_prompt(
            prompt or "", outfit_id, civilization=civilization,
        )
    try:
        glb = hunyuan_client.generate_mesh(image_bytes, with_texture=with_texture)
        return _save_model_job(
            glb,
            kind=kind,
            prompt=full_prompt,
            source="image",
            with_texture=with_texture,
            job_id=job_id,
            outfit=outfit,
            user_id=user_id,
        )
    except hunyuan_client.Hunyuan3DError as exc:
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(exc),
            "kind": kind,
            "glb_url": None,
        }


def create_model_job_from_text(
    prompt: str,
    *,
    kind: ModelKind = "character",
    with_texture: bool = False,
    job_id: str | None = None,
    outfit_id: str | None = None,
    civilization: str | None = None,
) -> dict[str, Any]:
    prompt = prompt.strip()
    if len(prompt) < 2:
        return {"status": "failed", "error": "prompt too short", "glb_url": None, "job_id": job_id}
    outfit = None
    full_prompt = prompt
    if kind == "character":
        full_prompt, outfit = apply_outfit_to_prompt(
            prompt, outfit_id, civilization=civilization,
        )
        if outfit_id and outfit is None:
            return {
                "job_id": job_id,
                "status": "failed",
                "error": f"unknown outfit_id: {outfit_id}",
                "kind": kind,
                "glb_url": None,
            }
    try:
        image_bytes = _reference_image_bytes(full_prompt, kind)
        glb = hunyuan_client.generate_mesh(image_bytes, with_texture=with_texture)
        source = "text_via_dit" if get_settings().hunyuan3d_text2img_mode == "dit" else "text_via_lite"
        return _save_model_job(
            glb,
            kind=kind,
            prompt=full_prompt,
            source=source,
            with_texture=with_texture,
            job_id=job_id,
            outfit=outfit,
        )
    except hunyuan_client.Hunyuan3DError as exc:
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(exc),
            "kind": kind,
            "glb_url": None,
        }
    except Exception as exc:
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(exc),
            "kind": kind,
            "glb_url": None,
        }


def _write_model_owner(out_dir: Path, job_id: str) -> None:
    try:
        from . import jobs as gen_jobs
        job = gen_jobs.get_job(job_id)
        uid = (job or {}).get("user_id")
        if uid:
            (out_dir / "owner.json").write_text(
                json.dumps({"user_id": uid}),
                encoding="utf-8",
            )
    except Exception:
        pass


def get_model_glb_path(job_id: str) -> Path | None:
    for sub in ("models", "characters"):
        p = output_root() / sub / job_id / "model.glb"
        if p.is_file():
            return p
    return None


def model_owned_by(job_id: str, user_id: str) -> bool:
    """False only when a persisted owner record names a different account."""
    if not user_id:
        return False
    path = get_model_glb_path(job_id)
    if not path:
        return True
    owner_file = path.parent / "owner.json"
    if not owner_file.is_file():
        return True
    try:
        data = json.loads(owner_file.read_text(encoding="utf-8"))
    except Exception:
        return True
    owner = data.get("user_id") if isinstance(data, dict) else None
    return not owner or owner == user_id


def get_map_paths(slug: str) -> tuple[Path | None, Path | None]:
    base = output_root() / "maps"
    png = base / f"{slug}.png"
    js = base / f"{slug}.json"
    return (png if png.is_file() else None, js if js.is_file() else None)


def create_map_job(prompt: str, genre: str | None = None) -> dict[str, Any]:
    return generate_map(prompt, genre)


def create_character_job(
    image_bytes: bytes,
    *,
    with_texture: bool = False,
    user_id: str | None = None,
) -> dict[str, Any]:
    return create_model_job_from_image(
        image_bytes, kind="character", with_texture=with_texture, user_id=user_id,
    )


def get_character_glb_path(job_id: str) -> Path | None:
    return get_model_glb_path(job_id)
