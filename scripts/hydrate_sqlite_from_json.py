"""
Hidrata referentes_contenido en SQLite desde market_research/latest.json.
Útil tras arreglar el FK de clientes cuando ya hay un scrape en JSON pero DB vacía.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.db import (  # noqa: E402
    create_or_update_cliente,
    init_db,
    upsert_referente,
    set_referente_analisis,
)


def hydrate(cliente_id: str, plan: str = "basico", nombre: str = None) -> None:
    latest_path = ROOT / "data" / "clients" / cliente_id / "market_research" / "latest.json"
    if not latest_path.exists():
        print(f"No existe {latest_path}")
        return

    data = json.loads(latest_path.read_text(encoding="utf-8"))
    posts = data.get("posts") or []
    if not posts:
        print("Sin posts en latest.json")
        return

    init_db(cliente_id)
    create_or_update_cliente(cliente_id, nombre=nombre or cliente_id, plan=plan)

    saved = 0
    analyzed = 0
    for post in posts:
        m = post.get("metrics") or {}
        aj = post.get("analisis_json") or {}
        ref = upsert_referente(cliente_id, {
            "referente_username": post.get("owner", ""),
            "plataforma": "instagram",
            "url": post.get("url", ""),
            "tipo": "reel" if post.get("views", 0) > 0 else "carrusel",
            "fecha_publicacion": post.get("timestamp", ""),
            "descripcion": post.get("caption", ""),
            "transcripcion": post.get("transcripcion") or "",
            "vistas": post.get("views", 0),
            "likes": post.get("likes", 0),
            "comentarios": post.get("comments", 0),
            "guardados": post.get("saves", 0),
            "seguidores_al_scrape": post.get("owner_followers", 0),
            "fuerza": m.get("fuerza"),
            "relevancia": m.get("relevancia"),
            "engagement": m.get("engagement"),
            "ratio_conversacion": m.get("ratio_conversacion"),
            "score_ventas": m.get("score_ventas"),
        })
        saved += 1
        if ref and aj.get("hook") and post.get("modelabilidad") is not None:
            set_referente_analisis(
                cliente_id,
                ref["id"],
                aj,
                post.get("modelabilidad", 5),
                transcripcion=post.get("transcripcion") or None,
            )
            analyzed += 1

    print(f"Hidratado {cliente_id}: {saved} posts, {analyzed} con analisis_json")


if __name__ == "__main__":
    targets = sys.argv[1:] or ["negocio_básico"]
    for cid in targets:
        hydrate(cid, plan="basico")
