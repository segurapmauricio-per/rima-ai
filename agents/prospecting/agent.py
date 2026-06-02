from core.gemini_client import gemini
from core.brand_knowledge import PROSPECCION
import json
import os
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente de Prospección de RIMA. Generas estrategias y
scripts de prospección orgánica en Instagram para negocios de servicios en LATAM.

Usas esta metodología probada:

=== METODOLOGÍA PROSPECCIÓN ===
{PROSPECCION[:4000]}

Reglas:
- La prospección es orgánica: sin spam, con valor real
- Los mensajes abren conversación, no venden de entrada
- Identificas señales de compra en el perfil del prospecto
- Los DMs iniciales son breves (máx 3 líneas)
- Escribes en español LATAM"""

class ProspectingAgent:
    def __init__(self):
        self.name = "prospecting"

    def run(self, brand_brief: dict) -> dict:
        prompt = f"""
Genera una estrategia de prospección completa para este negocio:

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
PROBLEMA QUE RESUELVE: {brand_brief.get('problem')}
RESULTADO PRINCIPAL: {brand_brief.get('main_result')}

Entrega en este formato:

## DÓNDE ENCONTRAR PROSPECTOS
Hashtags a monitorear | Perfiles competidores | Grupos/comunidades

## CRITERIOS DE CALIFICACIÓN
Señales en el perfil que indican que es cliente ideal

## SECUENCIA DE DMs (fría)
DM 1 (primer contacto) | DM 2 (seguimiento 48h) | DM 3 (último intento)

## SECUENCIA DE DMs (desde Reel/Story)
Apertura por comentario | Apertura por vista de historia

## RUTINA DIARIA DE PROSPECCIÓN
Actividades y tiempo por actividad (total 45 min/día)
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
        os.makedirs("logs/prospecting", exist_ok=True)
        filename = f"logs/prospecting/{business_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

prospecting_agent = ProspectingAgent()
