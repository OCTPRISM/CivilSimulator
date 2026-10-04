"""In-memory async generation jobs."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def create_job(kind: str, prompt: str | None = None, *, outfit_id: str | None = None) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "kind": kind,
            "prompt": prompt,
            "outfit_id": outfit_id,
            "outfit": None,
            "error": None,
            "glb_url": None,
            "source": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        j = _jobs.get(job_id)
        return dict(j) if j else None


def _update(job_id: str, **fields: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(fields)
            _jobs[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()


def run_in_background(job_id: str, fn: Callable[[], dict[str, Any]]) -> None:
    def _worker() -> None:
        _update(job_id, status="running")
        try:
            result = fn()
            if result.get("status") == "done":
                _update(
                    job_id,
                    status="done",
                    glb_url=result.get("glb_url"),
                    source=result.get("source"),
                    prompt=result.get("prompt"),
                    outfit_id=result.get("outfit_id"),
                    outfit=result.get("outfit"),
                    error=None,
                )
            else:
                _update(job_id, status="failed", error=result.get("error") or "unknown error")
        except Exception as exc:
            _update(job_id, status="failed", error=str(exc))

    threading.Thread(target=_worker, daemon=True).start()
