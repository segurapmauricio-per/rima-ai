"""
Carousel Copy Agent
Para cada carrusel del calendario semanal:
1. Muestra 2 referentes del nicho (con métricas) para que el cliente elija cuál modelar
2. Una vez aprobado el referente, genera el copy completo del carrusel
   con uno de los 5 formatos probados (estilo skill Claude /carrusel)
"""
from core.gemini_client import gemini
from core.brand_knowledge import K_CAROUSEL_COPY
from core.client_store import load_memory, load_referents_db, update_memory
from core.weekly_helpers import format_slot_context_for_copy
from core.marca_visual import (
    contexto_marca_para_copy,
    idioma_cliente,
    idioma_cliente_label,
    merge_style_guide_from_marca,
)
import json
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente de Copy de Carruseles de RIMA.
Generás propuestas de copy para carruseles de Instagram, modelando referentes exitosos
del nicho y adaptándolos al negocio del cliente.

Base de conocimiento:
{K_CAROUSEL_COPY}

Reglas:
- Objetivo: carruseles que NUTREN — la audiencia debe terminar sintiendo que aprendió algo concreto
- 7 slides (1 gancho + 5 desarrollo con valor + 1 CTA con palabra clave)
- Cada slide de desarrollo enseña algo específico: dato, error común, paso, tip o micro-framework
- Al menos 3 slides deben incluir bullets (2-4 ítems cortos y accionables)
- main_text = titular potente del slide (1 frase); secondary_text = frase complementaria o takeaway
- bullets = listado concreto (tips, pasos, errores, beneficios) — nunca genéricos
- Copy directo, lenguaje claro, verdad incómoda — nunca motivacional vacío
- El slide 1 detiene el scroll; slides 2-6 entregan valor progresivo; slide 7 convierte
- Balance valor/CTA: dar aprendizaje real sin regalar el entregable completo del CTA
- visual_suggestion DETALLADA para IA (fondo, layout de listas si aplica, composición)
- Adaptar al tono y voz del cliente
- IDIOMA: TODO el copy visible (main_text, secondary_text, bullets, CTA, plan_resumen) en el
  idioma del cliente indicado en el prompt — nunca mezclar idiomas salvo nombres propios"""

FORMATOS = {
    "metaphoric": {
        "nombre": "Metafórico cinematográfico",
        "tono": "intenso, disruptivo, aspiracional",
        "estructura": (
            "Slide 1 gancho → slides 2-3 mito vs realidad con bullets → "
            "slide 4-5 tips/pasos accionables en lista → slide 6 resumen insight → slide 7 CTA"
        ),
    },
    "noticia": {
        "nombre": "Noticia urgente",
        "tono": "dramático, creíble, persuasivo",
        "estructura": (
            "Slide 1 titular breaking news → 2 subtítulo → 3 desarrollo noticia → "
            "4 declaración fuerte → 5 consecuencia → 6 solución → 7 CTA"
        ),
    },
    "comic": {
        "nombre": "Cómic narrativo",
        "tono": "humor dramático, diálogos cortos",
        "estructura": (
            "Slide 1 escena + diálogo → 2 problema intensificado → 3 frase dramática → "
            "4 descubrimiento solución → 5 cambio actitud → 6 resultado → 7 CTA"
        ),
    },
    "minimal": {
        "nombre": "Minimalista premium",
        "tono": "seguro, dominante, estratégico",
        "estructura": (
            "Slide 1 confesión impactante → 2 contexto → 3 qué aprendí → "
            "4 qué cambió → 5 amateur vs pro → 6 profesionales → 7 CTA elegante"
        ),
    },
    "recursos": {
        "nombre": "Recursos ocultos",
        "tono": "curiosidad extrema, genera DMs",
        "estructura": (
            "Slide 1 gancho curiosidad → slides 2-5 recursos/prompts descritos sin "
            "revelar del todo → slide 6 teaser → slide 7 CTA comentá palabra"
        ),
    },
}

SLIDE_ARQUETIPOS = [
    ("gancho", "Slide 1 — GANCHO: pregunta incómoda o afirmación polarizante. main_text potente, secondary_text opcional (contexto). bullets vacío."),
    ("mito", "Slide 2 — MITO/ERROR: desmontá una creencia falsa del nicho. main_text = el mito, bullets = 2-3 razones por las que está mal, secondary_text = takeaway."),
    ("consecuencia", "Slide 3 — CONSECUENCIA o CONTRASTE: qué pasa si no actuás vs qué cambia si actuás. bullets = lista antes/después o costos ocultos."),
    ("metodo", "Slide 4 — MÉTODO/TIPS: enseñá 3-4 acciones concretas. main_text = promesa del slide, bullets = pasos o tips numerables, secondary_text = por qué funciona."),
    ("profundidad", "Slide 5 — PROFUNDIDAD: dato, framework o truco poco conocido. bullets = desglose en ítems, secondary_text = cómo aplicarlo hoy."),
    ("resumen", "Slide 6 — RESUMEN/INSIGHT: sintetizá lo aprendido. main_text = insight final, bullets opcional (2 puntos clave), secondary_text = frase memorable."),
    ("cta", "Slide 7 — CTA: entregable + palabra clave. main_text = oferta clara, secondary_text = instrucción comentá PALABRA, bullets vacío."),
]

FORMAT_SIGNALS = {
    "noticia": ("urgente", "noticia", "cambio", "tendencia", "2026", "breaking"),
    "comic": ("cómic", "comic", "historia", "frustración", "diálogo", "protagonista"),
    "minimal": ("premium", "autoridad", "profesional", "minimal", "invertí", "confesión"),
    "recursos": ("recursos", "prompts", "herramientas", "lista", "tips", "secretos"),
    "metaphoric": ("mentalidad", "mindset", "metáfora", "transformación", "antes", "después"),
}


class CarouselCopyAgent:
    def __init__(self):
        self.name = "carousel_copy"

    def _elegir_formato(self, slot: dict) -> str:
        texto = " ".join([
            slot.get("topic", ""),
            slot.get("carousel_type", ""),
            slot.get("tematica", ""),
            slot.get("enfoque", ""),
            slot.get("format", ""),
        ]).lower()
        scores = {fid: 0 for fid in FORMATOS}
        for fid, keywords in FORMAT_SIGNALS.items():
            for kw in keywords:
                if kw in texto:
                    scores[fid] += 1
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            ctype = (slot.get("carousel_type") or "").lower()
            if "noticia" in ctype or "urgente" in ctype:
                return "noticia"
            if "recurso" in ctype or "lista" in ctype:
                return "recursos"
            if "historia" in ctype or "comic" in ctype:
                return "comic"
            return "metaphoric"
        return best

    def propose_referents(self, carousel_slot: dict, brand: str, brand_brief: dict) -> dict:
        """
        Step 1: Show 2 top referent carousels for client to choose which to model.
        """
        posts_db = load_referents_db(brand)
        carousels = [
            p for p in posts_db.values()
            if p.get("type", "").lower() in ("sidecar", "carousel", "image")
            and p.get("metrics", {}).get("fuerza", 0) > 0
        ]
        carousels.sort(
            key=lambda p: p.get("metrics", {}).get("score_ventas")
            or p.get("metrics", {}).get("engagement_score", 0),
            reverse=True,
        )

        topic = carousel_slot.get("topic", "")
        carousel_type = carousel_slot.get("carousel_type", "informativo")

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
            referent: dict = None, marca: dict = None) -> dict:
        """
        Step 2: Generate complete carousel copy once client picks a referent.
        """
        memory = load_memory(brand)
        tone_notes = "\n".join(memory.get("tone_preferences", [])) or "Natural y directo"
        disliked = ", ".join(memory.get("disliked_words", [])) or "ninguna"

        formato_id = self._elegir_formato(carousel_slot)
        formato = FORMATOS[formato_id]
        slides, meta = self._generate_slides(
            carousel_slot, brand_brief, referent, tone_notes, disliked,
            formato_id, formato, marca=marca,
        )
        style_guide = merge_style_guide_from_marca(
            meta.get("style_guide") or {}, marca, brand_brief,
        )

        result = {
            "agent": self.name,
            "brand": brand,
            "carousel_slot": carousel_slot,
            "referent_modeled": referent.get("url", "") if referent else None,
            "slides": slides,
            "formato": formato["nombre"],
            "formato_id": formato_id,
            "style_guide": style_guide,
            "idioma": style_guide.get("idioma", "es"),
            "cta_keyword": meta.get("cta_keyword", ""),
            "cta_deliverable": meta.get("cta_deliverable", ""),
            "plan_resumen": meta.get("plan_resumen", ""),
            "valor_audience": meta.get("valor_audience", ""),
            "status": "pending_approval",
            "changes_remaining": 3,
            "generated_at": datetime.now().isoformat(),
        }
        return result

    def _generate_slides(self, slot: dict, brief: dict, referent: dict,
                         tone_notes: str, disliked: str,
                         formato_id: str, formato: dict,
                         marca: dict = None) -> tuple:
        referent_context = ""
        slot_context = format_slot_context_for_copy(slot, referent)
        idioma = idioma_cliente_label(brief, marca)
        idioma_code = idioma_cliente(brief, marca)
        marca_context = contexto_marca_para_copy(marca, brief)
        if referent:
            referent_context = f"""
REFERENTE A MODELAR:
- Cuenta: {referent.get('owner', '')}
- Caption: {referent.get('caption_preview', referent.get('caption', ''))[:300]}
- Métricas: Fuerza {referent.get('fuerza', 0)}, Comentarios {referent.get('comments', 0)}
- URL: {referent.get('url', '')}
- Qué modelar: {referent.get('que_modelar', '')}
- Cómo adaptar: {referent.get('como_adaptar_guion', '')}
Modelá la DINÁMICA (estructura, ritmo, tipo de gancho) — NO el contenido textual.
"""

        arquetipos_txt = "\n".join(f"- {desc}" for _, desc in SLIDE_ARQUETIPOS)

        prompt = f"""
Genera el copy completo para un carrusel de Instagram de EXACTAMENTE 7 slides.
El carrusel debe NUTRIR: quien lo lea debe sentir que aprendió tips, pasos o insights aplicables.

FORMATO ELEGIDO: {formato['nombre']}
Tono: {formato['tono']}
Estructura obligatoria: {formato['estructura']}

ARQUETIPO POR SLIDE (seguí este mapa):
{arquetipos_txt}

NEGOCIO: {brief.get('business_name')}
SERVICIO: {brief.get('service')}
CLIENTE IDEAL: {brief.get('ideal_client')}
RESULTADO: {brief.get('main_result')}
CASOS DE ÉXITO: {brief.get('success_cases', '')}

{slot_context}

CARRUSEL:
- Fecha: {slot.get('date', '')}
- Tipo: {slot.get('carousel_type', 'informativo')}
- Tema: {slot.get('topic', '')}

TONO DEL CLIENTE: {tone_notes}
PALABRAS A EVITAR: {disliked}

IDIOMA DEL CLIENTE (OBLIGATORIO): {idioma}
- Escribí TODO el copy del carrusel en {idioma}: main_text, secondary_text, bullets,
  plan_resumen, valor_audience, cta_keyword (si aplica en ese idioma), cta_deliverable.
- visual_suggestion y notes pueden estar en español técnico para el equipo de diseño.

{marca_context}

{referent_context}

DENSIDAD DE VALOR (obligatorio):
- Slides 2, 3, 4 y 5 DEBEN tener bullets con 2-4 ítems concretos (tips, pasos, errores, datos)
- Cada bullet: máximo 12 palabras, accionable o específico — nada genérico tipo "esforzate más"
- secondary_text: frase complementaria que cierra el slide (takeaway, dato extra o puente al siguiente)
- main_text: titular corto (máx. 15 palabras) — no repitas en bullets lo mismo

Para cada slide, visual_suggestion debe describir layout para IA: si hay bullets, indicá
"lista vertical con íconos/bullets legibles"; fondo, composición y sensación visual.

Responde SOLO con este JSON:
{{
  "format": "{formato['nombre']}",
  "plan_resumen": "una línea del arco narrativo educativo del carrusel",
  "valor_audience": "qué aprende concretamente quien lo lee (1 frase)",
  "style_guide": {{
    "estilo_visual": "descripción coherente con la identidad visual del cliente",
    "tipografia": "tipografía legible en móvil (usar la de marca si está definida)",
    "colores": ["#hex1", "#hex2", "#hex3"],
    "idioma": "{idioma_code}"
  }},
  "slides": [
    {{
      "slide_number": 1,
      "role": "gancho",
      "content_type": "gancho",
      "main_text": "titular potente del slide",
      "secondary_text": "frase complementaria o takeaway (opcional en slide 1)",
      "bullets": [],
      "visual_suggestion": "idea visual detallada para IA incluyendo layout de texto",
      "notes": "indicaciones de diseño"
    }}
  ],
  "cta_keyword": "PALABRA",
  "cta_deliverable": "qué recibe quien comenta la palabra"
}}
Exactamente 7 slides. bullets es array de strings (vacío [] si no aplica).
Slides 2-5: bullets obligatorio con 2-4 ítems.
"""
        try:
            response = gemini.generate_json(prompt, SYSTEM_PROMPT)
        except Exception:
            response = gemini.generate(prompt, SYSTEM_PROMPT)

        slides, meta = self._parse_response(response)
        slides = [self._normalize_slide(s, i) for i, s in enumerate(slides or [])]
        if not slides:
            slides = [{"raw": response}]
        return slides, meta

    def _normalize_slide(self, slide: dict, idx: int) -> dict:
        if not isinstance(slide, dict):
            return slide
        s = dict(slide)
        bullets = s.get("bullets")
        if isinstance(bullets, str):
            bullets = [b.strip() for b in bullets.replace("•", "\n").split("\n") if b.strip()]
        elif not isinstance(bullets, list):
            bullets = []
        s["bullets"] = [str(b).strip() for b in bullets if str(b).strip()][:5]
        if not s.get("content_type"):
            roles = ["gancho", "mito", "consecuencia", "metodo", "profundidad", "resumen", "cta"]
            s["content_type"] = roles[idx] if idx < len(roles) else "desarrollo"
        if not s.get("role"):
            s["role"] = "gancho" if idx == 0 else ("cierre" if idx >= 6 else "desarrollo")
        return s

    def _parse_response(self, response: str) -> tuple:
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end <= start:
            return [], {}
        try:
            data = json.loads(text[start:end])
        except Exception:
            return [], {}
        meta = {
            "style_guide": data.get("style_guide") or {},
            "cta_keyword": data.get("cta_keyword", ""),
            "cta_deliverable": data.get("cta_deliverable", ""),
            "plan_resumen": data.get("plan_resumen", ""),
            "valor_audience": data.get("valor_audience", ""),
            "format": data.get("format", ""),
        }
        return data.get("slides", []), meta

    def _parse_slides(self, response: str) -> list:
        slides, _ = self._parse_response(response)
        return slides

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
