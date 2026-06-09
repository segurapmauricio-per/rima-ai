"""
Client Store — base de datos por cliente.
Maneja toda la persistencia en data/clients/{brand_slug}/
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

BASE_PATH = Path(__file__).parent.parent / "data" / "clients"


def _slug(name: str) -> str:
    """Convert business name to safe folder name."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "_", s)
    return s[:50]


def client_path(brand: str) -> Path:
    return BASE_PATH / _slug(brand)


def ensure_client_dirs(brand: str) -> Path:
    """Create all folder structure for a client if it doesn't exist."""
    root = client_path(brand)
    dirs = [
        root,
        root / "market_research" / "snapshots",
        root / "content",
        root / "scripts",
        root / "images" / "historias",
        root / "images" / "carruseles",
        root / "images" / "branding",
        root / "videos" / "clips",
        root / "videos" / "finals",
        root / "reels",
        root / "referents",
        root / "offer",
        root / "landing",
        root / "weekly",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return root


# ─── Brief ────────────────────────────────────────────────────────────────────

def save_brief(brand: str, brief: dict):
    root = ensure_client_dirs(brand)
    path = root / "brief.json"
    existing = load_brief(brand) or {}
    existing.update(brief)
    existing["updated_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def load_brief(brand: str) -> Optional[dict]:
    path = client_path(brand) / "brief.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


# ─── Memory (client preferences, accumulated over time) ───────────────────────

def load_memory(brand: str) -> dict:
    path = client_path(brand) / "memory.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "brand": brand,
        "created_at": datetime.now().isoformat(),
        "tone_preferences": [],
        "approved_content_patterns": [],
        "rejected_content_patterns": [],
        "preferred_hooks": [],
        "disliked_words": [],
        "preferred_formats": [],
        "recording_day": None,
        "plan": "standard",
        "ig_avg_views": 0,
        "changes_log": [],
    }


def update_memory(brand: str, updates: dict):
    """Merge updates into client memory."""
    root = ensure_client_dirs(brand)
    mem = load_memory(brand)

    # List fields: append, don't overwrite
    list_fields = [
        "tone_preferences", "approved_content_patterns",
        "rejected_content_patterns", "preferred_hooks",
        "disliked_words", "preferred_formats", "changes_log",
    ]
    for field in list_fields:
        if field in updates:
            val = updates.pop(field)
            if isinstance(val, list):
                mem[field].extend(val)
            else:
                mem[field].append(val)

    # Scalar fields: direct update
    mem.update(updates)
    mem["updated_at"] = datetime.now().isoformat()

    path = root / "memory.json"
    path.write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")
    return mem


def log_client_feedback(brand: str, feedback: str, context: str = ""):
    """Record a client feedback or preference change."""
    update_memory(brand, {
        "changes_log": {
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback,
            "context": context,
        }
    })


# ─── Market Research ──────────────────────────────────────────────────────────

def save_market_research(brand: str, data: dict, week_label: str = None) -> str:
    root = ensure_client_dirs(brand)
    week = week_label or datetime.now().strftime("W%W_%Y")

    # Save weekly snapshot
    snapshot_path = root / "market_research" / "snapshots" / f"{week}.json"
    snapshot_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Update/create posts DB with incremental logic
    posts_db_path = root / "referents" / "posts_db.json"
    posts_db = {}
    if posts_db_path.exists():
        posts_db = json.loads(posts_db_path.read_text(encoding="utf-8"))

    for post in data.get("posts", []):
        pid = post.get("id") or post.get("url", "")
        if not pid:
            continue
        if pid in posts_db:
            # Update metrics only
            posts_db[pid]["views"] = post.get("views", posts_db[pid].get("views", 0))
            posts_db[pid]["comments"] = post.get("comments", posts_db[pid].get("comments", 0))
            posts_db[pid]["likes"] = post.get("likes", posts_db[pid].get("likes", 0))
            posts_db[pid]["metrics"] = post.get("metrics", {})
            posts_db[pid]["last_updated"] = datetime.now().isoformat()
        else:
            # New post
            post["first_seen"] = datetime.now().isoformat()
            post["last_updated"] = datetime.now().isoformat()
            posts_db[pid] = post

    posts_db_path.write_text(json.dumps(posts_db, ensure_ascii=False, indent=2), encoding="utf-8")

    # Save latest analysis text
    analysis_path = root / "market_research" / "latest.json"
    analysis_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return str(snapshot_path)


def load_referents_db(brand: str) -> dict:
    path = client_path(brand) / "referents" / "posts_db.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def load_latest_market_research(brand: str) -> Optional[dict]:
    path = client_path(brand) / "market_research" / "latest.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def clear_market_research(brand: str) -> dict:
    """Borra posts scrapeados, snapshots y último análisis del cliente."""
    root = client_path(brand)
    posts_db_path = root / "referents" / "posts_db.json"
    latest_path = root / "market_research" / "latest.json"
    snapshots_dir = root / "market_research" / "snapshots"
    cleared = {"posts_db": False, "latest": False, "snapshots": 0}
    if posts_db_path.exists():
        posts_db_path.write_text("{}", encoding="utf-8")
        cleared["posts_db"] = True
    if latest_path.exists():
        latest_path.unlink()
        cleared["latest"] = True
    if snapshots_dir.exists():
        for f in snapshots_dir.glob("*.json"):
            f.unlink()
            cleared["snapshots"] += 1
    return cleared


# ─── Content Calendar ─────────────────────────────────────────────────────────

def save_content_calendar(brand: str, calendar_data: dict, month: str) -> str:
    root = ensure_client_dirs(brand)
    month_slug = month.replace(" ", "_").lower()
    path = root / "content" / f"{month_slug}_calendar.json"
    path.write_text(json.dumps(calendar_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def load_content_calendar(brand: str, month: str) -> Optional[dict]:
    month_slug = month.replace(" ", "_").lower()
    path = client_path(brand) / "content" / f"{month_slug}_calendar.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def update_calendar_item_status(brand: str, month: str, item_id: str, updates: dict):
    """Update approval status, client choice, feedback on a calendar item."""
    cal = load_content_calendar(brand, month)
    if not cal:
        return None

    def _update_in_slots(slots):
        for slot in slots:
            if slot.get("id") == item_id:
                slot.update(updates)
                slot["updated_at"] = datetime.now().isoformat()
                return True
            for idea in slot.get("ideas", []):
                if idea.get("id") == item_id:
                    idea.update(updates)
                    idea["updated_at"] = datetime.now().isoformat()
                    return True
        return False

    _update_in_slots(cal.get("calendar", []))
    save_content_calendar(brand, cal, month)
    return cal


# ─── Scripts ──────────────────────────────────────────────────────────────────

def save_script(brand: str, script_data: dict, reel_id: str = None) -> str:
    root = ensure_client_dirs(brand)
    rid = reel_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    path = root / "scripts" / f"{rid}.json"

    # Keep version history if file exists
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        versions = existing.get("versions", [existing])
        script_data["versions"] = versions

    path.write_text(json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


# ─── Images ───────────────────────────────────────────────────────────────────

def save_image_meta(brand: str, filename: str, category: str, meta: dict) -> str:
    root = ensure_client_dirs(brand)
    meta_path = root / "images" / category / f"{filename}.meta.json"
    meta["filename"] = filename
    meta["category"] = category
    meta["analyzed_at"] = datetime.now().isoformat()
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(meta_path)


def load_images_for_category(brand: str, category: str) -> list:
    """Return all image metadata for a category, sorted by suitability."""
    img_dir = client_path(brand) / "images" / category
    if not img_dir.exists():
        return []
    metas = []
    for f in img_dir.glob("*.meta.json"):
        try:
            metas.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return metas


def find_best_image(brand: str, category: str, requirements: dict = None) -> Optional[dict]:
    """
    Find the best image for given requirements.
    requirements: {vibe, text_zone_needed, approved_only}
    """
    images = load_images_for_category(brand, category)
    if not images:
        return None

    if not requirements:
        return images[0] if images else None

    vibe = requirements.get("vibe", "")
    zone = requirements.get("text_zone_needed", "")

    scored = []
    for img in images:
        score = 0
        if vibe and vibe.lower() in img.get("vibe", "").lower():
            score += 2
        if zone:
            for block in img.get("text_blocks", []):
                if block.get("zone") == zone and block.get("available"):
                    score += 1
        scored.append((score, img))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1] if scored else None


# ─── Weekly state ─────────────────────────────────────────────────────────────

def save_weekly_state(brand: str, week: str, state: dict):
    root = ensure_client_dirs(brand)
    path = root / "weekly" / f"{week}.json"
    state["week"] = week
    state["updated_at"] = datetime.now().isoformat()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def load_weekly_state(brand: str, week: str) -> dict:
    path = client_path(brand) / "weekly" / f"{week}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"week": week, "stage": "not_started", "items": []}


# ─── Generic save ─────────────────────────────────────────────────────────────

def save_agent_output(brand: str, agent: str, data: dict, filename: str = None) -> str:
    """Generic save for any agent output."""
    root = ensure_client_dirs(brand)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = filename or f"{agent}_{ts}.json"
    path = root / agent if (root / agent).is_dir() else root
    path.mkdir(parents=True, exist_ok=True)
    out = path / fname
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)
