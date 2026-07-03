"""Descubrimiento de referentes similares tras ancla del cliente (oferta + refs día 1)."""
from __future__ import annotations

from core.referentes_suggestions import suggest_referentes
from core.referentes_verify import fetch_profile_meta, verify_usernames, _norm_username


def _seed_profiles_from_meta(existing_usernames: list[str], meta: dict[str, dict]) -> list[dict]:
    seeds = []
    for raw in existing_usernames:
        user = _norm_username(raw)
        if not user or user not in meta:
            continue
        m = meta[user]
        seeds.append({
            "username": user,
            "full_name": m.get("full_name") or user,
            "business_category": m.get("business_category") or "",
            "followers": m.get("followers") or 0,
            "biography": m.get("biography") or "",
        })
    return seeds


def discover_similar_referentes(
    brand: dict,
    existing_usernames: list[str],
    limit: int = 4,
) -> list[dict]:
    """
    1. Scrapea perfiles que el cliente ya ingresó (ancla de nicho).
    2. Gemini sugiere perfiles similares según oferta + seeds scrapeados.
    3. Apify verifica que existan en Instagram.
    """
    cleaned = list(dict.fromkeys(_norm_username(u) for u in existing_usernames if u))
    if not cleaned:
        return []

    meta = fetch_profile_meta(cleaned)
    seeds = _seed_profiles_from_meta(cleaned, meta)
    if not seeds:
        return []

    exclude = set(cleaned)
    own = _norm_username(brand.get("brand_ig") or brand.get("ig_username") or "")
    if own:
        exclude.add(own)

    raw = suggest_referentes(
        brand,
        limit=max(limit + 2, 6),
        seed_profiles=seeds,
        exclude_usernames=exclude,
    )
    if not raw:
        return []

    by_user = {s["username"]: s for s in raw}
    verified = verify_usernames(list(by_user.keys()))
    out = []
    for v in verified:
        if v["username"] in exclude:
            continue
        sug = by_user.get(v["username"], {})
        out.append({
            **v,
            "nombre_nicho": sug.get("nombre_nicho") or v.get("full_name") or v["username"],
            "motivo": sug.get("motivo") or "Perfil similar a tus referentes y tu oferta.",
        })
        if len(out) >= limit:
            break
    return out
