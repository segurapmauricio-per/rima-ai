"""
Story Copy Agent
Genera 2 propuestas de copy para secuencias de historias Instagram (3-5 slides, 9:16).

Metodología: hook en frame 1 → valor → CTA (Santiago Muñoz / Nico Azero).
Temática y enfoque vienen fijados del calendario mensual — no se modifican.
"""
from core.gemini_client import gemini
from core.brand_knowledge import K_STORY_COPY
from core.client_store import load_memory, update_memory
from core.weekly_helpers import format_slot_context_for_copy
from core.marca_visual import (
    contexto_marca_para_copy,
    idioma_cliente,
    idioma_cliente_label,
    merge_style_guide_from_marca,
)
import json
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente de Copy de Historias de RIMA.
Escribís secuencias de historias de Instagram (3 a 5 slides, formato 9:16) para negocios de servicios.

Base de conocimiento:
{K_STORY_COPY}

Reglas:
- Secuencia de 3 a 5 slides según el tipo de historia (Hand Raiser: 3-4, CTA: 4-5, awareness: 3-4)
- Slide 1 = GANCHO: el hook arranca en el primer frame, sin silencio previo
- Slides intermedios = VALOR: tips, insight, desarrollo breve (1 idea por slide)
- Último slide = CTA o cierre (pregunta abierta si Hand Raiser, palabra clave si CTA)
- main_text = texto principal visible (máx 2-3 líneas cortas por slide)
- secondary_text = complemento, takeaway o instrucción (opcional)
- Marcá 1-2 palabras clave por slide con **asteriscos dobles** — el diseño las resalta con recuadro de color
- Podés usar MAYÚSCULAS en 1 palabra impactante por slide (se pinta en color acento)
- visual_suggestion DETALLADA para elegir/generar foto (escena, luz, encuadre 9:16)
- Temática y enfoque del calendario son FIJOS — adaptá el copy, no cambies el tema
- Copy directo, español LATAM natural (salvo idioma del cliente indicado)
- Generá EXACTAMENTE 2 propuestas con ángulos distintos (tono, gancho o estructura)"""


class StoryCopyAgent:
    def __init__(self):
        self.name = "story_copy"

    def run(self, story_slot: dict, brand_brief: dict, brand: str,
            market_research: str = "", marca: dict = None) -> dict:
        memory = load_memory(brand)
        proposals = self._generate_proposals(
            story_slot, brand_brief, memory, market_research, marca=marca,
        )

        return {
            "agent": self.name,
            "brand": brand,
            "story_slot": story_slot,
            "proposals": proposals,
            "status": "pending_approval",
            "changes_remaining": 3,
            "generated_at": datetime.now().isoformat(),
        }

    def _elegir_total_slides(self, slot: dict) -> int:
        story_type = (slot.get("story_type") or slot.get("tematica") or "").lower()
        if "cta" in story_type or "venta" in story_type:
            return 5
        if "hand" in story_type or "raiser" in story_type:
            return 4
        return 4

    def _generate_proposals(self, slot: dict, brief: dict, memory: dict,
                             market_research: str, marca: dict = None) -> list:
        story_type = slot.get("story_type") or slot.get("tematica", "awareness")
        topic = slot.get("topic") or slot.get("tematica", "")
        date = slot.get("date", "")
        total_slides = self._elegir_total_slides(slot)

        tone_notes = "\n".join(memory.get("tone_preferences", [])) or "Natural y cercano"
        disliked = ", ".join(memory.get("disliked_words", [])) or "ninguna"
        preferred_hooks = "\n".join(memory.get("preferred_hooks", [])) or "ninguna preferencia"

        slot_context = format_slot_context_for_copy(slot)
        idioma = idioma_cliente_label(brief, marca)
        idioma_code = idioma_cliente(brief, marca)
        marca_context = contexto_marca_para_copy(marca, brief)

        research_context = ""
        if market_research:
            research_context = f"\n{market_research[:2000]}\n"

        prompt = f"""
Genera 2 propuestas DISTINTAS de copy para una SECUENCIA de historias de Instagram.

NEGOCIO: {brief.get('business_name')}
SERVICIO: {brief.get('service')}
CLIENTE IDEAL: {brief.get('ideal_client')}
RESULTADO PRINCIPAL: {brief.get('main_result')}

{slot_context}

HISTORIA (temática y enfoque FIJOS — no los cambies):
- Fecha: {date}
- Tipo de historia: {story_type}
- Tema: {topic}
- Posición en secuencia semanal: {slot.get('sequence_position', 1)}

ESTRUCTURA OBLIGATORIA: exactamente {total_slides} slides por propuesta.
- Slide 1: role "gancho" — hook en el primer frame
- Slides 2 a {total_slides - 1}: role "desarrollo" — valor, tips o insight
- Slide {total_slides}: role "cierre" — CTA, pregunta abierta o palabra clave

PREFERENCIAS DEL CLIENTE:
- Tono: {tone_notes}
- Palabras a evitar: {disliked}
- Hooks que le gustaron: {preferred_hooks}

IDIOMA DEL CLIENTE (OBLIGATORIO): {idioma}
- TODO el copy visible en {idioma}: main_text, secondary_text, plan_resumen, keyword.

{marca_context}

{research_context}

Propuesta 1 y Propuesta 2 deben diferir en ángulo (gancho, tono o enfoque del valor).

Responde SOLO JSON:
{{
  "proposal_1": {{
    "titulo": "nombre corto del ángulo A",
    "angulo": "descripción del enfoque A",
    "total_slides": {total_slides},
    "plan_resumen": "qué aprende o siente quien ve la secuencia",
    "slides": [
      {{
        "slide_number": 1,
        "role": "gancho",
        "main_text": "hook corto",
        "secondary_text": "",
        "visual_suggestion": "escena concreta 9:16 para foto o IA",
        "sticker_type": "none"
      }}
    ],
    "cta_keyword": "palabra para responder (si aplica)",
    "keyword": "igual que cta_keyword",
    "notes": "indicaciones de entrega"
  }},
  "proposal_2": {{
    "titulo": "...",
    "angulo": "...",
    "total_slides": {total_slides},
    "plan_resumen": "...",
    "slides": [...],
    "cta_keyword": "...",
    "keyword": "...",
    "notes": "..."
  }}
}}
"""
        response = gemini.generate(prompt, SYSTEM_PROMPT)
        return self._parse_json(response, total_slides)

    def _parse_json(self, response: str, total_slides: int) -> list:
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
                out = []
                for key in ("proposal_1", "proposal_2"):
                    prop = data.get(key) or {}
                    prop = self._normalizar_propuesta(prop, total_slides)
                    out.append(prop)
                return out if out else [{"raw": response}, {}]
            except Exception:
                pass
        return [{"raw": response}, {}]

    def _normalizar_propuesta(self, prop: dict, total_slides: int) -> dict:
        slides = prop.get("slides") or []
        if not slides and prop.get("hook_text"):
            slides = self._legacy_a_slides(prop)
        prop["slides"] = self._ajustar_slides(slides, total_slides)
        prop["total_slides"] = len(prop["slides"])
        if not prop.get("keyword") and prop.get("cta_keyword"):
            prop["keyword"] = prop["cta_keyword"]
        hook = prop["slides"][0]["main_text"] if prop["slides"] else ""
        bodies = [s["main_text"] for s in prop["slides"][1:-1] if s.get("main_text")]
        cierre = prop["slides"][-1] if prop["slides"] else {}
        prop.setdefault("hook_text", hook)
        prop.setdefault("body_texts", bodies)
        prop.setdefault("cta_text", cierre.get("main_text", ""))
        return prop

    def _legacy_a_slides(self, prop: dict) -> list:
        slides = []
        if prop.get("hook_text"):
            slides.append({
                "slide_number": 1, "role": "gancho",
                "main_text": prop["hook_text"],
                "secondary_text": "",
                "visual_suggestion": prop.get("image_vibe_needed", ""),
            })
        for i, body in enumerate(prop.get("body_texts") or [], start=2):
            if body:
                slides.append({
                    "slide_number": i, "role": "desarrollo",
                    "main_text": body, "secondary_text": "",
                    "visual_suggestion": prop.get("image_vibe_needed", ""),
                })
        cta = (prop.get("cta_text") or "").strip()
        if cta:
            kw = prop.get("keyword") or prop.get("cta_keyword") or ""
            slides.append({
                "slide_number": len(slides) + 1, "role": "cierre",
                "main_text": cta,
                "secondary_text": f"Comentá: {kw}" if kw else "",
                "visual_suggestion": prop.get("image_vibe_needed", ""),
            })
        return slides

    def _ajustar_slides(self, slides: list, total: int) -> list:
        slides = [dict(s) for s in slides if s.get("main_text")]
        if len(slides) < 3:
            return slides
        if len(slides) > 5:
            slides = slides[:5]
        roles = ["gancho"] + ["desarrollo"] * max(0, len(slides) - 2) + ["cierre"]
        if len(roles) != len(slides):
            roles = (["gancho"] + ["desarrollo"] * (len(slides) - 2)
                     + ["cierre"])[:len(slides)]
        for i, s in enumerate(slides):
            s["slide_number"] = i + 1
            s.setdefault("role", roles[i] if i < len(roles) else "desarrollo")
            s.setdefault("secondary_text", "")
            s.setdefault("visual_suggestion", "")
            s.setdefault("sticker_type", "none")
        return slides

    def apply_feedback(self, brand: str, feedback: str, approved_proposal: dict):
        if approved_proposal.get("hook_text"):
            update_memory(brand, {"preferred_hooks": approved_proposal["hook_text"]})
        elif approved_proposal.get("slides"):
            first = approved_proposal["slides"][0]
            if first.get("main_text"):
                update_memory(brand, {"preferred_hooks": first["main_text"]})
        if feedback:
            update_memory(brand, {
                "tone_preferences": feedback,
                "changes_log": {
                    "agent": "story_copy",
                    "feedback": feedback,
                    "timestamp": datetime.now().isoformat(),
                },
            })


story_copy_agent = StoryCopyAgent()
