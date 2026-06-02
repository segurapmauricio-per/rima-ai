from core.gemini_client import gemini
from core.brand_knowledge import OPERACIONES
import json
import os
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente de Operaciones de RIMA. Generas SOPs, checklists
y sistemas operativos para escalar negocios de servicios en LATAM sin trabajar más horas.

Usas esta metodología probada:

=== METODOLOGÍA OPERACIONES ===
{OPERACIONES[:4000]}

Reglas:
- Los sistemas deben ser simples y delegables desde el día 1
- Cada SOP tiene un responsable, frecuencia y resultado esperado
- Priorizas automatización sobre contratación cuando es posible
- Los checklists son accionables: verbo + objeto + estándar
- Escribes en español LATAM"""

class OperationsAgent:
    def __init__(self):
        self.name = "operations"

    def run(self, brand_brief: dict) -> dict:
        prompt = f"""
Genera un sistema operativo completo para escalar este negocio:

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
RESULTADO PRINCIPAL: {brand_brief.get('main_result')}
PRECIO: {brand_brief.get('price')}

Entrega en este formato:

## SISTEMA SEMANAL (rutina de 5 días)
Por día: actividades de marketing, ventas y entrega de servicio

## SOPs CLAVE
SOP 1: Onboarding de cliente nuevo
SOP 2: Publicación de contenido semanal
SOP 3: Seguimiento de prospectos
SOP 4: Entrega del servicio / sesiones

## MÉTRICAS A MONITOREAR (tablero semanal)
KPI | Meta semanal | Cómo medirlo

## HERRAMIENTAS RECOMENDADAS
Por área: marketing / ventas / entrega / finanzas

## PRIMEROS 3 SISTEMAS A DELEGAR
Con perfil del asistente ideal para cada uno
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
        os.makedirs("logs/operations", exist_ok=True)
        filename = f"logs/operations/{business_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

operations_agent = OperationsAgent()
