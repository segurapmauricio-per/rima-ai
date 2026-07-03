"""Estado del tour del dashboard y flujo guiado post-onboarding."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

REF_DISCOVERY_DAYS = 3
REF_DISCOVERY_MIN_SECONDS = REF_DISCOVERY_DAYS * 24 * 3600


def _default_activation() -> dict:
    return {
        "status": "pending",
        "step": 1,
        "referentes_confirmed": False,
        "market_done": False,
        "calendar_done": False,
        "weekly_done": False,
    }


def _default_tour() -> dict:
    return {"seen_count": 0, "dismissed": False}


def _default_referentes_discovery() -> dict:
    return {
        "status": "pending",
        "suggestions": [],
        "generated_at": None,
        "anchor_at": None,
    }


def _user_created_ts(user: dict) -> Optional[int]:
    raw = user.get("created_at")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return int(datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp())
        except Exception:
            return None
    return None


def days_since_signup(user: dict) -> Optional[float]:
    ts = _user_created_ts(user)
    if ts is None:
        return None
    return (time.time() - ts) / 86400.0


def is_referentes_discovery_eligible(user: dict) -> bool:
    ts = _user_created_ts(user)
    if ts is None:
        return False
    return (time.time() - ts) >= REF_DISCOVERY_MIN_SECONDS


def ensure_dashboard_flags(user: dict) -> bool:
    changed = False
    if "dashboard_tour" not in user:
        user["dashboard_tour"] = _default_tour()
        changed = True
    if "activation_flow" not in user:
        user["activation_flow"] = _default_activation()
        changed = True
    if "referentes_discovery" not in user:
        user["referentes_discovery"] = _default_referentes_discovery()
        changed = True
    return changed


def get_tour_state(user: dict) -> dict:
    ensure_dashboard_flags(user)
    tour = user["dashboard_tour"]
    seen = int(tour.get("seen_count") or 0)
    dismissed = bool(tour.get("dismissed"))
    return {
        "seen_count": seen,
        "dismissed": dismissed,
        "should_show": not dismissed and seen < 2,
    }


def mark_tour_seen(user: dict, dismiss_permanent: bool = False) -> dict:
    ensure_dashboard_flags(user)
    tour = user["dashboard_tour"]
    if dismiss_permanent:
        tour["dismissed"] = True
    else:
        tour["seen_count"] = int(tour.get("seen_count") or 0) + 1
    return get_tour_state(user)


def get_activation_state(user: dict, onboarding_completed: bool = True) -> dict:
    ensure_dashboard_flags(user)
    flow = user["activation_flow"]
    status = flow.get("status") or "pending"
    if not onboarding_completed:
        status = "blocked"
    elif status == "pending" and flow.get("weekly_done"):
        status = "completed"
        flow["status"] = "completed"
    return {
        "status": status,
        "step": int(flow.get("step") or 1),
        "referentes_confirmed": bool(flow.get("referentes_confirmed")),
        "market_done": bool(flow.get("market_done")),
        "calendar_done": bool(flow.get("calendar_done")),
        "weekly_done": bool(flow.get("weekly_done")),
        "should_show": onboarding_completed and status in ("pending", "in_progress"),
    }


def start_activation(user: dict) -> dict:
    ensure_dashboard_flags(user)
    flow = user["activation_flow"]
    if flow.get("status") not in ("completed", "skipped"):
        flow["status"] = "in_progress"
    return get_activation_state(user, True)


def advance_activation(user: dict, step: int, **flags) -> dict:
    ensure_dashboard_flags(user)
    flow = user["activation_flow"]
    flow["status"] = "in_progress"
    flow["step"] = max(int(flow.get("step") or 1), step)
    for key, val in flags.items():
        if key in flow:
            flow[key] = bool(val)
    if flow.get("weekly_done"):
        flow["status"] = "completed"
    return get_activation_state(user, True)


def skip_activation(user: dict) -> dict:
    ensure_dashboard_flags(user)
    user["activation_flow"]["status"] = "skipped"
    return get_activation_state(user, True)


def reset_activation_on_onboarding_complete(user: dict) -> None:
    ensure_dashboard_flags(user)
    user["activation_flow"] = _default_activation()


def get_referentes_discovery_state(user: dict, referente_count: int = 0) -> dict:
    ensure_dashboard_flags(user)
    disc = user["referentes_discovery"]
    status = disc.get("status") or "pending"
    eligible = is_referentes_discovery_eligible(user)
    days = days_since_signup(user)
    suggestions = disc.get("suggestions") or []
    has_anchor = referente_count > 0
    return {
        "status": status,
        "eligible": eligible,
        "has_anchor": has_anchor,
        "anchor_at": disc.get("anchor_at"),
        "days_since_signup": round(days, 1) if days is not None else None,
        "days_until_eligible": max(0, REF_DISCOVERY_DAYS - (days or 0)) if days is not None else None,
        "suggestions": suggestions,
        "should_show_popup": eligible and has_anchor and status == "ready" and len(suggestions) > 0,
        "should_generate": eligible and has_anchor and status == "pending",
        "is_running": status == "running",
        "waiting_for_referentes": eligible and not has_anchor and status == "pending",
    }


def mark_referentes_anchor_ready(user: dict) -> None:
    ensure_dashboard_flags(user)
    disc = user["referentes_discovery"]
    if not disc.get("anchor_at"):
        disc["anchor_at"] = datetime.now().isoformat()


def mark_referentes_discovery_running(user: dict) -> dict:
    ensure_dashboard_flags(user)
    disc = user["referentes_discovery"]
    if disc.get("status") == "pending":
        disc["status"] = "running"
    return get_referentes_discovery_state(user)


def save_referentes_discovery_result(user: dict, suggestions: list[dict]) -> dict:
    ensure_dashboard_flags(user)
    disc = user["referentes_discovery"]
    disc["generated_at"] = datetime.now().isoformat()
    disc["suggestions"] = suggestions
    disc["status"] = "ready" if suggestions else "empty"
    return get_referentes_discovery_state(user)


def mark_referentes_discovery_shown(user: dict) -> dict:
    ensure_dashboard_flags(user)
    disc = user["referentes_discovery"]
    if disc.get("status") in ("ready", "empty", "running"):
        disc["status"] = "shown"
    return get_referentes_discovery_state(user)
