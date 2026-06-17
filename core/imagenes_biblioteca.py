"""
Registro de imágenes en la biblioteca del cliente (tabla imagenes).

Las generadas con KIE se guardan en data/uploads/clientes/{id}/generadas/
y se indexan en biblioteca (historial / reutilización manual).
No se asignan automáticamente a carruseles nuevos — cada carrusel genera imágenes frescas vía KIE.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.db import create_imagen, get_imagen_por_url, set_imagen_analisis


def cliente_generadas_dir(uploads_root: Path, cliente_id: str) -> Path:
    d = uploads_root / "clientes" / cliente_id / "generadas"
    d.mkdir(parents=True, exist_ok=True)
    return d


def url_generada(cliente_id: str, nombre_archivo: str) -> str:
    return f"/uploads/clientes/{cliente_id}/generadas/{nombre_archivo}"


def registrar_imagen_generada(
    cliente_id: str,
    archivo_path: Path,
    prompt: str = "",
    spec: Optional[dict] = None,
    paleta: Optional[list] = None,
) -> dict:
    """Indexa una imagen IA en la biblioteca. Idempotente por archivo_url."""
    spec = spec or {}
    nombre = archivo_path.name
    archivo_url = url_generada(cliente_id, nombre)

    existente = get_imagen_por_url(cliente_id, archivo_url)
    if existente:
        return existente

    desc = (prompt or spec.get("descripcion") or "Imagen generada con IA")[:400]
    analisis = {
        "description": desc,
        "vibe": spec.get("vibe", ""),
        "dominant_colors": paleta or spec.get("paleta_colores") or [],
        "production_quality": "media",
        "suggested_category": "carrusel informativo",
        "best_text_zone": (spec.get("zona_texto") or {}).get("zone", "center"),
        "origen_biblioteca": "generada_ia",
        "prompt_usado": (prompt or "")[:500],
    }
    usable = ["carrusel", "historia", "branding"]
    tags = ["generada_ia", "biblioteca", "reutilizable"]

    img = create_imagen(cliente_id, archivo_url, nombre=nombre)
    set_imagen_analisis(cliente_id, img["id"], analisis, usable, tags)
    img["analisis_json"] = analisis
    img["usable_para_json"] = usable
    img["tags_json"] = tags
    return img
