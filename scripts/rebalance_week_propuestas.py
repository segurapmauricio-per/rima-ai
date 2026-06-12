"""Rebalancea propuestas pendientes de la semana actual para un cliente."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.weekly_helpers import (
    week_bounds,
    get_week_publicaciones,
    refresh_pending_propuestas,
)
from core.client_store import load_latest_market_research
from core.db import get_publicaciones, init_db

cid = sys.argv[1] if len(sys.argv) > 1 else "negocio_básico"
init_db(cid)
week_start, week_end, label = week_bounds()
market = load_latest_market_research(cid) or {}
refreshed = refresh_pending_propuestas(cid, week_start, week_end, market)
print(f"Semana {label} ({week_start}..{week_end})")
for item in refreshed:
    alts = item["alternativas"]
    print(
        item["fecha"],
        item["tematica"],
        "->",
        [a.get("url", "")[-18:] for a in alts],
    )
    print("   ", [a.get("titulo", "")[:55] for a in alts])
print("Actualizadas:", len(refreshed))
