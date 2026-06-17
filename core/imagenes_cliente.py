"""
Imágenes por cliente — rutas en disco + registro en SQLite (tabla imagenes).

Antes: data/uploads/carruseles|historias (global, todas las cuentas veían lo mismo).
Ahora: data/uploads/clientes/{cliente_id}/carruseles|historias
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.db import (
    create_imagen,
    get_imagen_por_url,
    init_db,
    set_imagen_analisis,
    get_imagenes_para,
)

CATEGORIAS = ("historias", "carruseles", "branding")
USO_POR_CATEGORIA = {"historias": "historia", "carruseles": "carrusel", "branding": "branding"}
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def cliente_images_dir(uploads_root: Path, cliente_id: str, category: str) -> Path:
    d = uploads_root / "clientes" / cliente_id / category
    d.mkdir(parents=True, exist_ok=True)
    return d


def archivo_url(cliente_id: str, category: str, nombre: str) -> str:
    return f"/uploads/clientes/{cliente_id}/{category}/{nombre}"


def register_uploaded_image(
    cliente_id: str,
    category: str,
    nombre: str,
    *,
    analisis: Optional[dict] = None,
    tags: Optional[list] = None,
) -> dict:
    """Registra en SQLite una imagen recién subida (analisis mínimo si no hay Gemini)."""
    init_db(cliente_id)
    url = archivo_url(cliente_id, category, nombre)
    existente = get_imagen_por_url(cliente_id, url)
    if existente and existente.get("analizado_at"):
        return existente

    uso = USO_POR_CATEGORIA.get(category, "carrusel")
    meta = analisis or {
        "description": nombre.replace("_", " ").rsplit(".", 1)[0][:200],
        "vibe": "",
        "suggested_category": category,
        "dominant_colors": [],
        "best_text_zone": "center",
        "production_quality": "media",
        "origen": "upload",
    }
    usable = [uso, "branding"]
    tag_list = tags or ["upload", category]

    if existente:
        set_imagen_analisis(cliente_id, existente["id"], meta, usable, tag_list)
        existente["analisis_json"] = meta
        existente["usable_para_json"] = usable
        return existente

    img = create_imagen(cliente_id, url, nombre=nombre)
    set_imagen_analisis(cliente_id, img["id"], meta, usable, tag_list)
    img["analisis_json"] = meta
    img["usable_para_json"] = usable
    return img


def sync_carpeta_cliente(uploads_root: Path, cliente_id: str, category: str) -> int:
    """Indexa en DB archivos del disco que aún no están registrados."""
    carpeta = cliente_images_dir(uploads_root, cliente_id, category)
    if not carpeta.exists():
        return 0
    nuevas = 0
    for p in carpeta.iterdir():
        if p.suffix.lower() not in IMG_EXTS:
            continue
        url = archivo_url(cliente_id, category, p.name)
        if get_imagen_por_url(cliente_id, url):
            continue
        register_uploaded_image(cliente_id, category, p.name)
        nuevas += 1
    return nuevas


def sync_todas_carpetas_cliente(uploads_root: Path, cliente_id: str) -> int:
    total = 0
    for cat in CATEGORIAS:
        total += sync_carpeta_cliente(uploads_root, cliente_id, cat)
    return total


def listar_archivos_cliente(uploads_root: Path, cliente_id: str, category: str) -> list:
    carpeta = cliente_images_dir(uploads_root, cliente_id, category)
    items = []
    for p in sorted(carpeta.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.suffix.lower() not in IMG_EXTS:
            continue
        stat = p.stat()
        items.append({
            "name": p.name,
            "url": archivo_url(cliente_id, category, p.name),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "uploaded_at": int(stat.st_mtime),
            "category": category,
        })
    return items


def usable_para_from_meta(uso_base: str, meta: dict) -> list:
    usable = [uso_base]
    sugerida = (meta.get("suggested_category") or "").lower()
    for extra in ("historia", "carrusel", "branding"):
        if extra in sugerida and extra not in usable:
            usable.append(extra)
    return usable


def biblioteca_imagenes(cliente_id: str, uso: str = "", uploads_root: Path = None) -> list:
    """Imágenes listas para picker de carrusel (DB, tras sync)."""
    root = uploads_root or Path(__file__).parent.parent / "data" / "uploads"
    sync_todas_carpetas_cliente(root, cliente_id)
    return get_imagenes_para(cliente_id, uso or "")
