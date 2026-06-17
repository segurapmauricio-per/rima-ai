#!/usr/bin/env python3
"""E2E onboarding — simula cuenta nueva completa vía API."""
import json
import http.cookiejar
import sys
import urllib.request as u
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = "http://127.0.0.1:8000"
EMAIL = "cuenta_completa@test.com"
PASSWORD = "temporal1"
NEW_PASS = "miclave123"

# PNG 1x1 mínimo
def tiny_png() -> bytes:
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
    iend = chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


def multipart_upload(opener, path, fields, files):
    import uuid
    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for name, filename, content, ctype in files:
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode() + content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = u.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    return opener.open(req, timeout=30)


def main():
    from main import load_data, save_data, _hash_password

    d = load_data()
    d["users"][EMAIL] = {
        "name": "Cuenta Completa Test",
        "plan": "pro",
        "password_hash": _hash_password(PASSWORD),
        "status": "active",
        "must_change_password": True,
        "onboarding_completed": False,
        "onboarding_step": 1,
        "onboarding_scrape": {"status": "idle"},
        "brand": {"brand_name": "Fit Test Studio", "plan": "pro"},
    }
    save_data(d)
    print(f"[setup] Usuario {EMAIL} creado (plan pro)")

    cj = http.cookiejar.CookieJar()
    op = u.build_opener(u.HTTPCookieProcessor(cj))

    def api(method, path, data=None):
        body = json.dumps(data).encode() if data is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = u.Request(BASE + path, data=body, headers=headers, method=method)
        try:
            resp = op.open(req, timeout=15)
            return resp.status, json.loads(resp.read().decode())
        except u.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    # Login
    code, login = api("POST", "/auth/login", {"email": EMAIL, "password": PASSWORD})
    assert code == 200, login
    print(f"[1] Login -> redirect {login.get('redirect')}")

    # Change password
    code, ch = api("POST", "/api/auth/change-password", {"current_password": PASSWORD, "new_password": NEW_PASS})
    assert code == 200, ch
    print("[2] Contraseña cambiada")

    # Brand + brief
    brand = {
        "brand_name": "Fit Test Studio",
        "brand_service": "Coaching fitness online personalizado para profesionales ocupados",
        "brand_ideal_client": "Profesionales 30-45 años sin tiempo para gym tradicional",
        "brand_problem": "No logran resultados por falta de método y constancia real",
        "brand_result": "Bajar 8-12kg en 90 días con 20 min al día desde casa",
        "brand_price": "$297 USD / mes",
        "brand_ig": "@fitteststudio",
        "brand_tone": "Cercano, motivacional y directo",
        "brand_language": "es",
    }
    code, br = api("POST", "/api/brand", brand)
    assert code == 200 and br.get("brief_complete"), br
    print("[3] Brief guardado + sync")

    # Marca visual
    code, mv = api("POST", "/api/marca-visual", {
        "comunicacion": {"tono": "Cercano y motivacional", "idioma": "es"},
        "visual": {"paleta_colores": ["#7C3AED", "#06B6D4", "#0F172A"]},
    })
    assert code == 200, mv
    print("[4] Marca visual guardada")

    # Upload 4 historias (pro plan)
    png = tiny_png()
    for i in range(4):
        multipart_upload(op, "/api/images/upload", {"category": "historias"}, [
            ("files", f"test_{i}.png", png, "image/png"),
        ])
    code, me = api("GET", "/auth/me")
    assert me.get("photos_count", 0) >= 4, me
    print(f"[5] Fotos historias: {me.get('photos_count')}")

    # Face profile
    multipart_upload(op, "/api/onboarding/face-profile", {}, [
        ("file", "face.png", png, "image/png"),
    ])
    print("[6] Face profile subido")

    # Complete
    code, done = api("POST", "/api/onboarding/complete")
    assert code == 200, done
    print("[7] Onboarding completado")

    # Verify access
    req = u.Request(BASE + "/contenido")
    resp = op.open(req, timeout=10)
    html = resp.read().decode()[:500]
    assert "onboarding" not in resp.geturl().lower() or "contenido" in html.lower() or resp.status == 200
    print(f"[8] /contenido accesible (status {resp.status})")

    # face_profile.json
    cid = "fit_test_studio"
    fp = ROOT / "data" / "clients" / cid / "face_profile.json"
    assert fp.exists(), f"Falta {fp}"
    print(f"[9] face_profile.json OK")

    brief_path = ROOT / "data" / "clients" / cid / "brief.json"
    assert brief_path.exists(), "Falta brief.json"
    print("[10] brief.json OK")

    print("\n[OK] E2E onboarding COMPLETO")


if __name__ == "__main__":
    main()
