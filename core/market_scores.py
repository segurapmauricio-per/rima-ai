"""
Métricas compuestas para estudio de mercado — prioriza contenido modelable de ventas.
"""
from __future__ import annotations

import math
from typing import Any


def infer_categoria(post: dict) -> str:
    """Clasificación preliminar ventas / educacion / conexion."""
    angulo = (post.get("analisis_json") or {}).get("tipo_angulo", "")
    angulo_l = angulo.lower() if angulo else ""
    if angulo_l in ("problema", "solución", "solucion"):
        return "ventas"
    if angulo_l in ("resultado", "proceso"):
        return "educacion"
    if angulo_l == "mentalidad":
        return "conexion"

    cap = (post.get("caption") or "").lower()
    ventas_kw = (
        "comenta", "comentá", "dm", "link en bio", "agenda", "cupos",
        "oferta", "compr", "venta", "cliente", "resultado", "transform",
    )
    conexion_kw = (
        "mi historia", "detrás de", "detras de", "vulnerab", "personal",
        "mentalidad", "creo que", "honest", "confes",
    )
    if any(k in cap for k in ventas_kw):
        return "ventas"
    if any(k in cap for k in conexion_kw):
        return "conexion"
    return "educacion"


def calculate_score_ventas(post: dict) -> float:
    """
    Score 0–100 para priorizar posts/referentes orientados a ventas modelables.
    Pesos: modelabilidad, conversación, relevancia, alcance comprimido + bonuses.
    """
    m = post.get("metrics") or {}
    analisis = post.get("analisis_json") or {}

    mod = post.get("modelabilidad")
    if mod is not None:
        try:
            model_n = max(0, min(10, int(mod))) / 10.0
        except (TypeError, ValueError):
            model_n = 0.0
    else:
        model_n = 0.0

    if model_n <= 0:
        cat = infer_categoria(post)
        model_n = {"ventas": 0.55, "educacion": 0.35, "conexion": 0.25}.get(cat, 0.35)

    conv = min((m.get("ratio_conversacion") or 0) / 5.0, 1.0)
    rel = min((m.get("relevancia") or 0) / 3.0, 1.0)
    fuerza = max(m.get("fuerza") or 0, 0)
    alcance = min(math.log1p(fuerza) / math.log1p(100), 1.0)

    score = model_n * 0.35 + conv * 0.25 + rel * 0.20 + alcance * 0.10

    enfoque = (analisis.get("enfoque_contenido") or "").lower()
    if "venta" in enfoque:
        score += 0.10

    angulo = (analisis.get("tipo_angulo") or "").lower()
    if angulo in ("problema", "solución", "solucion"):
        score += 0.05

    cta = (analisis.get("cta") or "").strip().lower()
    if cta and cta not in ("sin cta explícito", "sin cta", "implícito: sígueme"):
        score += 0.03

    return round(min(score, 1.0) * 100, 1)


def attach_score_ventas(post: dict) -> float:
    """Calcula y guarda score_ventas en post['metrics']."""
    metrics = post.setdefault("metrics", {})
    sv = calculate_score_ventas(post)
    metrics["score_ventas"] = sv
    return sv
