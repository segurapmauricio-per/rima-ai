"""
Scrape del perfil IG del cliente para onboarding (20 posts + análisis Gemini).
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.gemini_client import gemini
from agents.market_research.agent import market_research_agent, _norm_username

SCRAPE_POSTS_LIMIT = 20

ANALYSIS_SYSTEM = """Eres analista de marca para RIMA AI (marketing LATAM).
A partir del perfil de Instagram y sus últimas publicaciones, extrae señales
accionables para generar contenido alineado al cliente.

Responde SOLO JSON válido en español."""


def _scrape_client_posts(username: str, limit: int = SCRAPE_POSTS_LIMIT) -> dict:
    user = _norm_username(username)
    if not user:
        return {"posts": [], "note": "Usuario vacío"}

    profile_meta = market_research_agent._fetch_profile_meta([user])
    meta = profile_meta.get(user) or {}

    scrape = market_research_agent._scrape_instagram([user], [])
    posts = []
    for p in scrape.get("posts") or []:
        owner = _norm_username(p.get("owner") or "")
        if owner == user:
            posts.append(p)
    posts = posts[:limit]

    return {
        "username": user,
        "profile": {
            "username": user,
            "full_name": meta.get("full_name") or "",
            "biography": meta.get("biography") or "",
            "business_category": meta.get("business_category") or "",
            "followers": meta.get("followers") or 0,
            "profile_pic_url": meta.get("profile_pic_url") or "",
            "profile_url": meta.get("profile_url") or f"https://www.instagram.com/{user}/",
        },
        "profile_meta": profile_meta,
        "posts": posts,
        "posts_count": len(posts),
        "note": scrape.get("note", ""),
    }


def _extract_highlight_urls(profile_raw: dict, posts: list) -> list:
    """URLs de imágenes representativas: foto perfil + posts recientes."""
    urls = []
    pic = profile_raw.get("profile_pic_url") or ""
    if pic:
        urls.append({"tipo": "perfil", "url": pic, "titulo": "Foto de perfil"})

    for p in posts[:8]:
        url = p.get("url") or p.get("displayUrl") or ""
        if url:
            urls.append({
                "tipo": p.get("type", "post"),
                "url": url,
                "titulo": (p.get("caption") or "")[:60] or "Publicación",
            })
    return urls[:12]


def _analyze_with_gemini(profile: dict, posts: list) -> dict:
    captions = []
    types_count: dict = {}
    for p in posts:
        cap = (p.get("caption") or "").strip()
        if cap:
            captions.append(cap[:400])
        tipo = (p.get("type") or "Image").lower()
        types_count[tipo] = types_count.get(tipo, 0) + 1

    posts_summary = []
    for i, p in enumerate(posts[:20]):
        posts_summary.append({
            "n": i + 1,
            "tipo": p.get("type", "Image"),
            "caption": (p.get("caption") or "")[:250],
            "likes": p.get("likes", 0),
            "views": p.get("views", 0),
        })

    prompt = f"""Analiza este perfil de Instagram y sus publicaciones para onboarding de marca.

PERFIL:
- Usuario: @{profile.get('username', '')}
- Nombre: {profile.get('full_name', '')}
- Bio: {profile.get('biography', '')}
- Categoría: {profile.get('business_category', '')}
- Seguidores: {profile.get('followers', 0)}

DISTRIBUCIÓN TIPOS: {json.dumps(types_count, ensure_ascii=False)}

PUBLICACIONES (últimas {len(posts)}):
{json.dumps(posts_summary, ensure_ascii=False)}

CAPTIONS COMPLETOS (muestra):
{chr(10).join(captions[:12])}

Devuelve JSON con esta estructura exacta:
{{
  "tipografias": ["Fuente sugerida 1", "Fuente sugerida 2"],
  "paleta_colores": ["#hex o nombre", "..."],
  "colores_primarios": ["..."],
  "colores_secundarios": ["..."],
  "tipos_contenido": {{
    "reels_pct": 0,
    "carruseles_pct": 0,
    "historias_estilo_pct": 0,
    "descripcion": "cómo publica habitualmente"
  }},
  "oferta_detectada": "qué vende o promete en bio/posts",
  "problema_detectado": "dolor del cliente que ataca",
  "resultado_prometido": "transformación que promete",
  "cliente_ideal": "a quién le habla",
  "forma_de_hablar": "tono y estilo (ej: cercano, directo, motivacional)",
  "muletillas": ["palabras o frases recurrentes"],
  "temas_frecuentes": ["tema1", "tema2"],
  "destacados_inferidos": [
    {{"titulo": "nombre highlight", "tema": "de qué trata"}}
  ],
  "biografia_resumen": "resumen accionable de la bio",
  "estilo_visual": "descripción del estilo visual del feed"
}}"""

    try:
        raw = gemini.generate_json(prompt, system_prompt=ANALYSIS_SYSTEM)
        return json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception as e:
        print(f"[onboarding_scrape] Gemini error: {e}")
        return _fallback_insights(profile, posts, types_count)


def _fallback_insights(profile: dict, posts: list, types_count: dict) -> dict:
    bio = profile.get("biography") or ""
    total = max(sum(types_count.values()), 1)
    return {
        "tipografias": ["Inter Bold", "Montserrat SemiBold"],
        "paleta_colores": ["#7C3AED", "#06B6D4", "#0F172A", "#F8FAFC"],
        "colores_primarios": ["#7C3AED"],
        "colores_secundarios": ["#06B6D4"],
        "tipos_contenido": {
            "reels_pct": round(100 * types_count.get("video", 0) / total),
            "carruseles_pct": round(100 * types_count.get("sidecar", 0) / total),
            "historias_estilo_pct": round(100 * types_count.get("image", 0) / total),
            "descripcion": "Mix de formatos según feed reciente",
        },
        "oferta_detectada": bio.split("\n")[0][:200] if bio else "",
        "problema_detectado": "",
        "resultado_prometido": "",
        "cliente_ideal": profile.get("business_category") or "",
        "forma_de_hablar": "Cercano y profesional",
        "muletillas": [],
        "temas_frecuentes": [],
        "destacados_inferidos": [],
        "biografia_resumen": bio[:300],
        "estilo_visual": profile.get("business_category") or "Profesional",
    }


def build_marca_from_scrape(scrape_data: dict, insights: dict, brand: Optional[dict] = None) -> dict:
    from core.marca_visual import build_from_ig_scrape, normalizar_marca, merge_from_brand

    profile = scrape_data.get("profile") or {}
    meta = (scrape_data.get("profile_meta") or {}).get(profile.get("username", "")) or profile
    posts = scrape_data.get("posts") or []

    marca = build_from_ig_scrape(meta, brand, posts)
    visual = marca.get("visual") or {}
    comm = marca.get("comunicacion") or {}

    paleta = insights.get("paleta_colores") or []
    if paleta:
        visual["paleta_colores"] = paleta[:8]
        visual["colores_primarios"] = (insights.get("colores_primarios") or paleta[:3])[:3]
        visual["colores_secundarios"] = (insights.get("colores_secundarios") or paleta[3:8])[:5]

    tips = insights.get("tipografias") or []
    if tips:
        visual["tipografias"] = tips[:2]

    estilo = insights.get("estilo_visual") or ""
    if estilo:
        visual["estilo_imagen"] = estilo

    tono = insights.get("forma_de_hablar") or ""
    if tono:
        comm["tono"] = tono

    muletillas = insights.get("muletillas") or []
    if muletillas:
        comm["muletillas"] = muletillas[:8]

    palabras = insights.get("temas_frecuentes") or []
    if palabras:
        comm["palabras_frecuentes"] = palabras[:12]

    tipos = insights.get("tipos_contenido") or {}
    if tipos.get("descripcion"):
        comm["estilo_copy"] = tipos["descripcion"]

    marca["visual"] = visual
    marca["comunicacion"] = comm
    marca["origen"] = "onboarding_ig"
    marca["onboarding_scrape"] = {
        "posts_analizados": scrape_data.get("posts_count", 0),
        "tipos_contenido": tipos,
        "destacados": insights.get("destacados_inferidos") or [],
        "imagenes_destacadas": _extract_highlight_urls(profile, posts),
        "oferta_detectada": insights.get("oferta_detectada") or "",
        "biografia_resumen": insights.get("biografia_resumen") or profile.get("biography") or "",
        "analyzed_at": datetime.now().isoformat(),
    }
    marca["updated_at"] = datetime.now().isoformat()

    if brand:
        marca = merge_from_brand(marca, brand)
    return normalizar_marca(marca)


def save_scrape_artifact(cliente_id: str, payload: dict) -> Path:
    root = Path(__file__).parent.parent / "data" / "clients" / cliente_id
    root.mkdir(parents=True, exist_ok=True)
    path = root / "onboarding_scrape.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_client_scrape(username: str, cliente_id: str, brand: Optional[dict] = None) -> dict:
    """Scrape completo: perfil + 20 posts + análisis + marca_visual."""
    scrape_data = _scrape_client_posts(username, SCRAPE_POSTS_LIMIT)
    if not scrape_data.get("posts") and scrape_data.get("note"):
        return {
            "ok": False,
            "error": scrape_data.get("note") or "Sin publicaciones",
            "username": _norm_username(username),
        }

    insights = _analyze_with_gemini(scrape_data.get("profile") or {}, scrape_data.get("posts") or [])
    marca = build_marca_from_scrape(scrape_data, insights, brand)

    from core.db import init_db, set_marca_visual, create_or_update_cliente, get_cliente

    init_db(cliente_id)
    if not get_cliente(cliente_id):
        create_or_update_cliente(cliente_id, nombre=cliente_id, plan="basico")
    set_marca_visual(cliente_id, marca)

    artifact = {
        "username": scrape_data.get("username"),
        "profile": scrape_data.get("profile"),
        "posts_count": scrape_data.get("posts_count"),
        "insights": insights,
        "marca_visual": marca,
        "scraped_at": datetime.now().isoformat(),
    }
    save_scrape_artifact(cliente_id, artifact)

    return {
        "ok": True,
        "username": scrape_data.get("username"),
        "posts_count": scrape_data.get("posts_count"),
        "insights": insights,
        "marca_visual": marca,
        "profile": scrape_data.get("profile"),
    }
