"""HTTP client for local Hunyuan3D-2 API server."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import httpx

from ..config import get_settings


class Hunyuan3DError(RuntimeError):
    pass


def _base_url() -> str:
    return get_settings().hunyuan3d_url.rstrip("/")


def check_status(timeout: float = 3.0) -> dict[str, Any]:
    cfg = get_settings()
    info: dict[str, Any] = {
        "enabled": cfg.hunyuan3d_enabled,
        "url": cfg.hunyuan3d_url,
        "model": cfg.hunyuan3d_model,
        "subfolder": cfg.hunyuan3d_subfolder,
        "texture_enabled": cfg.hunyuan3d_texture,
        "text_to_3d": True,
        "online": False,
        "message": "",
    }
    if not cfg.hunyuan3d_enabled:
        info["message"] = "Hunyuan3D integration disabled in config"
        return info
    try:
        with httpx.Client(timeout=timeout) as client:
            for path in ("/docs", "/openapi.json"):
                try:
                    r = client.get(f"{_base_url()}{path}")
                    if r.status_code < 500:
                        info["online"] = True
                        info["message"] = "Hunyuan3D API reachable"
                        return info
                except httpx.HTTPError:
                    continue
            info["message"] = "Hunyuan3D offline — run backend/scripts/hunyuan3d/start_server.sh"
    except httpx.HTTPError as exc:
        info["message"] = f"Hunyuan3D offline: {exc}"
    return info


def _post_generate(payload: dict[str, Any], timeout: float = 2400.0) -> bytes:
    cfg = get_settings()
    if not cfg.hunyuan3d_enabled:
        raise Hunyuan3DError("Hunyuan3D disabled")

    url = f"{_base_url()}/generate"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                url,
                headers={"Content-Type": "application/json"},
                content=json.dumps(payload),
            )
    except httpx.ConnectError as exc:
        raise Hunyuan3DError(
            f"Hunyuan3D 服务未启动（{cfg.hunyuan3d_url}）。"
            f"请先运行：./backend/scripts/hunyuan3d/start_server.sh"
        ) from exc
    except httpx.TimeoutException as exc:
        raise Hunyuan3DError("Hunyuan3D 请求超时，模型可能仍在加载") from exc

    if r.status_code >= 400:
        raise Hunyuan3DError(f"Hunyuan3D error {r.status_code}: {r.text[:400]}")
    ct = r.headers.get("content-type", "")
    if ct.startswith("application/json"):
        data = r.json()
        if data.get("error_code"):
            raise Hunyuan3DError(data.get("text", "generation failed"))
        if "model_base64" in data:
            return base64.b64decode(data["model_base64"])
        if "glb" in data:
            return base64.b64decode(data["glb"])
    if len(r.content) > 100:
        return r.content
    raise Hunyuan3DError("empty response from Hunyuan3D")


def generate_mesh(
    image_bytes: bytes,
    *,
    with_texture: bool = False,
    timeout: float = 2400.0,
) -> bytes:
    cfg = get_settings()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return _post_generate(
        {"image": b64, "texture": bool(with_texture and cfg.hunyuan3d_texture)},
        timeout=timeout,
    )


def generate_mesh_from_text(
    text: str,
    *,
    with_texture: bool = False,
    timeout: float = 2400.0,
) -> bytes:
    cfg = get_settings()
    return _post_generate(
        {"text": text, "texture": bool(with_texture and cfg.hunyuan3d_texture)},
        timeout=timeout,
    )


def generate_character_mesh(image_bytes: bytes, *, with_texture: bool = False, timeout: float = 2400.0) -> bytes:
    return generate_mesh(image_bytes, with_texture=with_texture, timeout=timeout)


def save_glb(data: bytes, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return out_path
