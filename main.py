from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Header
from fastapi.responses import HTMLResponse, JSONResponse
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
import uuid
import calendar as cal_module
import re

from dotenv import load_dotenv
load_dotenv(override=True)

from agents.landing.agent import landing_agent
from agents.content.agent import content_agent
from agents.meta.agent import meta_agent
from agents.sales.agent import sales_agent
from agents.prospecting.agent import prospecting_agent

app = FastAPI(title="RIMA AI", description="Marketing AI para LATAM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Persistencia local en JSON
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CSS compartido inyectado en <head>
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SHARED_CSS = """
<style id="rima-shared">
  /* Zoom global â€” equivale a 125% del navegador */
  html { zoom: 1.25; }
  /* NormalizaciÃ³n tipogrÃ¡fica global */
  body { font-size: 13px !important; }
  aside nav span { font-size: 11px !important; }
  aside p, aside .text-\\[9px\\], aside .text-\\[10px\\] { font-size: 9px !important; }
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
</style>
"""

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# JS universal inyectado al final del <body>
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SHARED_JS = """
<div id="rima-toast"></div>
<script>
(function() {
  var currentPath = window.location.pathname;

  // â”€â”€ Sidebar estandarizado (reemplaza el de cada pÃ¡gina) â”€â”€
  var NAV_ITEMS = [
    { label:'Dashboard',             href:'/',             group:'COMENCEMOS', color:'violet',  icon:'M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25A2.25 2.25 0 0113.5 8.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z' },
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

  // Reemplazar el aside existente con el sidebar estandarizado
  var existingAside = document.querySelector('aside');
  if (existingAside) {
    existingAside.parentNode.replaceChild(buildSidebar(), existingAside);
  }

  // â”€â”€ Toast helper â”€â”€
  window.rimaToast = function(msg, type) {
    var t = document.getElementById('rima-toast');
    t.textContent = (type === 'error' ? 'âœ—  ' : 'âœ“  ') + msg;
    t.className = type === 'error' ? 'error show' : 'show';
    setTimeout(function() { t.className = ''; }, 3000);
  };

  // â”€â”€ Guardar datos de marca â”€â”€
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
        var key = (lbl.textContent || '').trim().replace(/[^a-zA-ZÃ€-É0-9 ]/g,'').trim().toLowerCase().replace(/ +/g,'_').slice(0,40);
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

  // â”€â”€ Cargar datos de marca en formulario â”€â”€
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

  // â”€â”€ Credenciales â”€â”€
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

  // â”€â”€ Perfil de negocio (sidebar) â”€â”€
  async function loadProfile() {
    try {
      var r = await fetch('/api/brand');
      if (!r.ok) return;
      var d = await r.json();
      if (d.brand_name) {
        document.querySelectorAll('aside p.font-semibold, aside .font-semibold').forEach(function(el) {
          if (el.textContent.includes('FitLife') || el.textContent.includes('Studio')) el.textContent = d.brand_name;
        });
        // KPI sidebar initials
        document.querySelectorAll('aside span.font-bold.text-white').forEach(function(el) {
          var initials = d.brand_name.split(' ').map(function(w){return w[0]||'';}).join('').slice(0,2).toUpperCase();
          if (el.textContent === 'FL') el.textContent = initials;
        });
      }
    } catch(e) {}
  }

  // â”€â”€ Wiring de botones "Guardar" â”€â”€
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

  // â”€â”€ Cargar datos al iniciar â”€â”€
  window.addEventListener('DOMContentLoaded', function() {
    var path = window.location.pathname;
    if (path === '/credenciales') { loadCredentials(); }
    else { loadBrand(); loadProfile(); }
  });
  // tambiÃ©n si el DOM ya cargÃ³
  if (document.readyState !== 'loading') {
    var path = window.location.pathname;
    if (path === '/credenciales') { loadCredentials(); }
    else { loadBrand(); loadProfile(); }
  }

  // â”€â”€ Modal "Generar todo" â”€â”€
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


def serve_html(filename: str) -> HTMLResponse:
    path = DASHBOARD / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"PÃ¡gina no encontrada: {filename}")
    content = path.read_text(encoding="utf-8")
    # Inyectar CSS normalizado en <head>
    content = content.replace("</head>", SHARED_CSS + "\n</head>")
    # Inyectar JS universal antes del cierre de body
    content = content.replace("</body>", SHARED_JS + "\n</body>")
    return HTMLResponse(content=content)


# â”€â”€ Rutas de pÃ¡ginas â”€â”€

@app.get("/", response_class=HTMLResponse)
def home():
    return serve_html("rima-home.html")

@app.get("/calendario", response_class=HTMLResponse)
def calendario():
    return serve_html("rima-calenadrio.html")

@app.get("/contenido", response_class=HTMLResponse)
def contenido():
    return serve_html("rima-contenido.html")

@app.get("/mercado", response_class=HTMLResponse)
def mercado():
    return serve_html("rima-mercado.html")

@app.get("/meta", response_class=HTMLResponse)
def meta():
    return serve_html("rima-meta.html")

@app.get("/ventas", response_class=HTMLResponse)
def ventas():
    return serve_html("rima-ventas.html")

@app.get("/landing", response_class=HTMLResponse)
def landing():
    return serve_html("rima-landing.html")

@app.get("/marca", response_class=HTMLResponse)
def marca():
    return serve_html("rima-marca.html")

@app.get("/referencias", response_class=HTMLResponse)
def referencias():
    return serve_html("rima-referencias.html")

@app.get("/imagenes", response_class=HTMLResponse)
def imagenes():
    return serve_html("rima-imagenes.html")

@app.get("/videos", response_class=HTMLResponse)
def videos():
    return serve_html("rima-videos.html")

@app.get("/credenciales", response_class=HTMLResponse)
def credenciales():
    return serve_html("rima-credenciales.html")


# â”€â”€ API: Datos de marca â”€â”€

@app.get("/api/brand")
def get_brand():
    data = load_data()
    return JSONResponse(content=data.get("brand", {}))

@app.post("/api/brand")
def post_brand(payload: dict):
    data = load_data()
    existing = data.get("brand", {})
    existing.update(payload)
    data["brand"] = existing
    save_data(data)
    return {"status": "ok", "saved": len(existing)}

# â”€â”€ API: Credenciales â”€â”€

@app.get("/api/credentials")
def get_credentials():
    data = load_data()
    return JSONResponse(content=data.get("credentials", {}))

@app.post("/api/credentials")
def post_credentials(payload: dict):
    data = load_data()
    existing = data.get("credentials", {})
    existing.update(payload)
    data["credentials"] = existing
    save_data(data)
    return {"status": "ok"}


# â”€â”€ Modelos de request para agentes â”€â”€

class BrandBrief(BaseModel):
    business_name: str = "Mi Negocio"
    service: str = ""
    ideal_client: str = ""
    problem: str = ""
    main_result: str = ""
    price: str = ""
    success_cases: str = ""
    guarantee: str = ""


# â”€â”€ Endpoints de agentes â”€â”€

@app.post("/api/generate/landing")
def generate_landing(brief: BrandBrief):
    try:
        result = landing_agent.run(brief.model_dump())
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/contenido")
def generate_content(brief: BrandBrief):
    try:
        result = content_agent.run(brief.model_dump())
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/meta")
def generate_meta(brief: BrandBrief):
    try:
        result = meta_agent.run(brief.model_dump())
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/ventas")
def generate_sales(brief: BrandBrief):
    try:
        result = sales_agent.run(brief.model_dump())
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/prospecting")
def generate_prospecting(brief: BrandBrief):
    try:
        result = prospecting_agent.run(brief.model_dump())
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# â”€â”€ API: ImÃ¡genes â”€â”€

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_SIZE_MB = 10

@app.post("/api/images/upload")
async def upload_images(
    files: List[UploadFile] = File(...),
    category: str = Form("historias")
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
def list_images(category: str = "historias"):
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
def delete_image(category: str, filename: str):
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


# â”€â”€ API: Clips de video por reel â”€â”€

ALLOWED_VIDEO = {"video/mp4","video/quicktime","video/x-msvideo","video/webm","video/mpeg","video/mov"}
MAX_CLIP_MB = 500

@app.post("/api/videos/{reel_id}/clips")
async def upload_clip(reel_id: str, files: List[UploadFile] = File(...)):
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
def list_clips(reel_id: str):
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
def delete_clip(reel_id: str, filename: str):
    if ".." in filename or "/" in filename:
        raise HTTPException(400, "Nombre invÃ¡lido")
    p = UPLOADS_DIR / "clips" / reel_id / filename
    if not p.exists(): raise HTTPException(404, "No encontrado")
    p.unlink()
    return {"status": "deleted"}

# â”€â”€ API: Video final por reel â”€â”€

@app.post("/api/videos/{reel_id}/final")
async def upload_final(reel_id: str, file: UploadFile = File(...)):
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
def get_final(reel_id: str):
    d = load_data()
    final = d.get("reels", {}).get(reel_id, {}).get("final")
    if not final: return {"final": None}
    # Verificar que el archivo sigue existiendo
    path = UPLOADS_DIR / "finals" / final["name"]
    if not path.exists(): return {"final": None}
    return {"final": final}

# â”€â”€ API: Estado de reel (aprobaciÃ³n guiÃ³n, paso actual) â”€â”€

@app.get("/api/videos/{reel_id}/state")
def get_reel_state(reel_id: str):
    d = load_data()
    return d.get("reels", {}).get(reel_id, {}).get("state", {"script_approved": False, "step": 1})

@app.post("/api/videos/{reel_id}/state")
def set_reel_state(reel_id: str, payload: dict):
    d = load_data()
    d.setdefault("reels", {}).setdefault(reel_id, {})["state"] = payload
    save_data(d)
    return {"status": "ok"}


@app.post("/api/videos/{reel_id}/edit")
def trigger_edit(reel_id: str):
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
    return {"status": "queued", "message": f"EdiciÃ³n iniciada â€” {len(clip_files)} clip(s) en cola", "clips": clip_files}


# â”€â”€ API: Calendario â”€â”€

@app.get("/api/calendar")
def get_calendar(month: str = None):
    data = load_data()
    items = data.get("calendar_items", [])
    if month:
        items = [i for i in items if i.get("date", "").startswith(month)]
    return {"items": items}

@app.post("/api/calendar")
def create_calendar_item(payload: dict):
    data = load_data()
    items = data.setdefault("calendar_items", [])
    item = {
        "id": str(uuid.uuid4()),
        "date": payload.get("date", ""),
        "type": payload.get("type", "reel"),
        "title": payload.get("title", ""),
        "caption": payload.get("caption", ""),
        "hashtags": payload.get("hashtags", []),
        "status": payload.get("status", "pendiente"),
        "metrics": payload.get("metrics", {}),
        "created_at": int(time.time()),
    }
    items.append(item)
    save_data(data)
    return item

@app.put("/api/calendar/{item_id}")
def update_calendar_item(item_id: str, payload: dict):
    data = load_data()
    items = data.get("calendar_items", [])
    for i, item in enumerate(items):
        if item["id"] == item_id:
            items[i].update({k: v for k, v in payload.items() if k != "id"})
            save_data(data)
            return items[i]
    raise HTTPException(404, "Item no encontrado")

@app.delete("/api/calendar/{item_id}")
def delete_calendar_item(item_id: str):
    data = load_data()
    items = data.get("calendar_items", [])
    data["calendar_items"] = [i for i in items if i["id"] != item_id]
    save_data(data)
    return {"status": "deleted"}

@app.post("/api/calendar/generate")
def generate_calendar(payload: dict):
    from core.gemini_client import gemini
    month = payload.get("month")
    if not month:
        raise HTTPException(400, "month requerido (YYYY-MM)")

    brand = load_data().get("brand", {})
    brand_name = brand.get("brand_name", "Mi Negocio")
    service = brand.get("brand_service", "servicios de alto valor")
    ideal_client = brand.get("brand_ideal_client", "emprendedores LATAM")

    year, mon = map(int, month.split("-"))
    days_in_month = cal_module.monthrange(year, mon)[1]
    month_name = cal_module.month_name[mon]
    mon_str = str(mon).zfill(2)

    prompt = f"""Eres experto en marketing de contenidos para Instagram en LATAM.
Genera un plan de contenidos para {month_name} {year} ({days_in_month} dÃ­as).

Negocio: {brand_name}
Servicio: {service}
Cliente ideal: {ideal_client}

Genera exactamente 20 piezas distribuidas a lo largo del mes.
DistribuciÃ³n: 8 Reels, 6 Carruseles, 6 Historias.
MÃ¡ximo 1 pieza por dÃ­a. Prefer lunes/miercoles/viernes/sabado para reels.

Responde SOLO con JSON array vÃ¡lido, sin markdown, sin texto extra:
[
  {{"date": "{year}-{mon_str}-DD", "type": "reel|carrusel|historia", "title": "TÃ­tulo", "caption": "Caption completo...", "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"]}},
  ...20 items...
]
Las fechas deben estar entre {year}-{mon_str}-01 y {year}-{mon_str}-{str(days_in_month).zfill(2)}."""

    try:
        raw = gemini.generate(prompt)
        match = re.search(r'\[[\s\S]*\]', raw)
        if not match:
            raise HTTPException(500, "No se pudo parsear la respuesta de IA")
        items_data = json.loads(match.group())
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"JSON invÃ¡lido de IA: {e}")

    data = load_data()
    existing = [i for i in data.get("calendar_items", []) if not i.get("date", "").startswith(month)]

    new_items = []
    for d in items_data:
        new_items.append({
            "id": str(uuid.uuid4()),
            "date": d.get("date", ""),
            "type": d.get("type", "reel"),
            "title": d.get("title", ""),
            "caption": d.get("caption", ""),
            "hashtags": d.get("hashtags", []),
            "status": "pendiente",
            "metrics": {},
            "created_at": int(time.time()),
        })

    data["calendar_items"] = existing + new_items
    save_data(data)
    return {"items": new_items, "count": len(new_items)}


# â”€â”€ API: Contenido â€” slides, regenerar, telegram â”€â”€

@app.post("/api/calendar/{item_id}/generate-slides")
def generate_slides(item_id: str):
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
def regenerate_item(item_id: str):
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
def telegram_validate(item_id: str):
    data = load_data()
    items = data.get("calendar_items", [])
    idx = next((i for i, x in enumerate(items) if x["id"] == item_id), None)
    if idx is None: raise HTTPException(404, "Item no encontrado")
    items[idx]["status"] = "validacion"
    items[idx]["telegram_sent"] = True
    items[idx]["telegram_sent_at"] = int(time.time())
    save_data(data)
    return {"status": "ok", "item": items[idx]}


@app.post("/api/calendar/{item_id}/approve")
def approve_item(item_id: str):
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


# â”€â”€ Webhook Lemon Squeezy â”€â”€

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


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

