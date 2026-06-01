from core.gemini_client import gemini
from core.brand_knowledge import LANDING, OFERTA, VENTAS
import json
import os
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente Landing de RIMA. Generas landing pages de ventas 
y scripts de VSL para negocios de servicios en LATAM.

Usas esta metodología probada:

=== METODOLOGÍA LANDING ===
{LANDING}

=== METODOLOGÍA OFERTA ===
{OFERTA[:3000]}

Reglas:
- Siempre vendes RESULTADOS, nunca servicios
- La promesa debe ser específica y con tiempo concreto
- El VSL sigue la estructura de 6 partes exactamente
- El copy usa el lenguaje del cliente ideal, no jerga técnica
- Escribes en español LATAM"""

class LandingAgent:
    def __init__(self):
        self.name = "landing"

    def run(self, brand_brief: dict) -> dict:
        prompt = f"""
Genera una landing page completa y script VSL para este negocio:

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
PROBLEMA QUE RESUELVE: {brand_brief.get('problem')}
RESULTADO PRINCIPAL: {brand_brief.get('main_result')}
PRECIO: {brand_brief.get('price')}
CASOS DE ÉXITO: {brand_brief.get('success_cases', 'No especificados')}
GARANTÍA: {brand_brief.get('guarantee', 'No especificada')}

Entrega en este formato:

## HEADLINE
## SUBHEADLINE
## COPY LANDING
## SCRIPT VSL
## BIO INSTAGRAM
## UTMs SUGERIDOS
"""
        response = gemini.generate(prompt, SYSTEM_PROMPT)
        result = {
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "brand": brand_brief.get('business_name'),
            "output": response
        }
        self._save(result, brand_brief.get('business_name', 'unknown'))
        return result

    def _save(self, result: dict, business_name: str):
        os.makedirs("logs/landing", exist_ok=True)
        filename = f"logs/landing/{business_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

landing_agent = LandingAgent()