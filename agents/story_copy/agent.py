"""
Story Copy Agent
Genera 2 propuestas de copy para una historia de Instagram.
Una historia a la vez, en secuencia (el weekly orchestrator lo llama iterativamente).
"""
from core.gemini_client import gemini
from core.brand_knowledge import K_STORY_COPY
from core.client_store import load_memory, update_memory
from core.weekly_helpers import format_slot_context_for_copy
import json
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente de Copy de Historias de RIMA.
Escribís copies para historias de Instagram en negocios de servicios en LATAM.

Base de conocimiento:
{K_STORY_COPY}

Reglas:
- El hook comienza en el PRIMER cuadro — sin silencios
- Copy corto: máximo 2-3 líneas de texto por historia
- Adaptar al tono y voz del cliente (preferencias en memoria)
- Escribir en español LATAM natural, como un chat real
- Si el tipo es Hand Raiser: terminar con pregunta abierta
- Si el tipo es CTA: ser honesto sobre la intención de venta"""


class StoryCopyAgent:
    def __init__(self):
        self.name = "story_copy"

    def run(self, story_slot: dict, brand_brief: dict, brand: str,
            market_research: str = "") -> dict:
        """
        story_slot: {
          date, day_of_week, week, story_type, topic, sequence_position
        }
        Returns: {proposal_1: {...}, proposal_2: {...}}
        """
        memory = load_memory(brand)
        proposals = self._generate_proposals(story_slot, brand_brief, memory, market_research)

        result = {
            "agent": self.name,
            "brand": brand,
            "story_slot": story_slot,
            "proposals": proposals,
            "status": "pending_approval",
            "changes_remaining": 3,
            "generated_at": datetime.now().isoformat(),
        }
        return result

    def _generate_proposals(self, slot: dict, brief: dict, memory: dict,
                             market_research: str) -> list:
        story_type = slot.get("story_type", "awareness")
        topic = slot.get("topic", "")
        date = slot.get("date", "")

        tone_notes = "\n".join(memory.get("tone_preferences", [])) or "Natural y cercano"
        disliked = ", ".join(memory.get("disliked_words", [])) or "ninguna"
        preferred_hooks = "\n".join(memory.get("preferred_hooks", [])) or "ninguna preferencia"

        research_context = ""
        if market_research:
            research_context = f"\n{market_research[:1500]}\n"

        slot_context = format_slot_context_for_copy(slot)

        prompt = f"""
Genera 2 propuestas de copy para esta historia de Instagram.

NEGOCIO: {brief.get('business_name')}
SERVICIO: {brief.get('service')}
CLIENTE IDEAL: {brief.get('ideal_client')}
RESULTADO PRINCIPAL: {brief.get('main_result')}
CASOS DE ÉXITO: {brief.get('success_cases', '')}

{slot_context}

HISTORIA A CREAR:
- Fecha: {date}
- Tipo: {story_type}
- Tema: {topic}
- Posición en la secuencia: {slot.get('sequence_position', 1)} de {slot.get('sequence_total', 1)}

PREFERENCIAS DEL CLIENTE:
- Tono: {tone_notes}
- Palabras a evitar: {disliked}
- Hooks que le gustaron antes: {preferred_hooks}

{research_context}

Genera EXACTAMENTE 2 propuestas distintas de copy para esta historia.
Propuesta 1 y Propuesta 2 deben tener ángulos o tonos diferentes.

Responde en JSON:
{{
  "proposal_1": {{
    "hook_text": "primer texto que aparece (arranca en el frame 1)",
    "body_texts": ["texto línea 1", "texto línea 2", "texto línea 3"],
    "cta_text": "texto del botón o respuesta esperada (si aplica)",
    "keyword": "palabra clave para responder (si es Hand Raiser)",
    "image_vibe_needed": "descripción del tipo de imagen que necesita",
    "notes": "indicaciones extra de tono o entrega"
  }},
  "proposal_2": {{
    "hook_text": "...",
    "body_texts": ["..."],
    "cta_text": "...",
    "keyword": "...",
    "image_vibe_needed": "...",
    "notes": "..."
  }}
}}
Solo el JSON, sin texto adicional.
"""
        response = gemini.generate(prompt, SYSTEM_PROMPT)
        return self._parse_json(response)

    def _parse_json(self, response: str) -> list:
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
                return [data.get("proposal_1", {}), data.get("proposal_2", {})]
            except Exception:
                pass
        return [{"raw": response}, {}]

    def apply_feedback(self, brand: str, feedback: str, approved_proposal: dict):
        """Learn from client feedback to improve future proposals."""
        if approved_proposal.get("hook_text"):
            update_memory(brand, {"preferred_hooks": approved_proposal["hook_text"]})
        if feedback:
            update_memory(brand, {
                "tone_preferences": feedback,
                "changes_log": {
                    "agent": "story_copy",
                    "feedback": feedback,
                    "timestamp": datetime.now().isoformat(),
                }
            })


story_copy_agent = StoryCopyAgent()
