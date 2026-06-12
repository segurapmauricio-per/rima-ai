"""
Cuotas semanales de contenido por plan.

Regla de negocio:
  ocupados_en_semana(tipo) = planificado + propuesta/copy/producción en curso
  al regenerar (mensual o semanal) solo se crean/procesan piezas hasta:
      limite_cuenta(tipo) - ocupados_en_semana(tipo)
"""
from __future__ import annotations

from datetime import date
from collections import defaultdict

from core.plan_limits import CONTENT_WEEKLY, normalize_plan
from core.weekly_helpers import week_bounds


CANCELADO = "cancelado"

# Estados que consumen cupo semanal (cualquier etapa de aprobación o calendario pendiente)
CUPO_STATUSES = frozenset({
    "planificado",
    "propuesta_generada",
    "propuesta_enviada",
    "propuesta_aprobada",
    "copy_generado",
    "copy_enviado",
    "copy_aprobado",
    "en_produccion",
    "produccion_enviada",
    "produccion_aprobada",
    "programado",
    "publicado",
})

TIPO_TO_LIMIT_KEY = {
    "reel": "reels",
    "carrusel": "carruseles",
    "historia": "historias",
}


def week_bounds_for_date(fecha_str: str) -> tuple[str, str]:
    d = date.fromisoformat(fecha_str)
    start, end, _ = week_bounds(d)
    return start, end


def get_weekly_limits(plan: str) -> dict:
    tier = normalize_plan(plan)
    lim = CONTENT_WEEKLY.get(tier, CONTENT_WEEKLY["pro"])
    return {
        "reel": lim["reels"],
        "carrusel": lim["carruseles"],
        "historia": lim["historias"],
    }


def pub_cuenta_cupo(pub: dict) -> bool:
    if pub.get("status") == CANCELADO:
        return False
    return pub.get("status", "planificado") in CUPO_STATUSES


def count_week_by_tipo(pubs: list) -> dict:
    counts = {"reel": 0, "carrusel": 0, "historia": 0}
    for p in pubs:
        if not pub_cuenta_cupo(p):
            continue
        t = p.get("tipo")
        if t in counts:
            counts[t] += 1
    return counts


def remaining_week_quota(plan: str, pubs_in_week: list) -> dict:
    """Cuántas piezas más se pueden agregar por tipo esta semana."""
    limits = get_weekly_limits(plan)
    used = count_week_by_tipo(pubs_in_week)
    return {
        t: max(0, limits[t] - used.get(t, 0))
        for t in limits
    }


def week_quota_summary(plan: str, pubs_in_week: list) -> dict:
    limits = get_weekly_limits(plan)
    used = count_week_by_tipo(pubs_in_week)
    remaining = remaining_week_quota(plan, pubs_in_week)
    return {
        "limits": limits,
        "used": used,
        "remaining": remaining,
        "at_limit": {t: remaining[t] <= 0 for t in limits},
    }


def group_pubs_by_calendar_week(pubs: list) -> dict[tuple[str, str], list]:
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for p in pubs:
        fecha = p.get("fecha") or ""
        if not fecha:
            continue
        ws, we = week_bounds_for_date(fecha)
        groups[(ws, we)].append(p)
    return dict(groups)


def can_create_slot(plan: str, week_pubs: list, tipo: str,
                    batch_counts: dict | None = None) -> bool:
    """¿Hay cupo para crear un slot planificado más en esta semana?"""
    limits = get_weekly_limits(plan)
    used = count_week_by_tipo(week_pubs)
    extra = (batch_counts or {}).get(tipo, 0)
    return used.get(tipo, 0) + extra < limits.get(tipo, 0)


def trim_excess_planificado(cliente_id: str, plan: str,
                            start_date: str = None, end_date: str = None) -> int:
    """
    Elimina slots planificado sobrantes (sin propuesta/copy) cuando una semana
    supera el límite del plan. No toca piezas en validación ni con avance.
    """
    from core.db.database import (
        get_publicaciones, publicacion_es_protegida, db,
    )

    pubs = get_publicaciones(cliente_id)
    if start_date:
        pubs = [p for p in pubs if (p.get("fecha") or "") >= start_date]
    if end_date:
        pubs = [p for p in pubs if (p.get("fecha") or "") <= end_date]

    limits = get_weekly_limits(plan)
    deleted = 0

    for (_ws, _we), week_pubs in group_pubs_by_calendar_week(pubs).items():
        for tipo, limit in limits.items():
            activos = [p for p in week_pubs if p.get("tipo") == tipo and pub_cuenta_cupo(p)]
            if len(activos) <= limit:
                continue
            sobrante = len(activos) - limit
            candidatos = [
                p for p in activos
                if p.get("status") == "planificado"
                and not publicacion_es_protegida(p)
            ]
            candidatos.sort(key=lambda p: p.get("fecha", ""), reverse=True)
            for p in candidatos[:sobrante]:
                with db(cliente_id) as conn:
                    conn.execute(
                        "DELETE FROM publicaciones WHERE id = ? AND cliente_id = ?",
                        (p["id"], cliente_id),
                    )
                deleted += 1
                sobrante -= 1
                if sobrante <= 0:
                    break
    return deleted
