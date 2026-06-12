"""
Fase B.0 — Hidratar tabla `imagenes` desde el sistema global viejo de uploads.

Toma las imágenes de data/uploads/{historias,carruseles}/ (sistema global, sin
cliente), las analiza con agents/image_analysis (Gemini Vision) y las persiste
en la tabla SQLite `imagenes` del cliente indicado, para que
get_imagenes_para(cliente_id, "historia"/"carrusel") devuelva candidatas reales
en la Fase B del Sprint Visual.

Idempotente: si archivo_url ya existe en la tabla, se salta.

Uso:
    python scripts/analyze_uploads_to_db.py --limit 2            # prueba: 2 por categoría
    python scripts/analyze_uploads_to_db.py                      # todas las pendientes
    python scripts/analyze_uploads_to_db.py --category historias # solo historias
    python scripts/analyze_uploads_to_db.py --dry-run            # listar sin llamar a Gemini
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.db import create_imagen, get_imagenes_para, init_db, set_imagen_analisis

CLIENTE_ID = "negocio_básico"
BRAND = "Negocio Básico"
UPLOADS = ROOT / "data" / "uploads"
EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# carpeta global -> uso singular que consume get_imagenes_para()
CATEGORIA_USO = {"historias": "historia", "carruseles": "carrusel"}


def usable_para_from_meta(uso_base: str, meta: dict) -> list:
    """uso de la carpeta de origen + extras que sugiera el análisis."""
    usable = [uso_base]
    sugerida = (meta.get("suggested_category") or "").lower()
    for extra in ("historia", "carrusel", "branding"):
        if extra in sugerida and extra not in usable:
            usable.append(extra)
    return usable


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0,
                        help="máximo de imágenes NUEVAS a analizar por categoría (0 = todas)")
    parser.add_argument("--category", choices=[*CATEGORIA_USO, "all"], default="all")
    parser.add_argument("--dry-run", action="store_true",
                        help="listar pendientes sin llamar a Gemini ni escribir en DB")
    args = parser.parse_args()

    init_db(CLIENTE_ID)
    # uso="" matchea todas las imágenes ya analizadas (LIKE '%%')
    existentes = {img.get("archivo_url") for img in get_imagenes_para(CLIENTE_ID, "")}

    categorias = list(CATEGORIA_USO) if args.category == "all" else [args.category]
    total_ok, total_err, total_skip = 0, 0, 0

    for categoria in categorias:
        carpeta = UPLOADS / categoria
        if not carpeta.exists():
            print(f"[{categoria}] carpeta no existe: {carpeta}")
            continue
        uso = CATEGORIA_USO[categoria]
        nuevas = 0
        for archivo in sorted(carpeta.iterdir()):
            if archivo.suffix.lower() not in EXTS:
                continue
            archivo_url = f"/uploads/{categoria}/{archivo.name}"
            if archivo_url in existentes:
                total_skip += 1
                continue
            if args.limit and nuevas >= args.limit:
                print(f"[{categoria}] límite {args.limit} alcanzado")
                break
            if args.dry_run:
                print(f"[{categoria}] PENDIENTE {archivo.name}")
                nuevas += 1
                continue

            print(f"[{categoria}] analizando {archivo.name} ...", flush=True)
            # Import perezoso: instancia el cliente Vertex solo si hay trabajo real.
            from agents.image_analysis.agent import image_analysis_agent
            meta = image_analysis_agent.analyze(str(archivo), BRAND, categoria)
            if meta.get("error") or "Error al analizar" in (meta.get("description") or ""):
                print(f"  ERROR: {meta.get('error') or meta.get('description')}")
                total_err += 1
                continue

            img = create_imagen(CLIENTE_ID, archivo_url, nombre=archivo.name)
            set_imagen_analisis(
                CLIENTE_ID, img["id"],
                analisis=meta,
                usable_para=usable_para_from_meta(uso, meta),
                tags=meta.get("tags", []),
            )
            existentes.add(archivo_url)
            print(f"  OK id={img['id'][:8]} zona={meta.get('best_text_zone')} "
                  f"vibe={str(meta.get('vibe'))[:50]}")
            nuevas += 1
            total_ok += 1

    print(f"\nResumen: {total_ok} analizadas y persistidas, "
          f"{total_skip} ya existían, {total_err} con error.")


if __name__ == "__main__":
    main()
