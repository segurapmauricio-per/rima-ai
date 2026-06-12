"""
Métricas compuestas para estudio de mercado — prioriza contenido modelable de ventas.
"""
from __future__ import annotations

import math
import re
from typing import Any

TEMATICA_RANK_KEYS = ("problema", "solucion", "resultado", "proceso", "mentalidad")


def _norm_tematica_key(val: str) -> str:
    v = (val or "").lower().strip()
    v = v.replace("ó", "o").replace("ú", "u").replace("í", "i").replace("á", "a").replace("é", "e")
    for key in TEMATICA_RANK_KEYS:
        if key in v:
            return key
    aliases = {
        "problema": ("problem", "pain", "dolor"),
        "solucion": ("solution", "solucion", "como"),
        "resultado": ("result", "testimonio", "transform"),
        "proceso": ("process", "metodo", "rutina", "sistema"),
        "mentalidad": ("mindset", "creencia", "actitud"),
    }
    for key, syns in aliases.items():
        if any(s in v for s in syns):
            return key
    return "problema" if v else "problema"


def infer_scores_tematica(post: dict) -> dict[str, float]:
    """
    Score 0–100 de qué tan modelable es el post para cada temática RIMA.
    Usa scores_tematica de Gemini si existen; si no, infiere desde tipo_angulo + texto.
    """
    analisis = post.get("analisis_json") or {}
    if isinstance(analisis, str):
        try:
            import json
            analisis = json.loads(analisis)
        except Exception:
            analisis = {}

    raw = analisis.get("scores_tematica") or {}
    if isinstance(raw, dict) and len(raw) >= 3:
        out = {}
        for k, v in raw.items():
            try:
                out[_norm_tematica_key(k)] = max(0.0, min(100.0, float(v)))
            except (TypeError, ValueError):
                continue
        for key in TEMATICA_RANK_KEYS:
            out.setdefault(key, 15.0)
        return out

    try:
        mod = max(1, min(10, int(post.get("modelabilidad") or 5)))
    except (TypeError, ValueError):
        mod = 5
    base = 38.0 + mod * 5.5

    scores = {k: 18.0 for k in TEMATICA_RANK_KEYS}
    primary = _norm_tematica_key(
        analisis.get("tipo_angulo") or analisis.get("tematica") or "",
    )
    scores[primary] = base

    blob = " ".join(
        str(analisis.get(k) or "") for k in (
            "tematica", "tipo_angulo", "que_modelar", "problema_resuelto",
            "estructura_guion", "como_adaptar",
        )
    ).lower()
    blob += " " + (post.get("caption") or "")[:400].lower()

    keyword_map = {
        "problema": ("problema", "dolor", "excusa", "friccion", "pain", "struggle"),
        "solucion": ("solucion", "solución", "como ", "tutorial", "paso", "guia"),
        "resultado": ("resultado", "transform", "antes", "despues", "testimonio"),
        "proceso": ("proceso", "rutina", "metodo", "sistema", "workflow", "habito"),
        "mentalidad": ("mentalidad", "mindset", "creencia", "actitud", "motivacion"),
    }
    secondary_cap = max(28.0, base - 18.0)
    for key, words in keyword_map.items():
        if not any(w in blob for w in words):
            continue
        boost = 32.0 + mod * 2
        if key == primary:
            scores[key] = max(scores[key], boost)
        else:
            scores[key] = max(scores[key], min(boost, secondary_cap))

    ventas = float((post.get("metrics") or {}).get("score_ventas") or 0)
    if ventas > 0:
        scores[primary] = min(100.0, scores[primary] + ventas * 0.06)

    return scores


def score_tematica_for_slot(post: dict, slot_tematica: str) -> float:
    """Puntaje de encaje del post con la temática del slot."""
    key = _norm_tematica_key(slot_tematica)
    return float(infer_scores_tematica(post).get(key, 0.0))


def attach_scores_tematica(post: dict) -> dict[str, float]:
    """Calcula y persiste scores_tematica en analisis_json."""
    scores = infer_scores_tematica(post)
    analisis = post.setdefault("analisis_json", {})
    if isinstance(analisis, str):
        try:
            import json
            analisis = json.loads(analisis)
            post["analisis_json"] = analisis
        except Exception:
            analisis = {}
            post["analisis_json"] = analisis
    analisis["scores_tematica"] = {k: round(scores[k], 1) for k in TEMATICA_RANK_KEYS}
    return scores


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
