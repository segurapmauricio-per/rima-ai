"""Verifica bloques semanales del Monthly Planner (sin Gemini)."""
from datetime import date, timedelta
from unittest.mock import patch

from agents.content.agent import ContentAgent, PLAN_LIMITS

agent = ContentAgent()
limits = PLAN_LIMITS["basico"]


def simulate(label: str, fake_today: date):
    start_date = fake_today - timedelta(days=fake_today.weekday())
    tomorrow = fake_today + timedelta(days=1)

    with patch("agents.content.agent.date") as mock_date:
        mock_date.today.return_value = fake_today
        mock_date.side_effect = lambda *a, **k: date(*a, **k)

        blocks = agent._get_weekly_blocks(limits, start_date)

    print(f"=== {label} {fake_today} (lun={start_date}, man={tomorrow}) ===")
    if not blocks:
        print("  (sin bloques)")
        return

    b1 = blocks[0]
    print(
        f"  Semana 1: offsets {b1['offset_start']}-{b1['offset_end']} "
        f"({b1['days']}d) -> {b1['reels']}r {b1['carruseles']}c {b1['historias']}h"
    )
    offs = []
    for fmt, cnt in [
        ("reel", b1["reels"]),
        ("carrusel", b1["carruseles"]),
        ("historia", b1["historias"]),
    ]:
        offs.extend(
            agent._pick_varied_offsets(
                b1["offset_start"], b1["offset_end"], cnt, b1["week"], fmt, start_date
            )
        )
    slot_dates = sorted({start_date + timedelta(days=o) for o in offs})
    bad = [d for d in slot_dates if d < tomorrow]
    print(f"  fechas sem1: {[d.strftime('%a %m-%d') for d in slot_dates]}")
    assert not bad, f"slots antes de manana: {bad}"
    assert slot_dates, f"semana 1 vacia en {label}"
    if b1["offset_start"] == (tomorrow - start_date).days or b1["days"] < 7:
        assert slot_dates[0] >= tomorrow
    print()


simulate("Lunes (HOY en captura)", date(2026, 6, 15))
simulate("Miercoles", date(2026, 6, 11))
simulate("Domingo (bug anterior)", date(2026, 6, 14))
simulate("Domingo fin de sem", date(2026, 6, 21))
print("Todos los checks pasaron.")
