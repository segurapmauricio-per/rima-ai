"""
Perfil de rostro del cliente para coherencia en generación KIE.
Persistencia: data/clients/{cliente_id}/face_profile.json
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

FACE_PROFILE_PROMPT = (
    "Retrato fotorrealista de la misma persona de la imagen de referencia. "
    "Mantener identidad facial exacta, sin cambiar rasgos ni inventar otro rostro."
)

FACE_RESTRICTIONS = [
    "usar el rostro de la imagen de referencia",
    "no inventar personajes ni personas genéricas",
    "mantener identidad facial consistente en todas las slides",
]


def _client_root(cliente_id: str) -> Path:
    return Path(__file__).parent.parent / "data" / "clients" / cliente_id


def face_profile_path(cliente_id: str) -> Path:
    return _client_root(cliente_id) / "face_profile.json"


def public_asset_url(relative_url: str) -> str:
    if not relative_url:
        return ""
    if str(relative_url).startswith(("http://", "https://")):
        return relative_url
    base = os.getenv("BASE_URL", "")
    if not base:
        login = os.getenv("APP_LOGIN_URL", "http://127.0.0.1:8000/login")
        base = login.rsplit("/login", 1)[0]
    return base.rstrip("/") + relative_url


def save_face_profile(
    cliente_id: str,
    image_url: str,
    *,
    filename: str = "",
    analisis: Optional[dict] = None,
    brand_name: str = "",
) -> dict:
    root = _client_root(cliente_id)
    root.mkdir(parents=True, exist_ok=True)
    profile = {
        "cliente_id": cliente_id,
        "brand_name": brand_name,
        "image_url": image_url,
        "image_url_public": public_asset_url(image_url),
        "filename": filename,
        "prompt_base": FACE_PROFILE_PROMPT,
        "restricciones": FACE_RESTRICTIONS,
        "analisis": analisis or {},
        "updated_at": datetime.now().isoformat(),
    }
    face_profile_path(cliente_id).write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return profile


def load_face_profile(cliente_id: str) -> Optional[dict]:
    path = face_profile_path(cliente_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def has_face_profile(cliente_id: str) -> bool:
    p = load_face_profile(cliente_id)
    return bool(p and p.get("image_url"))


def get_face_reference_for_kie(cliente_id: str) -> Optional[str]:
    """URL pública para image_input de KIE."""
    p = load_face_profile(cliente_id)
    if not p:
        return None
    url = p.get("image_url_public") or public_asset_url(p.get("image_url", ""))
    return url if url.startswith(("http://", "https://")) else None


def prompt_suffix_for_kie(cliente_id: str) -> str:
    p = load_face_profile(cliente_id)
    if not p:
        return ""
    parts = [p.get("prompt_base") or FACE_PROFILE_PROMPT]
    restr = p.get("restricciones") or FACE_RESTRICTIONS
    if restr:
        parts.append("Restricciones: " + "; ".join(restr))
    return " " + " ".join(parts)
