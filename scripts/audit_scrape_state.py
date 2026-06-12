"""Estado actual del scrape + qué pasaría en el próximo run."""
import json
import sqlite3
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "clients"


def audit(cid: str) -> None:
    root = BASE / cid
    latest_path = root / "market_research" / "latest.json"
    if not latest_path.exists():
        print(f"\n=== {cid}: sin latest.json ===")
        return

    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    posts = latest.get("posts", [])

    print(f"\n=== {cid} ===")
    print(f"  scrape_at: {latest.get('timestamp', '?')[:19]}")
    print(f"  referentes: {latest.get('profiles_scraped', [])}")
    meta_keys = [
        "metrics_updated", "viral_spikes", "deep_analyzed",
        "deep_analysis_parsed", "transcripts_ok", "profile_insights",
    ]
    for k in meta_keys:
        v = latest.get(k)
        if v is not None:
            print(f"  {k}: {v}")

    owners = Counter(p.get("owner") for p in posts)
    print(f"  posts en JSON: {len(posts)} -> {dict(owners)}")

    has_trans = sum(1 for p in posts if (p.get("transcripcion") or "").strip())
    has_hook = sum(1 for p in posts if (p.get("analisis_json") or {}).get("hook"))
    has_guion = sum(1 for p in posts if (p.get("analisis_json") or {}).get("hook_hablado"))
    has_que = sum(1 for p in posts if (p.get("analisis_json") or {}).get("que_modelar"))
    print(f"  con transcripcion: {has_trans} | hook: {has_hook} | hook_hablado: {has_guion} | que_modelar: {has_que}")

    pub = sorted(((p.get("timestamp") or "")[:10] for p in posts if p.get("timestamp")), reverse=True)
    if pub:
        print(f"  post mas reciente (fecha IG): {pub[0]} | en 2026: {sum(1 for d in pub if d.startswith('2026'))}")

    print("\n  TOP 5 views (baseline para comparar):")
    for p in sorted(posts, key=lambda x: x.get("views", 0), reverse=True)[:5]:
        m = p.get("metrics") or {}
        url = (p.get("url") or "")[-24:]
        print(
            f"    @{p.get('owner')} views={p.get('views', 0):,} "
            f"likes={p.get('likes', 0):,} comm={p.get('comments', 0):,} "
            f"rel={m.get('relevancia')} sv={m.get('score_ventas')} …{url}"
        )

    db_path = root / "rima.db"
    if not db_path.exists():
        print("  SQLite: NO existe rima.db")
        print("  >> PROXIMO SCRAPE: todos los URLs serán _is_new → capa 2 completa (~9 posts)")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) c FROM referentes_contenido").fetchone()["c"]
    analyzed = conn.execute(
        "SELECT COUNT(*) c FROM referentes_contenido WHERE analizado_at IS NOT NULL"
    ).fetchone()["c"]
    try:
        with_trans = conn.execute(
            "SELECT COUNT(*) c FROM referentes_contenido "
            "WHERE transcripcion IS NOT NULL AND transcripcion != ''"
        ).fetchone()["c"]
    except sqlite3.OperationalError:
        with_trans = "?"

    urls_json = {p.get("url") for p in posts if p.get("url")}
    rows = conn.execute("SELECT url FROM referentes_contenido").fetchall()
    urls_db = {r["url"] for r in rows}
    overlap = urls_json & urls_db

    print(f"\n  SQLite: {total} filas | analizados={analyzed} | transcripcion={with_trans}")
    print(f"  URLs JSON ∩ SQLite: {len(overlap)}/{len(urls_json)}")

    if total == 0:
        print("  >> PROXIMO SCRAPE: SQLite vacío → todos _is_new → capa 2 + transcripción (~9)")
    elif len(overlap) == len(urls_json):
        print("  >> PROXIMO SCRAPE (mismos referentes):")
        print("     - Capa 1: SÍ actualiza vistas/likes/comentarios en cada URL conocido")
        print("     - Métricas: SÍ recalcula fuerza/relevancia/engagement/score_ventas")
        print("     - Capa 2: NO re-analiza salvo URL nuevo o viral_spike detectado")
        print("     - Contenido nuevo: solo si Apify trae post con URL no visto antes")
    else:
        new_in_json = len(urls_json - urls_db)
        print(f"  >> Mezcla: {new_in_json} URLs en JSON que no están en SQLite")

    conn.close()


if __name__ == "__main__":
    for cid in ("negocio_básico", "default", "mi_negocio"):
        audit(cid)
