from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Header, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from typing import Any, List, Optional
import uvicorn
import json
import os
import shutil
import time
import hmac
import hashlib
import secrets
import uuid
import calendar as cal_module
import re
import urllib.request
import asyncio
import smtplib
from email.message import EmailMessage
from datetime import datetime

from core.auth import (
    verify_login, create_token, require_auth, get_current_user, COOKIE_NAME,
    get_or_create_google_user, decode_token, _hash_password,
)

from dotenv import load_dotenv
load_dotenv(override=True)

from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth

from agents.landing.agent import landing_agent
from agents.content.agent import content_agent
from agents.meta.agent import meta_agent
from agents.sales.agent import sales_agent
from agents.prospecting.agent import prospecting_agent
from agents.market_research.agent import market_research_agent
from agents.script.agent import script_agent
from agents.weekly.agent import weekly_agent
from agents.image_analysis.agent import image_analysis_agent
from agents.story_copy.agent import story_copy_agent
from agents.carousel_copy.agent import carousel_copy_agent
from agents.reel_copy.agent import reel_copy_agent
from agents.weekly.agent import weekly_agent
from core.client_store import (
    save_brief, load_brief, load_memory, update_memory,
    ensure_client_dirs, load_weekly_state, save_weekly_state, clear_weekly_state,
    load_latest_market_research, clear_market_research,
)
from core.referentes_store import (
    get_profiles, add_profile, update_profile, delete_profile,
    consume_manual_scrape, reset_manual_scrape_after_weekly,
    get_user_brand, set_user_brand, get_user_plan, cliente_id_from_brand,
    active_ig_usernames, sync_ig_profiles_from_meta,
)
from core.plan_limits import get_ref_limits, normalize_plan, MANUAL_SCRAPE_CREDITS

app = FastAPI(title="RIMA AI", description="Marketing AI para LATAM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET", "rima-session-dev-secret"),
)

_oauth = OAuth()
_oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

DASHBOARD   = Path(__file__).parent / "dashboard"
DATA_FILE   = Path(__file__).parent / "data" / "rima_data.json"
UPLOADS_DIR = Path(__file__).parent / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
(UPLOADS_DIR / "historias").mkdir(exist_ok=True)
(UPLOADS_DIR / "carruseles").mkdir(exist_ok=True)
(UPLOADS_DIR / "clips").mkdir(exist_ok=True)
(UPLOADS_DIR / "finals").mkdir(exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
# Persistencia local en JSON
# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

ENFOQUE_RECOMENDADO = {"ventas": 60, "educacion": 30, "conexion": 10}
ENFOQUE_LEGACY = {"ventas": 70, "educacion": 20, "conexion": 10}


def normalize_enfoque_default(enfoque: Optional[dict] = None) -> dict:
    """Devuelve el enfoque guardado o el recomendado (60/30/10). Migra el legacy 70/20/10."""
    if not enfoque:
        return dict(ENFOQUE_RECOMENDADO)
    try:
        v = int(enfoque.get("ventas", ENFOQUE_RECOMENDADO["ventas"]))
        e = int(enfoque.get("educacion", ENFOQUE_RECOMENDADO["educacion"]))
        c = int(enfoque.get("conexion", ENFOQUE_RECOMENDADO["conexion"]))
    except (TypeError, ValueError):
        return dict(ENFOQUE_RECOMENDADO)
    if v == ENFOQUE_LEGACY["ventas"] and e == ENFOQUE_LEGACY["educacion"] and c == ENFOQUE_LEGACY["conexion"]:
        return dict(ENFOQUE_RECOMENDADO)
    return {"ventas": v, "educacion": e, "conexion": c}


def load_data() -> dict:
    DATA_FILE.parent.mkdir(exist_ok=True)
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_data(data: dict):
    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
# CSS compartido inyectado en <head>
# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

SIDEBAR_HTML = """<aside id="rima-sidebar" style="width:240px;min-width:240px;flex-shrink:0;display:flex;flex-direction:column;height:100%;min-height:0;align-self:stretch;background:rgba(15,15,25,0.97);border-right:1px solid rgba(255,255,255,0.07);overflow:hidden">
  <div style="padding:16px 18px;border-bottom:1px solid rgba(255,255,255,0.06);display:flex;align-items:center;gap:10px;flex-shrink:0">
    <div style="width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#7C3AED,#6D28D9);display:flex;align-items:center;justify-content:center;flex-shrink:0">
      <svg style="width:16px;height:16px;color:#fff" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/></svg>
    </div>
    <div><p style="font-size:15px;font-weight:700;background:linear-gradient(135deg,#7C3AED,#06B6D4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin:0">RIMA</p>
    <p style="font-size:9px;color:#475569;margin:0">Marketing AI · LATAM</p></div>
  </div>
  <div style="padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.06);flex-shrink:0">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <div style="width:34px;height:34px;border-radius:50%;padding:2px;background:linear-gradient(135deg,#7C3AED,#06B6D4);flex-shrink:0">
        <div style="width:100%;height:100%;border-radius:50%;background:linear-gradient(135deg,#f43f5e,#fb923c,#fbbf24);display:flex;align-items:center;justify-content:center">
          <span id="rima-initials" style="font-size:11px;font-weight:700;color:#fff">FL</span>
        </div>
      </div>
      <div><p id="rima-brand-name" style="font-size:12px;font-weight:600;color:#fff;margin:0">FitLife Studio</p>
      <p id="rima-brand-handle" style="font-size:10px;color:#475569;margin:0">@fitlifestudio_mx</p></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px">
      <div style="border-radius:8px;padding:5px;text-align:center;background:rgba(124,58,237,0.1);border:1px solid rgba(124,58,237,0.2)"><p style="font-size:11px;font-weight:700;color:#A78BFA;margin:0">12.4K</p><p style="font-size:8px;color:#475569;margin:0">Seg.</p></div>
      <div style="border-radius:8px;padding:5px;text-align:center;background:rgba(6,182,212,0.1);border:1px solid rgba(6,182,212,0.2)"><p style="font-size:11px;font-weight:700;color:#22D3EE;margin:0">48</p><p style="font-size:8px;color:#475569;margin:0">Msg.</p></div>
      <div style="border-radius:8px;padding:5px;text-align:center;background:rgba(52,211,153,0.1);border:1px solid rgba(52,211,153,0.2)"><p style="font-size:11px;font-weight:700;color:#34D399;margin:0">$18K</p><p style="font-size:8px;color:#475569;margin:0">Ventas</p></div>
    </div>
  </div>
  <nav id="rima-nav" style="flex:1 1 auto;min-height:0;padding:10px;overflow-y:auto;scrollbar-width:none"></nav>
  <div id="rima-user-bar" style="position:relative;padding:8px 10px;border-top:1px solid rgba(255,255,255,0.06);flex-shrink:0">
    <div style="display:flex;align-items:center;gap:6px">
      <button type="button" id="rima-user-trigger" style="flex:1;min-width:0;display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:10px;border:1px solid transparent;background:transparent;cursor:pointer;text-align:left;transition:background .15s">
        <div style="width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);display:flex;align-items:center;justify-content:center;flex-shrink:0">
          <span id="rima-user-initials" style="font-size:11px;font-weight:700;color:#CBD5E1">—</span>
        </div>
        <div style="flex:1;min-width:0">
          <p id="rima-user-name" style="font-size:11px;font-weight:600;color:#E2E8F0;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3">Cargando…</p>
          <p id="rima-user-plan" style="font-size:10px;color:#64748B;margin:2px 0 0;line-height:1.2">Plan —</p>
        </div>
        <svg id="rima-user-chevron" style="width:14px;height:14px;color:#475569;flex-shrink:0;transition:transform .15s" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 15L12 18.75 15.75 15"/></svg>
      </button>
      <button type="button" id="rima-user-settings" title="Cerrar sesión" style="width:32px;height:32px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;transition:background .15s">
        <svg style="width:14px;height:14px;color:#94A3B8" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
      </button>
    </div>
    <div id="rima-user-menu" style="display:none;position:absolute;bottom:calc(100% + 6px);left:8px;right:8px;background:#14141F;border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:6px;box-shadow:0 -8px 32px rgba(0,0,0,0.45);z-index:200">
      <div style="padding:8px 10px 6px;border-bottom:1px solid rgba(255,255,255,0.06);margin-bottom:4px">
        <p id="rima-user-menu-email" style="font-size:11px;color:#94A3B8;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">—</p>
        <p id="rima-user-menu-plan" style="font-size:10px;color:#64748B;margin:4px 0 0">—</p>
      </div>
      <a href="/auth/logout" style="display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;font-size:11px;color:#F87171;text-decoration:none;transition:background .12s">
        <svg style="width:13px;height:13px" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9"/></svg>
        Cerrar sesión
      </a>
    </div>
  </div>
</aside>"""

SHARED_CSS = """
<style id="rima-shared">
  /* Layout base */
  html { zoom: 1.1; }
  body { display:flex !important; height:calc(100vh / 1.1) !important; overflow:hidden !important; font-size: 13px !important; }
  #rima-sidebar { flex-shrink:0 !important; width:240px !important; min-width:240px !important;
    display:flex !important; flex-direction:column !important; height:100% !important; min-height:0 !important; align-self:stretch !important; overflow:hidden !important; }
  #rima-nav { flex:1 1 auto !important; min-height:0 !important; overflow-y:auto !important; }
  #rima-user-bar { flex-shrink:0 !important; z-index:50 !important; background:rgba(15,15,25,0.97) !important; font-size:11px !important; }
  #rima-user-name { font-size:11px !important; font-weight:600 !important; color:#E2E8F0 !important; }
  #rima-user-plan { font-size:10px !important; color:#64748B !important; }
  #rima-user-initials { font-size:11px !important; font-weight:700 !important; }
  #rima-user-menu-email { font-size:11px !important; }
  #rima-user-menu-plan { font-size:10px !important; }
  #rima-user-menu a { font-size:11px !important; }
  body > main, body > .flex-1 { flex:1 !important; min-width:0 !important; min-height:0 !important; overflow:hidden !important; display:flex !important; flex-direction:column !important; }
  main > div[class*="overflow-y-auto"], main > .flex-1 { flex:1 !important; min-height:0 !important; overflow-y:auto !important; }
  aside nav span { font-size: 11px !important; }
  #rima-nav p { font-size: 9px !important; }
  #rima-sidebar > div:not(#rima-user-bar) p { font-size: 9px !important; }
  #rima-brand-name { font-size: 12px !important; font-weight: 600 !important; }
  #rima-brand-handle { font-size: 10px !important; }
  input, textarea, select { font-size: 12px !important; font-family: 'Inter', sans-serif !important; }
  button { font-family: 'Inter', sans-serif !important; }

  /* Toast global */
  #rima-toast {
    position: fixed; bottom: 24px; right: 24px; z-index: 99999;
    display: flex; align-items: center; gap: 10px;
    padding: 12px 18px; border-radius: 14px;
    font-size: 12px; font-weight: 600; font-family: 'Inter', sans-serif;
    color: #fff; pointer-events: none;
    transform: translateY(80px); opacity: 0;
    transition: all .35s cubic-bezier(.34,1.56,.64,1);
    background: linear-gradient(135deg,#7C3AED,#6D28D9);
    border: 1px solid rgba(124,58,237,0.5);
    box-shadow: 0 8px 32px rgba(124,58,237,0.35);
  }
  #rima-toast.show { transform: translateY(0); opacity: 1; }
  #rima-toast.error { background: linear-gradient(135deg,#DC2626,#991B1B); border-color: rgba(220,38,38,0.5); box-shadow: 0 8px 32px rgba(220,38,38,0.35); }

  /* User bar (footer sidebar) */
  #rima-user-trigger:hover { background: rgba(255,255,255,0.05) !important; }
  #rima-user-settings:hover { background: rgba(255,255,255,0.08) !important; border-color: rgba(124,58,237,0.3) !important; }
  #rima-user-menu.open { display: block !important; }
  #rima-user-menu a:hover { background: rgba(255,255,255,0.06); }
  #rima-user-bar.menu-open #rima-user-chevron { transform: rotate(180deg); }
</style>
"""

# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
# JS universal inyectado al final del <body>
# â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€

SHARED_JS = """
<div id="rima-toast"></div>
<script>
(function() {
  var currentPath = window.location.pathname;

  // â"€â"€ Sidebar estandarizado (reemplaza el de cada pÃ¡gina) â"€â"€
  var NAV_ITEMS = [
    { label:'Dashboard',             href:'/home',         group:'COMENCEMOS', color:'violet',  icon:'M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25A2.25 2.25 0 0113.5 8.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z' },
    { label:'Calendario',            href:'/calendario',   group:'COMENCEMOS', color:'violet',  icon:'M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5' },
    { label:'Contenido',             href:'/contenido',    group:'COMENCEMOS', color:'pink',    icon:'M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z' },
    { label:'Estudio de mercado',    href:'/mercado',      group:'COMENCEMOS', color:'sky',     icon:'M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z' },
    { label:'META Ads',              href:'/meta',         group:'COMENCEMOS', color:'blue',    icon:'M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z', filled:true },
    { label:'Ventas',                href:'/ventas',       group:'COMENCEMOS', color:'emerald', icon:'M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941' },
    { label:'Landing',               href:'/landing',      group:'COMENCEMOS', color:'amber',   icon:'M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z' },
    { label:'InformaciÃ³n de la marca', href:'/marca',      group:'MI NEGOCIO', color:'violet',  icon:'M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z' },
    { label:'Referencias',           href:'/referencias',  group:'MI NEGOCIO', color:'rose',    icon:'M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244' },
    { label:'ImÃ¡genes',              href:'/imagenes',     group:'MI NEGOCIO', color:'cyan',    icon:'M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z' },
    { label:'Videos',                href:'/videos',       group:'MI NEGOCIO', color:'orange',  icon:'M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z' },
    { label:'Credenciales',          href:'/credenciales', group:'MI NEGOCIO', color:'slate',   icon:'M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z', badge:'amber' },
  ];

  var COLOR_MAP = {
    violet:  'rgba(124,58,237,0.15)',
    pink:    'rgba(236,72,153,0.15)',
    sky:     'rgba(14,165,233,0.15)',
    blue:    'rgba(59,130,246,0.15)',
    emerald: 'rgba(52,211,153,0.15)',
    amber:   'rgba(245,158,11,0.15)',
    rose:    'rgba(244,63,94,0.15)',
    cyan:    'rgba(6,182,212,0.15)',
    orange:  'rgba(249,115,22,0.15)',
    slate:   'rgba(100,116,139,0.15)',
  };
  var TEXT_COLOR_MAP = {
    violet:'#A78BFA', pink:'#F472B6', sky:'#38BDF8', blue:'#60A5FA',
    emerald:'#34D399', amber:'#FBBF24', rose:'#FB7185', cyan:'#22D3EE',
    orange:'#FB923C', slate:'#94A3B8',
  };

  function buildNavItem(item) {
    var isActive = item.href === currentPath || (item.href !== '/' && currentPath.startsWith(item.href));
    var bg = isActive
      ? 'background:linear-gradient(135deg,rgba(124,58,237,0.18),rgba(6,182,212,0.08));border-color:rgba(124,58,237,0.45)'
      : 'background:transparent;border-color:transparent';
    var textColor = isActive ? 'color:#fff;font-weight:600' : 'color:#94A3B8;font-weight:400';
    var iconBg = COLOR_MAP[item.color] || 'rgba(124,58,237,0.15)';
    var iconColor = TEXT_COLOR_MAP[item.color] || '#A78BFA';

    var svgContent = item.filled
      ? '<svg style="width:10px;height:10px;color:'+iconColor+'" fill="currentColor" viewBox="0 0 24 24"><path d="'+item.icon+'"/></svg>'
      : '<svg style="width:10px;height:10px;color:'+iconColor+'" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="'+item.icon+'"/></svg>';

    var badge = item.badge
      ? '<span style="margin-left:auto;width:6px;height:6px;border-radius:50%;background:#FBBF24;flex-shrink:0"></span>'
      : '';

    var el = document.createElement('div');
    el.style.cssText = 'display:flex;align-items:center;gap:10px;padding:7px 12px;border-radius:10px;border:1px solid;cursor:pointer;transition:all .18s;' + bg;
    if (isActive) el.dataset.active = '1';
    el.innerHTML = '<div style="width:20px;height:20px;border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0;background:'+iconBg+'">'+svgContent+'</div>'
      + '<span style="font-size:11px;'+textColor+';white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+item.label+'</span>'
      + badge;
    el.addEventListener('click', function() { window.location.href = item.href; });
    el.addEventListener('mouseover', function() { if (!this.dataset.active) this.style.background = 'rgba(255,255,255,0.05)'; });
    el.addEventListener('mouseout',  function() { if (!this.dataset.active) this.style.background = 'transparent'; });
    return el;
  }

  function buildSidebar() {
    var sidebar = document.createElement('aside');
    sidebar.id = 'rima-sidebar';
    sidebar.style.cssText = 'width:240px;min-width:240px;display:flex;flex-direction:column;height:100vh;background:rgba(255,255,255,0.03);border-right:1px solid rgba(255,255,255,0.06);backdrop-filter:blur(12px);flex-shrink:0';

    // Logo header
    sidebar.innerHTML =
      '<div style="padding:16px 18px;border-bottom:1px solid rgba(255,255,255,0.05);display:flex;align-items:center;gap:10px;flex-shrink:0">'
      + '<div style="width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#7C3AED,#6D28D9);display:flex;align-items:center;justify-content:center;box-shadow:0 0 20px rgba(124,58,237,.25);flex-shrink:0">'
      + '<svg style="width:16px;height:16px;color:#fff" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/></svg>'
      + '</div>'
      + '<div><p style="font-size:15px;font-weight:700;background:linear-gradient(135deg,#7C3AED,#06B6D4);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1.2;margin:0">RIMA</p>'
      + '<p style="font-size:9px;color:#475569;margin:0">Marketing AI Â· LATAM</p></div>'
      + '</div>'
      // Profile
      + '<div style="padding:12px 14px;border-bottom:1px solid rgba(255,255,255,0.05);flex-shrink:0">'
      + '<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
      + '<div style="width:36px;height:36px;border-radius:50%;padding:2px;background:linear-gradient(135deg,#7C3AED,#06B6D4);flex-shrink:0">'
      + '<div style="width:100%;height:100%;border-radius:50%;background:linear-gradient(135deg,#f43f5e,#fb923c,#fbbf24);display:flex;align-items:center;justify-content:center">'
      + '<span id="rima-initials" style="font-size:11px;font-weight:700;color:#fff">FL</span>'
      + '</div></div>'
      + '<div style="min-width:0">'
      + '<p id="rima-brand-name" style="font-size:12px;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:0">FitLife Studio</p>'
      + '<p id="rima-brand-handle" style="font-size:10px;color:#475569;margin:0">@fitlifestudio_mx</p>'
      + '</div></div>'
      + '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px">'
      + '<div style="border-radius:8px;padding:5px;text-align:center;background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.15)"><p style="font-size:11px;font-weight:700;color:#A78BFA;margin:0">12.4K</p><p style="font-size:8px;color:#475569;margin:0">Seg.</p></div>'
      + '<div style="border-radius:8px;padding:5px;text-align:center;background:rgba(6,182,212,0.08);border:1px solid rgba(6,182,212,0.15)"><p style="font-size:11px;font-weight:700;color:#22D3EE;margin:0">48</p><p style="font-size:8px;color:#475569;margin:0">Msg.</p></div>'
      + '<div style="border-radius:8px;padding:5px;text-align:center;background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.15)"><p style="font-size:11px;font-weight:700;color:#34D399;margin:0">$18K</p><p style="font-size:8px;color:#475569;margin:0">Ventas</p></div>'
      + '</div></div>';

    // Nav
    var nav = document.createElement('nav');
    nav.style.cssText = 'flex:1;padding:10px;overflow-y:auto;scrollbar-width:none';

    var groups = {}, groupOrder = [];
    NAV_ITEMS.forEach(function(item) {
      if (!groups[item.group]) { groups[item.group] = []; groupOrder.push(item.group); }
      groups[item.group].push(item);
    });
    groupOrder.forEach(function(g) {
      var section = document.createElement('div');
      section.style.cssText = 'margin-bottom:12px';
      var label = document.createElement('p');
      label.style.cssText = 'font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:#334155;font-weight:700;padding:0 8px;margin:0 0 4px 0';
      label.textContent = g;
      section.appendChild(label);
      var list = document.createElement('div');
      list.style.cssText = 'display:flex;flex-direction:column;gap:2px';
      groups[g].forEach(function(item) { list.appendChild(buildNavItem(item)); });
      section.appendChild(list);
      nav.appendChild(section);
    });
    sidebar.appendChild(nav);

    // Footer
    var footer = document.createElement('div');
    footer.style.cssText = 'padding:10px 14px;border-top:1px solid rgba(255,255,255,0.05);display:flex;align-items:center;gap:10px;flex-shrink:0';
    footer.innerHTML =
      '<div style="width:28px;height:28px;border-radius:50%;padding:1.5px;background:linear-gradient(135deg,#7C3AED,#06B6D4);flex-shrink:0">'
      + '<div style="width:100%;height:100%;border-radius:50%;background:linear-gradient(135deg,#f43f5e,#fb923c,#fbbf24);display:flex;align-items:center;justify-content:center">'
      + '<span id="rima-initials-footer" style="font-size:9px;font-weight:700;color:#fff">FL</span>'
      + '</div></div>'
      + '<div style="flex:1;min-width:0">'
      + '<p id="rima-brand-footer" style="font-size:11px;font-weight:600;color:#CBD5E1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:0">FitLife Studio</p>'
      + '<div style="display:flex;align-items:center;gap:4px"><div style="width:6px;height:6px;border-radius:50%;background:#34D399"></div>'
      + '<p style="font-size:9px;color:#475569;margin:0">Plan Pro</p></div>'
      + '</div>';
    var settingsBtn = document.createElement('button');
    settingsBtn.style.cssText = 'width:26px;height:26px;border-radius:8px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0';
    settingsBtn.innerHTML = '<svg style="width:12px;height:12px;color:#64748B" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>';
    settingsBtn.addEventListener('click', function() { window.location.href = '/marca'; });
    footer.appendChild(settingsBtn);
    sidebar.appendChild(footer);
    return sidebar;
  }

  // Poblar el nav del sidebar (Python ya lo inyecta en serve_html — no duplicar)
  function initSidebar() {
    var nav = document.getElementById('rima-nav');
    if (!nav) return;
    if (nav.dataset.rimaBuilt === '1' || nav.children.length > 0) return;

    var groups = {}, groupOrder = [];
    NAV_ITEMS.forEach(function(item) {
      if (!groups[item.group]) { groups[item.group] = []; groupOrder.push(item.group); }
      groups[item.group].push(item);
    });
    groupOrder.forEach(function(g) {
      var section = document.createElement('div');
      section.style.cssText = 'margin-bottom:12px';
      var label = document.createElement('p');
      label.style.cssText = 'font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:#334155;font-weight:700;padding:0 8px;margin:0 0 4px 0';
      label.textContent = g;
      section.appendChild(label);
      var list = document.createElement('div');
      list.style.cssText = 'display:flex;flex-direction:column;gap:2px';
      groups[g].forEach(function(item) { list.appendChild(buildNavItem(item)); });
      section.appendChild(list);
      nav.appendChild(section);
    });
    nav.dataset.rimaBuilt = '1';
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSidebar);
  } else {
    initSidebar();
  }

  // â"€â"€ Toast helper â"€â"€
  window.rimaToast = function(msg, type) {
    var t = document.getElementById('rima-toast');
    t.textContent = (type === 'error' ? 'âœ—  ' : 'âœ"  ') + msg;
    t.className = type === 'error' ? 'error show' : 'show';
    setTimeout(function() { t.className = ''; }, 3000);
  };

  // â"€â"€ Guardar datos de marca â"€â"€
  // Recoge TODOS los inputs de la pÃ¡gina usando label+placeholder como clave
  function collectAllInputs() {
    var data = {};
    // 1) Por id o name
    document.querySelectorAll('input[id],textarea[id],select[id],input[name],textarea[name],select[name]').forEach(function(el) {
      var key = el.id || el.name;
      if (key && el.value) data[key] = el.value;
    });
    // 2) Por pares .field-label + .f-input / .f-textarea (rima-marca.html)
    document.querySelectorAll('.field-group').forEach(function(fg) {
      var lbl = fg.querySelector('.field-label');
      var inp = fg.querySelector('input,textarea,select');
      if (lbl && inp && inp.value) {
        var key = (lbl.textContent || '').trim().replace(/[^a-zA-Z0-9 ]/g,'').trim().toLowerCase().replace(/ +/g,'_').slice(0,40);
        if (key) data[key] = inp.value;
      }
    });
    // 3) Fallback genÃ©rico: todos los inputs con value y placeholder como clave
    document.querySelectorAll('input,textarea').forEach(function(el) {
      if (!el.value || el.type === 'hidden') return;
      var key = el.id || el.name;
      if (!key && el.placeholder) key = el.placeholder.slice(0,30).toLowerCase().replace(/[^a-z0-9]/g,'_');
      if (key && !data[key]) data[key] = el.value;
    });
    return data;
  }

  async function saveBrand() {
    var data = collectAllInputs();
    try {
      var r = await fetch('/api/brand', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify(data)
      });
      if (r.ok) { rimaToast('InformaciÃ³n guardada'); }
      else { rimaToast('Error al guardar', 'error'); }
    } catch(e) { rimaToast('Sin conexiÃ³n', 'error'); }
  }

  // Override saveForm() que usan las pÃ¡ginas HTML inline
  window.saveForm = async function() {
    var ind = document.getElementById('save-indicator');
    if (ind) { ind.classList.remove('hidden'); setTimeout(function(){ind.classList.add('hidden');}, 2500); }
    await saveBrand();
  };

  // â"€â"€ Cargar datos de marca en formulario â"€â"€
  async function loadBrand() {
    try {
      var r = await fetch('/api/brand');
      if (!r.ok) return;
      var data = await r.json();
      // Intentar rellenar por id/name primero
      Object.keys(data).forEach(function(key) {
        var el = document.getElementById(key) || document.querySelector('[name="'+key+'"]');
        if (el && data[key] && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT')) {
          el.value = data[key];
        }
      });
    } catch(e) {}
  }

  // â"€â"€ Credenciales â"€â"€
  async function saveCredentials() {
    var data = {};
    document.querySelectorAll('.cred-input, input[data-cred], input[id*="cred"], input[id*="token"], input[id*="bot"], input[id*="telegram"], input[id*="instagram"], input[id*="meta"], input[id*="api"]').forEach(function(el) {
      if (el.id || el.name) data[el.id || el.name] = el.value;
    });
    // Fallback: todos los inputs de tipo password o con placeholder con "token"
    document.querySelectorAll('input[type="password"], input[type="text"]').forEach(function(el) {
      var ph = (el.placeholder || '').toLowerCase();
      if ((ph.includes('token') || ph.includes('bot') || ph.includes('api') || ph.includes('id')) && (el.id || el.name)) {
        data[el.id || el.name] = el.value;
      }
    });
    try {
      var r = await fetch('/api/credentials', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify(data)
      });
      if (r.ok) { rimaToast('Credenciales guardadas'); }
      else { rimaToast('Error al guardar', 'error'); }
    } catch(e) { rimaToast('Sin conexiÃ³n', 'error'); }
  }

  async function loadCredentials() {
    try {
      var r = await fetch('/api/credentials');
      if (!r.ok) return;
      var data = await r.json();
      Object.keys(data).forEach(function(key) {
        var el = document.getElementById(key) || document.querySelector('[name="'+key+'"]');
        if (el && data[key]) el.value = data[key];
      });
    } catch(e) {}
  }

  var PLAN_LABELS = { basico: 'Basic', pro: 'Pro', max: 'Max', admin: 'Admin' };

  function userInitials(name, email) {
    var n = (name || '').trim();
    if (n && n.indexOf('@') < 0) {
      return n.split(/\\s+/).filter(Boolean).map(function(w){ return w[0] || ''; }).join('').slice(0, 2).toUpperCase();
    }
    var e = (email || '').split('@')[0] || '?';
    return e.slice(0, 2).toUpperCase();
  }

  function setUserBarText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  function applyUserSession(u) {
    if (!u) return;
    var email = u.email || u.sub || '';
    var name = u.name || email.split('@')[0] || 'Usuario';
    var planKey = (u.plan || 'pro').toLowerCase();
    var planLabel = PLAN_LABELS[planKey] || planKey;
    var initials = u.initials || userInitials(name, email);

    setUserBarText('rima-user-initials', initials);
    setUserBarText('rima-user-name', name);
    setUserBarText('rima-user-plan', planLabel);
    setUserBarText('rima-user-menu-email', email);
    setUserBarText('rima-user-menu-plan', planLabel);
  }

  function initUserMenu() {
    var bar = document.getElementById('rima-user-bar');
    var menu = document.getElementById('rima-user-menu');
    var trigger = document.getElementById('rima-user-trigger');
    var settings = document.getElementById('rima-user-settings');
    if (!bar || !menu) return;

    function toggleMenu(force) {
      var open = force !== undefined ? force : !menu.classList.contains('open');
      menu.classList.toggle('open', open);
      bar.classList.toggle('menu-open', open);
    }

    if (trigger) {
      trigger.addEventListener('click', function(e) {
        e.stopPropagation();
        toggleMenu();
      });
    }
    if (settings) {
      settings.addEventListener('click', function(e) {
        e.stopPropagation();
        toggleMenu();
      });
    }
    document.addEventListener('click', function() { toggleMenu(false); });
    menu.addEventListener('click', function(e) { e.stopPropagation(); });
  }

  async function loadUserSession() {
    if (window.RIMA_USER) {
      applyUserSession(window.RIMA_USER);
      return;
    }
    try {
      var r = await fetch('/auth/me', { credentials: 'same-origin' });
      if (!r.ok) return;
      applyUserSession(await r.json());
    } catch(e) {}
  }

  // Perfil de negocio (parte superior del sidebar)
  async function loadProfile() {
    try {
      var r = await fetch('/api/brand');
      if (!r.ok) return;
      var d = await r.json();
      var brandName = d.brand_name || '';
      var handle = d.brand_ig || d.ig_username || '';
      if (brandName) {
        setUserBarText('rima-brand-name', brandName);
        var ini = userInitials(brandName, '');
        setUserBarText('rima-initials', ini);
      }
      if (handle) setUserBarText('rima-brand-handle', handle.indexOf('@') === 0 ? handle : '@' + handle);
    } catch(e) {}
  }

  // â"€â"€ Wiring de botones "Guardar" â"€â"€
  document.querySelectorAll('button').forEach(function(btn) {
    var txt = btn.textContent.trim().toLowerCase();

    if (txt.includes('generar todo')) {
      btn.addEventListener('click', generarTodo);
    }
    else if (txt.includes('guardar') || txt.includes('save')) {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        var path = window.location.pathname;
        if (path === '/credenciales') { saveCredentials(); }
        else { saveBrand(); }
      });
    }
    else if (txt.includes('conectar') || txt.includes('verificar') || txt.includes('connect')) {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        saveCredentials();
      });
    }
  });

  // Cargar datos al iniciar
  function bootSidebar() {
    initUserMenu();
    loadUserSession();
    var path = window.location.pathname;
    if (path === '/credenciales') { loadCredentials(); }
    else { loadBrand(); loadProfile(); }
  }
  window.addEventListener('DOMContentLoaded', bootSidebar);
  if (document.readyState !== 'loading') { bootSidebar(); }

  // â"€â"€ Modal "Generar todo" â"€â"€
  function generarTodo() {
    var modal = document.getElementById('rima-modal');
    if (modal) { modal.style.display = 'flex'; return; }
    modal = document.createElement('div');
    modal.id = 'rima-modal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.75);display:flex;align-items:center;justify-content:center;z-index:9999;padding:20px';
    modal.innerHTML = `
      <div style="background:#0F0F1A;border:1px solid rgba(124,58,237,0.4);border-radius:20px;padding:28px;width:100%;max-width:560px;max-height:90vh;overflow-y:auto">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
          <h2 style="font-size:15px;font-weight:700;color:#fff">Generar con RIMA</h2>
          <button onclick="document.getElementById('rima-modal').style.display='none'" style="background:transparent;border:none;color:#94A3B8;cursor:pointer;font-size:18px">âœ•</button>
        </div>
        <div style="display:grid;gap:10px;margin-bottom:18px">
          ${[
            ['r-nombre','Nombre del negocio','Ej: FitLife Studio'],
            ['r-servicio','Servicio / Oferta','Ej: MentorÃ­a para coaches que quieren escalar'],
            ['r-cliente','Cliente ideal','Ej: Coaches con 1-3 aÃ±os, facturando menos de $3K/mes'],
            ['r-problema','Problema que resuelves','Ej: No tienen sistema predecible para conseguir clientes'],
            ['r-resultado','Resultado principal prometido','Ej: Escalar a $10K/mes en 90 dÃ­as con Instagram sin ads'],
            ['r-precio','Precio','Ej: $2,500 USD'],
            ['r-garantia','GarantÃ­a (opcional)','Ej: Si no llegas a $10K en 90 dÃ­as, devolvemos el 100%'],
          ].map(([id,lbl,ph]) =>
            '<label style="font-size:10px;color:#94A3B8;font-weight:600;text-transform:uppercase;letter-spacing:.05em">'+lbl+'</label>' +
            '<input id="'+id+'" placeholder="'+ph+'" style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:10px 12px;color:#fff;font-size:12px;outline:none;width:100%"/>'
          ).join('')}
        </div>
        <button onclick="enviarGenerar()" id="rima-gen-btn" style="width:100%;background:linear-gradient(135deg,#7C3AED,#6D28D9);border:none;border-radius:12px;padding:12px;color:#fff;font-size:12px;font-weight:700;cursor:pointer">
          Generar Landing + Copy con RIMA
        </button>
        <div id="rima-output" style="display:none;margin-top:18px;background:rgba(124,58,237,0.06);border:1px solid rgba(124,58,237,0.2);border-radius:12px;padding:16px;max-height:400px;overflow-y:auto">
          <pre id="rima-output-text" style="font-size:11px;color:#CBD5E1;white-space:pre-wrap;font-family:inherit;line-height:1.6"></pre>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
    // Pre-llenar con datos guardados
    fetch('/api/brand').then(r=>r.json()).then(function(d) {
      if (d.brand_name) document.getElementById('r-nombre').value = d.brand_name;
      if (d.brand_service) document.getElementById('r-servicio').value = d.brand_service;
      if (d.brand_ideal_client) document.getElementById('r-cliente').value = d.brand_ideal_client;
      if (d.brand_problem) document.getElementById('r-problema').value = d.brand_problem;
      if (d.brand_result) document.getElementById('r-resultado').value = d.brand_result;
      if (d.brand_price) document.getElementById('r-precio').value = d.brand_price;
      if (d.brand_guarantee) document.getElementById('r-garantia').value = d.brand_guarantee;
    }).catch(function(){});
  }

  window.enviarGenerar = async function() {
    var btn = document.getElementById('rima-gen-btn');
    var out = document.getElementById('rima-output');
    var outText = document.getElementById('rima-output-text');
    btn.textContent = 'Generando...';
    btn.disabled = true;
    out.style.display = 'none';
    try {
      var resp = await fetch('/api/generate/landing', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          business_name: document.getElementById('r-nombre').value || 'Mi Negocio',
          service: document.getElementById('r-servicio').value || 'Servicio de alto valor',
          ideal_client: document.getElementById('r-cliente').value || 'Emprendedores LATAM',
          problem: document.getElementById('r-problema').value || 'No tienen clientes',
          main_result: document.getElementById('r-resultado').value || 'Escalar a $10K/mes',
          price: document.getElementById('r-precio').value || '$2,500 USD',
          guarantee: document.getElementById('r-garantia').value || ''
        })
      });
      var data = await resp.json();
      outText.textContent = data.output || JSON.stringify(data, null, 2);
      out.style.display = 'block';
      rimaToast('Landing generada con RIMA');
    } catch(e) {
      outText.textContent = 'Error: ' + e.message;
      out.style.display = 'block';
      rimaToast('Error al conectar con el servidor', 'error');
    }
    btn.textContent = 'Generar Landing + Copy con RIMA';
    btn.disabled = false;
  };

})();
</script>
"""


NAV_ITEMS_PY = [
    ("Dashboard",            "/home",         "COMENCEMOS", "violet",  "M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25A2.25 2.25 0 0113.5 8.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"),
    ("Calendario",           "/calendario",   "COMENCEMOS", "violet",  "M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"),
    ("Contenido",            "/contenido",    "COMENCEMOS", "pink",    "M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z"),
    ("Estudio de mercado",   "/mercado",      "COMENCEMOS", "sky",     "M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"),
    ("META Ads",             "/meta",         "COMENCEMOS", "blue",    "M12 2C6.477 2 2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.879V14.89h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.989C18.343 21.129 22 16.99 22 12c0-5.523-4.477-10-10-10z"),
    ("Ventas",               "/ventas",       "COMENCEMOS", "emerald", "M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941"),
    ("Landing",              "/landing",      "COMENCEMOS", "amber",   "M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z"),
    ("Informacion de la marca", "/marca",     "MI NEGOCIO", "violet",  "M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z"),
    ("Referencias",          "/referencias",  "MI NEGOCIO", "rose",    "M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244"),
    ("Imagenes",             "/imagenes",     "MI NEGOCIO", "cyan",    "M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"),
    ("Videos",               "/videos",       "MI NEGOCIO", "orange",  "M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z"),
    ("Credenciales",         "/credenciales", "MI NEGOCIO", "slate",   "M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z"),
]

COLOR_HEX = {
    "violet": "#A78BFA", "pink": "#F472B6", "sky": "#38BDF8", "blue": "#60A5FA",
    "emerald": "#34D399", "amber": "#FBBF24", "rose": "#FB7185", "cyan": "#22D3EE",
    "orange": "#FB923C", "slate": "#94A3B8",
}
COLOR_BG = {
    "violet": "rgba(124,58,237,0.15)", "pink": "rgba(236,72,153,0.15)",
    "sky": "rgba(14,165,233,0.15)", "blue": "rgba(59,130,246,0.15)",
    "emerald": "rgba(52,211,153,0.15)", "amber": "rgba(245,158,11,0.15)",
    "rose": "rgba(244,63,94,0.15)", "cyan": "rgba(6,182,212,0.15)",
    "orange": "rgba(249,115,22,0.15)", "slate": "rgba(100,116,139,0.15)",
}

def _build_nav_html(current_path: str) -> str:
    groups: dict = {}
    order: list = []
    for label, href, group, color, icon in NAV_ITEMS_PY:
        if group not in groups:
            groups[group] = []
            order.append(group)
        groups[group].append((label, href, color, icon))

    html = ""
    for g in order:
        html += f'<div style="margin-bottom:12px"><p style="font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:#334155;font-weight:700;padding:0 8px;margin:0 0 4px 0">{g}</p><div style="display:flex;flex-direction:column;gap:2px">'
        for label, href, color, icon in groups[g]:
            is_active = (href == current_path) or (href != "/" and current_path.startswith(href))
            if is_active:
                bg = "background:linear-gradient(135deg,rgba(124,58,237,0.18),rgba(6,182,212,0.08));border-color:rgba(124,58,237,0.45)"
                tc = "color:#fff;font-weight:600"
            else:
                bg = "background:transparent;border-color:transparent"
                tc = "color:#94A3B8;font-weight:400"
            ic = COLOR_HEX.get(color, "#A78BFA")
            ib = COLOR_BG.get(color, "rgba(124,58,237,0.15)")
            html += (
                f'<a href="{href}" style="display:flex;align-items:center;gap:10px;padding:7px 12px;border-radius:10px;border:1px solid;text-decoration:none;transition:all .18s;{bg}">'
                f'<div style="width:20px;height:20px;border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0;background:{ib}">'
                f'<svg style="width:10px;height:10px;color:{ic}" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="{icon}"/></svg>'
                f'</div><span style="font-size:11px;{tc};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{label}</span></a>'
            )
        html += "</div></div>"
    return html


PLAN_DISPLAY = {"basico": "Basic", "pro": "Pro", "max": "Max", "admin": "Admin"}


def _user_initials(name: str, email: str = "") -> str:
    n = (name or "").strip()
    if n and "@" not in n:
        parts = [p for p in n.split() if p]
        return "".join(p[0] for p in parts[:2]).upper()[:2] or "?"
    local = (email or "").split("@")[0] or "?"
    return local[:2].upper()


def _session_from_request(request: Optional[Request]) -> Optional[dict]:
    if not request:
        return None
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None

    email = payload.get("sub", "")
    role = payload.get("role", "user")
    data = load_data()

    if role == "admin":
        brand = get_user_brand(data, email)
        plan = normalize_plan(brand.get("plan", "max"))
        name = payload.get("name", "Admin")
    else:
        rec = data.get("users", {}).get(email, {})
        plan = get_user_plan(data, email)
        name = rec.get("name", payload.get("name", email.split("@")[0] if email else "Usuario"))

    return {
        "email": email,
        "sub": email,
        "name": name,
        "plan": plan,
        "initials": _user_initials(name, email),
    }


def _apply_session_to_sidebar(sidebar: str, session: dict) -> str:
    plan_label = PLAN_DISPLAY.get(session.get("plan", "pro"), session.get("plan", "pro"))
    name = session.get("name", "Usuario")
    initials = session.get("initials", "?")
    email = session.get("email", "")
    sidebar = sidebar.replace(
        '<span id="rima-user-initials" style="font-size:11px;font-weight:700;color:#CBD5E1">—</span>',
        f'<span id="rima-user-initials" style="font-size:11px;font-weight:700;color:#CBD5E1">{initials}</span>',
    )
    sidebar = sidebar.replace(
        '<p id="rima-user-name" style="font-size:11px;font-weight:600;color:#E2E8F0;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3">Cargando…</p>',
        f'<p id="rima-user-name" style="font-size:11px;font-weight:600;color:#E2E8F0;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3">{name}</p>',
    )
    sidebar = sidebar.replace(
        '<p id="rima-user-plan" style="font-size:10px;color:#64748B;margin:2px 0 0;line-height:1.2">Plan —</p>',
        f'<p id="rima-user-plan" style="font-size:10px;color:#64748B;margin:2px 0 0;line-height:1.2">{plan_label}</p>',
    )
    sidebar = sidebar.replace(
        '<p id="rima-user-menu-email" style="font-size:11px;color:#94A3B8;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">—</p>',
        f'<p id="rima-user-menu-email" style="font-size:11px;color:#94A3B8;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{email}</p>',
    )
    sidebar = sidebar.replace(
        '<p id="rima-user-menu-plan" style="font-size:10px;color:#64748B;margin:4px 0 0">—</p>',
        f'<p id="rima-user-menu-plan" style="font-size:10px;color:#64748B;margin:4px 0 0">{plan_label}</p>',
    )
    return sidebar


def _user_bootstrap_script(session: dict) -> str:
    payload = json.dumps(session, ensure_ascii=False)
    return (
        f"<script>window.RIMA_USER={payload};</script>\n"
        "<script>\n"
        "(function(){var u=window.RIMA_USER;if(!u)return;"
        "function s(id,v){var e=document.getElementById(id);if(e)e.textContent=v;}"
        "var plans={basico:'Basic',pro:'Pro',max:'Max',admin:'Admin'};"
        "var plan=plans[(u.plan||'pro').toLowerCase()]||u.plan;"
        "s('rima-user-initials',u.initials||'?');"
        "s('rima-user-name',u.name||'Usuario');"
        "s('rima-user-plan',plan);"
        "s('rima-user-menu-email',u.email||'');"
        "s('rima-user-menu-plan',plan);"
        "})();\n"
        "</script>\n"
    )


def serve_html(filename: str, request: Optional[Request] = None) -> HTMLResponse:
    import re as _re
    path = DASHBOARD / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Pagina no encontrada: {filename}")
    content = path.read_text(encoding="utf-8")

    # Determinar path activo para resaltar nav item
    route_map = {
        "rima-home.html": "/home", "rima-calenadrio.html": "/calendario",
        "rima-contenido.html": "/contenido", "rima-mercado.html": "/mercado",
        "rima-meta.html": "/meta", "rima-ventas.html": "/ventas",
        "rima-landing.html": "/landing", "rima-marca.html": "/marca",
        "rima-referencias.html": "/referencias", "rima-imagenes.html": "/imagenes",
        "rima-videos.html": "/videos", "rima-credenciales.html": "/credenciales",
        "rima-configuracion.html": "/configuracion",
    }
    current_path = route_map.get(filename, "/")

    session = _session_from_request(request)

    # Construir sidebar con nav activo
    nav_html = _build_nav_html(current_path)
    sidebar = SIDEBAR_HTML.replace(
        '<nav id="rima-nav" style="flex:1 1 auto;min-height:0;padding:10px;overflow-y:auto;scrollbar-width:none"></nav>',
        f'<nav id="rima-nav" data-rima-built="1" style="flex:1 1 auto;min-height:0;padding:10px;overflow-y:auto;scrollbar-width:none">{nav_html}</nav>',
    )
    if session:
        sidebar = _apply_session_to_sidebar(sidebar, session)

    # Reemplazar cualquier aside (vacío o lleno) con el sidebar generado
    content = _re.sub(r'<aside[^>]*>.*?</aside>', sidebar, content, count=1, flags=_re.DOTALL)

    # Inyectar CSS en <head>
    content = content.replace("</head>", SHARED_CSS + "\n</head>")

    user_bootstrap = _user_bootstrap_script(session) if session else ""

    # Inyectar sesión + JS universal antes del cierre de body
    content = content.replace("</body>", user_bootstrap + SHARED_JS + "\n</body>")
    return HTMLResponse(content=content)


# â"€â"€ Rutas de pÃ¡ginas â"€â"€

@app.get("/home", response_class=HTMLResponse)
def home_dashboard(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    return serve_html("rima-home.html", request)

@app.get("/calendario", response_class=HTMLResponse)
def calendario(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-calenadrio.html", request)

@app.get("/contenido", response_class=HTMLResponse)
def contenido(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-contenido.html", request)

@app.get("/lab", response_class=HTMLResponse)
def agent_lab(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-lab.html", request)

@app.get("/mercado", response_class=HTMLResponse)
def mercado(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-mercado.html", request)

@app.get("/meta", response_class=HTMLResponse)
def meta(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-meta.html", request)

@app.get("/ventas", response_class=HTMLResponse)
def ventas(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-ventas.html", request)

@app.get("/landing", response_class=HTMLResponse)
def landing(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-landing.html", request)

@app.get("/marca", response_class=HTMLResponse)
def marca(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-marca.html", request)

@app.get("/referencias", response_class=HTMLResponse)
def referencias(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-referencias.html", request)

@app.get("/imagenes", response_class=HTMLResponse)
def imagenes(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-imagenes.html", request)

@app.get("/videos", response_class=HTMLResponse)
def videos(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-videos.html", request)

@app.get("/credenciales", response_class=HTMLResponse)
def credenciales(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-credenciales.html", request)

@app.get("/configuracion", response_class=HTMLResponse)
def configuracion(request: Request):
    redirect = require_auth(request)
    if redirect: return redirect
    return serve_html("rima-configuracion.html", request)


# â"€â"€ API: Datos de marca â"€â"€

def _brand_brief_from_brand(brand: dict, user_plan: str = None) -> dict:
    return {
        "business_name": brand.get("brand_name", "Mi Negocio"),
        "service": brand.get("brand_service", ""),
        "ideal_client": brand.get("brand_ideal_client", ""),
        "problem": brand.get("brand_problem", ""),
        "main_result": brand.get("brand_result", ""),
        "price": brand.get("brand_price", ""),
        "success_cases": brand.get("brand_success_cases", ""),
        "guarantee": brand.get("brand_guarantee", ""),
        "ig_avg_views": brand.get("ig_avg_views", 0),
        "plan": normalize_plan(user_plan or brand.get("plan", "pro")),
        "enfoque": normalize_enfoque_default(brand.get("enfoque_default")),
    }


@app.get("/api/brand")
def get_brand(user: dict = Depends(get_current_user)):
    data = load_data()
    email = user.get("email", "")
    brand = dict(get_user_brand(data, email))
    normalized = normalize_enfoque_default(brand.get("enfoque_default"))
    if brand.get("enfoque_default") != normalized:
        brand["enfoque_default"] = normalized
        set_user_brand(data, email, brand)
        save_data(data)
    brand["plan"] = get_user_plan(data, email)
    return JSONResponse(content=brand)

@app.post("/api/brand")
def post_brand(payload: dict, user: dict = Depends(get_current_user)):
    data = load_data()
    email = user.get("email", "")
    existing = dict(get_user_brand(data, email))
    existing.update(payload)
    if "enfoque_default" in payload:
        existing["enfoque_default"] = normalize_enfoque_default(existing.get("enfoque_default"))
    set_user_brand(data, email, existing)
    save_data(data)
    return {"status": "ok", "saved": len(existing)}

# â"€â"€ API: Credenciales â"€â"€

@app.get("/api/credentials")
def get_credentials(user: dict = Depends(get_current_user)):
    data = load_data()
    return JSONResponse(content=data.get("credentials", {}))

@app.post("/api/credentials")
def post_credentials(payload: dict, user: dict = Depends(get_current_user)):
    data = load_data()
    existing = data.get("credentials", {})
    existing.update(payload)
    data["credentials"] = existing
    save_data(data)
    return {"status": "ok"}


# â"€â"€ Modelos de request para agentes â"€â"€

class BrandBrief(BaseModel):
    business_name: str = "Mi Negocio"
    service: str = ""
    ideal_client: str = ""
    problem: str = ""
    main_result: str = ""
    price: str = ""
    success_cases: str = ""
    guarantee: str = ""


# â"€â"€ Endpoints de agentes â"€â"€

@app.post("/api/generate/landing")
def generate_landing(brief: BrandBrief, user: dict = Depends(get_current_user)):
    try:
        result = landing_agent.run(brief.model_dump())
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/contenido")
def generate_content(brief: BrandBrief, user: dict = Depends(get_current_user)):
    try:
        result = content_agent.run(brief.model_dump())
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/meta")
def generate_meta(brief: BrandBrief, user: dict = Depends(get_current_user)):
    try:
        result = meta_agent.run(brief.model_dump())
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/ventas")
def generate_sales(brief: BrandBrief, user: dict = Depends(get_current_user)):
    try:
        result = sales_agent.run(brief.model_dump())
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/prospecting")
def generate_prospecting(brief: BrandBrief, user: dict = Depends(get_current_user)):
    try:
        result = prospecting_agent.run(brief.model_dump())
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# â"€â"€ API: ImÃ¡genes â"€â"€

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE_MB = 10

@app.post("/api/images/upload")
async def upload_images(
    files: List[UploadFile] = File(...),
    category: str = Form("historias"),
    user: dict = Depends(get_current_user),
):
    if category not in ("historias", "carruseles"):
        raise HTTPException(status_code=400, detail="CategorÃ­a invÃ¡lida")

    saved = []
    errors = []
    dest_dir = UPLOADS_DIR / category

    for f in files:
        if f.content_type not in ALLOWED_TYPES:
            errors.append({"name": f.filename, "error": "Tipo no permitido"})
            continue

        content = await f.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > MAX_SIZE_MB:
            errors.append({"name": f.filename, "error": f"Supera {MAX_SIZE_MB} MB"})
            continue

        # Nombre Ãºnico para evitar colisiones
        stem = Path(f.filename).stem[:40].replace(" ", "_")
        ext  = Path(f.filename).suffix.lower() or ".jpg"
        unique_name = f"{stem}_{int(time.time() * 1000)}{ext}"
        dest = dest_dir / unique_name
        dest.write_bytes(content)

        saved.append({
            "name": unique_name,
            "original": f.filename,
            "size_mb": round(size_mb, 2),
            "url": f"/uploads/{category}/{unique_name}",
            "category": category,
            "uploaded_at": int(time.time()),
        })

    return {"saved": saved, "errors": errors}


@app.get("/api/images")
def list_images(category: str = "historias", user: dict = Depends(get_current_user)):
    if category not in ("historias", "carruseles"):
        raise HTTPException(status_code=400, detail="CategorÃ­a invÃ¡lida")

    folder = UPLOADS_DIR / category
    images = []
    for p in sorted(folder.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            stat = p.stat()
            images.append({
                "name": p.name,
                "url": f"/uploads/{category}/{p.name}",
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "uploaded_at": int(stat.st_mtime),
                "category": category,
            })
    return {"images": images, "total": len(images)}


@app.delete("/api/images/{category}/{filename}")
def delete_image(category: str, filename: str, user: dict = Depends(get_current_user)):
    if category not in ("historias", "carruseles"):
        raise HTTPException(status_code=400, detail="CategorÃ­a invÃ¡lida")
    # Seguridad: no path traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Nombre invÃ¡lido")
    path = UPLOADS_DIR / category / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    path.unlink()
    return {"status": "deleted", "file": filename}


# â"€â"€ API: Clips de video por reel â"€â"€

ALLOWED_VIDEO = {"video/mp4","video/quicktime","video/x-msvideo","video/webm","video/mpeg","video/mov"}
MAX_CLIP_MB = 500

@app.post("/api/videos/{reel_id}/clips")
async def upload_clip(reel_id: str, files: List[UploadFile] = File(...), user: dict = Depends(get_current_user)):
    reel_dir = UPLOADS_DIR / "clips" / reel_id
    reel_dir.mkdir(parents=True, exist_ok=True)
    saved, errors = [], []
    for f in files:
        content = await f.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > MAX_CLIP_MB:
            errors.append({"name": f.filename, "error": f"Supera {MAX_CLIP_MB} MB"})
            continue
        stem = Path(f.filename).stem[:40].replace(" ", "_")
        ext  = Path(f.filename).suffix.lower() or ".mp4"
        unique = f"{stem}_{int(time.time()*1000)}{ext}"
        (reel_dir / unique).write_bytes(content)
        saved.append({
            "name": unique, "original": f.filename,
            "size_mb": round(size_mb, 2),
            "url": f"/uploads/clips/{reel_id}/{unique}",
            "uploaded_at": int(time.time()),
        })
    return {"saved": saved, "errors": errors}

@app.get("/api/videos/{reel_id}/clips")
def list_clips(reel_id: str, user: dict = Depends(get_current_user)):
    folder = UPLOADS_DIR / "clips" / reel_id
    folder.mkdir(parents=True, exist_ok=True)
    clips = []
    for p in sorted(folder.iterdir(), key=lambda x: x.stat().st_mtime):
        if p.suffix.lower() in (".mp4",".mov",".avi",".webm",".mpeg"):
            st = p.stat()
            clips.append({
                "name": p.name, "url": f"/uploads/clips/{reel_id}/{p.name}",
                "size_mb": round(st.st_size/(1024*1024), 2),
                "uploaded_at": int(st.st_mtime),
            })
    return {"clips": clips, "reel_id": reel_id}

@app.delete("/api/videos/{reel_id}/clips/{filename}")
def delete_clip(reel_id: str, filename: str, user: dict = Depends(get_current_user)):
    if ".." in filename or "/" in filename:
        raise HTTPException(400, "Nombre invÃ¡lido")
    p = UPLOADS_DIR / "clips" / reel_id / filename
    if not p.exists(): raise HTTPException(404, "No encontrado")
    p.unlink()
    return {"status": "deleted"}

# â"€â"€ API: Video final por reel â"€â"€

@app.post("/api/videos/{reel_id}/final")
async def upload_final(reel_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    finals_dir = UPLOADS_DIR / "finals"
    finals_dir.mkdir(exist_ok=True)
    content = await file.read()
    size_mb = len(content) / (1024*1024)
    if size_mb > MAX_CLIP_MB:
        raise HTTPException(400, f"Supera {MAX_CLIP_MB} MB")
    ext = Path(file.filename).suffix.lower() or ".mp4"
    fname = f"{reel_id}_final_{int(time.time())}{ext}"
    (finals_dir / fname).write_bytes(content)
    # Guardar referencia en data
    d = load_data()
    d.setdefault("reels", {}).setdefault(reel_id, {})["final"] = {
        "name": fname, "url": f"/uploads/finals/{fname}",
        "size_mb": round(size_mb, 2), "uploaded_at": int(time.time())
    }
    save_data(d)
    return {"url": f"/uploads/finals/{fname}", "name": fname}

@app.get("/api/videos/{reel_id}/final")
def get_final(reel_id: str, user: dict = Depends(get_current_user)):
    d = load_data()
    final = d.get("reels", {}).get(reel_id, {}).get("final")
    if not final: return {"final": None}
    # Verificar que el archivo sigue existiendo
    path = UPLOADS_DIR / "finals" / final["name"]
    if not path.exists(): return {"final": None}
    return {"final": final}

# â"€â"€ API: Estado de reel (aprobaciÃ³n guiÃ³n, paso actual) â"€â"€

@app.get("/api/videos/{reel_id}/state")
def get_reel_state(reel_id: str, user: dict = Depends(get_current_user)):
    d = load_data()
    return d.get("reels", {}).get(reel_id, {}).get("state", {"script_approved": False, "step": 1})

@app.post("/api/videos/{reel_id}/state")
def set_reel_state(reel_id: str, payload: dict, user: dict = Depends(get_current_user)):
    d = load_data()
    d.setdefault("reels", {}).setdefault(reel_id, {})["state"] = payload
    save_data(d)
    return {"status": "ok"}


@app.post("/api/videos/{reel_id}/edit")
def trigger_edit(reel_id: str, user: dict = Depends(get_current_user)):
    """Stub: envÃ­a los clips al agente editor. Por ahora devuelve confirmaciÃ³n."""
    d = load_data()
    clips_dir = UPLOADS_DIR / "clips" / reel_id
    clip_files = []
    if clips_dir.exists():
        clip_files = [p.name for p in clips_dir.iterdir() if p.suffix.lower() in (".mp4",".mov",".avi",".webm")]
    if not clip_files:
        raise HTTPException(400, "No hay clips para editar")
    # Registrar solicitud de ediciÃ³n en datos
    d.setdefault("reels", {}).setdefault(reel_id, {})["edit_requested"] = {
        "clips": clip_files,
        "requested_at": int(time.time())
    }
    save_data(d)
    return {"status": "queued", "message": f"Edicion iniciada - {len(clip_files)} clip(s) en cola", "clips": clip_files}


# â"€â"€ API: Calendario â"€â"€

# NOTA: los endpoints /api/calendar* (GET/POST/PUT/DELETE/generate) que usaban
# almacenamiento en JSON (load_data/save_data, "calendar_items") fueron retirados —
# quedaban registrados ANTES que los adaptadores basados en SQLite (más abajo en
# este archivo) y FastAPI siempre matcheaba estos primero, por lo que el calendario
# nunca reflejaba lo generado por el agente (que sí escribe en SQLite). Los
# endpoints vigentes para /api/calendar* viven más abajo y leen/escriben en
# `publicaciones` (SQLite por cliente).


# â"€â"€ API: Contenido â€" slides, regenerar, telegram â"€â"€

@app.post("/api/calendar/{item_id}/generate-slides")
def generate_slides(item_id: str, user: dict = Depends(get_current_user)):
    from core.gemini_client import gemini
    data = load_data()
    items = data.get("calendar_items", [])
    idx = next((i for i, x in enumerate(items) if x["id"] == item_id), None)
    if idx is None:
        raise HTTPException(404, "Item no encontrado")
    item = items[idx]
    ctype = item.get("type", "reel")
    brand = data.get("brand", {})
    brand_name = brand.get("brand_name", "Mi Negocio")
    if ctype == "reel":
        structure = "Hook (0-3s), Desarrollo (3-20s), ClÃ­max/Giro (20-25s), CTA (25-30s)"
        n = 4
    elif ctype == "carrusel":
        structure = "Cover (gancho), Slide 2, Slide 3, Slide 4, Slide 5, Slide 6, CTA final"
        n = 7
    else:
        structure = "Hook/Portada, Desarrollo 1, Desarrollo 2, Desarrollo 3, Desarrollo 4, CTA con sticker"
        n = 6

    prompt = f"""Eres experto en contenido Instagram para LATAM.
Genera el copy especÃ­fico para cada slide de esta publicaciÃ³n.

Negocio: {brand_name}
Tipo: {ctype}
Concepto: {item.get('title','')}
DescripciÃ³n: {item.get('caption','')}
Estructura recomendada: {structure}

Genera exactamente {n} slides. Responde SOLO con JSON array (sin markdown):
[
  {{"num": 1, "label": "Hook", "copy": "Texto exacto corto y potente para este slide..."}},
  ...{n} items total...
]"""
    try:
        raw = gemini.generate(prompt)
        match = re.search(r'\[[\s\S]*\]', raw)
        if not match: raise HTTPException(500, "Sin JSON en respuesta")
        slides = json.loads(match.group())
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"JSON invÃ¡lido: {e}")
    items[idx]["slides"] = slides
    save_data(data)
    return {"slides": slides}


@app.post("/api/calendar/{item_id}/regenerate")
def regenerate_item(item_id: str, user: dict = Depends(get_current_user)):
    from core.gemini_client import gemini
    data = load_data()
    items = data.get("calendar_items", [])
    idx = next((i for i, x in enumerate(items) if x["id"] == item_id), None)
    if idx is None: raise HTTPException(404, "Item no encontrado")
    item = items[idx]
    regen = item.get("regen_count", 0)
    if regen >= 3: raise HTTPException(400, "MÃ¡ximo 3 regeneraciones alcanzado")
    brand = data.get("brand", {})
    prompt = f"""Eres experto en contenido Instagram para LATAM.
Genera UNA nueva propuesta DIFERENTE para Instagram.

Negocio: {brand.get('brand_name','Mi Negocio')}
Servicio: {brand.get('brand_service','servicio de alto valor')}
Cliente: {brand.get('brand_ideal_client','emprendedores LATAM')}
Tipo: {item.get('type','reel')}
Fecha: {item.get('date','')}
PROPUESTA ANTERIOR (NO repetir): {item.get('title','')}

Crea Ã¡ngulo/hook completamente diferente. Responde SOLO con JSON (sin markdown):
{{"title": "Nuevo hook/tÃ­tulo", "caption": "Caption completo con gancho...", "hashtags": ["#tag1","#tag2","#tag3","#tag4","#tag5"]}}"""
    try:
        raw = gemini.generate(prompt)
        match = re.search(r'\{{[\s\S]*\}}', raw)
        if not match: raise HTTPException(500, "Sin JSON en respuesta")
        nd = json.loads(match.group())
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"JSON invÃ¡lido: {e}")
    items[idx].update({"title": nd.get("title", item["title"]), "caption": nd.get("caption",""),
                       "hashtags": nd.get("hashtags",[]), "regen_count": regen + 1, "slides": []})
    save_data(data)
    return items[idx]


@app.post("/api/calendar/{item_id}/telegram")
async def telegram_validate(item_id: str, payload: dict = {}):
    """
    Envía un ítem del calendario a Telegram para validación del cliente.
    Bypass del flujo secuencial — envío directo desde el dashboard.
    """
    data  = load_data()
    items = data.get("calendar_items", [])
    idx   = next((i for i, x in enumerate(items) if x["id"] == item_id), None)
    if idx is None:
        raise HTTPException(404, "Item no encontrado")

    item = items[idx]

    # Buscar chat_id del cliente (por brand o el primero vinculado)
    brand   = payload.get("brand", data.get("brand", {}).get("brand_slug", ""))
    users   = data.get("telegram_users", {})
    chat_id = payload.get("chat_id")
    if not chat_id and users:
        chat_id = list(users.values())[0].get("chat_id")
    if not chat_id:
        raise HTTPException(400, "No hay cliente vinculado a Telegram")

    # Enviar al bot
    try:
        from bot.weekly_flow import enviar_item_directo
        from telegram.ext import Application as TGApp

        tg_app = TGApp.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
        await tg_app.initialize()
        await enviar_item_directo(tg_app, int(chat_id), item, brand)
        await tg_app.shutdown()
    except Exception as e:
        raise HTTPException(500, f"Error enviando a Telegram: {e}")

    # Actualizar estado
    items[idx]["status"] = "validacion"
    items[idx]["telegram_sent"] = True
    items[idx]["telegram_sent_at"] = int(time.time())
    save_data(data)
    return {"status": "ok", "item": items[idx]}


@app.post("/api/calendar/{item_id}/approve")
def approve_item(item_id: str, user: dict = Depends(get_current_user)):
    data = load_data()
    items = data.get("calendar_items", [])
    idx = next((i for i, x in enumerate(items) if x["id"] == item_id), None)
    if idx is None: raise HTTPException(404, "Item no encontrado")
    items[idx]["status"] = "programado"
    items[idx]["telegram_approved"] = True
    save_data(data)
    return {"status": "ok", "item": items[idx]}


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "RIMA AI"}


# ── API: Flujo semanal + Telegram ──

@app.post("/api/weekly/start")
async def weekly_start(payload: dict, user: dict = Depends(get_current_user)):
    """
    Inicia el flujo semanal para un cliente.
    Corre el scraping y manda la primera historia a Telegram.

    Body: { "brand": "fitlife", "week": "W23_2026", "chat_id": 5149024498 }
    """
    brand    = payload.get("brand", "")
    week     = payload.get("week", "")
    chat_id  = payload.get("chat_id")
    profiles = payload.get("competitor_profiles", [])

    if not brand or not chat_id:
        raise HTTPException(400, "brand y chat_id son requeridos")

    # 1. Arrancar el orquestador (scraping + inicializar estado)
    try:
        result = weekly_agent.start_week(brand, week_label=week,
                                          competitor_profiles=profiles)
    except Exception as e:
        raise HTTPException(500, f"Error iniciando semana: {e}")

    # 2. Obtener la primera historia y mandarla por Telegram
    try:
        from bot.weekly_flow import enviar_historia
        from telegram import Bot
        bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))

        next_story = weekly_agent.next_story(brand, result["week"])
        if not next_story.get("done"):
            # Crear app temporal solo para enviar
            from telegram.ext import Application as TGApp
            tg_app = TGApp.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
            await tg_app.initialize()

            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🚀 *¡Tu semana de contenido está lista!*\n\n"
                    f"Vamos a revisar el copy pieza por pieza.\n"
                    f"Son {next_story['total_stories']} historias, "
                    f"unos minutos de tu tiempo y RIMA se encarga del resto."
                ),
                parse_mode="Markdown"
            )

            await enviar_historia(
                tg_app, chat_id, brand, result["week"],
                next_story["story_index"],
                next_story["total_stories"],
                next_story["slot"],
                next_story.get("proposals", [])
            )
            await tg_app.shutdown()

    except Exception as e:
        # No fallar si Telegram falla — el estado ya fue guardado
        print(f"Warning Telegram: {e}")

    return {
        "status": "started",
        "brand": brand,
        "week": result["week"],
        "stage": result["stage"],
        "message": "Flujo semanal iniciado. Primera historia enviada por Telegram."
    }


# â"€â"€ Webhook Lemon Squeezy â"€â"€

LEMON_WEBHOOK_SECRET = os.getenv("LEMON_WEBHOOK_SECRET", "")

def _verify_lemon_signature(payload: bytes, signature: str) -> bool:
    if not LEMON_WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        LEMON_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

def _create_user_from_payment(email: str, name: str, plan: str):
    """Registra al cliente en el JSON local y podrias agregar envio de email aqui."""
    d = load_data()
    users = d.setdefault("users", {})
    if email not in users:
        users[email] = {
            "name": name,
            "plan": plan,
            "status": "active",
            "created_at": int(time.time()),
        }
        save_data(d)
        print(f"[RIMA] Usuario creado: {email} | Plan: {plan}")
    else:
        users[email]["plan"] = plan
        users[email]["status"] = "active"
        save_data(d)
        print(f"[RIMA] Usuario actualizado: {email} | Plan: {plan}")

@app.post("/api/webhooks/lemon")
async def lemon_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None),
):
    payload = await request.body()

    if not x_signature or not _verify_lemon_signature(payload, x_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_name = data.get("meta", {}).get("event_name", "")
    print(f"[RIMA] Webhook recibido: {event_name}")

    if event_name in ("order_created", "subscription_created"):
        attrs = data.get("data", {}).get("attributes", {})
        email = attrs.get("user_email", "")
        name  = attrs.get("user_name", "")
        plan  = attrs.get("product_name", "")
        if email:
            _create_user_from_payment(email=email, name=name, plan=plan)

    elif event_name == "subscription_cancelled":
        attrs = data.get("data", {}).get("attributes", {})
        email = attrs.get("user_email", "")
        if email:
            d = load_data()
            if email in d.get("users", {}):
                d["users"][email]["status"] = "cancelled"
                save_data(d)
                print(f"[RIMA] Suscripcion cancelada: {email}")

    return {"status": "ok"}


# ── Webhook Gumroad (piloto) ──

GUMROAD_SELLER_ID = os.getenv("GUMROAD_SELLER_ID", "")

def _verify_gumroad_seller(seller_id: str) -> bool:
    return bool(GUMROAD_SELLER_ID) and seller_id == GUMROAD_SELLER_ID


SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)
APP_LOGIN_URL = os.getenv("APP_LOGIN_URL", "https://rima.n8n-ghl.com/login")


def _send_email_sync(to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


async def send_welcome_email(to_email: str, name: str, temp_password: str) -> None:
    if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        print(f"[RIMA] SMTP no configurado, omitiendo correo de bienvenida a {to_email}")
        return

    subject = "Tu cuenta RIMA AI está lista"
    body = (
        f"Hola {name},\n\n"
        f"Tu cuenta de RIMA AI ya está activa.\n\n"
        f"Email: {to_email}\n"
        f"Contraseña temporal: {temp_password}\n\n"
        f"Inicia sesión aquí: {APP_LOGIN_URL}\n"
        f"Te recomendamos cambiar tu contraseña luego de tu primer ingreso.\n\n"
        f"Equipo RIMA AI"
    )

    try:
        await asyncio.to_thread(_send_email_sync, to_email, subject, body)
        print(f"[RIMA] Correo de bienvenida enviado a {to_email}")
    except Exception as e:
        print(f"[RIMA] Error enviando correo de bienvenida a {to_email}: {e}")


async def _provision_user_from_payment(email: str, name: str, plan: str, brand_name: str = None) -> str:
    """Crea/actualiza usuario completamente provisionado: plan, password, brand inicial y SQLite.

    A diferencia de _create_user_from_payment (Lemon, legacy), deja al usuario
    con password utilizable y un cliente_id derivado (evita caer en "default").
    """
    from core.db import init_db

    email = (email or "").strip().lower()
    plan_norm = normalize_plan(plan)
    brand_name = (brand_name or name or email.split("@")[0] or "Mi Negocio").strip()
    cliente_id = cliente_id_from_brand({"brand_name": brand_name})

    d = load_data()
    users = d.setdefault("users", {})
    if email not in users:
        temp_password = secrets.token_urlsafe(8)
        users[email] = {
            "name": name or email,
            "plan": plan_norm,
            "password_hash": _hash_password(temp_password),
            "status": "active",
            "created_at": int(time.time()),
            "brand": {"brand_name": brand_name, "plan": plan_norm},
        }
        save_data(d)
        print(f"[RIMA] Usuario creado via Gumroad: {email} | Plan: {plan_norm} | cliente_id: {cliente_id}")
        await send_welcome_email(email, users[email]["name"], temp_password)
    else:
        users[email]["plan"] = plan_norm
        users[email]["status"] = "active"
        existing_brand = users[email].setdefault("brand", {})
        existing_brand.setdefault("brand_name", brand_name)
        existing_brand["plan"] = plan_norm
        save_data(d)
        print(f"[RIMA] Usuario actualizado via Gumroad: {email} | Plan: {plan_norm}")

    init_db(cliente_id)
    return cliente_id


@app.post("/api/webhooks/gumroad")
async def gumroad_webhook(request: Request):
    form = await request.form()
    data = dict(form)

    resource = data.get("resource_name", "sale")
    is_test = data.get("test") == "true"
    print(f"[RIMA] Gumroad ping recibido: resource={resource} test={is_test} email={data.get('email', '')}")

    if not _verify_gumroad_seller(data.get("seller_id", "")):
        raise HTTPException(status_code=401, detail="seller_id invalido")

    if resource in ("sale", "") and data.get("email"):
        email = data.get("email", "")
        name = data.get("full_name", "") or email
        plan = data.get("product_name", "")
        if data.get("refunded") == "true" or data.get("disputed") == "true":
            d = load_data()
            email_norm = email.strip().lower()
            if email_norm in d.get("users", {}):
                d["users"][email_norm]["status"] = "cancelled"
                save_data(d)
                print(f"[RIMA] Venta reembolsada/disputada (Gumroad): {email_norm}")
        else:
            await _provision_user_from_payment(email=email, name=name, plan=plan)

    elif resource in ("cancellation", "refund", "dispute"):
        email = data.get("email", "")
        if email:
            d = load_data()
            email_norm = email.strip().lower()
            if email_norm in d.get("users", {}):
                d["users"][email_norm]["status"] = "cancelled"
                save_data(d)
                print(f"[RIMA] Suscripcion cancelada (Gumroad): {email_norm}")

    return {"status": "ok"}


# ── Endpoint: análisis de imagen al subir ──

@app.post("/api/images/analyze/{brand}/{category}/{filename}")
def analyze_image(brand: str, category: str, filename: str, user: dict = Depends(get_current_user)):
    """Analyze an already-uploaded image with Gemini Vision."""
    image_path = str(UPLOADS_DIR / category / filename)
    try:
        result = image_analysis_agent.analyze(image_path, brand, category)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/images/analyze-batch/{brand}/{category}")
def analyze_image_batch(brand: str, category: str, user: dict = Depends(get_current_user)):
    """Analyze all non-analyzed images in a category."""
    try:
        results = image_analysis_agent.analyze_batch(brand, category)
        return JSONResponse(content={"analyzed": len(results), "results": results})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Modelos para nuevos agentes ──

class MarketResearchRequest(BaseModel):
    brand_brief: dict = {}
    competitor_profiles: List[str] = []
    hashtags: List[str] = []


class ContentMonthlyRequest(BaseModel):
    brand_brief: dict = {}
    market_research: str = ""
    month: str = ""


class ScriptRequest(BaseModel):
    idea: dict = {}
    brand_brief: dict = {}
    tone_notes: str = ""


class SalesDMRequest(BaseModel):
    conversation_text: str = ""
    brand_brief: dict = {}


# ── Endpoint: Estudio de Mercado ──

@app.post("/api/agent/market-research")
def run_market_research(req: MarketResearchRequest, user: dict = Depends(get_current_user)):
    try:
        data = load_data()
        email = user.get("email", "")
        brand = get_user_brand(data, email)
        brand_slug = cliente_id_from_brand(brand)
        brief = req.brand_brief if req.brand_brief else _brand_brief_from_brand(
            brand, user_plan=get_user_plan(data, email)
        )
        profiles = req.competitor_profiles or active_ig_usernames(data, email)
        result = market_research_agent.run(
            brand=brand_slug,
            brand_brief=brief,
            competitor_profiles=profiles,
            hashtags=req.hashtags,
            cliente_id=brand_slug,
        )
        if email and result.get("profile_meta"):
            sync_ig_profiles_from_meta(data, email, result["profile_meta"])
            save_data(data)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/market-research/latest")
def api_market_research_latest(user: dict = Depends(get_current_user)):
    from core.db import init_db, get_referentes_market_dashboard, referente_row_to_post

    slug = _get_cliente_id(user)
    latest = load_latest_market_research(slug) or {}

    posts = latest.get("posts") or []
    top_posts = latest.get("top_posts") or []

    # Fallback/enriquecimiento desde SQLite si no hay posts en el JSON backup
    if not posts:
        try:
            init_db(slug)
            db_rows = get_referentes_market_dashboard(slug, limit=60)
            if db_rows:
                posts = [referente_row_to_post(r) for r in db_rows]
                top_posts = posts[:20]
        except Exception:
            pass

    if not latest:
        return {
            "posts": posts,
            "top_posts": top_posts,
            "analysis": "",
            "week": None,
        }

    latest["posts"] = posts
    latest["top_posts"] = top_posts or posts[:20]
    return latest


@app.delete("/api/market-research/scraped")
def api_clear_market_research(user: dict = Depends(get_current_user)):
    from core.db import clear_referentes_contenido, init_db

    slug = _get_cliente_id(user)
    cleared = clear_market_research(slug)
    try:
        init_db(slug)
        cleared["sqlite_referentes"] = clear_referentes_contenido(slug)
    except Exception as e:
        cleared["sqlite_error"] = str(e)
    return {"ok": True, "cleared": cleared}


# ── API: Perfiles referentes (por plan) ──

@app.get("/api/referentes/image")
def api_referente_image(url: str):
    """Proxy de fotos IG (evita bloqueo CORS/hotlink en el dashboard)."""
    if not url or not any(h in url for h in ("cdninstagram.com", "fbcdn.net", "instagram.com")):
        raise HTTPException(400, "URL de imagen no permitida")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RIMA/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "image/jpeg")
        return Response(content=body, media_type=ctype, headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        raise HTTPException(502, f"No se pudo cargar la imagen: {e}")


@app.get("/api/referentes/profiles")
def api_referentes_profiles(user: dict = Depends(get_current_user)):
    data = load_data()
    email = user.get("email", "")
    result = get_profiles(data, email)
    # Persistir limpieza de perfiles vacíos
    if email in data.get("users", {}):
        save_data(data)
    return result


class ReferenteProfileRequest(BaseModel):
    plataforma: str = "instagram"
    username: str = ""
    nombre_nicho: str = ""
    tipos: List[str] = []
    seguidores: str = ""


@app.post("/api/referentes/profiles")
def api_add_referente_profile(req: ReferenteProfileRequest, user: dict = Depends(get_current_user)):
    data = load_data()
    email = user.get("email", "")
    plataforma = req.plataforma if req.plataforma in ("instagram", "youtube") else "instagram"
    try:
        profile = add_profile(data, email, plataforma, req.model_dump())
        save_data(data)
        return {"ok": True, "profile": profile}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.patch("/api/referentes/profiles/{profile_id}")
def api_update_referente_profile(profile_id: str, payload: dict,
                                  user: dict = Depends(get_current_user)):
    data = load_data()
    email = user.get("email", "")
    plataforma = payload.pop("plataforma", "instagram")
    updated = update_profile(data, email, plataforma, profile_id, payload)
    if not updated:
        raise HTTPException(404, "Perfil no encontrado")
    save_data(data)
    return {"ok": True, "profile": updated}


@app.delete("/api/referentes/profiles/{profile_id}")
def api_delete_referente_profile(profile_id: str, plataforma: str = "instagram",
                                  user: dict = Depends(get_current_user)):
    data = load_data()
    email = user.get("email", "")
    if not delete_profile(data, email, plataforma, profile_id):
        raise HTTPException(404, "Perfil no encontrado")
    save_data(data)
    return {"ok": True}


@app.post("/api/referentes/scrape")
def api_referentes_scrape(user: dict = Depends(get_current_user)):
    """Actualización manual — consume 1 crédito semanal (se renueva cada lunes)."""
    data = load_data()
    email = user.get("email", "")
    try:
        remaining = consume_manual_scrape(data, email)
    except ValueError as e:
        raise HTTPException(429, str(e))

    brand = get_user_brand(data, email)
    slug = cliente_id_from_brand(brand)
    brief = _brand_brief_from_brand(brand, user_plan=get_user_plan(data, email))
    profiles = active_ig_usernames(data, email)
    if not profiles:
        raise HTTPException(400, "Agrega al menos un perfil de Instagram activo en Referencias")

    try:
        result = market_research_agent.run(
            brand=slug,
            brand_brief=brief,
            competitor_profiles=profiles,
            cliente_id=slug,
        )
        # Actualizar referentes: foto, seguidores, nicho, último scrape
        user_rec = data["users"][email]
        now_label = datetime.now().strftime("Lun %d %b · %H:%M")
        if result.get("profile_meta"):
            sync_ig_profiles_from_meta(data, email, result["profile_meta"])
        for p in user_rec.get("referentes_profiles", {}).get("instagram", []):
            if p.get("username", "").strip():
                p["ultimo_scraping"] = now_label
                p["estado"] = "activo"
        save_data(data)
        return {
            "ok": True,
            "manual_remaining": remaining,
            "posts_analyzed": result.get("posts_analyzed", 0),
            "transcripts_ok": result.get("transcripts_ok", 0),
            "deep_analyzed": result.get("deep_analyzed", 0),
            "analysis_preview": (result.get("analysis") or "")[:300],
        }
    except Exception as e:
        # Devolver crédito si falló el scrape
        user_rec = data["users"][email]
        scraping = user_rec.setdefault("scraping", {})
        scraping["manual_remaining"] = min(
            MANUAL_SCRAPE_CREDITS,
            scraping.get("manual_remaining", 0) + 1,
        )
        save_data(data)
        raise HTTPException(500, str(e))


# ── Endpoint: Calendario mensual de contenido ──

@app.post("/api/agent/content-monthly")
def run_content_monthly(req: ContentMonthlyRequest, user: dict = Depends(get_current_user)):
    try:
        result = content_agent.run(
            brand_brief=req.brand_brief,
            market_research=req.market_research or None,
            month=req.month or None,
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint: Calendario de contenido desde dashboard ──

class ContentRunRequest(BaseModel):
    month: str = ""
    enfoque: dict = {"ventas": 60, "educacion": 30, "conexion": 10}

@app.post("/api/agent/content/run")
def run_content_dashboard(req: ContentRunRequest, user: dict = Depends(get_current_user)):
    """Genera calendario mensual usando el brief guardado en rima_data.json."""
    data = load_data()
    email = user.get("email", "")
    brand = get_user_brand(data, email)
    brand_brief = _brand_brief_from_brand(brand, user_plan=get_user_plan(data, email))
    enfoque = normalize_enfoque_default(req.enfoque or brand.get("enfoque_default"))
    cliente_id = cliente_id_from_brand(brand)
    try:
        result = content_agent.run(
            brand_brief=brand_brief,
            month=req.month or None,
            enfoque=enfoque,
            cliente_id=cliente_id,
        )
        data["last_content_calendar"] = result
        save_data(data)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/content/clear-planned")
def clear_planned_content(user: dict = Depends(get_current_user)):
    """Borra piezas planificadas sin aprobaciones ni contenido cargado (ventana 30 días)."""
    from core.db import delete_publicaciones_regenerables, init_db
    from datetime import date, timedelta
    from agents.content.agent import PLAN_DAYS
    cid = _get_cliente_id(user)
    try:
        init_db(cid)
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=PLAN_DAYS - 1)
        deleted = delete_publicaciones_regenerables(
            cid,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
        )
        return {
            "ok": True,
            "deleted": deleted,
            "starts_on": start.strftime("%Y-%m-%d"),
            "ends_on": end.strftime("%Y-%m-%d"),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ── API: Publicaciones desde SQLite ──

def _get_cliente_id(user: dict) -> str:
    data = load_data()
    brand = get_user_brand(data, user.get("email", ""))
    return cliente_id_from_brand(brand)

@app.get("/api/publicaciones")
def api_get_publicaciones(mes: str = None, status: str = None,
                           tipo: str = None, desde: str = None, hasta: str = None,
                           user: dict = Depends(get_current_user)):
    from core.db import get_publicaciones, init_db
    cid = _get_cliente_id(user)
    try:
        init_db(cid)
        pubs = get_publicaciones(cid, mes=mes, status=status, tipo=tipo)
        if desde or hasta:
            pubs = [
                p for p in pubs
                if (not desde or (p.get("fecha") or "") >= desde)
                and (not hasta or (p.get("fecha") or "") <= hasta)
            ]
        return {"publicaciones": pubs, "total": len(pubs)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/publicaciones/{pub_id}")
def api_get_publicacion(pub_id: str, user: dict = Depends(get_current_user)):
    from core.db import get_publicacion
    cid = _get_cliente_id(user)
    pub = get_publicacion(cid, pub_id)
    if not pub:
        raise HTTPException(404, "Publicacion no encontrada")
    return pub

@app.patch("/api/publicaciones/{pub_id}/status")
def api_update_status(pub_id: str, payload: dict, user: dict = Depends(get_current_user)):
    from core.db import update_publicacion_status
    cid = _get_cliente_id(user)
    status = payload.get("status")
    if not status:
        raise HTTPException(400, "status requerido")
    update_publicacion_status(cid, pub_id, status)
    return {"ok": True, "pub_id": pub_id, "status": status}

@app.patch("/api/publicaciones/{pub_id}/aprobar")
def api_aprobar(pub_id: str, payload: dict, user: dict = Depends(get_current_user)):
    from core.db import update_publicacion_field, update_publicacion_status, get_publicacion
    from core.weekly_helpers import sync_weekly_state_from_db
    cid = _get_cliente_id(user)
    campo = payload.get("campo")  # tematica | copy | visual
    if campo not in ("tematica", "copy", "visual"):
        raise HTTPException(400, "campo debe ser tematica, copy o visual")
    pub = get_publicacion(cid, pub_id)
    if not pub:
        raise HTTPException(404, "Publicacion no encontrada")
    aprobaciones = pub.get("aprobaciones_json") or {}
    aprobaciones[campo] = True
    update_publicacion_field(cid, pub_id, "aprobaciones_json", aprobaciones)

    # Transiciones de estado: aprobar copy/visual avanza el pipeline E2E.
    status = pub.get("status")
    new_status = status
    if campo == "copy" and status in ("copy_generado", "copy_enviado"):
        new_status = "copy_aprobado"
    elif campo == "visual" and status in ("en_produccion", "produccion_enviada"):
        new_status = "produccion_aprobada"
    if new_status != status:
        update_publicacion_status(cid, pub_id, new_status)
        brand_name = get_user_brand(load_data(), user.get("email", "")).get("brand_name") or "default"
        sync_weekly_state_from_db(cid, brand_name, pub.get("fecha"))
    return {"ok": True, "aprobaciones": aprobaciones, "status": new_status}

@app.get("/api/referentes/top")
def api_top_referentes(tipo: str = None, limit: int = 10,
                        user: dict = Depends(get_current_user)):
    from core.db import get_top_referentes, init_db
    cid = _get_cliente_id(user)
    try:
        init_db(cid)
        refs = get_top_referentes(cid, tipo=tipo, limit=limit)
        return {"referentes": refs, "total": len(refs)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/imagenes")
def api_get_imagenes(uso: str = None, user: dict = Depends(get_current_user)):
    from core.db import get_imagenes_para, init_db
    cid = _get_cliente_id(user)
    try:
        init_db(cid)
        imgs = get_imagenes_para(cid, uso or "")
        return {"imagenes": imgs, "total": len(imgs)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Endpoint: Generación de guion ──

@app.post("/api/agent/script")
def run_script(req: ScriptRequest, user: dict = Depends(get_current_user)):
    try:
        result = script_agent.run(
            idea=req.idea,
            brand_brief=req.brand_brief,
            tone_notes=req.tone_notes,
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Endpoint: Ventas DMs ──

SALES_DM_SYSTEM = """Eres el Agente de Ventas de RIMA especializado en análisis de DMs de Instagram.
Evaluás conversaciones de prospectos y generás respuestas usando metodología de ventas consultiva.

Reglas:
- Calificás al prospecto antes de proponer una llamada
- Las respuestas suenan humanas, no robóticas
- Nunca revelás el precio sin establecer valor primero
- Identificás la etapa del prospecto: frío / tibio / caliente / listo para agendar
- Escribís en español LATAM"""

@app.post("/api/agent/sales-dm")
def run_sales_dm(req: SalesDMRequest, user: dict = Depends(get_current_user)):
    try:
        brief = req.brand_brief
        prompt = f"""
Analiza esta conversación de DM de Instagram y genera una respuesta estratégica:

NEGOCIO: {brief.get('business_name', '')}
SERVICIO: {brief.get('service', '')}
PRECIO: {brief.get('price', '')}
RESULTADO PRINCIPAL: {brief.get('main_result', '')}

CONVERSACIÓN:
{req.conversation_text}

Entrega en este formato:

## CLASIFICACIÓN DEL PROSPECTO
- Temperatura: Frío / Tibio / Caliente / Listo para agendar
- Score de calificación (1-10):
- Señales detectadas (BANT — Budget/Authority/Need/Timeline):

## ANÁLISIS
Qué está pasando en esta conversación y qué quiere el prospecto realmente

## RESPUESTA SUGERIDA
El mensaje exacto para enviar por DM (sonando humano y conversacional)

## SIGUIENTE ACCIÓN
Qué hacer después de enviar esta respuesta:
- [ ] Esperar respuesta
- [ ] Proponer llamada
- [ ] Enviar más información
- [ ] Cerrar / no calificado

## RESPUESTA ALTERNATIVA (si rechaza)
Mensaje de seguimiento si no responde en 48h
"""
        response = gemini.generate(prompt, SALES_DM_SYSTEM)
        result = {
            "agent": "sales_dm",
            "timestamp": datetime.now().isoformat(),
            "brand": brief.get("business_name", ""),
            "analysis": response,
        }
        os.makedirs("logs/sales_dm", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f"logs/sales_dm/{brief.get('business_name', 'unknown')}_{ts}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Weekly Workflow Models ──

class WeeklyStartRequest(BaseModel):
    brand: str = ""
    week_label: str = ""
    month: str = ""
    competitor_profiles: List[str] = []
    skip_scrape: bool = True


class WeeklyClearRequest(BaseModel):
    week_start: str = ""   # lunes YYYY-MM-DD; vacío = semana actual
    restart: bool = False  # regenerar propuestas con el agente semanal


class WeeklyApprovalRequest(BaseModel):
    brand: str
    week: str
    index: int = 0
    chosen_proposal: dict = {}
    chosen_referent: dict = {}
    feedback: str = ""
    changes_requested: str = ""
    topic_override: str = ""


class MemoryUpdateRequest(BaseModel):
    brand: str
    updates: dict = {}


# ── Weekly Workflow Endpoints ──

@app.post("/api/agent/weekly/start")
def weekly_start(req: WeeklyStartRequest, user: dict = Depends(get_current_user)):
    try:
        data = load_data()
        email = user.get("email", "")
        brand_dict = get_user_brand(data, email)
        brand_name = req.brand or brand_dict.get("brand_name") or "default"
        cid = _get_cliente_id(user)
        brief = _brand_brief_from_brand(brand_dict, user_plan=get_user_plan(data, email))
        result = weekly_agent.start_week(
            brand=brand_name,
            week_label=req.week_label or None,
            month=req.month or None,
            competitor_profiles=req.competitor_profiles,
            cliente_id=cid,
            skip_scrape=req.skip_scrape,
            brand_brief=brief,
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/weekly/clear-week")
def weekly_clear_week(req: WeeklyClearRequest = WeeklyClearRequest(),
                      user: dict = Depends(get_current_user)):
    """Reinicia propuesta/copy de una semana sin borrar slots del plan mensual ni el estudio de mercado."""
    from datetime import datetime as dt
    from core.db import reset_weekly_work, init_db
    from core.weekly_helpers import week_bounds
    data = load_data()
    email = user.get("email", "")
    brand_dict = get_user_brand(data, email)
    brand_name = brand_dict.get("brand_name") or "default"
    cid = _get_cliente_id(user)
    try:
        init_db(cid)
        if req.week_start:
            ref = dt.strptime(req.week_start, "%Y-%m-%d").date()
            start, end, week = week_bounds(ref)
        else:
            start, end, week = week_bounds()
        reset = reset_weekly_work(cid, start, end)
        state_cleared = clear_weekly_state(brand_name, week)
        result = {
            "ok": True,
            "week": week,
            "week_start": start,
            "week_end": end,
            "reset": reset,
            "weekly_state_cleared": state_cleared,
        }
        if req.restart:
            brief = _brand_brief_from_brand(brand_dict, user_plan=get_user_plan(data, email))
            started = weekly_agent.start_week(
                brand=brand_name,
                week_label=week,
                cliente_id=cid,
                skip_scrape=True,
                brand_brief=brief,
                week_start=start,
            )
            result["restarted"] = True
            result["propuestas_generadas"] = started.get("propuestas_generadas", 0)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ElegirReferenteRequest(BaseModel):
    alternativa_index: int = 0
    generar_copy: bool = True


@app.post("/api/publicaciones/{pub_id}/refresh-propuesta")
def refresh_propuesta(pub_id: str, user: dict = Depends(get_current_user)):
    """Descarta las 2 alternativas actuales y muestra las siguientes del pool."""
    from core.client_store import load_latest_market_research
    from core.weekly_helpers import refresh_propuesta_for_pub
    cid = _get_cliente_id(user)
    market = load_latest_market_research(cid) or {}
    try:
        result = refresh_propuesta_for_pub(cid, pub_id, market)
        if not result.get("ok"):
            raise HTTPException(400, result.get("error") or "No se pudo refrescar")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/publicaciones/{pub_id}/elegir-referente")
def elegir_referente(pub_id: str, req: ElegirReferenteRequest,
                     user: dict = Depends(get_current_user)):
    """El cliente elige qué referente modelar (etapa Propuesta) y opcionalmente genera copy."""
    data = load_data()
    email = user.get("email", "")
    brand_dict = get_user_brand(data, email)
    brand_name = brand_dict.get("brand_name", "default")
    cid = _get_cliente_id(user)
    brief = _brand_brief_from_brand(brand_dict, user_plan=get_user_plan(data, email))
    try:
        if req.generar_copy:
            result = weekly_agent.generate_copy_for_publicacion(
                cid, brand_name, pub_id, req.alternativa_index, brand_brief=brief,
            )
        else:
            from core.db import get_publicacion, update_publicacion_field, update_publicacion_status
            pub = get_publicacion(cid, pub_id)
            if not pub:
                raise HTTPException(404, "Publicación no encontrada")
            prop = pub.get("propuesta_json") or {}
            alts = (prop if isinstance(prop, dict) else {}).get("alternativas") or []
            if req.alternativa_index >= len(alts):
                raise HTTPException(400, "Índice de alternativa inválido")
            elegida = alts[req.alternativa_index]
            prop["elegida"] = elegida
            prop["alternativa_index"] = req.alternativa_index
            update_publicacion_field(cid, pub_id, "propuesta_json", prop)
            update_publicacion_field(cid, pub_id, "referente_id", elegida.get("referente_id") or "")
            update_publicacion_status(cid, pub_id, "propuesta_aprobada")
            refreshed = weekly_agent._refresh_sibling_propuestas(
                cid, pub.get("fecha"), skip_pub_id=pub_id, tipo=pub.get("tipo"),
            )
            result = {
                "pub_id": pub_id,
                "referente": elegida,
                "status": "propuesta_aprobada",
                "propuestas_actualizadas": refreshed,
            }
        if result.get("error"):
            raise HTTPException(400, result["error"])
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/publicaciones/{pub_id}/producir")
def api_producir(pub_id: str, user: dict = Depends(get_current_user)):
    """Etapa 3: producción tras copy_aprobado.

    Reel → script_agent (guion teleprompter A/B).
    Carrusel/Historia → visual_composer (slides + imágenes del cliente o
    kie_pending con prompt sugerido). Determinístico, sin LLM.
    """
    from core.db import (
        get_publicacion, update_publicacion_field, update_publicacion_status,
    )
    from agents.visual_composer import plan_slides, match_images_to_slides
    from core.weekly_helpers import sync_weekly_state_from_db
    data = load_data()
    email = user.get("email", "")
    brand_dict = get_user_brand(data, email)
    brand_name = brand_dict.get("brand_name") or "default"
    cid = _get_cliente_id(user)
    pub = get_publicacion(cid, pub_id)
    if not pub:
        raise HTTPException(404, "Publicación no encontrada")
    if pub.get("status") != "copy_aprobado":
        raise HTTPException(400, "La publicación debe estar en copy_aprobado para pasar a producción")
    copy_j = pub.get("copy_json") or {}
    if isinstance(copy_j, str):
        try:
            copy_j = json.loads(copy_j)
        except Exception:
            copy_j = {}
    tipo = pub.get("tipo", "reel")
    try:
        if tipo == "reel":
            brief = _brand_brief_from_brand(brand_dict, user_plan=get_user_plan(data, email))
            idea = copy_j.get("idea") or {
                "hook": copy_j.get("hook", ""),
                "development": copy_j.get("desarrollo", ""),
                "cta": copy_j.get("cta", ""),
                "content_type": pub.get("tematica", ""),
            }
            script = script_agent.run(idea=idea, brand_brief=brief)
            produccion = {
                "etapa": "produccion",
                "tipo": "guion",
                "script_principal": script.get("script_principal", ""),
                "script_variante_b": script.get("script_variante_b", ""),
                "recording_tips": script.get("recording_tips", {}),
                "estimated_duration": script.get("estimated_duration", ""),
                "generated_at": script.get("timestamp", ""),
            }
        else:
            slot_context = {
                "tematica": pub.get("tematica", ""),
                "enfoque": pub.get("enfoque", ""),
                "fecha": pub.get("fecha", ""),
            }
            slides = plan_slides(copy_j, tipo, slot_context)
            if not slides:
                raise HTTPException(400, "El copy aprobado no tiene contenido para componer slides")
            produccion = {
                "etapa": "produccion",
                "tipo": "visual",
                "slides": match_images_to_slides(cid, tipo, slides, slot_context),
                "generated_at": datetime.now().isoformat(),
            }
        update_publicacion_field(cid, pub_id, "produccion_json", produccion)
        update_publicacion_status(cid, pub_id, "en_produccion")
        sync_weekly_state_from_db(cid, brand_name, pub.get("fecha"))
        return {"ok": True, "pub_id": pub_id, "tipo": tipo,
                "status": "en_produccion", "produccion": produccion}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class GenerarImagenSlideRequest(BaseModel):
    slide_index: int


@app.post("/api/publicaciones/{pub_id}/generar-imagen-slide")
def api_generar_imagen_slide(pub_id: str, req: GenerarImagenSlideRequest,
                             user: dict = Depends(get_current_user)):
    """Genera con KIE AI la imagen de UN slide kie_pending.

    Acción explícita del usuario (botón) — nunca generación masiva. El rate
    limit 20/10s lo garantiza core/kie_client.RateLimiter.
    """
    from core.db import get_publicacion, update_publicacion_field
    from core import kie_client
    from core.visual_spec import spec_a_prompt

    cid = _get_cliente_id(user)
    pub = get_publicacion(cid, pub_id)
    if not pub:
        raise HTTPException(404, "Publicación no encontrada")
    prod = pub.get("produccion_json") or {}
    if isinstance(prod, str):
        try:
            prod = json.loads(prod)
        except Exception:
            prod = {}
    slides = prod.get("slides") or []
    idx = req.slide_index
    if not 0 <= idx < len(slides):
        raise HTTPException(400, "slide_index fuera de rango")
    slide = slides[idx]
    if slide.get("image_source") != "kie_pending":
        raise HTTPException(400, "El slide no está pendiente de generación IA")
    spec = slide.get("spec_visual") or {}
    prompt = slide.get("prompt_sugerido") or (spec_a_prompt(spec) if spec else "")
    if not prompt:
        raise HTTPException(400, "El slide no tiene prompt_sugerido ni spec_visual")
    ratio = slide.get("ratio") or spec.get("ratio") or "1:1"

    res = kie_client.generate_image(prompt, ratio)
    if res.get("status") != "ok":
        return {"ok": False, "status": res.get("status", "error"),
                "reason": res.get("reason", "Error desconocido de KIE AI")}

    nombre = (f"{pub_id[:8]}_slide{slide.get('slide_number', idx + 1)}"
              f"_{int(datetime.now().timestamp())}.png")
    destino = UPLOADS_DIR / "generadas" / cid / nombre
    dl = kie_client.download_image(res["image_url"], destino)
    if dl.get("status") != "ok":
        # La imagen existe en el CDN de KIE — devolver URL y task para no
        # perder el crédito si la descarga falla.
        return {"ok": False, "status": "error",
                "reason": f"Imagen generada pero falló la descarga: {dl.get('reason')}",
                "task_id": res.get("task_id"), "image_url": res.get("image_url")}

    slide.update({
        "image_source": "generada_ia",
        "archivo_url": f"/uploads/generadas/{cid}/{nombre}",
        "text_zone": spec.get("zona_texto") or {"zone": "center"},
        "spec_usada": spec,
        "prompt_usado": prompt,
        "kie_task_id": res.get("task_id"),
        "generated_at": datetime.now().isoformat(),
    })
    update_publicacion_field(cid, pub_id, "produccion_json", prod)
    return {"ok": True, "slide_index": idx, "slide": slide,
            "credits_consumed": res.get("credits_consumed")}


@app.get("/api/agent/weekly/status/{brand}/{week}")
def weekly_status(brand: str, week: str, user: dict = Depends(get_current_user)):
    try:
        return JSONResponse(content=weekly_agent.get_weekly_status(brand, week))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/weekly/next-story")
def weekly_next_story(req: WeeklyApprovalRequest, user: dict = Depends(get_current_user)):
    try:
        return JSONResponse(content=weekly_agent.next_story(req.brand, req.week))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/weekly/approve-story")
def weekly_approve_story(req: WeeklyApprovalRequest, user: dict = Depends(get_current_user)):
    try:
        result = weekly_agent.approve_story(
            brand=req.brand, week=req.week,
            story_index=req.index,
            chosen_proposal=req.chosen_proposal,
            feedback=req.feedback,
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/weekly/next-carousel")
def weekly_next_carousel(req: WeeklyApprovalRequest, user: dict = Depends(get_current_user)):
    try:
        return JSONResponse(content=weekly_agent.next_carousel(req.brand, req.week))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/weekly/approve-carousel-referent")
def weekly_approve_carousel_referent(req: WeeklyApprovalRequest, user: dict = Depends(get_current_user)):
    try:
        result = weekly_agent.approve_carousel_referent(
            brand=req.brand, week=req.week,
            carousel_index=req.index,
            chosen_referent=req.chosen_referent,
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/weekly/approve-carousel-copy")
def weekly_approve_carousel_copy(req: WeeklyApprovalRequest, user: dict = Depends(get_current_user)):
    try:
        result = weekly_agent.approve_carousel_copy(
            brand=req.brand, week=req.week,
            carousel_index=req.index,
            feedback=req.feedback,
            changes_requested=req.changes_requested,
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/weekly/next-reel")
def weekly_next_reel(req: WeeklyApprovalRequest, user: dict = Depends(get_current_user)):
    try:
        return JSONResponse(content=weekly_agent.next_reel(req.brand, req.week))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/weekly/approve-reel-referent")
def weekly_approve_reel_referent(req: WeeklyApprovalRequest, user: dict = Depends(get_current_user)):
    try:
        result = weekly_agent.approve_reel_referent(
            brand=req.brand, week=req.week,
            reel_index=req.index,
            chosen_referent=req.chosen_referent,
            topic_override=req.topic_override or None,
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agent/weekly/approve-reel-copy")
def weekly_approve_reel_copy(req: WeeklyApprovalRequest, user: dict = Depends(get_current_user)):
    try:
        result = weekly_agent.approve_reel_copy(
            brand=req.brand, week=req.week,
            reel_index=req.index,
            feedback=req.feedback,
            changes_requested=req.changes_requested,
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Client Memory Endpoints ──

@app.get("/api/client/{brand}/memory")
def get_client_memory(brand: str, user: dict = Depends(get_current_user)):
    return JSONResponse(content=load_memory(brand))


@app.post("/api/client/{brand}/memory")
def patch_client_memory(brand: str, req: MemoryUpdateRequest, user: dict = Depends(get_current_user)):
    result = update_memory(brand, req.updates)
    return JSONResponse(content=result)


@app.get("/api/client/{brand}/brief")
def get_client_brief(brand: str, user: dict = Depends(get_current_user)):
    brief = load_brief(brand)
    if not brief:
        raise HTTPException(status_code=404, detail="Brief no encontrado")
    return JSONResponse(content=brief)


@app.post("/api/client/{brand}/setup")
def setup_client(brand: str, brief: BrandBrief):
    """Initialize client folder structure and save brief."""
    ensure_client_dirs(brand)
    save_brief(brand, brief.model_dump())
    return JSONResponse(content={"status": "ok", "brand": brand})


# ── Auth routes ──────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

@app.get("/", response_class=HTMLResponse)
def root_redirect():
    return RedirectResponse(url="/login", status_code=302)

@app.get("/login", response_class=HTMLResponse)
def login_page():
    path = DASHBOARD / "login.html"
    return HTMLResponse(content=path.read_text(encoding="utf-8"))

@app.get("/auth/google")
async def auth_google(request: Request):
    redirect_uri = os.environ.get("BASE_URL", "https://rima.n8n-ghl.com") + "/auth/google/callback"
    return await _oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request):
    token = await _oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or await _oauth.google.userinfo(token=token)
    email = userinfo["email"]
    name = userinfo.get("name", email)

    d = load_data()
    users_db = d.setdefault("users", {})
    user, created = get_or_create_google_user(email, name, users_db)
    if created:
        save_data(d)

    jwt_token = create_token(user["email"], user["role"])
    resp = RedirectResponse(url="/home", status_code=302)
    resp.set_cookie(
        key=COOKIE_NAME,
        value=jwt_token,
        httponly=True,
        max_age=8 * 3600,
        samesite="lax",
        secure=False,
    )
    return resp


@app.post("/auth/login")
def auth_login(body: LoginRequest, response: JSONResponse.__class__ = None):
    from fastapi.responses import JSONResponse as JR
    d = load_data()
    users_db = d.get("users", {})
    user = verify_login(body.email.strip().lower(), body.password.strip(), users_db)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = create_token(user["email"], user["role"])
    resp = JR(content={"ok": True, "redirect": "/home"})
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=8 * 3600,
        samesite="lax",
        secure=False,  # cambiar a True con HTTPS
    )
    return resp

@app.get("/auth/logout")
def auth_logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    return resp

@app.get("/auth/me")
def auth_me(user: dict = Depends(get_current_user)):
    data = load_data()
    email = user.get("email") or user.get("sub", "")
    role = user.get("role", "user")
    if role == "admin":
        brand = get_user_brand(data, email)
        return {
            "email": email,
            "sub": email,
            "role": role,
            "name": user.get("name", "Admin"),
            "plan": normalize_plan(brand.get("plan", "max")),
            "brand_name": brand.get("brand_name", "Mi Negocio"),
            "ref_limits": get_ref_limits(brand.get("plan", "max")),
        }
    rec = data.get("users", {}).get(email, {})
    brand = get_user_brand(data, email)
    plan = get_user_plan(data, email)
    limits = get_ref_limits(plan)
    return {
        "email": email,
        "sub": email,
        "role": role,
        "name": rec.get("name", user.get("name", email.split("@")[0] if email else "Usuario")),
        "plan": plan,
        "brand_name": brand.get("brand_name", ""),
        "ref_limits": limits,
    }

# ── Proteger home y dashboard ─────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home_protected(request: Request):
    redirect = require_auth(request)
    if redirect:
        return redirect
    return serve_html("index.html", request)


# ── API: Calendar (adaptador para rima-calenadrio.html) ──
# Mapea publicaciones SQLite al formato esperado por el calendario del dashboard.

def _pub_to_calendar_item(pub: dict) -> dict:
    copy_j = pub.get("copy_json") or {}
    prop_j = pub.get("propuesta_json") or {}
    if isinstance(copy_j, str):
        import json as _json
        try: copy_j = _json.loads(copy_j)
        except Exception: copy_j = {}
    if isinstance(prop_j, str):
        import json as _json
        try: prop_j = _json.loads(prop_j)
        except Exception: prop_j = {}

    title = (
        copy_j.get("titulo") or
        prop_j.get("angulo") or
        pub.get("tematica") or
        pub.get("tipo", "Sin título")
    )

    status_map = {
        "planificado": "pendiente",
        "propuesta_generada": "validacion",
        "propuesta_enviada": "validacion",
        "propuesta_aprobada": "validacion",
        "copy_generado": "validacion",
        "copy_enviado": "validacion",
        "copy_aprobado": "validacion",
        "en_produccion": "validacion",
        "produccion_enviada": "validacion",
        "produccion_aprobada": "validacion",
        "programado": "programado",
        "publicado": "publicado",
        "cancelado": "pendiente",
    }

    return {
        "id": pub["id"],
        "date": pub["fecha"],
        "type": pub["tipo"],
        "title": title,
        "caption": copy_j.get("hook", ""),
        "development": copy_j.get("desarrollo", "") or prop_j.get("hook_idea", ""),
        "cta": copy_j.get("cta", ""),
        "status": status_map.get(pub.get("status", "planificado"), "pendiente"),
        "content_type": (pub.get("tematica") or "").lower().replace("ó", "o").replace("ú", "u"),
        "content_type_label": pub.get("tematica", ""),
        "enfoque": pub.get("enfoque", ""),
        "semana": pub.get("semana"),
        "dia": pub.get("dia", ""),
    }


@app.get("/api/calendar")
def api_calendar_get(month: str = None, user: dict = Depends(get_current_user)):
    """GET /api/calendar?month=YYYY-MM — retorna items en formato calendario.

    Filtra por RANGO DE FECHAS del mes mostrado en la grilla (no por el string
    "mes" guardado en cada fila). Esto es necesario porque el plan del agente es
    una ventana continua de 30 días desde mañana — sus piezas pueden caer en dos
    meses calendario distintos, y filtrar por igualdad de string "mes" dejaba
    piezas recién generadas fuera de la vista (parecía que "no se reflejaban").
    """
    from core.db import get_publicaciones, init_db
    from datetime import date
    import calendar as _calmod
    cid = _get_cliente_id(user)
    try:
        init_db(cid)
        if month:
            y, m = (int(x) for x in month.split("-"))
        else:
            today = date.today()
            y, m = today.year, today.month

        last_day = _calmod.monthrange(y, m)[1]
        start_str = f"{y:04d}-{m:02d}-01"
        end_str = f"{y:04d}-{m:02d}-{last_day:02d}"
        mes_str = f"{y:04d}-{m:02d}"

        pubs = get_publicaciones(cid)
        pubs_in_range = [p for p in pubs if start_str <= (p.get("fecha") or "") <= end_str]
        items = [_pub_to_calendar_item(p) for p in pubs_in_range]
        return {"items": items, "total": len(items), "mes": mes_str}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/calendar/generate")
def api_calendar_generate(payload: dict, user: dict = Depends(get_current_user)):
    """POST /api/calendar/generate — ejecuta el Planificador (ventana de 30 días
    desde mañana, según límites de volumen del plan del cliente) y retorna las
    piezas recién creadas, identificadas por su rango real de fechas (starts_on..ends_on)
    — no por un "mes calendario", que el plan ya no usa como ancla.
    """
    data = load_data()
    email = user.get("email", "")
    brand = get_user_brand(data, email)
    brand_brief = _brand_brief_from_brand(brand, user_plan=get_user_plan(data, email))
    enfoque = normalize_enfoque_default(payload.get("enfoque") or brand.get("enfoque_default"))
    cid = cliente_id_from_brand(brand)

    try:
        result = content_agent.run(
            brand_brief=brand_brief,
            enfoque=enfoque,
            cliente_id=cid,
        )
        starts_on = result.get("starts_on")
        ends_on = result.get("ends_on")

        from core.db import get_publicaciones
        pubs = get_publicaciones(cid)
        pubs_in_range = [p for p in pubs
                         if starts_on <= (p.get("fecha") or "") <= ends_on]
        items = [_pub_to_calendar_item(p) for p in pubs_in_range]
        return {
            "items": items,
            "count": len(items),
            "starts_on": starts_on,
            "ends_on": ends_on,
            "plan_tier": result.get("plan_tier"),
            "limites_semanales": result.get("limites_semanales"),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/calendar")
def api_calendar_create(payload: dict, user: dict = Depends(get_current_user)):
    """POST /api/calendar — crea una publicación manual."""
    from core.db import create_publicacion, init_db
    from datetime import date as _date, datetime as _dt
    cid = _get_cliente_id(user)
    try:
        init_db(cid)
        fecha = payload.get("date", str(_date.today()))
        tipo = payload.get("type", "reel")
        title = payload.get("title", "Sin título")
        caption = payload.get("caption", "")
        status_in = payload.get("status", "pendiente")

        # Calcular mes y dia
        d = _dt.strptime(fecha, "%Y-%m-%d")
        MESES = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                 "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        DIAS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
        mes_str = MESES[d.month - 1] + " " + str(d.year)
        dia_str = DIAS[d.weekday()]
        semana = (d.day - 1) // 7 + 1

        # Mapear status inverso
        inv_status = {
            "pendiente": "planificado", "validacion": "propuesta_generada",
            "programado": "programado", "publicado": "publicado",
        }
        db_status = inv_status.get(status_in, "planificado")

        pub = create_publicacion(cid, {
            "fecha": fecha, "semana": semana, "dia": dia_str,
            "mes": mes_str, "tipo": tipo, "tematica": title,
            "status": db_status, "agente_origen": "manual",
        })

        # Si hay caption, guardarlo en copy_json
        if caption:
            from core.db import update_publicacion_field
            update_publicacion_field(cid, pub["id"], "copy_json", {"hook": caption})
            pub["copy_json"] = {"hook": caption}

        return _pub_to_calendar_item(pub)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.put("/api/calendar/{item_id}")
def api_calendar_update(item_id: str, payload: dict, user: dict = Depends(get_current_user)):
    """PUT /api/calendar/{id} — actualiza titulo, tipo, caption y status."""
    from core.db import get_publicacion, update_publicacion_field, update_publicacion_status
    cid = _get_cliente_id(user)
    pub = get_publicacion(cid, item_id)
    if not pub:
        raise HTTPException(404, "Publicacion no encontrada")

    if "title" in payload:
        update_publicacion_field(cid, item_id, "tematica", payload["title"])
    if "type" in payload:
        update_publicacion_field(cid, item_id, "tipo", payload["type"])
    if "caption" in payload:
        from core.db import update_publicacion_field as upf
        copy_j = pub.get("copy_json") or {}
        copy_j["hook"] = payload["caption"]
        upf(cid, item_id, "copy_json", copy_j)
    if "status" in payload:
        inv_status = {
            "pendiente": "planificado", "validacion": "propuesta_generada",
            "programado": "programado", "publicado": "publicado",
        }
        update_publicacion_status(cid, item_id, inv_status.get(payload["status"], "planificado"))

    from core.db import get_publicacion as gp
    updated = gp(cid, item_id)
    return _pub_to_calendar_item(updated)


@app.delete("/api/calendar/{item_id}")
def api_calendar_delete(item_id: str, user: dict = Depends(get_current_user)):
    """DELETE /api/calendar/{id} — elimina la publicación."""
    from core.db import db as _db
    cid = _get_cliente_id(user)
    with _db(cid) as conn:
        conn.execute("DELETE FROM publicaciones WHERE id = ? AND cliente_id = ?", (item_id, cid))
    return {"ok": True, "deleted": item_id}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

