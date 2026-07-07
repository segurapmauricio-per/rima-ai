"""KPIs reales del cliente para sidebar y dashboard."""
from __future__ import annotations

from datetime import date, timedelta

from core.referentes_store import (
    cliente_id_from_brand,
    format_followers,
    get_profiles,
    get_user_brand,
)
from core.referentes_store import get_user_record

# Estados que implican que la pieza sigue en el pipeline (no lista/publicada)
_ESTADOS_PENDIENTES_VALIDACION = {
    "copy_generado", "copy_enviado", "en_produccion",
    "produccion_enviada", "produccion_aprobada",
}
MESES_NOMBRE = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _followers_from_user(user: dict) -> int:
    scrape = user.get("onboarding_scrape") or {}
    profile = scrape.get("profile") or {}
    followers = profile.get("followers")
    if followers:
        return int(followers)
    insights = scrape.get("insights") or {}
    marca = scrape.get("marca_visual") or {}
    ov = (marca.get("onboarding_scrape") or {}).get("seguidores")
    if ov:
        return int(ov)
    return 0


def get_dashboard_stats(data: dict, email: str) -> dict:
    email = (email or "").strip().lower()
    user = get_user_record(data, email)
    brand = get_user_brand(data, email)
    cid = cliente_id_from_brand(brand)

    profiles = get_profiles(data, email)
    ref_count = profiles.get("counts", {}).get("instagram", 0)

    followers = _followers_from_user(user)
    if not followers:
        try:
            from pathlib import Path
            import json
            artifact = Path(__file__).parent.parent / "data" / "clients" / cid / "onboarding_scrape.json"
            if artifact.exists():
                payload = json.loads(artifact.read_text(encoding="utf-8"))
                followers = int((payload.get("profile") or {}).get("followers") or 0)
        except Exception:
            pass

    pubs_total = 0
    pubs_pending = 0
    avg_fuerza = None
    market_posts = 0
    calendario = {"mes_label": "", "piezas_mes": 0, "proxima": None}
    contenido = {"en_validacion": 0, "historias": 0, "carruseles": 0, "reels": 0}
    mercado_top = None
    pendientes_items = []
    esta_semana = []

    try:
        from core.db import get_publicaciones, init_db, get_referentes_market_dashboard

        init_db(cid)
        pubs = get_publicaciones(cid) or []
        pubs_total = len(pubs)
        pending_status = {"planificado", "propuesta_generada", "copy_generado", "pendiente"}
        pubs_pending = sum(1 for p in pubs if (p.get("status") or "") in pending_status)

        hoy = date.today()
        mes_actual = f"{MESES_NOMBRE[hoy.month - 1]} {hoy.year}"
        pubs_mes = [p for p in pubs if (p.get("mes") or "") == mes_actual]
        proximas_mes = sorted(
            (p for p in pubs_mes if (p.get("fecha") or "") >= hoy.isoformat()
             and p.get("status") != "publicado"),
            key=lambda p: p.get("fecha") or "",
        )
        calendario = {
            "mes_label": mes_actual,
            "piezas_mes": len(pubs_mes),
            "proxima": (
                {
                    "tipo": proximas_mes[0].get("tipo"),
                    "tematica": proximas_mes[0].get("tematica"),
                    "fecha": proximas_mes[0].get("fecha"),
                }
                if proximas_mes else None
            ),
        }

        en_pipeline = [p for p in pubs if (p.get("status") or "") in _ESTADOS_PENDIENTES_VALIDACION]
        contenido = {
            "en_validacion": len(en_pipeline),
            "historias": sum(1 for p in en_pipeline if p.get("tipo") == "historia"),
            "carruseles": sum(1 for p in en_pipeline if p.get("tipo") == "carrusel"),
            "reels": sum(1 for p in en_pipeline if p.get("tipo") == "reel"),
        }

        # Pendientes reales — reemplaza el panel mockup
        piezas_validacion = [
            p for p in pubs
            if (p.get("status") or "") in ("copy_generado", "en_produccion", "produccion_aprobada")
        ]
        if piezas_validacion:
            pendientes_items.append({
                "tipo": "validacion",
                "label": f"{len(piezas_validacion)} pieza{'s' if len(piezas_validacion) != 1 else ''} esperando validación",
                "href": "/contenido",
            })
        reels_por_grabar = [
            p for p in pubs
            if p.get("tipo") == "reel" and (p.get("status") or "") in ("copy_aprobado", "en_produccion")
        ]
        if reels_por_grabar:
            pendientes_items.append({
                "tipo": "reels",
                "label": f"{len(reels_por_grabar)} reel{'s' if len(reels_por_grabar) != 1 else ''} pendiente{'s' if len(reels_por_grabar) != 1 else ''} de grabar",
                "href": "/contenido",
            })
        atrasadas = [
            p for p in pubs
            if (p.get("fecha") or "") < hoy.isoformat()
            and p.get("status") not in ("publicado", "cancelado")
        ]
        if atrasadas:
            pendientes_items.append({
                "tipo": "atrasado",
                "label": f"{len(atrasadas)} pieza{'s' if len(atrasadas) != 1 else ''} programada{'s' if len(atrasadas) != 1 else ''} sin publicar",
                "href": "/contenido",
                "warning": True,
            })
        from core.onboarding import brief_missing_fields, BRIEF_FIELD_SPECS
        missing = brief_missing_fields(brand)
        if missing:
            total_fields = len(BRIEF_FIELD_SPECS)
            pct = round((total_fields - len(missing)) / total_fields * 100)
            pendientes_items.append({
                "tipo": "brief",
                "label": f"Brief de marca — {pct}% completo",
                "href": "/marca",
            })

        # Esta semana (lunes-domingo actual)
        semana_inicio = hoy - timedelta(days=hoy.weekday())
        semana_fin = semana_inicio + timedelta(days=6)
        semana_pubs = sorted(
            (p for p in pubs
             if semana_inicio.isoformat() <= (p.get("fecha") or "") <= semana_fin.isoformat()),
            key=lambda p: p.get("fecha") or "",
        )
        for p in semana_pubs[:6]:
            fecha_str = p.get("fecha") or ""
            atrasada = bool(fecha_str) and fecha_str < hoy.isoformat() and p.get("status") not in ("publicado", "cancelado")
            esta_semana.append({
                "tipo": p.get("tipo"),
                "tematica": p.get("tematica"),
                "fecha": fecha_str,
                "status": p.get("status"),
                "atrasada": atrasada,
            })

        refs = get_referentes_market_dashboard(cid, limit=200)
        market_posts = len(refs)
        fuerzas = [float(r.get("fuerza") or 0) for r in refs if r.get("fuerza")]
        if fuerzas:
            avg_fuerza = round(sum(fuerzas) / len(fuerzas) * 100, 1)
        if refs:
            top = max(refs, key=lambda r: float(r.get("score_ventas") or 0))
            mercado_top = {
                "owner": top.get("referente_username") or top.get("owner") or "",
                "fuerza_pct": round(float(top.get("fuerza") or 0) * 100, 1),
            }
    except Exception:
        pass

    return {
        "followers": followers,
        "followers_label": format_followers(followers) if followers else "—",
        "referentes_count": ref_count,
        "publicaciones_total": pubs_total,
        "publicaciones_pendientes": pubs_pending,
        "market_posts": market_posts,
        "fuerza_promedio_pct": avg_fuerza,
        "brand_name": brand.get("brand_name") or "",
        "brand_ig": brand.get("brand_ig") or brand.get("ig_username") or "",
        "calendario": calendario,
        "contenido": contenido,
        "mercado_top": mercado_top,
        "pendientes": pendientes_items,
        "esta_semana": esta_semana,
    }
