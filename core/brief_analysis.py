"""
Análisis del brief de negocio (oferta, avatar, problema, resultado) desde scrape IG.
Usa Gemini + metodología de Conocimiento/oferta-nicho.md.
"""
from __future__ import annotations

import json
from typing import Optional

from core.brand_knowledge import OFERTA
from core.gemini_client import gemini

BRIEF_SYSTEM = """Eres estratega de oferta para RIMA AI (negocios de servicios en LATAM).

Tu trabajo es inferir el brief REAL del negocio a partir de señales de Instagram.
- NO copies la biografía textualmente en "servicio".
- Vendés resultados, no entregables sueltos (metodología Hormozi / oferta irresistible).
- Si no hay evidencia clara en bio + posts para un campo, dejá "texto" vacío y "confianza": "baja".
- Nunca inventes datos genéricos ni placeholders.
- "confianza" solo puede ser: "alta", "media" o "baja".

Responde SOLO JSON válido en español."""

CONFIDENCE_OK = frozenset({"alta", "media"})


def _field_text(entry: dict) -> str:
    if not isinstance(entry, dict):
        return ""
    conf = (entry.get("confianza") or "").strip().lower()
    if conf not in CONFIDENCE_OK:
        return ""
    return (entry.get("texto") or "").strip()


def brief_fields_for_brand(brief: Optional[dict]) -> dict[str, str]:
    """Extrae solo campos con confianza alta/media para prellenar brand."""
    brief = brief or {}
    out = {}
    mapping = {
        "servicio": "brand_service",
        "cliente_ideal": "brand_ideal_client",
        "problema": "brand_problem",
        "resultado_principal": "brand_result",
    }
    for src, dst in mapping.items():
        text = _field_text(brief.get(src) or {})
        if text:
            out[dst] = text[:500]
    return out


def analyze_brief_from_ig(
    profile: dict,
    posts: list,
    insights: Optional[dict] = None,
) -> dict:
    """Analiza oferta real, avatar, problema y resultado desde perfil + posts."""
    insights = insights or {}
    posts_summary = []
    for i, p in enumerate((posts or [])[:15]):
        posts_summary.append({
            "n": i + 1,
            "tipo": p.get("type", "Image"),
            "caption": (p.get("caption") or "")[:300],
        })

    prior = {
        "oferta_detectada": insights.get("oferta_detectada") or "",
        "problema_detectado": insights.get("problema_detectado") or "",
        "resultado_prometido": insights.get("resultado_prometido") or "",
        "cliente_ideal": insights.get("cliente_ideal") or "",
        "temas_frecuentes": insights.get("temas_frecuentes") or [],
        "biografia_resumen": insights.get("biografia_resumen") or "",
    }

    prompt = f"""Analizá este negocio de Instagram y completá su brief estratégico.

=== METODOLOGÍA OFERTA (referencia) ===
{OFERTA[:3500]}

=== PERFIL ===
Usuario: @{profile.get('username', '')}
Nombre: {profile.get('full_name', '')}
Bio: {profile.get('biography', '')}
Categoría: {profile.get('business_category', '')}

=== SEÑALES PREVIAS (pueden estar incompletas o imprecisas) ===
{json.dumps(prior, ensure_ascii=False)}

=== PUBLICACIONES RECIENTES ===
{json.dumps(posts_summary, ensure_ascii=False)}

Devolvé JSON con esta estructura exacta:
{{
  "servicio": {{
    "texto": "qué vende/promete el negocio como oferta concreta (resultado + vehículo, no la bio copiada)",
    "confianza": "alta|media|baja"
  }},
  "cliente_ideal": {{
    "texto": "avatar del cliente ideal: quién es, contexto, dolores",
    "confianza": "alta|media|baja"
  }},
  "problema": {{
    "texto": "problema raíz que resuelve (dolor profundo, no síntoma)",
    "confianza": "alta|media|baja"
  }},
  "resultado_principal": {{
    "texto": "transformación/resultado principal que promete",
    "confianza": "alta|media|baja"
  }}
}}"""

    try:
        raw = gemini.generate_json(prompt, system_prompt=BRIEF_SYSTEM)
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        if isinstance(data, dict):
            return data
    except Exception as e:
        print(f"[brief_analysis] Gemini error: {e}")
    return {
        "servicio": {"texto": "", "confianza": "baja"},
        "cliente_ideal": {"texto": "", "confianza": "baja"},
        "problema": {"texto": "", "confianza": "baja"},
        "resultado_principal": {"texto": "", "confianza": "baja"},
    }
