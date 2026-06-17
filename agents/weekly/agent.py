"""
Weekly Orchestrator Agent
Se ejecuta el día antes del día de grabación del cliente (desde brief.recording_day).

Flujo completo:
1. 5 AM: Scraping de referentes (MarketResearchAgent)
2. 9 AM: Genera propuestas de copy en etapas para aprobación via Telegram
   - Etapa 1: Historias (secuenciales, 2 propuestas c/u)
   - Etapa 2: Carruseles (elige referente a modelar, luego copy)
   - Etapa 3: Reels (elige referente, puede cambiar temática)
3. Cuando todo está aprobado: genera assets (image agents + script agent)
4. Aprobación final via plataforma o Telegram

El estado de cada etapa se persiste en weekly/{week}.json
"""
from agents.market_research.agent import market_research_agent
from agents.story_copy.agent import story_copy_agent
from agents.carousel_copy.agent import carousel_copy_agent
from agents.reel_copy.agent import reel_copy_agent
from core.client_store import (
    load_brief, load_memory, load_content_calendar,
    save_weekly_state, load_weekly_state, update_memory,
    load_latest_market_research,
)
from core.weekly_helpers import (
    week_bounds, pub_to_slot, get_week_publicaciones,
    assign_propuestas_rotating, build_propuesta_json,
    collect_used_referente_urls, collect_used_historia_angulos,
    refresh_pending_propuestas, format_slot_context_for_copy,
    sync_weekly_state_from_db, market_has_carousel_posts,
    _propuesta_carrusel_necesita_regenerar, _parse_propuesta,
)
from datetime import datetime, timedelta
import json


WEEK_STAGES = [
    "scraping",               # 5 AM: market research
    "stories_copy",           # 9 AM: story copy proposals
    "carousels_referents",    # Carousel: choose referent
    "carousels_copy",         # Carousel: generate copy
    "reels_referents",        # Reel: choose referent
    "reels_copy",             # Reel: generate idea
    "production",             # Generate final assets
    "final_approval",         # Client reviews final assets
    "complete",               # Done
]


class WeeklyAgent:
    def __init__(self):
        self.name = "weekly"

    def start_week(self, brand: str, week_label: str = None,
                   month: str = None, competitor_profiles: list = None,
                   cliente_id: str = None, skip_scrape: bool = True,
                   brand_brief: dict = None, week_start: str = None) -> dict:
        """
        Arranca el flujo semanal: lee slots planificados de SQLite, genera
        propuestas (2 referentes modelables por pieza) usando el estudio de mercado.
        """
        from datetime import datetime as dt
        from core.db import (
            get_publicaciones, update_publicacion_field, update_publicacion_status, init_db,
        )
        from core.week_quota import (
            remaining_week_quota, week_quota_summary, trim_excess_planificado,
            pub_cuenta_cupo,
        )

        ref = dt.strptime(week_start, "%Y-%m-%d").date() if week_start else None
        week_start, week_end, auto_week = week_bounds(ref)
        week = week_label or auto_week
        cid = cliente_id or brand.lower().replace(" ", "_")
        init_db(cid)

        brief = brand_brief or load_brief(brand) or {}
        plan_tier = (brief.get("plan") or "pro").lower()
        if plan_tier == "basic":
            plan_tier = "basico"
        memory = load_memory(brand)

        market = load_latest_market_research(cid) or {}
        if not skip_scrape and not market.get("posts"):
            scrape = self._run_scraping(brand, brief, week, competitor_profiles or [])
            market = load_latest_market_research(cid) or market
            market["_scrape_summary"] = scrape.get("analysis", "")[:500]

        all_week_pubs = get_week_publicaciones(get_publicaciones, cid, week_start, week_end)
        trimmed = trim_excess_planificado(cid, plan_tier, week_start, week_end)
        if trimmed:
            all_week_pubs = get_week_publicaciones(get_publicaciones, cid, week_start, week_end)

        quota = week_quota_summary(plan_tier, all_week_pubs)

        PIPELINE_STATUSES = {
            "propuesta_generada", "propuesta_enviada", "propuesta_aprobada",
            "copy_generado", "copy_enviado", "copy_aprobado",
            "en_produccion", "produccion_enviada", "produccion_aprobada",
            "programado", "publicado",
        }

        piezas = []
        omitidas = []
        to_generate = []

        for pub in sorted(all_week_pubs, key=lambda p: p.get("fecha", "")):
            if pub.get("status") != "planificado":
                if pub.get("status") in PIPELINE_STATUSES:
                    piezas.append({
                        "pub_id": pub["id"],
                        "fecha": pub.get("fecha"),
                        "tipo": pub.get("tipo"),
                        "tematica": pub.get("tematica"),
                        "status": pub.get("status"),
                        "skipped": True,
                        "reason": "Ya en validación — no se regenera",
                    })
                continue

            to_generate.append(pub)

        pending = []
        for pub in get_week_publicaciones(get_publicaciones, cid, week_start, week_end):
            status = pub.get("status")
            prop = _parse_propuesta(pub)
            if status == "planificado":
                pending.append(pub)
            elif status == "propuesta_generada":
                if not (prop.get("alternativas") or []):
                    pending.append(pub)
                elif _propuesta_carrusel_necesita_regenerar(pub, market):
                    pending.append(pub)
        used_urls = collect_used_referente_urls(all_week_pubs)
        used_angulos = collect_used_historia_angulos(all_week_pubs)
        assignments = assign_propuestas_rotating(
            pending, market, exclude_urls=used_urls, exclude_angulos=used_angulos,
        )

        for pub in pending:
            slot = pub_to_slot(pub)
            alternativas = assignments.get(pub["id"]) or []
            if not alternativas:
                propuesta_vacia = build_propuesta_json([], slot)
                propuesta_vacia["warning"] = "sin_referentes"
                update_publicacion_field(cid, pub["id"], "propuesta_json", propuesta_vacia)
                if pub.get("status") == "propuesta_generada":
                    update_publicacion_status(cid, pub["id"], "planificado")
                piezas.append({
                    "pub_id": pub["id"],
                    "fecha": pub.get("fecha"),
                    "tipo": pub.get("tipo"),
                    "tematica": pub.get("tematica"),
                    "alternativas": [],
                    "warning": "Sin referentes modelables para este slot",
                })
                continue

            propuesta = build_propuesta_json(alternativas, slot)
            prop_prev = pub.get("propuesta_json") or {}
            if isinstance(prop_prev, str):
                try:
                    prop_prev = json.loads(prop_prev)
                except Exception:
                    prop_prev = {}
            if prop_prev.get("fuente"):
                propuesta["fuente"] = prop_prev["fuente"]
            update_publicacion_field(cid, pub["id"], "propuesta_json", propuesta)
            update_publicacion_status(cid, pub["id"], "propuesta_generada")
            piezas.append({
                "pub_id": pub["id"],
                "fecha": pub.get("fecha"),
                "tipo": pub.get("tipo"),
                "tematica": pub.get("tematica"),
                "enfoque": pub.get("enfoque"),
                "alternativas": alternativas,
                "nueva": pub["id"] in {p["id"] for p in to_generate},
            })

        nuevas = [p for p in piezas if p.get("nueva")]
        stories = [p for p in piezas if p.get("tipo") == "historia"]
        carousels = [p for p in piezas if p.get("tipo") == "carrusel"]
        reels = [p for p in piezas if p.get("tipo") == "reel"]

        state = {
            "week": week,
            "week_start": week_start,
            "week_end": week_end,
            "brand": brand,
            "cliente_id": cid,
            "stage": "propuesta" if nuevas else "complete",
            "recording_day": memory.get("recording_day", "martes"),
            "slots": [pub_to_slot(p) for p in all_week_pubs if pub_cuenta_cupo(p)],
            "stories": stories,
            "carousels": carousels,
            "reels": reels,
            "propuestas_generadas": len(nuevas),
            "cuota": quota,
            "omitidas_cupo": omitidas,
            "recortadas_planificado": trimmed,
            "market_research_done": bool(market.get("posts")),
            "copy_stage_done": False,
            "production_done": False,
        }
        save_weekly_state(brand, week, state)

        return {
            "agent": self.name,
            "brand": brand,
            "cliente_id": cid,
            "week": week,
            "week_start": week_start,
            "week_end": week_end,
            "stage": state["stage"],
            "propuestas_generadas": state["propuestas_generadas"],
            "total_piezas": len(piezas),
            "piezas": piezas,
            "cuota": quota,
            "omitidas_cupo": omitidas,
            "recortadas_planificado": trimmed,
            "message": (
                f"Propuestas nuevas: {state['propuestas_generadas']}. "
                f"Cupo semanal — reels {quota['used']['reel']}/{quota['limits']['reel']}, "
                f"carruseles {quota['used']['carrusel']}/{quota['limits']['carrusel']}, "
                f"historias {quota['used']['historia']}/{quota['limits']['historia']}."
            ),
            "next_action": "Elegir referente por pieza en /contenido o POST /api/publicaciones/{id}/elegir-referente",
        }

    def generate_copy_for_publicacion(self, cliente_id: str, brand: str,
                                      pub_id: str, alternativa_index: int = 0,
                                      brand_brief: dict = None) -> dict:
        """Etapa Copy: genera texto adaptado tras elegir referente modelable."""
        from core.db import (
            get_publicacion, update_publicacion_field, update_publicacion_status,
        )

        pub = get_publicacion(cliente_id, pub_id)
        if not pub:
            return {"error": "Publicación no encontrada"}

        brief = brand_brief or load_brief(brand) or {}
        prop = pub.get("propuesta_json") or {}
        if isinstance(prop, str):
            try:
                prop = json.loads(prop)
            except Exception:
                prop = {}

        alternativas = prop.get("alternativas") or []
        if not alternativas:
            return {"error": "Sin propuestas — ejecutá el orquestador semanal primero"}
        if alternativa_index < 0 or alternativa_index >= len(alternativas):
            alternativa_index = 0

        elegida = alternativas[alternativa_index]
        slot = pub_to_slot(pub)
        slot_ctx = format_slot_context_for_copy(slot)
        referent = {
            "owner": elegida.get("owner", ""),
            "url": elegida.get("url", ""),
            "caption_preview": elegida.get("caption_preview", ""),
            "fuerza": elegida.get("fuerza", 0),
            "que_modelar": elegida.get("que_modelar", ""),
            "hook_hablado": elegida.get("hook_hablado", ""),
            "como_adaptar_guion": elegida.get("como_adaptar_guion", ""),
        }

        research_ctx = slot_ctx + "\n\n"
        if elegida.get("tipo_propuesta") == "estrategia":
            research_ctx += (
                f"TIPO DE HISTORIA (estrategia RIMA): {elegida.get('story_type', slot.get('tematica',''))}\n"
                f"ÁNGULO: {elegida.get('titulo','')}\n"
                f"Qué comunicar: {elegida.get('idea_principal','')}\n"
                "Generá copy siguiendo la estructura de estrategia para este tipo. "
                "NO modelar un referente externo del mercado.\n"
            )
        else:
            research_ctx += (
                f"REFERENTE: @{elegida.get('owner','')}\n"
                f"Qué modelar: {elegida.get('que_modelar','')}\n"
                f"Hook hablado: {elegida.get('hook_hablado','')}\n"
                f"Cómo adaptar: {elegida.get('como_adaptar_guion','')}\n"
            )

        tipo = pub.get("tipo", "reel")
        if tipo == "historia":
            from core.db import get_marca_visual
            from core.marca_visual import normalizar_marca, idioma_cliente
            marca = normalizar_marca(get_marca_visual(cliente_id))
            copy_result = story_copy_agent.run(
                slot, brief, brand, research_ctx, marca=marca,
            )
            proposals = copy_result.get("proposals") or [{}]
            copy_elegido = proposals[0] if proposals else {}
            copy_json = {
                "etapa": "copy",
                "referente_url": elegida.get("url") or "",
                "referente_owner": elegida.get("owner") or "",
                "story_type": elegida.get("story_type") or slot.get("tematica", ""),
                "angulo_estrategico": elegida.get("titulo", ""),
                "tematica": pub.get("tematica", ""),
                "enfoque": pub.get("enfoque", ""),
                "propuestas_copy": proposals,
                "propuesta_copy_index": 0,
                "copy_elegido": copy_elegido,
                "slides": copy_elegido.get("slides", []),
                "titulo": copy_elegido.get("titulo", ""),
                "plan_resumen": copy_elegido.get("plan_resumen", ""),
                "cta_keyword": copy_elegido.get("cta_keyword")
                or copy_elegido.get("keyword", ""),
                "idioma": idioma_cliente(brief, marca),
                "style_guide": copy_elegido.get("style_guide") or {},
            }
        elif tipo == "carrusel":
            from core.db import get_marca_visual
            from core.marca_visual import normalizar_marca
            marca = normalizar_marca(get_marca_visual(cliente_id))
            copy_result = carousel_copy_agent.run(
                slot, brief, brand, referent=referent, marca=marca,
            )
            copy_json = {
                "etapa": "copy",
                "referente_url": elegida.get("url"),
                "referente_owner": elegida.get("owner"),
                "slides": copy_result.get("slides", []),
                "formato": copy_result.get("formato", ""),
                "formato_id": copy_result.get("formato_id", ""),
                "style_guide": copy_result.get("style_guide", {}),
                "idioma": copy_result.get("idioma", "es"),
                "plan_resumen": copy_result.get("plan_resumen", ""),
                "valor_audience": copy_result.get("valor_audience", ""),
                "cta_keyword": copy_result.get("cta_keyword", ""),
                "cta_deliverable": copy_result.get("cta_deliverable", ""),
            }
        else:
            copy_result = reel_copy_agent.run(slot, brief, brand, referent=referent)
            idea = copy_result.get("idea") or {}
            copy_json = {
                "etapa": "copy",
                "referente_url": elegida.get("url"),
                "referente_owner": elegida.get("owner"),
                "titulo": idea.get("titulo", ""),
                "hook": idea.get("hook", ""),
                "desarrollo": idea.get("development", ""),
                "cta": idea.get("cta", ""),
                "cta_keyword": idea.get("cta_keyword", ""),
                "script_completo": idea.get("development", ""),
                "recording_notes": idea.get("recording_notes", ""),
                "idea": idea,
            }

        prop["elegida"] = elegida
        prop["alternativa_index"] = alternativa_index
        prop["etapa"] = "propuesta_aprobada"

        update_publicacion_field(cliente_id, pub_id, "propuesta_json", prop)
        update_publicacion_field(cliente_id, pub_id, "referente_id", elegida.get("referente_id") or "")
        update_publicacion_field(cliente_id, pub_id, "copy_json", copy_json)
        update_publicacion_status(cliente_id, pub_id, "copy_generado")

        if tipo in ("carrusel", "historia"):
            from agents.visual_composer import compose_produccion
            slot_ctx_dict = {
                "tematica": pub.get("tematica", ""),
                "enfoque": pub.get("enfoque", ""),
                "fecha": pub.get("fecha", ""),
            }
            previsual = compose_produccion(
                cliente_id, copy_json, tipo, slot_ctx_dict, modo="previsual",
            )
            if previsual:
                update_publicacion_field(cliente_id, pub_id, "produccion_json", previsual)

        sync_weekly_state_from_db(cliente_id, brand, pub.get("fecha"))

        refreshed = self._refresh_sibling_propuestas(
            cliente_id, pub.get("fecha"), skip_pub_id=pub_id, tipo=tipo,
        )

        return {
            "agent": self.name,
            "pub_id": pub_id,
            "tipo": tipo,
            "referente": elegida,
            "copy_json": copy_json,
            "status": "copy_generado",
            "propuestas_actualizadas": refreshed,
        }

    def _refresh_sibling_propuestas(self, cliente_id: str, pub_fecha: str,
                                    skip_pub_id: str = None, tipo: str = None) -> list:
        """Recalcula alternativas de otras piezas pendientes en la misma semana."""
        from datetime import datetime as dt

        if not pub_fecha:
            return []
        try:
            ref = dt.strptime(pub_fecha, "%Y-%m-%d").date()
        except ValueError:
            return []
        week_start, week_end, _ = week_bounds(ref)
        market = load_latest_market_research(cliente_id) or {}
        return refresh_pending_propuestas(
            cliente_id, week_start, week_end, market,
            skip_pub_id=skip_pub_id, tipo=tipo,
        )

    def next_story(self, brand: str, week: str) -> dict:
        """Get the next story proposal. Called iteratively until all stories approved."""
        state = load_weekly_state(brand, week) or {}
        brief = load_brief(brand) or {}

        # Auto-cargar stories del calendario si el estado está vacío
        if not state.get("stories"):
            month = state.get("month") or datetime.now().strftime("%B_%Y").lower()
            calendar = load_content_calendar(brand, month)
            if calendar:
                slots = self._extract_week_slots(calendar, week)
                state["stories"]   = [s for s in slots if s.get("type") == "historia"]
                state["carousels"] = [s for s in slots if s.get("type") == "carrusel"]
                state["reels"]     = [s for s in slots if s.get("type") == "reel"]
                state["week"]      = week
                state["brand"]     = brand
                state.setdefault("stage", "stories_copy")
                save_weekly_state(brand, week, state)

        stories = state.get("stories", [])
        idx = state.get("current_story_index", 0)

        if idx >= len(stories):
            # All stories done → move to carousels
            state["stage"] = "carousels_referents"
            state["copy_stage"] = "carousels"
            save_weekly_state(brand, week, state)
            return {
                "stage": "carousels_referents",
                "message": "Historias completadas. Pasamos a los carruseles.",
                "done": True,
            }

        slot = stories[idx]
        research_summary = state.get("market_research_summary", "")
        proposals = story_copy_agent.run(slot, brief, brand, research_summary)

        return {
            "agent": "story_copy",
            "brand": brand,
            "week": week,
            "story_index": idx,
            "total_stories": len(stories),
            "slot": slot,
            "proposals": proposals.get("proposals", []),
            "message": (
                f"Historia {idx + 1}/{len(stories)} — "
                f"{slot.get('date', '')} ({slot.get('story_type', '')})"
            ),
            "next_action": "POST /api/agent/weekly/approve-story con {story_index, chosen_proposal, feedback}",
        }

    def approve_story(self, brand: str, week: str, story_index: int,
                      chosen_proposal: dict, feedback: str = "") -> dict:
        """Record story approval and advance index."""
        state = load_weekly_state(brand, week) or {}
        state.setdefault("story_approvals", {})[str(story_index)] = {
            "approved": chosen_proposal,
            "feedback": feedback,
            "approved_at": datetime.now().isoformat(),
        }
        state["current_story_index"] = story_index + 1

        # Learn from feedback
        if feedback:
            story_copy_agent.apply_feedback(brand, feedback, chosen_proposal)

        save_weekly_state(brand, week, state)
        return {"status": "approved", "next_story_index": story_index + 1}

    def next_carousel(self, brand: str, week: str) -> dict:
        """Get referent options for next carousel."""
        state = load_weekly_state(brand, week)
        brief = load_brief(brand) or {}
        carousels = state.get("carousels", [])
        idx = state.get("current_carousel_index", 0)

        if idx >= len(carousels):
            state["stage"] = "reels_referents"
            save_weekly_state(brand, week, state)
            return {"stage": "reels_referents", "message": "Carruseles listos.", "done": True}

        slot = carousels[idx]
        referents = carousel_copy_agent.propose_referents(slot, brand, brief)

        return {
            "agent": "carousel_copy",
            "brand": brand,
            "week": week,
            "carousel_index": idx,
            "total_carousels": len(carousels),
            "slot": slot,
            "referent_options": referents.get("options", []),
            "message": referents.get("message", ""),
            "next_action": "POST /api/agent/weekly/approve-carousel-referent con {carousel_index, chosen_referent}",
        }

    def approve_carousel_referent(self, brand: str, week: str, carousel_index: int,
                                   chosen_referent: dict) -> dict:
        """Generate carousel copy after referent is chosen."""
        state = load_weekly_state(brand, week)
        brief = load_brief(brand) or {}
        carousels = state.get("carousels", [])
        slot = carousels[carousel_index]

        cid = brand.lower().replace(" ", "_")
        from core.db import get_marca_visual
        from core.marca_visual import normalizar_marca
        marca = normalizar_marca(get_marca_visual(cid))
        copy_result = carousel_copy_agent.run(
            slot, brief, brand, referent=chosen_referent, marca=marca,
        )

        state.setdefault("carousel_approvals", {})[str(carousel_index)] = {
            "referent": chosen_referent,
            "copy": copy_result,
            "status": "pending",
        }
        save_weekly_state(brand, week, state)

        return {
            "agent": "carousel_copy",
            "carousel_index": carousel_index,
            "slides": copy_result.get("slides", []),
            "next_action": "POST /api/agent/weekly/approve-carousel-copy",
        }

    def approve_carousel_copy(self, brand: str, week: str, carousel_index: int,
                               feedback: str = "", changes_requested: str = "") -> dict:
        """Finalize carousel copy approval."""
        state = load_weekly_state(brand, week) or {}
        approvals = state.setdefault("carousel_approvals", {})

        if changes_requested and str(carousel_index) in approvals:
            # Re-generate with feedback
            brief = load_brief(brand) or {}
            approvals[str(carousel_index)]["status"] = "revision"
            carousel_copy_agent.apply_feedback(brand, changes_requested)

        else:
            if str(carousel_index) in approvals:
                approvals[str(carousel_index)]["status"] = "approved"
                approvals[str(carousel_index)]["approved_at"] = datetime.now().isoformat()
            state["current_carousel_index"] = carousel_index + 1

        save_weekly_state(brand, week, state)
        return {"status": "approved", "next_carousel_index": carousel_index + 1}

    def next_reel(self, brand: str, week: str) -> dict:
        """Get referent options for next reel."""
        state = load_weekly_state(brand, week)
        brief = load_brief(brand) or {}
        reels = state.get("reels", [])
        idx = state.get("current_reel_index", 0)

        if idx >= len(reels):
            state["stage"] = "production"
            save_weekly_state(brand, week, state)
            return {"stage": "production", "message": "Reels listos. Pasamos a producción.", "done": True}

        slot = reels[idx]
        referents = reel_copy_agent.propose_referents(slot, brand, brief)

        return {
            "agent": "reel_copy",
            "brand": brand,
            "week": week,
            "reel_index": idx,
            "total_reels": len(reels),
            "slot": slot,
            "referent_options": referents.get("options", []),
            "message": referents.get("message", ""),
            "can_change_topic": True,
            "next_action": "POST /api/agent/weekly/approve-reel-referent",
        }

    def approve_reel_referent(self, brand: str, week: str, reel_index: int,
                               chosen_referent: dict, topic_override: str = None) -> dict:
        """Generate reel idea after referent (and optional topic change) is chosen."""
        state = load_weekly_state(brand, week)
        brief = load_brief(brand) or {}
        reels = state.get("reels", [])
        slot = reels[reel_index]

        if topic_override:
            # Update calendar slot topic
            slot["topic"] = topic_override
            reels[reel_index] = slot
            state["reels"] = reels

        idea_result = reel_copy_agent.run(slot, brief, brand,
                                          referent=chosen_referent,
                                          topic_override=topic_override)

        state.setdefault("reel_approvals", {})[str(reel_index)] = {
            "referent": chosen_referent,
            "idea": idea_result,
            "topic_changed": bool(topic_override),
            "status": "pending",
        }
        save_weekly_state(brand, week, state)

        return {
            "agent": "reel_copy",
            "reel_index": reel_index,
            "idea": idea_result.get("idea", {}),
            "next_action": "POST /api/agent/weekly/approve-reel-copy",
        }

    def approve_reel_copy(self, brand: str, week: str, reel_index: int,
                           feedback: str = "", changes_requested: str = "") -> dict:
        """Finalize reel idea approval."""
        state = load_weekly_state(brand, week) or {}
        approvals = state.setdefault("reel_approvals", {})

        if changes_requested:
            reel_copy_agent.apply_feedback(brand, changes_requested)

        if str(reel_index) in approvals and not changes_requested:
            approvals[str(reel_index)]["status"] = "approved"
            approvals[str(reel_index)]["approved_at"] = datetime.now().isoformat()
            state["current_reel_index"] = reel_index + 1

        save_weekly_state(brand, week, state)
        return {"status": "approved", "next_reel_index": reel_index + 1}

    def get_weekly_status(self, brand: str, week: str) -> dict:
        """Return current state of the weekly workflow."""
        state = load_weekly_state(brand, week)
        stories = state.get("stories", [])
        carousels = state.get("carousels", [])
        reels = state.get("reels", [])

        def count_approved(approvals: dict) -> int:
            return sum(1 for v in approvals.values() if v.get("status") == "approved")

        return {
            "week": week,
            "brand": brand,
            "stage": state.get("stage", "not_started"),
            "stories": {
                "total": len(stories),
                "approved": count_approved(state.get("story_approvals", {})),
                "current_index": state.get("current_story_index", 0),
            },
            "carousels": {
                "total": len(carousels),
                "approved": count_approved(state.get("carousel_approvals", {})),
                "current_index": state.get("current_carousel_index", 0),
            },
            "reels": {
                "total": len(reels),
                "approved": count_approved(state.get("reel_approvals", {})),
                "current_index": state.get("current_reel_index", 0),
            },
            "next_action": self._get_next_action(state),
        }

    def _get_next_action(self, state: dict) -> str:
        stage = state.get("stage", "not_started")
        actions = {
            "scraping": "Esperando scraping",
            "stories_copy": "POST /api/agent/weekly/next-story",
            "carousels_referents": "POST /api/agent/weekly/next-carousel",
            "carousels_copy": "POST /api/agent/weekly/approve-carousel-referent",
            "reels_referents": "POST /api/agent/weekly/next-reel",
            "reels_copy": "POST /api/agent/weekly/approve-reel-referent",
            "production": "POST /api/agent/weekly/start-production",
            "final_approval": "Revisar en plataforma o continuar por Telegram",
            "complete": "Semana completada",
        }
        return actions.get(stage, "Estado desconocido")

    def _extract_week_slots(self, calendar: dict, week: str) -> list:
        """Extract slots for a specific week from the monthly calendar."""
        all_slots = calendar.get("calendar", [])
        # Try to match by week number
        week_num = int(week.replace("W", "").split("_")[0]) if "W" in week else 1
        week_slots = [s for s in all_slots if s.get("semana") == week_num]
        return week_slots if week_slots else all_slots[:7]  # fallback: first week

    def _run_scraping(self, brand: str, brief: dict, week: str,
                      competitor_profiles: list) -> dict:
        """Run market research scraping."""
        try:
            result = market_research_agent.run(
                brand=brand,
                brand_brief=brief,
                competitor_profiles=competitor_profiles,
                week_label=week,
            )
            return result
        except Exception as e:
            return {"analysis": f"Error en scraping: {e}", "posts_analyzed": 0}


weekly_agent = WeeklyAgent()
