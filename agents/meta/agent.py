from core.gemini_client import gemini
from core.brand_knowledge import META_ADS
import json
import os
from datetime import datetime

SYSTEM_PROMPT = f"""Eres el Agente META Ads de RIMA. Generas copy de anuncios para
Facebook e Instagram Ads para negocios de servicios en LATAM.

Usas esta metodología probada:

=== METODOLOGÍA META ADS ===
{META_ADS[:4000]}

Reglas:
- Siempre creas sets completos: TOFU (frío), MOFU (tibio), BOFU (retargeting)
- Cada anuncio tiene headline, copy principal, CTA y descripción
- El copy de TOFU interrumpe con dolor o curiosidad — sin mencionar precio
- El BOFU usa urgencia, prueba social y oferta directa
- Escribes en español LATAM
- Los textos son concisos y directos — menos es más en Meta"""

class MetaAgent:
    def __init__(self):
        self.name = "meta"

    def run(self, brand_brief: dict) -> dict:
        prompt = f"""
Genera un set completo de anuncios META Ads para este negocio:

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
PROBLEMA QUE RESUELVE: {brand_brief.get('problem')}
RESULTADO PRINCIPAL: {brand_brief.get('main_result')}
PRECIO: {brand_brief.get('price')}
GARANTÍA: {brand_brief.get('guarantee', 'No especificada')}

Entrega en este formato:

## TOFU — 3 anuncios (audiencia fría)
Para cada uno: Headline | Copy | CTA | Descripción

## MOFU — 2 anuncios (seguidores y leads)
Para cada uno: Headline | Copy | CTA | Descripción

## BOFU — 2 anuncios (retargeting caliente)
Para cada uno: Headline | Copy | CTA | Descripción

## AUDIENCIAS SUGERIDAS (intereses, lookalikes)
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
        os.makedirs("logs/meta", exist_ok=True)
        filename = f"logs/meta/{business_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

meta_agent = MetaAgent()
