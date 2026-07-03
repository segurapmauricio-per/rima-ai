"""
Runner simple de jobs en background (in-process, thread por job).

Motivo: scrape Apify + transcripciones + análisis Gemini + batches KIE tardan
minutos; corriendo síncronos dentro del request HTTP dan 502/504 detrás de
nginx. Patrón: POST devuelve {job_id} de inmediato y la UI hace polling a
GET /api/jobs/{job_id}.

Limitación conocida: el registro vive en memoria del proceso — con un solo
worker uvicorn (setup actual) es suficiente; con múltiples workers habría que
mover el estado a SQLite/Redis.
"""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from typing import Any, Callable, Optional

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
JOB_TTL_S = 6 * 3600  # resultados disponibles 6h


def _purge_locked(now: float) -> None:
    stale = [
        jid for jid, j in _JOBS.items()
        if j.get("finished_at") and now - j["finished_at"] > JOB_TTL_S
    ]
    for jid in stale:
        _JOBS.pop(jid, None)


def start_job(kind: str, fn: Callable[[], Any], owner: str = "") -> str:
    """Lanza fn() en un thread daemon y devuelve el job_id."""
    job_id = uuid.uuid4().hex[:12]
    now = time.time()
    with _LOCK:
        _purge_locked(now)
        _JOBS[job_id] = {
            "id": job_id,
            "kind": kind,
            "owner": owner,
            "status": "running",
            "result": None,
            "error": None,
            "created_at": now,
            "finished_at": None,
        }

    def _run():
        try:
            result = fn()
            with _LOCK:
                job = _JOBS.get(job_id)
                if job is not None:
                    job["status"] = "done"
                    job["result"] = result
                    job["finished_at"] = time.time()
        except Exception as e:
            traceback.print_exc()
            with _LOCK:
                job = _JOBS.get(job_id)
                if job is not None:
                    job["status"] = "error"
                    job["error"] = str(e)
                    job["finished_at"] = time.time()

    threading.Thread(target=_run, daemon=True, name=f"job-{kind}-{job_id}").start()
    return job_id


def get_job(job_id: str, owner: str = "") -> Optional[dict]:
    """Estado del job. Si owner no coincide, se trata como inexistente."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        if owner and job.get("owner") and job["owner"] != owner:
            return None
        return dict(job)


def running_job_for(kind: str, owner: str) -> Optional[str]:
    """Job en curso del mismo tipo/dueño (guard contra doble click)."""
    with _LOCK:
        for jid, j in _JOBS.items():
            if j["kind"] == kind and j["owner"] == owner and j["status"] == "running":
                return jid
    return None
