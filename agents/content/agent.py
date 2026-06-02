from core.gemini_client import gemini
from core.brand_knowledge import CONTENIDO
import json
import os
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente de Contenido de RIMA. Generas planes de contenido,
guiones de Reels y copy de posts para Instagram en negocios de servicios en LATAM.

Usas esta metodología probada:

=== METODOLOGÍA CONTENIDO ===
{CONTENIDO[:4000]}

Reglas:
- Creas contenido que convierte: cada pieza tiene un objetivo claro (atraer, nutrir o vender)
- Los guiones de Reels siguen el gancho de 3 segundos + desarrollo + CTA
- El copy usa el lenguaje del cliente ideal, no jerga técnica
- Escribes en español LATAM
- Priorizas video sobre imagen"""

class ContentAgent:
    def __init__(self):
        self.name = "content"

    def run(self, brand_brief: dict) -> dict:
        prompt = f"""
Genera un plan de contenido para 1 semana (5 Reels + 2 carruseles) para este negocio:

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
PROBLEMA QUE RESUELVE: {brand_brief.get('problem')}
RESULTADO PRINCIPAL: {brand_brief.get('main_result')}
PRECIO: {brand_brief.get('price')}

Entrega en este formato para cada pieza:

## REEL 1 / REEL 2 / ... / CARRUSEL 1 / CARRUSEL 2
- Gancho (primeros 3 segundos)
- Desarrollo (qué mostrar/decir)
- CTA
- Hashtags (10 relevantes)
- Mejor horario de publicación
"""
        response = gemini.generate(prompt, SYSTEM_PROMPT)
        result = {
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "brand": brand_brief.get("business_name"),
            "output": response,
        }
        self._save(result, brand_brief.get("business_name", "unknown"))
        return result

    def _save(self, result: dict, business_name: str):
        os.makedirs("logs/content", exist_ok=True)
        filename = f"logs/content/{business_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

content_agent = ContentAgent()
