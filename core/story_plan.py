"""
Plan de secuencia de historias — artefacto antes de generación visual/KIE.

Metodología: hook → valor (2-3 slides) → CTA (Santiago Muñoz / Nico Azero).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from core import kie_client

PLAN_VERSION = 1


def build_story_plan(
    pub: dict,
    copy_json: dict,
    style_guide: dict,
    slides: list,
    modelo_kie: Optional[str] = None,
) -> dict:
    copy_json = copy_json or {}
    style_guide = style_guide or {}
    modelo = modelo_kie or kie_client.model_imagen()
    plan_slides = []
    for idx, slide in enumerate(slides):
        plan_slides.append({
            "slide_number": slide.get("slide_number", idx + 1),
            "role": slide.get("role", "desarrollo"),
            "main_text": slide.get("main_text", ""),
            "secondary_text": slide.get("secondary_text", ""),
            "visual_suggestion": slide.get("visual_suggestion", ""),
            "sticker_type": slide.get("sticker_type", ""),
            "prompt_kie": slide.get("prompt_sugerido") or slide.get("prompt_usado") or "",
            "ratio": slide.get("ratio") or "9:16",
            "resolution": slide.get("kie_resolution") or kie_client.default_resolution(),
        })
    return {
        "version": PLAN_VERSION,
        "modelo_kie": modelo,
        "resolution": kie_client.default_resolution(),
        "aspect_ratio": "9:16",
        "output_format": "png",
        "formato": "1080x1920",
        "tema": pub.get("tematica") or copy_json.get("story_type") or "",
        "enfoque": pub.get("enfoque") or "",
        "fecha": pub.get("fecha") or "",
        "angulo": copy_json.get("angulo_estrategico") or "",
        "plan_resumen": copy_json.get("plan_resumen") or "",
        "style_guide": style_guide,
        "total_slides": len(slides),
        "coherencia": "Misma línea visual en la secuencia; fondos 9:16 con copy superpuesto.",
        "slides": plan_slides,
        "generated_at": datetime.now().isoformat(),
    }
