"""
Reel Copy Agent
Para cada reel del calendario semanal:
1. Muestra 3 referentes del nicho (con métricas de fuerza) para que el cliente elija
2. El cliente puede cambiar la temática si no quiere grabar ese tipo de reel
3. Genera el copy/idea adaptado al negocio
"""
from core.gemini_client import gemini
from core.brand_knowledge import K_REEL_COPY
from core.client_store import load_memory, load_referents_db, load_content_calendar, update_memory
import json
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente de Copy de Reels de RIMA.
Generás propuestas de ideas de Reels de Instagram modelando referentes exitosos
del nicho y adaptándolos al negocio y tono del cliente.

Base de conocimiento:
{K_REEL_COPY}

Reglas:
- Modelar la DINÁMICA del referente (hook, ritmo, estructura) — nunca copiar el texto
- Hook agresivo, directo, que rompa el scroll — sin introducción ni relleno
- Un solo concepto por reel
- La prueba social = 1 número concreto en 1 oración
- CTA = entregable específico + palabra clave
- Adaptar al tono, voz y jerga del cliente
- Si el cliente quiere cambiar la temática, adaptar las 3 propuestas al nuevo ángulo"""


class ReelCopyAgent:
    def __init__(self):
        self.name = "reel_copy"

    def propose_referents(self, reel_slot: dict, brand: str, brand_brief: dict) -> dict:
        """
        Step 1: Show 3 top referent reels for client to choose which to model.
        Returns options with metrics and links.
        """
        posts_db = load_referents_db(brand)
        # Filter video posts with good metrics
        videos = [
            p for p in posts_db.values()
            if p.get("type", "").lower() in ("video", "reel", "xdt_graph_video")
            and p.get("metrics", {}).get("fuerza", 0) > 0
        ]
        videos.sort(
            key=lambda p: p.get("metrics", {}).get("score_ventas")
            or p.get("metrics", {}).get("engagement_score", 0),
            reverse=True,
        )

        content_type = reel_slot.get("content_type", "Problema")
        topic = reel_slot.get("topic", "")

        # Take top 3
        top_3 = videos[:3]
        options = []
        for v in top_3:
            m = v.get("metrics", {})
            options.append({
                "owner": v.get("owner", ""),
                "url": v.get("url", ""),
                "caption_preview": v.get("caption", "")[:200],
                "fuerza": round(m.get("fuerza", 0), 4),
                "consistencia": round(m.get("consistencia", 0), 4),
                "traccion_pct": round(m.get("traccion_pct", 0), 4),
                "views": v.get("views", 0),
                "comments": v.get("comments", 0),
            })

        return {
            "agent": self.name,
            "step": "propose_referents",
            "reel_slot": reel_slot,
            "content_type": content_type,
            "topic": topic,
            "options": options,
            "message": (
                f"Para el reel del {reel_slot.get('date', '')} "
                f"(tipo: {content_type}), te muestro los 3 referentes "
                f"con mejor desempeño esta semana. ¿Cuál modelamos?"
            ),
            "can_change_topic": True,
        }

    def run(self, reel_slot: dict, brand_brief: dict, brand: str,
            referent: dict = None, topic_override: str = None) -> dict:
        """
        Step 2: Generate reel idea + copy once client picks referent.
        topic_override: if client wanted to change the topic
        """
        memory = load_memory(brand)
        tone_notes = "\n".join(memory.get("tone_preferences", [])) or "Directo y auténtico"
        disliked = ", ".join(memory.get("disliked_words", [])) or "ninguna"
        preferred_formats = memory.get("preferred_formats", [])

        if topic_override:
            reel_slot = {**reel_slot, "topic": topic_override}

        idea = self._generate_idea(reel_slot, brand_brief, referent, tone_notes,
                                   disliked, preferred_formats)

        result = {
            "agent": self.name,
            "brand": brand,
            "reel_slot": reel_slot,
            "referent_modeled": referent.get("url", "") if referent else None,
            "topic_changed": bool(topic_override),
            "idea": idea,
            "status": "pending_approval",
            "changes_remaining": 3,
            "generated_at": datetime.now().isoformat(),
        }
        return result

    def _generate_idea(self, slot: dict, brief: dict, referent: dict,
                       tone_notes: str, disliked: str, preferred_formats: list) -> dict:
        referent_context = ""
        if referent:
            referent_context = f"""
REFERENTE A MODELAR:
- Cuenta: {referent.get('owner', '')}
- Caption: {referent.get('caption_preview', referent.get('caption', ''))[:300]}
- Fuerza: {referent.get('fuerza', 0)}, Tracción: {referent.get('traccion_pct', 0)}%
- URL: {referent.get('url', '')}
Modelá la DINÁMICA — estructura del hook, ritmo, tipo de gancho y CTA. NO el texto.
"""

        formats_hint = ", ".join(preferred_formats) if preferred_formats else "Talking head, B-roll con texto"

        prompt = f"""
Genera la propuesta completa para este Reel de Instagram.

NEGOCIO: {brief.get('business_name')}
SERVICIO: {brief.get('service')}
CLIENTE IDEAL: {brief.get('ideal_client')}
RESULTADO: {brief.get('main_result')}
CASOS DE ÉXITO: {brief.get('success_cases', '')}

REEL:
- Fecha: {slot.get('date', '')}
- Tipo de contenido: {slot.get('content_type', 'Problema')}
- Tema: {slot.get('topic', '')}

TONO DEL CLIENTE: {tone_notes}
PALABRAS A EVITAR: {disliked}
FORMATOS PREFERIDOS: {formats_hint}

{referent_context}

Genera en JSON:
{{
  "titulo": "título corto descriptivo de la idea",
  "content_type": "Problema|Solución|Resultado|Mentalidad",
  "format": "Talking head|B-roll con texto|Selfie POV|Clip podcast|Explicativo",
  "hook": "texto exacto del gancho (agresivo, directo, sin introducción)",
  "development": "qué decir/mostrar en el desarrollo (3-4 oraciones)",
  "social_proof": "1 resultado concreto con número (UNA sola oración)",
  "cta": "texto del CTA completo con entregable + palabra clave",
  "cta_keyword": "palabra clave sola",
  "recording_notes": "indicaciones de grabación: energía, encuadre, elemento visual del hook",
  "estimated_duration": "30 seg|45 seg|60 seg",
  "why_works": "por qué este ángulo funciona para este nicho (1 línea)"
}}
Solo el JSON, sin texto adicional.
"""
        response = gemini.generate(prompt, SYSTEM_PROMPT)
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except Exception:
                pass
        return {"raw": response}

    def apply_feedback(self, brand: str, feedback: str, approved_format: str = "",
                       approved_topic: str = ""):
        updates = {
            "changes_log": {
                "agent": "reel_copy",
                "feedback": feedback,
                "timestamp": datetime.now().isoformat(),
            }
        }
        if approved_format:
            updates["preferred_formats"] = approved_format
        update_memory(brand, updates)


reel_copy_agent = ReelCopyAgent()
