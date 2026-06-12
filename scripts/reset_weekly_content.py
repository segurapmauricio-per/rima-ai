"""Reinicia el trabajo del agente semanal (propuestas/copy) sin tocar plan mensual ni mercado."""
import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.client_store import clear_weekly_state, load_brief
from core.db import init_db, reset_weekly_work, get_publicaciones
from core.weekly_helpers import week_bounds
from agents.weekly.agent import weekly_agent


def main():
    parser = argparse.ArgumentParser(description="Reinicia contenido semanal del orquestador RIMA")
    parser.add_argument("cliente_id", nargs="?", default="negocio_básico")
    parser.add_argument("--week-start", help="Lunes de la semana (YYYY-MM-DD). Default: semana actual")
    parser.add_argument("--restart", action="store_true", help="Regenerar propuestas tras el reset")
    parser.add_argument("--brand", help="Nombre de marca (default: derivado del cliente_id)")
    args = parser.parse_args()

    cid = args.cliente_id
    init_db(cid)

    ref = datetime.strptime(args.week_start, "%Y-%m-%d").date() if args.week_start else None
    start, end, week = week_bounds(ref)
    brand = args.brand or cid.replace("_", " ").title()

    before = [p for p in get_publicaciones(cid) if start <= (p.get("fecha") or "") <= end]
    print(f"Cliente: {cid}")
    print(f"Semana:  {week} ({start} -> {end})")
    print(f"Piezas:  {len(before)}")

    reset = reset_weekly_work(cid, start, end)
    cleared = clear_weekly_state(brand, week)
    print(f"Reiniciadas: {reset} piezas (slots del plan mensual intactos)")
    print(f"Estado weekly JSON eliminado: {cleared}")

    if args.restart:
        brief = load_brief(brand) or {"business_name": brand, "plan": "pro"}
        result = weekly_agent.start_week(
            brand=brand,
            week_label=week,
            cliente_id=cid,
            skip_scrape=True,
            brand_brief=brief,
            week_start=start,
        )
        print(f"Propuestas regeneradas: {result.get('propuestas_generadas', 0)}")

    after = [p for p in get_publicaciones(cid) if start <= (p.get("fecha") or "") <= end]
    for p in after:
        prop = p.get("propuesta_json") or {}
        n = len(prop.get("alternativas") or []) if isinstance(prop, dict) else 0
        print(f"  {p['fecha']} {p['tipo']:8} {p.get('status'):20} alts={n} tematica={p.get('tematica')}")


if __name__ == "__main__":
    main()
