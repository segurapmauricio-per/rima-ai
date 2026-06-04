"""
Autenticacion JWT simple para RIMA AI.
- Un admin hardcodeado via env vars (RIMA_ADMIN_EMAIL / RIMA_ADMIN_PASSWORD)
- Cualquier usuario creado via Lemon Squeezy webhook
- Token JWT con 8h de expiracion
"""
import os
import time
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

SECRET_KEY = os.environ.get("RIMA_JWT_SECRET", "rima-dev-secret-change-in-prod-2024")
ALGORITHM  = "HS256"
TOKEN_TTL  = 8 * 3600  # 8 horas
COOKIE_NAME = "rima_token"

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Utilidades de token
# ---------------------------------------------------------------------------

def create_token(email: str, role: str = "user") -> str:
    payload = {
        "sub": email,
        "role": role,
        "exp": int(time.time()) + TOKEN_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Verificacion de credenciales
# ---------------------------------------------------------------------------

def verify_login(email: str, password: str, users_db: dict) -> Optional[dict]:
    """
    Verifica credenciales contra:
    1. Admin hardcodeado en env vars
    2. Usuarios en rima_data.json (creados via Lemon webhook)
    """
    admin_email    = os.environ.get("RIMA_ADMIN_EMAIL", "admin@rima.ai")
    admin_password = os.environ.get("RIMA_ADMIN_PASSWORD", "rima2024")

    # Admin
    if email == admin_email and password == admin_password:
        return {"email": email, "role": "admin", "name": "Admin"}

    # Usuarios del JSON
    user = users_db.get(email)
    if user and user.get("status") == "active":
        stored_hash = user.get("password_hash", "")
        if stored_hash and pwd_ctx.verify(password, stored_hash):
            return {"email": email, "role": "user", "name": user.get("name", email)}
        # Compatibilidad: si no tiene hash todavia (creado via webhook sin password)
        # se permite login con password = email (temporal, se fuerza cambio)
        if not stored_hash and password == email:
            return {"email": email, "role": "user", "name": user.get("name", email)}

    return None


# ---------------------------------------------------------------------------
# Middleware / dependencia de proteccion
# ---------------------------------------------------------------------------

def get_current_user(request: Request) -> dict:
    """Dependencia FastAPI — lanza 401 si no hay token valido."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido o expirado",
        )
    return payload


def require_auth(request: Request) -> Optional[RedirectResponse]:
    """
    Para rutas HTML — redirige a /login si no hay sesion activa.
    Uso: redirect = require_auth(request); if redirect: return redirect
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token or not decode_token(token):
        return RedirectResponse(url="/login", status_code=302)
    return None
