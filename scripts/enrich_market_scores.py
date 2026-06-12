"""Persiste score_ventas y scores_tematica en latest.json del cliente."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.client_store import client_path
from core.market_scores import attach_score_ventas, attach_scores_tematica

cid = sys.argv[1] if len(sys.argv) > 1 else "negocio_básico"
path = client_path(cid) / "market_research" / "latest.json"
if not path.exists():
    print(f"No existe {path}")
    sys.exit(1)

data = json.loads(path.read_text(encoding="utf-8"))
posts = data.get("posts") or []
for post in posts:
    attach_score_ventas(post)
    attach_scores_tematica(post)
data["posts"] = posts
if data.get("top_posts"):
    top_ids = {p.get("id") for p in data["top_posts"]}
    data["top_posts"] = [p for p in posts if p.get("id") in top_ids][:20]
path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Enriquecidos {len(posts)} posts en {path}")
