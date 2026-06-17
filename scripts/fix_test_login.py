#!/usr/bin/env python3
"""Restaura password_hash y campos base de cuentas de prueba sin borrar referentes."""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "rima_data.json"
PWD_HASH = "sha256:bf0ec3694e122e067d9964a38ec7d8415781df4b24f442ad767b4621fb98f8c5"

SPECS = [
    {"email": "basico@test.com", "name": "Primero Basico", "plan": "basico", "brand_name": "Negocio Básico"},
    {"email": "pro@test.com", "name": "Segundo Medio", "plan": "pro", "brand_name": "Negocio Pro"},
    {"email": "max@test.com", "name": "Tercero Superior", "plan": "max", "brand_name": "Negocio Max"},
]


def main() -> int:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8")) if DATA_FILE.exists() else {}
    users = data.setdefault("users", {})
    now = int(time.time())

    for spec in SPECS:
        u = users.setdefault(spec["email"], {})
        refs = len((u.get("referentes_profiles") or {}).get("instagram") or [])
        u["name"] = spec["name"]
        u["plan"] = spec["plan"]
        u["password_hash"] = PWD_HASH
        u["status"] = "active"
        u.setdefault("created_at", now)
        u.setdefault("referentes_profiles", {"instagram": [], "youtube": []})
        u.setdefault("scraping", {
            "manual_remaining": 3,
            "last_reset_week": None,
            "last_manual_scrape_at": None,
        })
        brand = u.setdefault("brand", {})
        brand.setdefault("brand_name", spec["brand_name"])
        brand.setdefault("plan", spec["plan"])
        brand.setdefault("enfoque_default", {"ventas": 60, "educacion": 30, "conexion": 10})
        print(f"OK  {spec['email']}  plan={spec['plan']}  referentes={refs}")

    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado en {DATA_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
