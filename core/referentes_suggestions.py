"""Sugerencia de perfiles referentes del nicho vía Gemini."""
from __future__ import annotations

import json
import re

from core.gemini_client import gemini

SUGGEST_SYSTEM = """Sugerís perfiles de Instagram en LATAM que un negocio puede modelar para contenido.
Solo usernames reales y plausibles del nicho (sin inventar cuentas genéricas tipo @coach123).
Si no conocés cuentas concretas, devolvé lista vacía en "sugerencias".
Responde SOLO JSON válido en español."""

_USERNAME_RE = re.compile(r"^[a-z0-9._]{2,30}$")


def _norm_username(raw: str) -> str:
    u = (raw or "").strip().lstrip("@").lower()
    return u if _USERNAME_RE.match(u) else ""


def suggest_referentes(
    brand: dict,
    limit: int = 4,
    seed_profiles: list[dict] | None = None,
    exclude_usernames: set[str] | None = None,
) -> list[dict]:
    service = brand.get("brand_service") or brand.get("service") or ""
    ideal = brand.get("brand_ideal_client") or brand.get("ideal_client") or ""
    problem = brand.get("brand_problem") or brand.get("problem") or ""
    result = brand.get("brand_result") or brand.get("result") or ""
    ig = brand.get("brand_ig") or brand.get("ig_username") or ""
    name = brand.get("brand_name") or brand.get("business_name") or ""

    seeds_block = ""
    if seed_profiles:
        lines = []
        for s in seed_profiles:
            user = s.get("username") or "?"
            lines.append(
                f"- @{user}: {s.get('full_name') or user} | "
                f"categoría: {s.get('business_category') or '—'} | "
                f"seguidores: {s.get('followers') or 0} | "
                f"bio: {(s.get('biography') or '')[:220]}"
            )
        seeds_block = (
            "\nREFERENTES QUE EL CLIENTE YA ELIGIÓ (perfiles reales — buscá cuentas SIMILARES, "
            "mismo tipo de oferta/audiencia, no repetir estos @):\n"
            + "\n".join(lines)
            + "\n"
        )

    prompt = f"""Sugerí hasta {limit} perfiles de Instagram ADICIONALES para modelar contenido.

NEGOCIO: {name}
IG PROPIO: {ig}
SERVICIO/OFERTA: {service[:400]}
CLIENTE IDEAL: {ideal[:300]}
PROBLEMA QUE RESUELVE: {problem[:300]}
RESULTADO PRINCIPAL: {result[:200]}
{seeds_block}
Criterios: alineados a la oferta del cliente y similares a sus referentes ya elegidos;
mismo nicho o nicho adyacente; buen contenido educativo/ventas en español LATAM;
cuentas medianas (no solo celebridades). No repitas referentes ya elegidos ni el @ del negocio.

JSON:
{{
  "sugerencias": [
    {{
      "username": "sin_arroba",
      "nombre_nicho": "Nombre visible · nicho",
      "motivo": "por qué es buen referente (1 línea)"
    }}
  ]
}}"""

    try:
        raw = gemini.generate_json(prompt, system_prompt=SUGGEST_SYSTEM)
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        own = _norm_username(ig)
        blocked = set(exclude_usernames or ())
        blocked.add(own)
        out = []
        seen = set()
        for item in (data.get("sugerencias") or [])[:limit + 4]:
            if not isinstance(item, dict):
                continue
            user = _norm_username(item.get("username", ""))
            if not user or user in blocked or user in seen:
                continue
            seen.add(user)
            out.append({
                "username": user,
                "nombre_nicho": (item.get("nombre_nicho") or user)[:120],
                "motivo": (item.get("motivo") or "")[:200],
            })
            if len(out) >= limit:
                break
        return out
    except Exception as e:
        print(f"[referentes_suggestions] error: {e}")
        return []
