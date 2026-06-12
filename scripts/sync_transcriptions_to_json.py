"""Fusiona transcripcion desde SQLite hacia latest.json (fix puntual sin re-scrape)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.db import get_referentes_by_urls  # noqa: E402


def sync_transcriptions(cliente_id: str) -> None:
    latest_path = ROOT / "data" / "clients" / cliente_id / "market_research" / "latest.json"
    if not latest_path.exists():
        print(f"No existe latest.json para {cliente_id}")
        return

    data = json.loads(latest_path.read_text(encoding="utf-8"))
    posts = data.get("posts") or []
    urls = [p.get("url") for p in posts if p.get("url")]
    by_url = get_referentes_by_urls(cliente_id, urls)

    merged = 0
    for post in posts:
        row = by_url.get(post.get("url", ""))
        if not row:
            continue
        trans = (row.get("transcripcion") or "").strip()
        if trans and not (post.get("transcripcion") or "").strip():
            post["transcripcion"] = trans
            merged += 1

    latest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{cliente_id}: {merged} transcripciones fusionadas en latest.json")


if __name__ == "__main__":
    targets = sys.argv[1:] or ["negocio_básico"]
    for cid in targets:
        sync_transcriptions(cid)
