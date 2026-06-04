from core.gemini_client import gemini
from core.brand_knowledge import CONTENIDO
import json
import os
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente de Contenido de RIMA. Generas calendarios mensuales de contenido
y propuestas de ideas de Reels para negocios de servicios en LATAM.

Metodología que usas:

=== METODOLOGÍA CONTENIDO ===
{CONTENIDO[:5000]}

Reglas de generación:
- El calendario es para 4 semanas: 5 reels/semana = 20 reels + stories calendar
- Distribución de tipos: 50% Problema, 30% Solución/Resultado, 15% Proceso, 5% Mentalidad
- Por cada reel generas 3 ideas distintas con el mismo tipo/día — el cliente elige una
- Los hooks son agresivos, directos, que rompan el scroll
- El CTA siempre tiene un entregable concreto + palabra clave
- Hablas SIEMPRE un nivel por encima del cliente objetivo (regla 80/20)
- Escribe en español LATAM"""

CONTENT_TYPES = ["Problema", "Problema", "Solución", "Resultado", "Mentalidad"]
DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

STORIES_TEMPLATE = {
    "Lunes": "CTA informativo (presentar el programa/servicio)",
    "Martes": "Hand Raiser (lead magnet — 'Respondé [palabra] y te mando [recurso]')",
    "Miércoles": "Hand Raiser (segundo lead magnet de la semana)",
    "Jueves": "Libre / Awareness — victorias de clientes",
    "Viernes": "CTA informativo + urgencia suave",
    "Sábado": "Hand Raiser (lead magnet del fin de semana)",
    "Domingo": "Encuesta (Poll) + Cajita de preguntas (Q&A)",
}


class ContentAgent:
    def __init__(self):
        self.name = "content"

    def run(self, brand_brief: dict, market_research: str = None, month: str = None) -> dict:
        """
        brand_brief: dict estándar del negocio
        market_research: texto del análisis de referentes (opcional)
        month: mes objetivo ej "Julio 2025" (opcional, usa el actual si no se especifica)
        """
        business_name = brand_brief.get("business_name", "unknown")
        target_month = month or datetime.now().strftime("%B %Y")

        # Generate monthly calendar with ideas
        calendar = self._generate_monthly_calendar(brand_brief, market_research, target_month)

        # Generate stories calendar
        stories = self._generate_stories_calendar(brand_brief, market_research)

        result = {
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "brand": business_name,
            "month": target_month,
            "total_reels": 20,
            "calendar": calendar,
            "stories_calendar": stories,
            "used_market_research": bool(market_research),
        }
        self._save(result, business_name, target_month)
        return result

    def _generate_monthly_calendar(self, brand_brief: dict, market_research: str, month: str) -> list:
        """Generates 20 reel slots, each with 3 ideas. Returns list of slot dicts."""

        research_context = ""
        if market_research:
            research_context = f"""
ANÁLISIS DE REFERENTES DEL NICHO (úsalo como inspiración):
{market_research[:3000]}
"""

        prompt = f"""
Genera el calendario mensual completo de contenido para {month}.

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
PROBLEMA QUE RESUELVE: {brand_brief.get('problem')}
RESULTADO PRINCIPAL: {brand_brief.get('main_result')}
PRECIO: {brand_brief.get('price')}
CASOS DE ÉXITO: {brand_brief.get('success_cases', '')}

{research_context}

ESTRUCTURA DEL CALENDARIO:
- 4 semanas × 5 reels por semana = 20 reels en total
- Distribución OBLIGATORIA de tipos de contenido:
  * Lunes: Problema (50% del total)
  * Martes: Problema
  * Miércoles: Solución
  * Jueves: Resultado de cliente / Prueba social
  * Viernes: Mentalidad o Proceso

PARA CADA UNO DE LOS 20 REELS, entrega EXACTAMENTE 3 IDEAS en este formato JSON:

{{
  "semana": 1,
  "dia": "Lunes",
  "tipo": "Problema",
  "ideas": [
    {{
      "titulo": "título corto de la idea",
      "hook": "texto exacto del gancho (primeros 3 segundos)",
      "development": "qué decir/mostrar en el desarrollo (2-3 oraciones)",
      "cta": "CTA concreto con entregable + palabra clave",
      "format": "Talking head / B-roll con texto / Selfie / Clip de podcast",
      "why_works": "por qué este ángulo funciona para este nicho (1 línea)"
    }},
    {{ idea 2 }},
    {{ idea 3 }}
  ]
}}

Entrega los 20 slots como un array JSON válido. Solo el JSON, sin texto adicional antes ni después.
Ejemplo de estructura:
[
  {{ semana 1, lunes, tipo Problema, 3 ideas }},
  {{ semana 1, martes, tipo Problema, 3 ideas }},
  ...
  {{ semana 4, viernes, tipo Mentalidad, 3 ideas }}
]
"""
        response = gemini.generate(prompt, SYSTEM_PROMPT)

        # Parse JSON response
        calendar = self._parse_calendar_json(response)
        return calendar

    def _parse_calendar_json(self, response: str) -> list:
        """Extract and parse JSON from Gemini response."""
        # Try to extract JSON array from response
        text = response.strip()

        # Find the first [ and last ]
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            json_str = text[start:end + 1]
            try:
                parsed = json.loads(json_str)
                # Add approval_status to each idea
                for slot in parsed:
                    for idea in slot.get("ideas", []):
                        idea["approval_status"] = "pending"
                return parsed
            except json.JSONDecodeError:
                pass

        # Fallback: return raw text wrapped in a single slot
        return [{
            "semana": 1,
            "dia": "Mes completo",
            "tipo": "Mixto",
            "ideas": [{
                "titulo": "Ver contenido generado",
                "hook": "Ver respuesta",
                "development": response,
                "cta": "",
                "format": "",
                "why_works": "",
                "approval_status": "pending",
            }]
        }]

    def _generate_stories_calendar(self, brand_brief: dict, market_research: str) -> dict:
        views = brand_brief.get("ig_avg_views", 0)
        try:
            views_int = int(str(views).replace(",", "").replace(".", ""))
        except (ValueError, TypeError):
            views_int = 0

        if views_int < 3000:
            template = {
                "Lunes": "Hand Raiser (3 por semana — sin CTAs de venta aún)",
                "Martes": "Awareness / Victorias de clientes",
                "Miércoles": "Hand Raiser",
                "Jueves": "Awareness / Victorias de clientes",
                "Viernes": "Hand Raiser",
                "Sábado": "Awareness / Victorias de clientes",
                "Domingo": "Awareness / Victorias de clientes",
                "_note": "Menos de 3K views: solo Hand Raisers y Awareness, sin CTAs de venta directa",
            }
        else:
            template = {
                "Lunes": "Awareness / Victorias + CTA informativo",
                "Martes": "Hand Raiser (lead magnet)",
                "Miércoles": "Libre o Awareness",
                "Jueves": "Hand Raiser (lead magnet)",
                "Viernes": "Awareness / Victorias + CTA informativo",
                "Sábado": "Libre o Awareness",
                "Domingo": "Hand Raiser",
                "_note": "Más de 3K views: 2 CTAs por semana + Hand Raisers regulares",
            }

        return {
            "weekly_template": template,
            "daily_non_negotiable": "6-8 historias documentando el día a día (no venta, humanización)",
        }

    def _save(self, result: dict, business_name: str, month: str):
        os.makedirs("logs/content", exist_ok=True)
        month_slug = month.replace(" ", "_").lower()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logs/content/{business_name}_{month_slug}_{ts}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)


content_agent = ContentAgent()
