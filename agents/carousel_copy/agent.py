"""
Carousel Copy Agent
Para cada carrusel del calendario semanal:
1. Muestra 2 referentes del nicho (con métricas) para que el cliente elija cuál modelar
2. Una vez aprobado el referente, genera el copy completo del carrusel
"""
from core.gemini_client import gemini
from core.brand_knowledge import K_CAROUSEL_COPY
from core.client_store import load_memory, load_referents_db, update_memory
import json
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente de Copy de Carruseles de RIMA.
Generás propuestas de copy para carruseles de Instagram, modelando referentes exitosos
del nicho y adaptándolos al negocio del cliente.

Base de conocimiento:
{K_CAROUSEL_COPY}

Reglas:
- Insight, no valor: mostrar que tenés la respuesta, no darla completa
- 7 slides por carrusel (1 gancho + 5 desarrollo + 1 CTA con palabra clave)
- Copy directo, lenguaje de 16 años, verdad incómoda — nunca motivacional genérico
- El slide 1 es el más importante — decide si la persona desliza
- El CTA siempre tiene entregable específico + palabra clave
- Adaptar al tono y voz del cliente"""


class CarouselCopyAgent:
    def __init__(self):
        self.name = "carousel_copy"

    def propose_referents(self, carousel_slot: dict, brand: str, brand_brief: dict) -> dict:
        """
        Step 1: Show 2 top referent carousels for client to choose which to model.
        """
        posts_db = load_referents_db(brand)
        # Filter only Image/carousel type posts with good metrics
        carousels = [
            p for p in posts_db.values()
            if p.get("type", "").lower() in ("sidecar", "carousel", "image")
            and p.get("metrics", {}).get("fuerza", 0) > 0
        ]
        carousels.sort(key=lambda p: p.get("metrics", {}).get("engagement_score", 0), reverse=True)

        topic = carousel_slot.get("topic", "")
        carousel_type = carousel_slot.get("carousel_type", "informativo")

        # Take top 2 relevant referents
        top_2 = carousels[:2]
        options = []
        for c in top_2:
            m = c.get("metrics", {})
            options.append({
                "owner": c.get("owner", ""),
                "url": c.get("url", ""),
                "caption_preview": c.get("caption", "")[:200],
                "fuerza": m.get("fuerza", 0),
                "consistencia": m.get("consistencia", 0),
                "traccion_pct": m.get("traccion_pct", 0),
                "views": c.get("views", 0),
                "comments": c.get("comments", 0),
            })

        return {
            "agent": self.name,
            "step": "propose_referents",
            "carousel_slot": carousel_slot,
            "carousel_type": carousel_type,
            "topic": topic,
            "options": options,
            "message": f"Para el carrusel de {carousel_slot.get('date', '')}, tema: {topic}. ¿Cuál de estos referentes modelamos?",
        }

    def run(self, carousel_slot: dict, brand_brief: dict, brand: str,
            referent: dict = None) -> dict:
        """
        Step 2: Generate complete carousel copy once client picks a referent.
        referent: the chosen referent post dict
        """
        memory = load_memory(brand)
        tone_notes = "\n".join(memory.get("tone_preferences", [])) or "Natural y directo"
        disliked = ", ".join(memory.get("disliked_words", [])) or "ninguna"

        slides = self._generate_slides(carousel_slot, brand_brief, referent, tone_notes, disliked)

        result = {
            "agent": self.name,
            "brand": brand,
            "carousel_slot": carousel_slot,
            "referent_modeled": referent.get("url", "") if referent else None,
            "slides": slides,
            "status": "pending_approval",
            "changes_remaining": 3,
            "generated_at": datetime.now().isoformat(),
        }
        return result

    def _generate_slides(self, slot: dict, brief: dict, referent: dict,
                         tone_notes: str, disliked: str) -> list:
        referent_context = ""
        if referent:
            referent_context = f"""
REFERENTE A MODELAR:
- Cuenta: {referent.get('owner', '')}
- Caption: {referent.get('caption_preview', referent.get('caption', ''))[:300]}
- Métricas: Fuerza {referent.get('fuerza', 0)}, Comentarios {referent.get('comments', 0)}
- URL: {referent.get('url', '')}
Modelá la DINÁMICA (estructura, ritmo, tipo de gancho) — NO el contenido textual.
"""

        prompt = f"""
Genera el copy completo para este carrusel de Instagram (7 slides).

NEGOCIO: {brief.get('business_name')}
SERVICIO: {brief.get('service')}
CLIENTE IDEAL: {brief.get('ideal_client')}
RESULTADO: {brief.get('main_result')}
CASOS DE ÉXITO: {brief.get('success_cases', '')}

CARRUSEL:
- Fecha: {slot.get('date', '')}
- Tipo: {slot.get('carousel_type', 'informativo')}
- Tema: {slot.get('topic', '')}
- Formato: {slot.get('format', 'estándar')}

TONO DEL CLIENTE: {tone_notes}
PALABRAS A EVITAR: {disliked}

{referent_context}

Genera el copy en JSON:
{{
  "format": "nombre del formato (ej: Noticia urgente, Metafórico, Cómic, Minimalista, Recursos ocultos)",
  "slides": [
    {{
      "slide_number": 1,
      "role": "gancho",
      "main_text": "texto principal del slide",
      "secondary_text": "texto secundario si aplica",
      "visual_suggestion": "descripción de la imagen/visual sugerida para este slide",
      "notes": "indicaciones de diseño si aplica"
    }},
    ...7 slides en total...
  ],
  "cta_keyword": "palabra clave para comentarios",
  "cta_deliverable": "qué se entrega al comentar la palabra clave"
}}
Solo el JSON, sin texto adicional.
"""
        response = gemini.generate(prompt, SYSTEM_PROMPT)
        return self._parse_slides(response)

    def _parse_slides(self, response: str) -> list:
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
                return data.get("slides", [])
            except Exception:
                pass
        return [{"raw": response}]

    def apply_feedback(self, brand: str, feedback: str, approved_format: str = ""):
        update_memory(brand, {
            "approved_content_patterns": f"carrusel formato {approved_format}" if approved_format else "",
            "changes_log": {
                "agent": "carousel_copy",
                "feedback": feedback,
                "timestamp": datetime.now().isoformat(),
            }
        })


carousel_copy_agent = CarouselCopyAgent()
