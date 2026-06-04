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
    save_weekly_state, load_weekly_state, update_memory
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
                   month: str = None, competitor_profiles: list = None) -> dict:
        """
        Kick off the weekly workflow.
        Called at 5 AM on recording_day - 1.
        """
        week = week_label or datetime.now().strftime("W%W_%Y")
        brief = load_brief(brand) or {}
        memory = load_memory(brand)
        current_month = month or datetime.now().strftime("%B_%Y").lower()

        # Load content calendar for this month to know what to create this week
        calendar = load_content_calendar(brand, current_month)
        week_slots = self._extract_week_slots(calendar, week) if calendar else []

        # Initialize weekly state
        state = {
            "week": week,
            "month": current_month,
            "brand": brand,
            "stage": "scraping",
            "recording_day": memory.get("recording_day", "martes"),
            "slots": week_slots,
            "stories": [s for s in week_slots if s.get("type") == "historia"],
            "carousels": [s for s in week_slots if s.get("type") == "carrusel"],
            "reels": [s for s in week_slots if s.get("type") == "reel"],
            "story_approvals": {},
            "carousel_approvals": {},
            "reel_approvals": {},
            "current_story_index": 0,
            "current_carousel_index": 0,
            "current_reel_index": 0,
            "market_research_done": False,
            "copy_stage_done": False,
            "production_done": False,
        }
        save_weekly_state(brand, week, state)

        # Step 1: Run market research (scraping)
        result = self._run_scraping(brand, brief, week, competitor_profiles or [])
        state["market_research_done"] = True
        state["market_research_summary"] = result.get("analysis", "")[:500]
        state["stage"] = "stories_copy"
        save_weekly_state(brand, week, state)

        return {
            "agent": self.name,
            "brand": brand,
            "week": week,
            "stage": "stories_copy",
            "message": "Scraping completado. Comenzando propuestas de historias.",
            "next_action": "call /api/agent/weekly/next-story",
        }

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

        copy_result = carousel_copy_agent.run(slot, brief, brand, referent=chosen_referent)

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
