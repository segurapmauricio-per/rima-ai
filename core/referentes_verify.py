"""Verificación de perfiles referentes vía Apify (instagram-profile-scraper)."""
from __future__ import annotations

import json
import os
import re
import urllib.request

ACTOR_PROFILE = "apify~instagram-profile-scraper"
_USERNAME_RE = re.compile(r"^[a-z0-9._]{2,30}$")


def _apify_token() -> str:
    return os.getenv("APIFY_API_TOKEN", "").strip()


def _norm_username(raw: str) -> str:
    u = (raw or "").strip().lstrip("@").lower()
    return u if _USERNAME_RE.match(u) else ""


def _apify_run(actor_input: dict, limit: int = 20, actor_id: str = ACTOR_PROFILE) -> list:
    token = _apify_token()
    if not token:
        return []
    url = (
        f"https://api.apify.com/v2/acts/{actor_id}/runs"
        f"?token={token}&waitForFinish=120"
    )
    payload = json.dumps(actor_input).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=150) as resp:
        run_data = json.loads(resp.read()).get("data", {})

    dataset_id = run_data.get("defaultDatasetId", "")
    if not dataset_id:
        return []

    items_url = (
        f"https://api.apify.com/v2/datasets/{dataset_id}/items"
        f"?token={token}&limit={limit}"
    )
    with urllib.request.urlopen(items_url, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_profile_meta(usernames: list[str]) -> dict[str, dict]:
    """Foto, nombre y URL — un run de instagram-profile-scraper."""
    cleaned = list(dict.fromkeys(_norm_username(u) for u in usernames if u))
    if not cleaned or not _apify_token():
        return {}
    try:
        items = _apify_run({"usernames": cleaned}, limit=len(cleaned) + 5)
    except Exception as e:
        print(f"[referentes_verify] apify error: {e}")
        return {}
    out: dict[str, dict] = {}
    for item in items:
        user = _norm_username(item.get("username") or "")
        if not user:
            continue
        fc = item.get("followersCount") or item.get("followers") or 0
        pic = item.get("profilePicUrlHD") or item.get("profilePicUrl") or ""
        full_name = (item.get("fullName") or "").strip()
        # apify~instagram-profile-scraper devuelve un item "vacío" (0 seguidores,
        # sin nombre) para usernames que NO existen en vez de omitirlos — sin este
        # filtro, verify_usernames() los cuenta como perfiles reales verificados.
        if not fc and not full_name:
            continue
        out[user] = {
            "followers": int(fc) if fc else 0,
            "profile_pic_url": pic,
            "profile_url": item.get("url") or f"https://www.instagram.com/{user}/",
            "full_name": full_name,
            "business_category": (
                item.get("businessCategoryName") or item.get("category") or ""
            ).strip(),
            "biography": (item.get("biography") or "").strip(),
        }
    return out


def verify_usernames(usernames: list[str]) -> list[dict]:
    """Devuelve solo perfiles que existen en Instagram (verificados por Apify)."""
    meta = fetch_profile_meta(usernames)
    out = []
    for user in usernames:
        u = _norm_username(user)
        if not u or u not in meta:
            continue
        m = meta[u]
        out.append({
            "username": u,
            "full_name": m.get("full_name") or u,
            "nombre_nicho": m.get("full_name") or u,
            "profile_pic_url": m.get("profile_pic_url") or "",
            "profile_url": m.get("profile_url") or f"https://www.instagram.com/{u}/",
            "followers": m.get("followers") or 0,
        })
    return out


def suggest_verified_referentes(
    brand: dict,
    existing_usernames: list[str] | None = None,
    limit: int = 4,
) -> list[dict]:
    """Alias: descubrimiento anclado en referentes del cliente."""
    from core.referentes_discovery import discover_similar_referentes
    return discover_similar_referentes(brand, existing_usernames or [], limit=limit)
