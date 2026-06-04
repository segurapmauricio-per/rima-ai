"""
Market Research Agent v2
- Scraping semanal de referentes (Apify instagram-scraper)
- Métricas: Fuerza, Consistencia, Tracción
- Actualización incremental (actualiza posts ya conocidos, agrega nuevos)
- Análisis con Gemini de patrones de hook, formato, CTA, ángulos
"""
from core.gemini_client import gemini
from core.brand_knowledge import K_MARKET_RESEARCH
from core.client_store import save_market_research, load_referents_db, load_latest_market_research
import json
import os
import urllib.request
from datetime import datetime

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")
ACTOR_ID = "apify~instagram-scraper"

SYSTEM_PROMPT = f"""Eres el Agente de Estudio de Mercado de RIMA.
Analizás referentes de Instagram para extraer patrones de contenido ganadores.

Base de conocimiento:
{K_MARKET_RESEARCH}

Reglas:
- Comments pesan más que likes (señal de conversación real)
- Fuerza = (views + comments*10) / followers — impacto relativo a la audiencia
- Consistencia = views / avg_views — superar el propio benchmark del creador
- Tracción = comments / views — ratio de engagement real
- Distinguir viral genérico de contenido nicheado que convierte
- Escribe en español LATAM"""


def calculate_metrics(post: dict, creator_avg_views: float = 0) -> dict:
    """Calculate Fuerza, Consistencia y Tracción for a post."""
    views = post.get("views", 0) or 0
    comments = post.get("comments", 0) or 0
    likes = post.get("likes", 0) or 0
    followers = post.get("owner_followers", 1) or 1

    fuerza = round((views + comments * 10) / max(followers, 1), 4)
    consistencia = round(views / max(creator_avg_views, 1), 4) if creator_avg_views else 0
    traccion = round(comments / max(views, 1) * 100, 4) if views else 0

    return {
        "fuerza": fuerza,
        "consistencia": consistencia,
        "traccion_pct": traccion,
        "engagement_score": round(fuerza * (1 + consistencia), 4),
    }


class MarketResearchAgent:
    def __init__(self):
        self.name = "market_research"

    def run(self, brand: str, brand_brief: dict, competitor_profiles: list = None,
            hashtags: list = None, week_label: str = None) -> dict:

        week = week_label or datetime.now().strftime("W%W_%Y")

        # Step 1: Scrape Instagram
        scraped = self._scrape_instagram(
            competitor_profiles=competitor_profiles or [],
            hashtags=hashtags or [],
        )

        # Step 2: Calculate per-creator average views first
        posts = scraped.get("posts", [])
        creator_avgs = self._calc_creator_averages(posts)

        # Step 3: Add metrics to each post
        for post in posts:
            owner = post.get("owner", "")
            avg = creator_avgs.get(owner, 0)
            post["metrics"] = calculate_metrics(post, avg)
            post["creator_avg_views"] = avg

        # Step 4: Sort by engagement_score (best referents first)
        posts.sort(key=lambda p: p.get("metrics", {}).get("engagement_score", 0), reverse=True)

        # Step 5: Analyze with Gemini
        top_posts = posts[:20]
        analysis = self._analyze_patterns(top_posts, brand_brief)

        # Step 6: Save to client store (incremental update of posts DB)
        data = {
            "week": week,
            "timestamp": datetime.now().isoformat(),
            "profiles_scraped": list({p.get("owner", "") for p in posts}),
            "posts": posts,
            "top_posts": top_posts,
            "analysis": analysis,
            "apify_used": bool(APIFY_TOKEN and posts),
        }
        save_market_research(brand, data, week)

        return {
            "agent": self.name,
            "brand": brand,
            "week": week,
            "posts_analyzed": len(posts),
            "top_referents": len({p.get("owner", "") for p in top_posts}),
            "analysis": analysis,
        }

    def _calc_creator_averages(self, posts: list) -> dict:
        """Calculate average views per creator to normalize Consistencia."""
        from collections import defaultdict
        creator_views = defaultdict(list)
        for p in posts:
            owner = p.get("owner", "")
            views = p.get("views", 0) or 0
            if owner and views:
                creator_views[owner].append(views)
        return {owner: sum(v) / len(v) for owner, v in creator_views.items() if v}

    def _scrape_instagram(self, competitor_profiles: list, hashtags: list) -> dict:
        if not APIFY_TOKEN:
            return {"posts": [], "note": "Sin APIFY_API_TOKEN — usando análisis general"}

        if competitor_profiles:
            actor_input = {
                "directUrls": [f"https://www.instagram.com/{p.strip().lstrip('@')}/" for p in competitor_profiles if p],
                "resultsType": "posts",
                "resultsLimit": 20,
            }
        elif hashtags:
            actor_input = {
                "hashtags": [h.strip().lstrip("#") for h in hashtags[:5]],
                "resultsType": "posts",
                "resultsLimit": 25,
            }
        else:
            return {"posts": [], "note": "Sin perfiles ni hashtags"}

        try:
            items = self._apify_run(actor_input)
        except Exception as e:
            return {"posts": [], "note": f"Error Apify: {e}"}

        posts = []
        for item in items:
            posts.append({
                "id": item.get("id") or item.get("shortCode") or item.get("url", ""),
                "owner": item.get("ownerUsername", ""),
                "owner_followers": item.get("ownerFollowersCount", 0),
                "type": item.get("type", "Image"),
                "caption": (item.get("caption") or "")[:600],
                "likes": item.get("likesCount", 0),
                "comments": item.get("commentsCount", 0),
                "views": item.get("videoViewCount") or item.get("videoPlayCount") or 0,
                "timestamp": item.get("timestamp", ""),
                "url": item.get("url", ""),
                "shortCode": item.get("shortCode", ""),
            })

        return {"posts": posts}

    def _apify_run(self, actor_input: dict) -> list:
        url = (
            f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs"
            f"?token={APIFY_TOKEN}&waitForFinish=120"
        )
        payload = json.dumps(actor_input).encode("utf-8")
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=150) as resp:
            run_data = json.loads(resp.read()).get("data", {})

        dataset_id = run_data.get("defaultDatasetId", "")
        if not dataset_id:
            return []

        items_url = (
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?token={APIFY_TOKEN}&limit=60"
        )
        with urllib.request.urlopen(items_url, timeout=30) as resp:
            return json.loads(resp.read())

    def _analyze_patterns(self, top_posts: list, brand_brief: dict) -> str:
        if top_posts:
            # Build concise summary for Gemini (avoid huge payloads)
            posts_summary = []
            for p in top_posts[:15]:
                m = p.get("metrics", {})
                posts_summary.append({
                    "owner": p["owner"],
                    "caption_preview": p["caption"][:200],
                    "views": p["views"],
                    "comments": p["comments"],
                    "fuerza": m.get("fuerza", 0),
                    "consistencia": m.get("consistencia", 0),
                    "traccion_pct": m.get("traccion_pct", 0),
                    "url": p["url"],
                })
            data_context = f"TOP POSTS (ordenados por engagement_score):\n{json.dumps(posts_summary, ensure_ascii=False, indent=2)}"
        else:
            data_context = "Sin datos de scraping disponibles. Analiza el nicho con tu conocimiento general."

        prompt = f"""
Realiza el estudio de mercado semanal de referentes de Instagram para:

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
RESULTADO: {brand_brief.get('main_result')}

{data_context}

Entrega el análisis en este formato:

## TOP REFERENTES DEL NICHO
Cuentas más relevantes con métricas clave (fuerza, consistencia, tracción)

## HOOKS QUE FUNCIONAN ESTA SEMANA
Los 5 tipos de hook más efectivos con texto exacto de ejemplo

## FORMATOS CON MEJOR ENGAGEMENT
3-4 formatos con descripción de setup y por qué funcionan

## ÁNGULOS DE CONTENIDO DOMINANTES
5 temas/problemas con mayor tracción en el nicho esta semana

## PATRONES DE CTA
3-5 CTAs más frecuentes y efectivos

## 5 IDEAS ADAPTADAS AL NEGOCIO
Ideas tomando los patrones exitosos, adaptadas al cliente.
Por idea:
- Tipo: Reel / Carrusel / Historia
- Hook: [texto exacto]
- Ángulo: Problema/Solución/Resultado/Mentalidad
- Formato: [descripción]
- Referente a modelar: [cuenta o URL si aplica]
- Por qué funciona: [1 línea]
"""
        return gemini.generate(prompt, SYSTEM_PROMPT)


market_research_agent = MarketResearchAgent()
