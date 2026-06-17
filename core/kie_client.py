"""
Cliente KIE AI — nano-banana-pro (skill carruseles Santiago Muñoz).

Imagen: POST /api/v1/jobs/createTask (asíncrono) + polling GET
/api/v1/jobs/recordInfo hasta state=success|fail. URLs en resultJson.resultUrls.

Modelo por defecto: nano-banana-pro (texto integrado en imagen, resolución 1K).
Referencia visual: input.image_input[] (pro) o google/nano-banana-edit (legacy).

Variables de entorno:
  KIE_API_KEY          — obligatoria
  KIE_MODEL_IMAGEN     — default nano-banana-pro
  KIE_MODEL_LEGACY     — fallback google/nano-banana (+ edit) si pro falla
  KIE_RESOLUTION       — default 1K (pro: 1K|2K|4K)

Rate limit: 20 generaciones / 10 s (ventana deslizante thread-safe).
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
MODEL_PRO = "nano-banana-pro"
MODEL_LEGACY = "google/nano-banana"
MODEL_LEGACY_EDIT = "google/nano-banana-edit"

RATE_MAX_LLAMADAS = 20
RATE_VENTANA_S = 10.0
POLL_INTERVALO_S = 3.0
POLL_TIMEOUT_S = 300.0
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


def model_imagen() -> str:
    return os.getenv("KIE_MODEL_IMAGEN", MODEL_PRO).strip() or MODEL_PRO


def default_resolution() -> str:
    return os.getenv("KIE_RESOLUTION", "1K").strip() or "1K"


def _is_pro_model(modelo: str) -> bool:
    m = (modelo or "").lower()
    return "pro" in m or m == MODEL_PRO


def is_configured() -> bool:
    return bool(os.getenv("KIE_API_KEY"))


def _request(method: str, url: str, body: Optional[dict] = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + os.environ["KIE_API_KEY"])
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
        return json.loads(resp.read().decode())


def _build_input(prompt: str, ratio: str, resolution: str,
                 reference_image: Optional[str], pro: bool) -> dict:
    entrada: dict = {
        "prompt": prompt,
        "aspect_ratio": ratio,
        "output_format": "png",
    }
    if pro:
        entrada["resolution"] = resolution
        if reference_image and str(reference_image).startswith(("http://", "https://")):
            entrada["image_input"] = [reference_image]
    elif reference_image and str(reference_image).startswith(("http://", "https://")):
        entrada["image_urls"] = [reference_image]
    return entrada


def _poll_task(task_id: str) -> dict:
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
            return {
                "status": "ok",
                "image_url": urls[0],
                "task_id": task_id,
                "model": data.get("model"),
                "credits_consumed": data.get("creditsConsumed"),
                "raw": data,
            }
        if estado == "fail":
            return {
                "status": "error",
                "task_id": task_id,
                "reason": data.get("failMsg") or data.get("failCode") or "fail",
                "raw": data,
            }
    return {
        "status": "error",
        "task_id": task_id,
        "reason": f"timeout tras {int(POLL_TIMEOUT_S)}s esperando la generación",
    }


def _create_and_poll(modelo: str, entrada: dict, pro: bool) -> dict:
    _rate_limiter.acquire()
    creacion = _request("POST", f"{API_BASE}/jobs/createTask",
                        {"model": modelo, "input": entrada})
    if creacion.get("code") != 200:
        return {
            "status": "error",
            "reason": f"createTask code={creacion.get('code')}: {creacion.get('msg')}",
            "model": modelo,
        }
    task_id = (creacion.get("data") or {}).get("taskId")
    if not task_id:
        return {"status": "error", "reason": "createTask sin taskId", "model": modelo}
    result = _poll_task(task_id)
    result["model"] = modelo
    return result


def generate_image(
    prompt: str,
    ratio: str = "1:1",
    reference_image: Optional[str] = None,
    resolution: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """Genera imagen vía KIE (createTask + polling). Fallback legacy opcional."""
    if not is_configured():
        return {"status": "not_configured", "reason": "Falta KIE_API_KEY"}

    modelo = model or model_imagen()
    res = resolution or default_resolution()
    pro = _is_pro_model(modelo)
    entrada = _build_input(prompt, ratio, res, reference_image, pro)

    try:
        if pro and reference_image:
            # Pro: mismo modelo con image_input (no edit separado)
            result = _create_and_poll(modelo, entrada, pro=True)
        elif pro:
            result = _create_and_poll(modelo, entrada, pro=True)
        elif reference_image:
            result = _create_and_poll(MODEL_LEGACY_EDIT, entrada, pro=False)
        else:
            result = _create_and_poll(modelo or MODEL_LEGACY, entrada, pro=False)

        if result.get("status") == "ok":
            result["resolution"] = res
            return result

        legacy = os.getenv("KIE_MODEL_LEGACY", MODEL_LEGACY).strip()
        if pro and legacy and legacy != modelo:
            entrada_legacy = _build_input(prompt, ratio, res, reference_image, pro=False)
            edit_model = MODEL_LEGACY_EDIT if reference_image else legacy
            fallback = _create_and_poll(edit_model, entrada_legacy, pro=False)
            if fallback.get("status") == "ok":
                fallback["resolution"] = res
                fallback["fallback_from"] = modelo
            return fallback
        return result
    except urllib.error.HTTPError as e:
        return {"status": "error", "reason": f"HTTP {e.code} de KIE AI", "model": modelo}
    except Exception as e:
        return {"status": "error", "reason": str(e), "model": modelo}


def download_image(image_url: str, destino: Path) -> dict:
    """Descarga la imagen generada (CDN de KIE) a un archivo local."""
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(image_url)
        req.add_header(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp, \
                open(destino, "wb") as f:
            f.write(resp.read())
        return {"status": "ok", "path": str(destino)}
    except Exception as e:
        return {"status": "error", "reason": str(e)}
