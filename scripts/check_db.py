"""Quick audit: JSON vs SQLite market research persistence."""
import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "clients"


def audit_client(cid: str) -> None:
    root = BASE / cid
    db_path = root / "rima.db"
    latest = root / "market_research" / "latest.json"
    posts_db = root / "referents" / "posts_db.json"

    print(f"\n=== {cid} ===")
    latest_count = 0
    if latest.exists():
        d = json.loads(latest.read_text(encoding="utf-8"))
        latest_count = len(d.get("posts", []))
        has_pi = bool(d.get("profile_insights"))
        ts = (d.get("timestamp") or "?")[:19]
        print(f"  latest.json: posts={latest_count} profile_insights={has_pi} ts={ts}")
    else:
        print("  latest.json: NO")

    if posts_db.exists():
        pdb = json.loads(posts_db.read_text(encoding="utf-8"))
        print(f"  posts_db.json: {len(pdb)} entradas")
    else:
        print("  posts_db.json: NO")

    if not db_path.exists():
        print("  rima.db: NO")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) c FROM referentes_contenido").fetchone()["c"]
    analyzed = conn.execute(
        "SELECT COUNT(*) c FROM referentes_contenido WHERE analizado_at IS NOT NULL"
    ).fetchone()["c"]
    try:
        with_sv = conn.execute(
            "SELECT COUNT(*) c FROM referentes_contenido WHERE score_ventas IS NOT NULL"
        ).fetchone()["c"]
    except sqlite3.OperationalError:
        with_sv = "col missing (run init_db)"
    try:
        sample = conn.execute(
            """SELECT referente_username, score_ventas, modelabilidad, fuerza
               FROM referentes_contenido ORDER BY COALESCE(score_ventas,0) DESC LIMIT 1"""
        ).fetchone()
    except sqlite3.OperationalError:
        sample = conn.execute(
            """SELECT referente_username, modelabilidad, fuerza
               FROM referentes_contenido ORDER BY COALESCE(fuerza,0) DESC LIMIT 1"""
        ).fetchone()
    print(
        f"  rima.db: total={total} analizados={analyzed} con_score_ventas={with_sv}"
    )
    if sample:
        sv = sample["score_ventas"] if "score_ventas" in sample.keys() else "n/a"
        print(
            f"  top: @{sample['referente_username']} "
            f"sv={sv} mod={sample['modelabilidad']}"
        )
    if latest_count and total != latest_count:
        print(f"  WARN mismatch latest.json ({latest_count}) vs sqlite ({total})")
    conn.close()


if __name__ == "__main__":
    if not BASE.exists():
        print("No clients dir")
    else:
        for p in sorted(BASE.iterdir()):
            if p.is_dir():
                audit_client(p.name)
