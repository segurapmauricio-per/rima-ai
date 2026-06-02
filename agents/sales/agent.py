from core.gemini_client import gemini
from core.brand_knowledge import VENTAS
import json
import os
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente de Ventas de RIMA. Generas scripts de cierre,
respuestas a objeciones y secuencias de DMs para negocios de servicios en LATAM.

Usas esta metodología probada:

=== METODOLOGÍA VENTAS ===
{VENTAS[:4000]}

Reglas:
- Los scripts son conversacionales, no robóticos — suenan humanos
- Cada objeción tiene 3 variantes de respuesta para elegir
- El setting (pre-cierre) separa leads calificados de curiosos
- Nunca revelamos el precio antes de establecer valor
- Escribes en español LATAM"""

class SalesAgent:
    def __init__(self):
        self.name = "sales"

    def run(self, brand_brief: dict) -> dict:
        prompt = f"""
Genera un kit de ventas completo para este negocio:

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
PROBLEMA QUE RESUELVE: {brand_brief.get('problem')}
RESULTADO PRINCIPAL: {brand_brief.get('main_result')}
PRECIO: {brand_brief.get('price')}
GARANTÍA: {brand_brief.get('guarantee', 'No especificada')}

Entrega en este formato:

## SCRIPT DE SETTING (DM para calificar)
Mensaje 1, 2 y 3 en secuencia

## SCRIPT DE LLAMADA DE CIERRE
Apertura | Diagnóstico (preguntas) | Presentación | Cierre

## OBJECIONES FRECUENTES + RESPUESTAS
Objeción 1: "Es muy caro" — 3 respuestas
Objeción 2: "Lo tengo que pensar" — 3 respuestas
Objeción 3: "No tengo tiempo" — 3 respuestas
Objeción 4: "¿Cómo sé que funciona para mí?" — 3 respuestas

## SEGUIMIENTO POST-LLAMADA (no cerró)
Secuencia de 3 mensajes en 7 días
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
        os.makedirs("logs/sales", exist_ok=True)
        filename = f"logs/sales/{business_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

sales_agent = SalesAgent()
