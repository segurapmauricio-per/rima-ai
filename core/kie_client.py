"""
Cliente KIE AI — integración real (Sprint KIE, Fase 2.2).

Imagen: modelo google/nano-banana vía POST /api/v1/jobs/createTask (asíncrono)
+ polling GET /api/v1/jobs/recordInfo hasta state=success/fail. La URL generada
viene en data.resultJson (string JSON) → resultUrls[].
Con reference_image (URL pública http/https) usa google/nano-banana-edit.

Video (Veo3.1): NO implementado — la API existe (/api/v1/veo/generate) pero el
costo en créditos no está documentado; queda pendiente. El esquema de spec
visual (core/visual_spec.py) ya reserva duracion_seg/escenas para ese caso.

Rate limit duro de la cuenta: 20 generaciones cada 10 segundos. RateLimiter
(ventana deslizante, thread-safe) lo garantiza aunque se llame en loop.

Nunca loguear KIE_API_KEY ni headers de autenticación.
"""
from __future__ import annotations

import json
import os
import time
import threading
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API_BASE = "https://api.kie.ai/api/v1"
MODEL_IMAGEN = "google/nano-banana"
MODEL_IMAGEN_EDIT = "google/nano-banana-edit"

RATE_MAX_LLAMADAS = 20
RATE_VENTANA_S = 10.0
POLL_INTERVALO_S = 3.0
POLL_TIMEOUT_S = 180.0
HTTP_TIMEOUT_S = 30.0


class RateLimiter:
    """Ventana deslizante thread-safe: máximo max_llamadas por ventana_s."""

    def __init__(self, max_llamadas: int = RATE_MAX_LLAMADAS,
                 ventana_s: float = RATE_VENTANA_S):
        self.max_llamadas = max_llamadas
        self.ventana_s = ventana_s
        self._marcas: deque = deque()
        self._lock = threading.Lock()

    def acquire(self) -> float:
        """Bloquea hasta que haya cupo. Devuelve segundos esperados."""
        esperado = 0.0
        while True:
            with self._lock:
                ahora = time.monotonic()
                while self._marcas and ahora - self._marcas[0] >= self.ventana_s:
                    self._marcas.popleft()
                if len(self._marcas) < self.max_llamadas:
                    self._marcas.append(ahora)
                    return esperado
                pausa = self.ventana_s - (ahora - self._marcas[0])
            pausa = max(pausa, 0.05)
            time.sleep(pausa)
            esperado += pausa


_rate_limiter = RateLimiter()


def is_configured() -> bool:
    return bool(os.getenv("KIE_API_KEY"))


def _request(method: str, url: str, body: Optional[dict] = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + os.environ["KIE_API_KEY"])
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode())


def generate_image(prompt: str, ratio: str = "1:1",
                   reference_image: Optional[str] = None) -> dict:
    """Genera una imagen vía KIE AI (síncrono: crea la tarea y espera el polling).

    Devuelve {"status": "ok", "image_url": ..., "task_id": ..., "raw": {...}}
    o {"status": "not_configured"|"error", "reason": ...} sin crashear.
    """
    if not is_configured():
        return {"status": "not_configured", "reason": "Falta KIE_API_KEY"}

    modelo = MODEL_IMAGEN
    entrada: dict = {"prompt": prompt, "aspect_ratio": ratio,
                     "output_format": "png"}
    if reference_image and str(reference_image).startswith(("http://", "https://")):
        modelo = MODEL_IMAGEN_EDIT
        entrada["image_urls"] = [reference_image]

    _rate_limiter.acquire()
    try:
        creacion = _request("POST", f"{API_BASE}/jobs/createTask",
                            {"model": modelo, "input": entrada})
        if creacion.get("code") != 200:
            return {"status": "error",
                    "reason": f"createTask code={creacion.get('code')}: {creacion.get('msg')}"}
        task_id = (creacion.get("data") or {}).get("taskId")
        if not task_id:
            return {"status": "error", "reason": "createTask sin taskId"}

        inicio = time.monotonic()
        while time.monotonic() - inicio < POLL_TIMEOUT_S:
            time.sleep(POLL_INTERVALO_S)
            detalle = _request("GET", f"{API_BASE}/jobs/recordInfo?taskId={task_id}")
            data = detalle.get("data") or {}
            estado = data.get("state")
            if estado == "success":
                resultado = json.loads(data.get("resultJson") or "{}")
                urls = resultado.get("resultUrls") or []
                if not urls:
                    return {"status": "error", "task_id": task_id,
                            "reason": "success sin resultUrls"}
                return {"status": "ok", "image_url": urls[0],
                        "task_id": task_id,
                        "credits_consumed": data.get("creditsConsumed"),
                        "raw": data}
            if estado == "fail":
                return {"status": "error", "task_id": task_id,
                        "reason": data.get("failMsg") or data.get("failCode") or "fail"}
            # waiting / queuing / generating → seguir esperando
        return {"status": "error", "task_id": task_id,
                "reason": f"timeout tras {int(POLL_TIMEOUT_S)}s esperando la generación"}
    except urllib.error.HTTPError as e:
        return {"status": "error", "reason": f"HTTP {e.code} de KIE AI"}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def download_image(image_url: str, destino: Path) -> dict:
    """Descarga la imagen generada (CDN de KIE) a un archivo local."""
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(image_url)
        # El CDN de KIE devuelve 403 al User-Agent default de urllib.
        req.add_header("User-Agent",
                       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0 Safari/537.36")
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp, \
                open(destino, "wb") as f:
            f.write(resp.read())
        return {"status": "ok", "path": str(destino)}
    except Exception as e:
        return {"status": "error", "reason": str(e)}
