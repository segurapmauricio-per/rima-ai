"""
Plan de carrusel (plan.json) — artefacto del skill /carrusel.

Consolida tema, estilo, slides y prompts KIE antes de la generación con
nano-banana-pro. Se persiste en copy_json y produccion_json.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from core import kie_client

PLAN_VERSION = 1

FASE_POR_ROL = {
    "gancho": "portada",
    "desarrollo": "desarrollo",
    "cierre": "cta",
}


def slide_fase(slide: dict, idx: int, total: int) -> str:
    role = (slide.get("role") or "desarrollo").lower()
    if idx == 0 or role == "gancho":
        return "portada"
    if idx >= total - 1 or role == "cierre":
        return "cta"
    return FASE_POR_ROL.get(role, "desarrollo")


def build_carousel_plan(
    pub: dict,
    copy_json: dict,
    style_guide: dict,
    slides: list,
    modelo_kie: Optional[str] = None,
) -> dict:
    """Arma plan.json listo para revisión y generación KIE."""
    copy_json = copy_json or {}
    style_guide = style_guide or {}
    total = len(slides)
    modelo = modelo_kie or kie_client.model_imagen()

    plan_slides = []
    for idx, slide in enumerate(slides):
        plan_slides.append({
            "slide_number": slide.get("slide_number", idx + 1),
            "role": slide.get("role", "desarrollo"),
            "fase": slide_fase(slide, idx, total),
            "main_text": slide.get("main_text", ""),
            "secondary_text": slide.get("secondary_text", ""),
            "bullets": list(slide.get("bullets") or []),
            "content_type": slide.get("content_type", ""),
            "visual_suggestion": slide.get("visual_suggestion", ""),
            "prompt_kie": slide.get("prompt_sugerido") or slide.get("prompt_usado") or "",
            "ratio": slide.get("ratio") or "1:1",
            "resolution": slide.get("kie_resolution") or kie_client.default_resolution(),
        })

    return {
        "version": PLAN_VERSION,
        "modelo_kie": modelo,
        "resolution": kie_client.default_resolution(),
        "aspect_ratio": "1:1",
        "output_format": "png",
        "tema": pub.get("tematica") or copy_json.get("tema") or "",
        "enfoque": pub.get("enfoque") or "",
        "fecha": pub.get("fecha") or "",
        "formato": copy_json.get("formato") or style_guide.get("formato_nombre") or "",
        "plan_resumen": copy_json.get("plan_resumen") or "",
        "style_guide": style_guide,
        "cta_keyword": copy_json.get("cta_keyword") or "",
        "cta_deliverable": copy_json.get("cta_deliverable") or "",
        "total_slides": total,
        "coherencia": (
            "Slide 1 (portada) define estilo; slides 2+ usan image_input "
            "con la portada como referencia visual vía nano-banana-pro."
        ),
        "slides": plan_slides,
        "generated_at": datetime.now().isoformat(),
    }
