"""
CRUD de perfiles referentes por usuario (Instagram / YouTube) en rima_data.json.
"""
from datetime import datetime
import uuid
from typing import Optional

from core.plan_limits import MANUAL_SCRAPE_CREDITS, get_ref_limits, normalize_plan


def _iso_week_key() -> str:
    return datetime.now().strftime("%G-W%V")


def get_user_record(data: dict, email: str) -> dict:
    return data.setdefault("users", {}).setdefault(email, {})


def get_user_plan(data: dict, email: str) -> str:
    user = data.get("users", {}).get(email, {})
    brand_plan = (user.get("brand") or {}).get("plan")
    return normalize_plan(user.get("plan") or brand_plan or "pro")


def get_user_brand(data: dict, email: str) -> dict:
    user = data.get("users", {}).get(email, {})
    return dict(user.get("brand") or {})


def set_user_brand(data: dict, email: str, brand: dict) -> dict:
    user = get_user_record(data, email)
    existing = dict(user.get("brand") or {})
    existing.update(brand)
    user["brand"] = existing
    return existing


def cliente_id_from_brand(brand: dict) -> str:
    name = brand.get("brand_name") or brand.get("business_name") or "default"
    return name.lower().replace(" ", "_")


def _norm_username(username: str) -> str:
    return (username or "").strip().lstrip("@").lower()


def format_followers(count: int) -> str:
    n = int(count or 0)
    if n >= 1_000_000:
        s = f"{n / 1_000_000:.1f}M"
        return s.replace(".0M", "M")
    if n >= 1_000:
        s = f"{n / 1_000:.1f}K"
        return s.replace(".0K", "K")
    return str(n)


def infer_nicho_from_meta(meta: dict) -> str:
    """Nombre · nicho a partir del perfil IG scrapeado."""
    cat = (meta.get("business_category") or "").strip()
    name = (meta.get("full_name") or "").strip()
    bio = ((meta.get("biography") or "").split("\n")[0] or "").strip()[:60]
    if name and cat:
        return f"{name} · {cat}"
    if cat:
        return cat
    if name and bio:
        return f"{name} · {bio}"
    return name or bio


def sync_ig_profiles_from_meta(data: dict, email: str, meta_by_username: dict) -> int:
    """Actualiza foto, seguidores y nicho en referentes tras un scrape."""
    if not email or not meta_by_username:
        return 0
    user = get_user_record(data, email)
    updated = 0
    for p in _ensure_profiles(user).get("instagram", []):
        key = _norm_username(p.get("username", ""))
        meta = meta_by_username.get(key)
        if not meta:
            continue
        if meta.get("followers"):
            p["seguidores"] = format_followers(meta["followers"])
        if meta.get("profile_pic_url"):
            p["profile_pic_url"] = meta["profile_pic_url"]
        username = p.get("username", "").strip().lstrip("@")
        p["ig_url"] = meta.get("profile_url") or (
            f"https://www.instagram.com/{username}/" if username else ""
        )
        nicho = infer_nicho_from_meta(meta)
        if nicho:
            p["nombre_nicho"] = nicho
        updated += 1
    return updated


def _ensure_profiles(user: dict) -> dict:
    profiles = user.setdefault("referentes_profiles", {})
    profiles.setdefault("instagram", [])
    profiles.setdefault("youtube", [])
    return profiles


def _ensure_scraping(user: dict) -> dict:
    scraping = user.setdefault("scraping", {})
    week = _iso_week_key()
    if scraping.get("last_reset_week") != week:
        scraping["manual_remaining"] = MANUAL_SCRAPE_CREDITS
        scraping["last_reset_week"] = week
    rem = scraping.get("manual_remaining", MANUAL_SCRAPE_CREDITS)
    scraping["manual_remaining"] = min(max(int(rem) if rem is not None else 0, 0), MANUAL_SCRAPE_CREDITS)
    scraping.setdefault("last_reset_week", week)
    scraping.setdefault("last_manual_scrape_at", None)
    return scraping


def _purge_empty_profiles(user: dict) -> bool:
    """Elimina perfiles sin @usuario guardado (borradores huérfanos)."""
    profiles = _ensure_profiles(user)
    changed = False
    for key in ("instagram", "youtube"):
        cleaned = [p for p in profiles[key] if p.get("username", "").strip()]
        if len(cleaned) != len(profiles[key]):
            profiles[key] = cleaned
            changed = True
    return changed


def get_profiles(data: dict, email: str) -> dict:
    user = get_user_record(data, email)
    if _purge_empty_profiles(user):
        pass  # caller debe save_data si persiste
    plan = get_user_plan(data, email)
    limits = get_ref_limits(plan)
    profiles = _ensure_profiles(user)
    scraping = _ensure_scraping(user)
    ig = [p for p in profiles.get("instagram", []) if p.get("username", "").strip()]
    yt = [p for p in profiles.get("youtube", []) if p.get("username", "").strip()]
    return {
        "plan": plan,
        "limits": limits,
        "instagram": ig,
        "youtube": yt,
        "counts": {"instagram": len(ig), "youtube": len(yt)},
        "scraping": {
            "manual_remaining": scraping.get("manual_remaining", MANUAL_SCRAPE_CREDITS),
            "last_reset_week": scraping.get("last_reset_week"),
            "last_manual_scrape_at": scraping.get("last_manual_scrape_at"),
        },
    }


def _platform_list(user: dict, plataforma: str) -> list:
    profiles = _ensure_profiles(user)
    return profiles["instagram" if plataforma == "instagram" else "youtube"]


def add_profile(data: dict, email: str, plataforma: str, payload: dict) -> dict:
    user = get_user_record(data, email)
    plan = get_user_plan(data, email)
    limits = get_ref_limits(plan)
    key = "instagram" if plataforma == "instagram" else "youtube"
    lst = _platform_list(user, plataforma)
    filled = [p for p in lst if p.get("username", "").strip()]
    if len(filled) >= limits[key]:
        raise ValueError(f"Límite de plan alcanzado: máximo {limits[key]} en {plataforma}")

    profile = {
        "id": str(uuid.uuid4()),
        "username": (payload.get("username") or "").strip(),
        "nombre_nicho": (payload.get("nombre_nicho") or "").strip(),
        "tipos": payload.get("tipos") or [],
        "seguidores": (payload.get("seguidores") or "").strip(),
        "ultimo_scraping": payload.get("ultimo_scraping"),
        "estado": payload.get("estado") or "activo",
        "created_at": datetime.now().isoformat(),
    }
    lst.append(profile)
    return profile


def update_profile(data: dict, email: str, plataforma: str, profile_id: str, payload: dict) -> Optional[dict]:
    user = get_user_record(data, email)
    lst = _platform_list(user, plataforma)
    for p in lst:
        if p.get("id") == profile_id:
            for field in (
                "username", "nombre_nicho", "seguidores", "ultimo_scraping", "estado",
                "profile_pic_url", "ig_url",
            ):
                if field in payload:
                    p[field] = payload[field]
            if "tipos" in payload:
                p["tipos"] = payload["tipos"]
            p["updated_at"] = datetime.now().isoformat()
            return p
    return None


def delete_profile(data: dict, email: str, plataforma: str, profile_id: str) -> bool:
    user = get_user_record(data, email)
    lst = _platform_list(user, plataforma)
    before = len(lst)
    user["referentes_profiles"][plataforma if plataforma in ("instagram", "youtube") else "instagram"] = [
        p for p in lst if p.get("id") != profile_id
    ]
    return len(user["referentes_profiles"].get(plataforma, [])) < before


def consume_manual_scrape(data: dict, email: str) -> int:
    user = get_user_record(data, email)
    scraping = _ensure_scraping(user)
    remaining = scraping.get("manual_remaining", 0)
    if remaining <= 0:
        raise ValueError("Sin actualizaciones manuales esta semana. Se renuevan el lunes.")
    scraping["manual_remaining"] = remaining - 1
    scraping["last_manual_scrape_at"] = datetime.now().isoformat()
    return scraping["manual_remaining"]


def reset_manual_scrape_after_weekly(data: dict, email: str) -> None:
    """Llamar tras el scrapeo programado del lunes."""
    user = get_user_record(data, email)
    scraping = _ensure_scraping(user)
    scraping["manual_remaining"] = MANUAL_SCRAPE_CREDITS
    scraping["last_reset_week"] = _iso_week_key()


def active_ig_usernames(data: dict, email: str) -> list:
    profiles = get_profiles(data, email)
    return [
        p["username"].lstrip("@").strip()
        for p in profiles["instagram"]
        if p.get("username", "").strip() and p.get("estado", "activo") != "pausado"
    ]
