from core.gemini_client import gemini
import json
import os
from datetime import datetime

SYSTEM_PROMPT = """Eres el Agente de Guion de RIMA. Escribes guiones de Reels de Instagram
para negocios de servicios en LATAM, adaptados a la voz y estilo del cliente.

Estructura obligatoria de todo guion (30-60 segundos):
ATENCIÓN → PROBLEMA → SOLUCIÓN → PRUEBA SOCIAL → CTA

Reglas de escritura:
- Lenguaje claro y directo, como si le hablaras a alguien de 16 años — sin tecnicismos
- Un solo concepto central por guion — no mezcles ideas
- El hook debe ser agresivo o incómodo: rompe el patrón de scroll
- La prueba social: UN número concreto y tangible en una sola oración
- El CTA siempre tiene un entregable específico + palabra clave para DM
- Tono emocional, verdad incómoda — NUNCA frase motivacional genérica
- Ritmo ágil: frases cortas, impacto inmediato
- Formato teleprompter: cada idea en línea separada, con [PAUSA] donde corresponde
- Escribe en español LATAM usando el tono y jerga del cliente cuando se especifique"""


class ScriptAgent:
    def __init__(self):
        self.name = "script"

    def run(self, idea: dict, brand_brief: dict, tone_notes: str = "") -> dict:
        """
        idea: dict con {hook, development, cta, content_type, format}
        brand_brief: dict estándar del negocio
        tone_notes: texto libre con palabras, muletillas, jerga del cliente
        """
        business_name = brand_brief.get("business_name", "unknown")

        script_a = self._generate_script(idea, brand_brief, tone_notes, variant="A")
        script_b = self._generate_script(idea, brand_brief, tone_notes, variant="B")

        result = {
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "brand": business_name,
            "idea": idea,
            "script_principal": script_a,
            "script_variante_b": script_b,
            "estimated_duration": "30-45 segundos",
            "recording_tips": self._get_recording_tips(idea.get("format", "")),
        }
        self._save(result, business_name)
        return result

    def _generate_script(self, idea: dict, brand_brief: dict, tone_notes: str, variant: str) -> str:
        variant_instruction = ""
        if variant == "B":
            variant_instruction = """
IMPORTANTE: Esta es la VARIANTE B del mismo guion.
Mantén el mismo ángulo y mensaje central, pero:
- Cambia el hook completamente (usa un estilo diferente: si la A era pregunta, la B es afirmación, etc.)
- Cambia el formato narrativo (si la A era directo a cámara, la B puede ser storytelling)
- El CTA puede variar ligeramente en la llamada a la acción
"""

        prompt = f"""
Escribe el guion completo para este Reel de Instagram:

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
RESULTADO PRINCIPAL: {brand_brief.get('main_result')}
PRECIO: {brand_brief.get('price')}
CASOS DE ÉXITO: {brand_brief.get('success_cases', 'No especificados')}

IDEA APROBADA:
- Hook base: {idea.get('hook', '')}
- Desarrollo: {idea.get('development', '')}
- CTA base: {idea.get('cta', '')}
- Tipo de contenido: {idea.get('content_type', 'Problema')}
- Formato de producción: {idea.get('format', 'Talking head')}

VOZ Y TONO DEL CLIENTE:
{tone_notes or "Español LATAM natural, directo y conversacional"}

{variant_instruction}

Entrega el guion en este formato exacto:

---
## VARIANTE {variant}

### GANCHO (3 segundos)
[texto exacto — debe ser agresivo o disruptivo]

### PROBLEMA (10-15 segundos)
[texto exacto línea por línea]
[PAUSA]
[continuación]

### SOLUCIÓN (10-15 segundos)
[texto exacto — muestra que el cliente tiene la respuesta, no la da completa]

### PRUEBA SOCIAL (5 segundos)
[UN resultado concreto con número — una sola oración]

### CTA (5-8 segundos)
[entregable específico + palabra clave]

---
### INDICACIONES DE GRABACIÓN
- Energía:
- Encuadre:
- Elemento visual del hook:
- Duración estimada:
---
"""
        return gemini.generate(prompt, SYSTEM_PROMPT)

    def _get_recording_tips(self, format_type: str) -> dict:
        tips = {
            "talking_head": {
                "setup": "Cara llena en pantalla, luz natural de frente o ring light, fondo limpio",
                "energy": "Alta — empezar hablando desde el primer frame sin silencio inicial",
                "framing": "Encuadre medio, de hombros hacia arriba, cámara a la altura de los ojos",
            },
            "selfie": {
                "setup": "Teléfono en mano, entorno natural del día a día",
                "energy": "Casual pero directo — como si le hablaras a un amigo",
                "framing": "POV — cámara frontal, ligeramente hacia arriba",
            },
            "broll": {
                "setup": "Video de fondo relacionado al nicho, texto en pantalla como hook principal",
                "energy": "Voz en off clara y contundente",
                "framing": "Texto ocupa los primeros 2-3 segundos, luego aparece el contenido",
            },
            "default": {
                "setup": "Luz natural o ring light, fondo limpio o relevante al nicho",
                "energy": "Alta energía desde el primer segundo — el silencio inicial mata el reel",
                "framing": "Adaptar al formato elegido",
            },
        }
        return tips.get(format_type.lower().replace(" ", "_"), tips["default"])

    def _save(self, result: dict, business_name: str):
        os.makedirs("logs/scripts", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logs/scripts/{business_name}_{ts}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)


script_agent = ScriptAgent()
