"""
Estado y persistencia del onboarding RIMA AI.
"""
from __future__ import annotations

import os
from typing import Optional

from core.referentes_store import get_user_brand, cliente_id_from_brand
from core.plan_limits import normalize_plan

SKIP_ONBOARDING = os.getenv("RIMA_SKIP_ONBOARDING", "") == "1"
ADMIN_EMAIL = os.getenv("RIMA_ADMIN_EMAIL", "admin@rima.ai")

# Rutas bloqueadas hasta completar brief esencial
LOCKED_UNTIL_BRIEF = {
    "/contenido", "/calendario", "/lab", "/mercado", "/meta",
    "/ventas", "/landing", "/referencias", "/imagenes", "/videos",
}

BRIEF_FIELD_SPECS = [
    ("brand_name", 2, "Nombre del negocio"),
    ("brand_service", 8, "Servicio u oferta"),
    ("brand_ideal_client", 8, "Cliente ideal"),
    ("brand_problem", 8, "Problema que resuelves"),
    ("brand_result", 8, "Resultado principal"),
    ("brand_ig", 2, "Instagram del negocio"),
]

BRAND_TO_BRIEF_KEYS = {
    "brand_name": "business_name",
    "brand_service": "service",
    "brand_ideal_client": "ideal_client",
    "brand_problem": "problem",
    "brand_result": "main_result",
    "brand_price": "price",
    "brand_success_cases": "success_cases",
    "brand_guarantee": "guarantee",
    "brand_ig": "ig_username",
    "ig_username": "ig_username",
    "brand_tone": "brand_tone",
    "brand_language": "brand_language",
    "enfoque_default": "enfoque",
}


def _field_value(brand: dict, key: str) -> str:
    if key == "brand_ig":
        return (brand.get("brand_ig") or brand.get("ig_username") or "").strip()
    return (brand.get(key) or "").strip()


def brief_missing_fields(brand: dict) -> list[str]:
    missing = []
    for key, min_len, label in BRIEF_FIELD_SPECS:
        val = _field_value(brand, key)
        if len(val) < min_len:
            missing.append(label)
    return missing


def is_brief_complete(brand: dict) -> bool:
    return len(brief_missing_fields(brand)) == 0


def brief_gate_active(email: str, brand: dict) -> bool:
    """¿Bloquear dashboard por brief incompleto?"""
    if SKIP_ONBOARDING:
        return False
    email = (email or "").strip().lower()
    if email.endswith("@test.com") or email == ADMIN_EMAIL:
        return False
    return not is_brief_complete(brand)


def ensure_user_onboarding_defaults(user: dict, email: str, brand: Optional[dict] = None) -> bool:
    """Rellena flags por defecto. Retorna True si mutó el usuario."""
    changed = False
    email = (email or "").strip().lower()
    brand = brand or {}

    if "onboarding_completed" not in user:
        if SKIP_ONBOARDING or email.endswith("@test.com") or email == ADMIN_EMAIL:
            user["onboarding_completed"] = True
        elif is_brief_complete(brand):
            user["onboarding_completed"] = True
        else:
            user["onboarding_completed"] = False
        changed = True

    if "must_change_password" not in user:
        user["must_change_password"] = False
        changed = True

    if "onboarding_step" not in user:
        user["onboarding_step"] = 1 if not user.get("onboarding_completed") else 0
        changed = True

    user.setdefault("onboarding_scrape", {"status": "idle"})
    persist_needed = changed
    return persist_needed


def get_onboarding_state(data: dict, email: str) -> dict:
    email = (email or "").strip().lower()
    users = data.get("users", {})
    user = users.get(email, {})
    brand = get_user_brand(data, email)

    if ensure_user_onboarding_defaults(user, email, brand):
        users[email] = user

    scrape = user.get("onboarding_scrape") or {"status": "idle"}
    missing = brief_missing_fields(brand)
    plan = normalize_plan(user.get("plan") or brand.get("plan") or "pro")
    cid = cliente_id_from_brand(brand)
    assets = onboarding_assets_status(cid, plan)

    return {
        "onboarding_completed": bool(user.get("onboarding_completed")),
        "must_change_password": bool(user.get("must_change_password")),
        "onboarding_step": int(user.get("onboarding_step") or 1),
        "brief_complete": is_brief_complete(brand),
        "brief_gate": brief_gate_active(email, brand),
        "brief_missing": missing,
        "scrape_status": scrape.get("status", "idle"),
        "scrape_username": scrape.get("username", ""),
        "scrape_error": scrape.get("error", ""),
        "posts_count": scrape.get("posts_count", 0),
        "insights": scrape.get("insights"),
        **assets,
    }


def post_login_redirect(state: dict) -> str:
    if SKIP_ONBOARDING:
        return "/home"
    if state.get("must_change_password") or not state.get("onboarding_completed"):
        return "/onboarding"
    if state.get("brief_gate"):
        return "/onboarding?step=3"
    return "/home"


def brand_to_brief_dict(brand: dict, plan: str = "pro") -> dict:
    brief = {}
    for brand_key, brief_key in BRAND_TO_BRIEF_KEYS.items():
        val = brand.get(brand_key)
        if val is not None and val != "":
            brief[brief_key] = val
    ig = _field_value(brand, "brand_ig")
    if ig:
        brief["ig_username"] = ig.lstrip("@")
        brief["brand_ig"] = ig if ig.startswith("@") else f"@{ig}"
    brief["business_name"] = brand.get("brand_name") or brief.get("business_name") or "Mi Negocio"
    brief["plan"] = normalize_plan(plan or brand.get("plan", "pro"))
    return brief


def sync_brand_storage(data: dict, email: str, brand: dict, plan: str) -> str:
    """Persiste brand en rima_data (caller), brief.json, SQLite clientes y marca_visual."""
    from core.client_store import save_brief, ensure_client_dirs
    from core.db import init_db, create_or_update_cliente, get_marca_visual, set_marca_visual
    from core.marca_visual import merge_from_brand

    cid = cliente_id_from_brand(brand)
    brief = brand_to_brief_dict(brand, plan)
    ig = brief.get("ig_username") or ""

    ensure_client_dirs(brand.get("brand_name") or cid)
    save_brief(brand.get("brand_name") or cid, brief)

    init_db(cid)
    create_or_update_cliente(
        cid,
        nombre=brand.get("brand_name") or cid,
        plan=normalize_plan(plan),
        ig_username=ig.lstrip("@") if ig else None,
        brief=brief,
    )
    marca = merge_from_brand(get_marca_visual(cid), brand)
    set_marca_visual(cid, marca)
    return cid


def cancel_cliente_sqlite(data: dict, email: str) -> None:
    from core.db import init_db, update_cliente_status, get_cliente, create_or_update_cliente

    brand = get_user_brand(data, email)
    cid = cliente_id_from_brand(brand)
    init_db(cid)
    if not get_cliente(cid):
        create_or_update_cliente(cid, nombre=brand.get("brand_name") or cid, plan="basico")
    update_cliente_status(cid, "cancelado")


MIN_PHOTOS_BY_PLAN = {"basico": 3, "basic": 3, "pro": 4, "max": 5}
FACE_REQUIRED_PLANS = {"pro", "max"}
ONBOARDING_MAX_STEP = 7


def min_photos_for_plan(plan: str) -> int:
    return MIN_PHOTOS_BY_PLAN.get(normalize_plan(plan), 3)


def face_profile_required(plan: str) -> bool:
    return normalize_plan(plan) in FACE_REQUIRED_PLANS


def count_historias_photos(cliente_id: str) -> int:
    from core.db import init_db, get_imagenes_para
    init_db(cliente_id)
    imgs = get_imagenes_para(cliente_id, "historia") or []
    return len(imgs)


def onboarding_assets_status(cliente_id: str, plan: str) -> dict:
    from core.face_profile import has_face_profile

    min_photos = min_photos_for_plan(plan)
    photos = count_historias_photos(cliente_id)
    face_ok = has_face_profile(cliente_id)
    face_req = face_profile_required(plan)
    missing = []
    if photos < min_photos:
        missing.append(f"Subí al menos {min_photos} fotos para historias ({photos}/{min_photos})")
    if face_req and not face_ok:
        missing.append("Subí tu foto de rostro (referencia para IA)")
    return {
        "min_photos": min_photos,
        "photos_count": photos,
        "photos_ok": photos >= min_photos,
        "face_required": face_req,
        "face_profile_ok": face_ok or not face_req,
        "assets_missing": missing,
        "assets_complete": len(missing) == 0,
    }


def onboarding_complete_missing(brand: dict, cliente_id: str, plan: str) -> list[str]:
    missing = list(brief_missing_fields(brand))
    assets = onboarding_assets_status(cliente_id, plan)
    missing.extend(assets["assets_missing"])
    return missing


def apply_scrape_to_brand(brand: dict, scrape_result: dict) -> dict:
    """Mezcla insights del scrape IG en el objeto brand para prellenar wizard."""
    brand = dict(brand)
    insights = scrape_result.get("insights") or {}
    profile = scrape_result.get("profile") or {}

    if profile.get("biography") and not brand.get("brand_service"):
        brand["brand_service"] = profile["biography"][:300]

    oferta = insights.get("oferta_detectada") or ""
    if oferta and not brand.get("brand_price"):
        brand["brand_price"] = oferta

    problema = insights.get("problema_detectado") or ""
    if problema and not brand.get("brand_problem"):
        brand["brand_problem"] = problema

    resultado = insights.get("resultado_prometido") or ""
    if resultado and not brand.get("brand_result"):
        brand["brand_result"] = resultado

    cliente = insights.get("cliente_ideal") or ""
    if cliente and not brand.get("brand_ideal_client"):
        brand["brand_ideal_client"] = cliente

    tono = insights.get("forma_de_hablar") or insights.get("tono") or ""
    if tono:
        brand["brand_tone"] = tono

    bio = profile.get("biography") or ""
    if bio:
        brand["brand_bio_ig"] = bio

    username = profile.get("username") or scrape_result.get("username") or ""
    if username:
        brand["brand_ig"] = f"@{username.lstrip('@')}"
        brand["ig_username"] = username.lstrip("@")

    return brand
