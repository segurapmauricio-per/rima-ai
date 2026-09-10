"""Cache local de fotos de perfil de referentes IG.

Los scrapers (Apify) devuelven una URL firmada de cdninstagram.com/fbcdn.net que
expira en horas. Si esa URL se guarda tal cual en rima_data.json, la foto se ve
bien el dia del scrape y queda rota semanas despues en Estudio de Mercado.

cache_referente_photos() descarga cada foto una vez a disco (data/uploads/
referentes_fotos/, ya montado como /uploads) y devuelve una copia del meta con
profile_pic_url apuntando a esa URL local estable -- lo que despues persiste
sync_ig_profiles_from_meta() en vez de la URL firmada.

Hace I/O de red: llamar SIEMPRE fuera de cualquier data_session()/lock.
"""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path

PHOTOS_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads" / "referentes_fotos"
_EXT_BY_CTYPE = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_ALLOWED_HOSTS = ("cdninstagram.com", "fbcdn.net", "instagram.com")
_USERNAME_RE = re.compile(r"^[a-z0-9._]{2,30}$")


def _safe_filename(username: str) -> str | None:
    u = (username or "").strip().lstrip("@").lower()
    return u if _USERNAME_RE.match(u) else None


def _existing_local_url(safe_username: str) -> str | None:
    for ext in _EXT_BY_CTYPE.values():
        if (PHOTOS_DIR / f"{safe_username}{ext}").exists():
            return f"/uploads/referentes_fotos/{safe_username}{ext}"
    return None


def _download_photo(safe_username: str, url: str) -> str | None:
    if not any(h in url for h in _ALLOWED_HOSTS):
        return None
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; RIMA/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
    except Exception as e:
        print(f"[referentes_photo_cache] descarga fallo para {safe_username}: {e}")
        return None
    ext = _EXT_BY_CTYPE.get(ctype, ".jpg")
    path = PHOTOS_DIR / f"{safe_username}{ext}"
    try:
        path.write_bytes(body)
    except Exception as e:
        print(f"[referentes_photo_cache] no se pudo guardar {path}: {e}")
        return None
    return f"/uploads/referentes_fotos/{safe_username}{ext}"


def cache_referente_photos(meta_by_username: dict) -> dict:
    """Descarga y cachea la foto de cada perfil en meta_by_username.

    Devuelve una copia del dict con profile_pic_url reemplazado por la URL
    local cuando la descarga funciona. Si falla (red, IG bloquea la request,
    url vacia) pero ya habia una foto cacheada de una corrida anterior, usa esa
    en vez de perderla -- una falla transitoria no debe revertir un perfil que
    ya tenia foto buena a la URL firmada (rota tarde o temprano) o a sin foto.
    """
    if not meta_by_username:
        return meta_by_username
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    out: dict = {}
    for username, meta in meta_by_username.items():
        meta = dict(meta)
        safe = _safe_filename(username)
        url = meta.get("profile_pic_url")
        if safe:
            local_url = _download_photo(safe, url) if url else None
            if not local_url:
                local_url = _existing_local_url(safe)
            if local_url:
                meta["profile_pic_url"] = local_url
        out[username] = meta
    return out
