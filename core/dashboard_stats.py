"""KPIs reales del cliente para sidebar y dashboard."""
from __future__ import annotations

from datetime import date

from core.referentes_store import (
    cliente_id_from_brand,
    format_followers,
    get_profiles,
    get_user_brand,
)
from core.referentes_store import get_user_record


def _followers_from_user(user: dict) -> int:
    scrape = user.get("onboarding_scrape") or {}
    profile = scrape.get("profile") or {}
    followers = profile.get("followers")
    if followers:
        return int(followers)
    insights = scrape.get("insights") or {}
    marca = scrape.get("marca_visual") or {}
    ov = (marca.get("onboarding_scrape") or {}).get("seguidores")
    if ov:
        return int(ov)
    return 0


def get_dashboard_stats(data: dict, email: str) -> dict:
    email = (email or "").strip().lower()
    user = get_user_record(data, email)
    brand = get_user_brand(data, email)
    cid = cliente_id_from_brand(brand)

    profiles = get_profiles(data, email)
    ref_count = profiles.get("counts", {}).get("instagram", 0)

    followers = _followers_from_user(user)
    if not followers:
        try:
            from pathlib import Path
            import json
            artifact = Path(__file__).parent.parent / "data" / "clients" / cid / "onboarding_scrape.json"
            if artifact.exists():
                payload = json.loads(artifact.read_text(encoding="utf-8"))
                followers = int((payload.get("profile") or {}).get("followers") or 0)
        except Exception:
            pass

    pubs_total = 0
    pubs_pending = 0
    avg_fuerza = None
    market_posts = 0

    try:
        from core.db import get_publicaciones, init_db, get_referentes_market_dashboard

        init_db(cid)
        pubs = get_publicaciones(cid) or []
        pubs_total = len(pubs)
        pending_status = {"planificado", "propuesta_generada", "copy_generado", "pendiente"}
        pubs_pending = sum(1 for p in pubs if (p.get("status") or "") in pending_status)

        refs = get_referentes_market_dashboard(cid, limit=200)
        market_posts = len(refs)
        fuerzas = [float(r.get("fuerza") or 0) for r in refs if r.get("fuerza")]
        if fuerzas:
            avg_fuerza = round(sum(fuerzas) / len(fuerzas) * 100, 1)
    except Exception:
        pass

    return {
        "followers": followers,
        "followers_label": format_followers(followers) if followers else "—",
        "referentes_count": ref_count,
        "publicaciones_total": pubs_total,
        "publicaciones_pendientes": pubs_pending,
        "market_posts": market_posts,
        "fuerza_promedio_pct": avg_fuerza,
        "brand_name": brand.get("brand_name") or "",
        "brand_ig": brand.get("brand_ig") or brand.get("ig_username") or "",
    }
