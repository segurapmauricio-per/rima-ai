#!/usr/bin/env python3
"""Crea 3 usuarios de prueba (básico / pro / max) con contraseña 'uno'."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "rima_data.json"
PWD_HASH = "sha256:bf0ec3694e122e067d9964a38ec7d8415781df4b24f442ad767b4621fb98f8c5"

USERS = [
    {
        "email": "basico@test.com",
        "name": "Primero Basico",
        "plan": "basico",
        "brand_name": "Negocio Básico",
    },
    {
        "email": "pro@test.com",
        "name": "Segundo Medio",
        "plan": "pro",
        "brand_name": "Negocio Pro",
    },
    {
        "email": "max@test.com",
        "name": "Tercero Superior",
        "plan": "max",
        "brand_name": "Negocio Max",
    },
]


def main():
    data = {}
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    users = data.setdefault("users", {})
    now = int(time.time())

    for spec in USERS:
        users[spec["email"]] = {
            "name": spec["name"],
            "plan": spec["plan"],
            "password_hash": PWD_HASH,
            "status": "active",
            "created_at": now,
            "brand": {
                "brand_name": spec["brand_name"],
                "brand_service": "Coaching fitness online",
                "brand_ideal_client": "Profesionales 30-45 años",
                "brand_problem": "No tienen tiempo para entrenar",
                "brand_result": "Rutina de 20 min en casa",
                "plan": spec["plan"],
                "enfoque_default": {"ventas": 60, "educacion": 30, "conexion": 10},
            },
            "referentes_profiles": {"instagram": [], "youtube": []},
            "scraping": {
                "manual_remaining": 3,
                "last_reset_week": None,
                "last_manual_scrape_at": None,
            },
        }
        print(f"OK  {spec['email']}  plan={spec['plan']}  pass=uno")

    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGuardado en {DATA_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
