#!/usr/bin/env python3
"""
Prueba el popup de descubrimiento de referentes (día 3+).

Modos:
  --mock     Inyecta sugerencias falsas ya verificadas → popup al instante en el navegador.
  --reset    Deja al usuario elegible (created_at hace 4 días) con discovery en pending.
  --api      Login + poll de GET /api/referentes/discovery (servidor en marcha).
  --real     Igual que --reset; la generación real ocurre al abrir el dashboard.

Uso típico (UI sin Apify/Gemini):
  python scripts/test_referentes_discovery.py --mock
  # Abrí http://127.0.0.1:8000/home con pro@test.com / uno

Flujo real (Apify + Gemini):
  python scripts/test_referentes_discovery.py --reset
  uvicorn main:app --reload
  # Login → /home y esperá ~15–40 s (el front reintenta cada 4 s)
"""
from __future__ import annotations

import argparse
import json
import http.cookiejar
import sys
import time
import urllib.error
import urllib.request as u
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = "http://127.0.0.1:8000"
DEFAULT_EMAIL = "pro@test.com"
DEFAULT_PASSWORD = "uno"
PWD_HASH = "sha256:bf0ec3694e122e067d9964a38ec7d8415781df4b24f442ad767b4621fb98f8c5"

from core.referentes_discovery_preview import get_preview_suggestions, PREVIEW_SUGGESTIONS


def _backdated_created_at(days_ago: float = 4.0) -> int:
    return int(time.time() - days_ago * 86400)


def _ensure_user(data: dict, email: str) -> dict:
    users = data.setdefault("users", {})
    rec = users.setdefault(email, {})
    rec.setdefault("name", email.split("@")[0].title())
    rec.setdefault("plan", "pro")
    rec.setdefault("password_hash", PWD_HASH)
    rec.setdefault("status", "active")
    rec.setdefault("onboarding_completed", True)
    rec.setdefault("referentes_profiles", {"instagram": [], "youtube": []})
    rec.setdefault("brand", {
        "brand_name": "Negocio Pro",
        "brand_service": "Coaching fitness online personalizado",
        "brand_ideal_client": "Profesionales 30-45 años sin tiempo",
        "brand_problem": "No logran constancia ni resultados",
        "brand_result": "Rutina de 20 min desde casa",
        "brand_ig": "@negociopro",
        "plan": "pro",
    })
    return rec


def _quiet_modals(rec: dict) -> None:
    """Evita que tour o activación tapen el popup de referentes."""
    rec["dashboard_tour"] = {"seen_count": 2, "dismissed": True}
    rec["activation_flow"] = {
        "status": "skipped",
        "step": 4,
        "referentes_confirmed": True,
        "market_done": True,
        "calendar_done": True,
        "weekly_done": True,
    }


def setup_mock(data: dict, email: str) -> dict:
    from core.activation_flow import save_referentes_discovery_result, mark_referentes_anchor_ready

    rec = _ensure_user(data, email)
    rec["created_at"] = _backdated_created_at(4)
    _quiet_modals(rec)
    refs = rec.setdefault("referentes_profiles", {"instagram": [], "youtube": []})
    if not refs.get("instagram"):
        refs["instagram"] = [{
            "id": "mock-anchor-1",
            "username": "coach_ejemplo",
            "nombre_nicho": "Coach Ejemplo · fitness",
            "estado": "activo",
        }]
    mark_referentes_anchor_ready(rec)
    state = save_referentes_discovery_result(rec, [dict(s) for s in PREVIEW_SUGGESTIONS])
    return state


def setup_reset(data: dict, email: str) -> dict:
    from core.activation_flow import get_referentes_discovery_state, mark_referentes_anchor_ready

    rec = _ensure_user(data, email)
    rec["created_at"] = _backdated_created_at(4)
    _quiet_modals(rec)
    rec["referentes_discovery"] = {
        "status": "pending",
        "suggestions": [],
        "generated_at": None,
        "anchor_at": None,
    }
    refs = rec.setdefault("referentes_profiles", {"instagram": [], "youtube": []})
    if not refs.get("instagram"):
        refs["instagram"] = [{
            "id": "mock-anchor-1",
            "username": "coach_ejemplo",
            "nombre_nicho": "Coach Ejemplo",
            "estado": "activo",
        }]
    mark_referentes_anchor_ready(rec)
    return get_referentes_discovery_state(rec, len(refs.get("instagram") or []))


def api_login(email: str, password: str):
    cj = http.cookiejar.CookieJar()
    op = u.build_opener(u.HTTPCookieProcessor(cj))

    def call(method: str, path: str, body: dict | None = None):
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        req = u.Request(BASE + path, data=payload, headers=headers, method=method)
        try:
            resp = op.open(req, timeout=60)
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
        except u.HTTPError as e:
            raw = e.read().decode()
            try:
                detail = json.loads(raw)
            except json.JSONDecodeError:
                detail = {"detail": raw}
            return e.code, detail

    code, login = call("POST", "/auth/login", {"email": email, "password": password})
    if code != 200:
        raise RuntimeError(f"Login falló ({code}): {login}")
    return call


def poll_discovery(call, timeout_sec: int = 120, interval: float = 4.0) -> dict:
    deadline = time.time() + timeout_sec
    last = {}
    while time.time() < deadline:
        code, state = call("GET", "/api/referentes/discovery")
        if code != 200:
            raise RuntimeError(f"Discovery API ({code}): {state}")
        last = state
        status = state.get("status")
        print(f"  status={status}  eligible={state.get('eligible')}  "
              f"suggestions={len(state.get('suggestions') or [])}  "
              f"should_show_popup={state.get('should_show_popup')}")
        if status in ("ready", "empty", "shown"):
            return state
        if status == "running":
            time.sleep(interval)
            continue
        if status == "pending" and state.get("should_generate"):
            time.sleep(interval)
            continue
        return state
    return last


def print_instructions(email: str, password: str, mode: str) -> None:
    print()
    print("== Como ver el popup ==")
    print(f"  1. Servidor: uvicorn main:app --reload  (si no está corriendo)")
    print(f"  2. Login:    {email} / {password}")
    print(f"  3. Abri:     {BASE}/home")
    print("     o click en \"Ver popup referentes\" (esquina inferior derecha)")
    print(f"     o URL:     {BASE}/home?preview_discovery=1")
    print()
    if mode == "mock":
        print("  El popup deberia aparecer en ~1-2 s (sin tour ni activacion).")
        print("  Titulo: \"RIMA encontro referentes para vos\"")
    else:
        print("  El front hace poll cada 4 s mientras status=running.")
        print("  Con APIFY_API_TOKEN + Vertex/Gemini puede tardar 15-40 s.")
    print()
    print("== Que muestra el popup ==")
    print("  - Overlay oscuro con blur (z-index 99965)")
    print("  - Card #12121C, borde cyan, max 480px")
    print("  - Filas: avatar 40px | @usuario (link a IG) + motivo | checkbox violeta")
    print("  - Boton gradiente violeta->cyan \"Agregar seleccionados\"")
    print("  - Link \"Ahora no\" -> dismiss sin agregar referentes")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba popup descubrimiento referentes (día 3+)")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help=f"Usuario (default: {DEFAULT_EMAIL})")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Contraseña (default: uno)")
    parser.add_argument("--mock", action="store_true", help="Sugerencias mock listas (sin Apify/Gemini)")
    parser.add_argument("--reset", action="store_true", help="Elegible + discovery pending (generación real)")
    parser.add_argument("--api", action="store_true", help="Login y poll del endpoint discovery")
    parser.add_argument("--timeout", type=int, default=120, help="Segundos máx. en --api")
    args = parser.parse_args()

    if not any((args.mock, args.reset, args.api)):
        args.mock = True

    from main import load_data, save_data

    data = load_data()
    email = args.email.strip().lower()

    if args.mock:
        state = setup_mock(data, email)
        save_data(data)
        print(f"[mock] {email}")
        print(f"  created_at -> hace ~4 dias ({datetime.fromtimestamp(_backdated_created_at(4)).isoformat()})")
        print(f"  referentes_discovery.status = {state.get('status')}")
        print(f"  suggestions = {len(state.get('suggestions') or [])}")
        print(f"  should_show_popup = {state.get('should_show_popup')}")
        print_instructions(email, args.password, "mock")

    if args.reset:
        state = setup_reset(data, email)
        save_data(data)
        print(f"[reset] {email}")
        print(f"  created_at -> hace ~4 dias")
        print(f"  referentes_discovery.status = {state.get('status')}")
        print(f"  should_generate = {state.get('should_generate')}")
        print_instructions(email, args.password, "reset")

    if args.api:
        print(f"[api] Login {email} -> poll discovery (timeout {args.timeout}s)")
        try:
            call = api_login(email, args.password)
        except (urllib.error.URLError, RuntimeError) as e:
            print(f"ERROR: {e}")
            print("¿Está corriendo uvicorn main:app en el puerto 8000?")
            return 1
        final = poll_discovery(call, timeout_sec=args.timeout)
        print()
        print("Resultado final:")
        print(json.dumps({
            "status": final.get("status"),
            "should_show_popup": final.get("should_show_popup"),
            "suggestions_count": len(final.get("suggestions") or []),
            "usernames": [s.get("username") for s in (final.get("suggestions") or [])],
        }, ensure_ascii=False, indent=2))
        if final.get("should_show_popup"):
            print_instructions(email, args.password, "api")
        elif final.get("status") == "empty":
            print("\nSin perfiles verificados (Gemini/Apify no devolvió coincidencias).")
        elif final.get("status") == "running":
            print("\nTimeout: sigue en running. Revisá logs del servidor y APIFY_API_TOKEN.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
