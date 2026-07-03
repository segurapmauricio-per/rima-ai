"""
Market Research Agent v3
- Capa 1: Scrape Apify (20 posts/referente) → actualiza métricas siempre
- Capa 1.5: Transcripción Gemini solo en posts de la cola capa 2 (reels con video)
- Capa 2: Análisis Gemini con caption + transcripción → guión modelable
- Métricas: fuerza, relevancia, engagement, ratio_conversacion, engagement_score
"""

from core.gemini_client import gemini
from core.brand_knowledge import K_MARKET_RESEARCH
from core.client_store import save_market_research
from core.plan_limits import get_deep_analysis_budget
from core.market_scores import (
    infer_categoria, attach_score_ventas, attach_scores_tematica,
    calculate_score_ventas, infer_scores_tematica, TEMATICA_RANK_KEYS,
)
import json
import os
import re
import urllib.request
from collections import defaultdict
from datetime import datetime

APIFY_TOKEN = os.getenv("APIFY_API_TOKEN", "")
ACTOR_POSTS = "apify~instagram-scraper"
ACTOR_PROFILE = "apify~instagram-profile-scraper"


def _apify_token() -> str:
    return os.getenv("APIFY_API_TOKEN", "") or APIFY_TOKEN


def _norm_username(username: str) -> str:
    return (username or "").strip().lstrip("@").lower()

SYSTEM_PROMPT = f"""Eres el Agente de Estudio de Mercado de RIMA.
Analizás referentes de Instagram para extraer patrones de contenido ganadores
que el equipo pueda modelar (adaptar, no copiar).

Base de conocimiento:
{K_MARKET_RESEARCH}

Reglas de análisis:
- Comentarios pesan más que likes (señal de conversación real, intención de compra)
- Guardados indican contenido de alto valor educativo o de referencia
- Fuerza mide impacto relativo al tamaño de audiencia — una cuenta chica con
  alta fuerza es más modelable que una cuenta masiva con bajo ratio
- Relevancia mide si el post supera el benchmark propio del creador
- Modelabilidad (1-10): ¿qué tan fácil es adaptar este contenido al negocio?
  10 = estructura directamente replicable; 1 = viral por factores no replicables
- Cuando hay transcripción del audio: modelá el GUION HABLADO (hook, estructura, CTA en voz),
  no solo el caption — muchos reels virales repiten plantillas de guión
- Distinguir viral genérico de contenido nicheado que convierte
- Escribe en español LATAM"""


def calculate_metrics(post: dict, creator_avg_views_10: float = 0) -> dict:
    """
    Calcula las métricas alineadas con el schema de referentes_contenido:
      fuerza             = (vistas + comentarios*10) / seguidores
      engagement         = (likes + comentarios*2 + guardados*3) / vistas
                           (guardados suele venir 0: apify~instagram-scraper no expone
                           savesCount — el término queda por si el actor lo agrega)
      ratio_conversacion = comentarios / vistas
      relevancia         = vistas / avg_vistas_últimas_10 del creador
      engagement_score   = fuerza * (1 + relevancia)  ← para rankear
    """
    vistas     = post.get("views", 0) or 0
    comentarios = post.get("comments", 0) or 0
    likes      = post.get("likes", 0) or 0
    guardados  = post.get("saves", 0) or 0
    seguidores = int(post.get("owner_followers") or 0)
    if seguidores <= 0:
        # Apify a veces no trae followers en posts — estimar con benchmark del creador
        seguidores = int(creator_avg_views_10 or vistas or 1)

    fuerza = round((vistas + comentarios * 10) / max(seguidores, 1), 4)
    engagement = round((likes + comentarios * 2 + guardados * 3) / max(vistas, 1), 4) if vistas else 0
    ratio_conversacion = round(comentarios / max(vistas, 1) * 100, 4) if vistas else 0
    relevancia = round(vistas / max(creator_avg_views_10, 1), 4) if creator_avg_views_10 else 0
    engagement_score = round(fuerza * (1 + relevancia), 4)

    return {
        "fuerza": fuerza,
        "engagement": engagement,
        "ratio_conversacion": ratio_conversacion,
        "relevancia": relevancia,
        "engagement_score": engagement_score,
    }


def detect_viral_spike(new_metrics: dict, old_row: dict, new_views: int = 0) -> bool:
    """
    Detecta si un post existente cruzó umbral viral desde el último scrape.
    Señales: relevancia >= 1.5, engagement_score +50%, vistas duplicadas.
    Si ya era viral y analizado, exige spike más fuerte (2x) para re-analizar.
    """
    if not old_row:
        return False

    old_fuerza = old_row.get("fuerza") or 0
    new_fuerza = new_metrics.get("fuerza") or 0
    old_rel = old_row.get("relevancia") or 0
    new_rel = new_metrics.get("relevancia") or 0
    old_views = old_row.get("vistas") or 0

    old_score = old_fuerza * (1 + old_rel)
    new_score = new_fuerza * (1 + new_rel)
    already_viral = old_rel >= 1.5 and old_row.get("analizado_at")

    if already_viral:
        if old_views > 0 and new_views >= old_views * 2:
            return True
        if old_score > 0 and new_score >= old_score * 2.5:
            return True
        return False

    if new_rel >= 1.5 and old_rel < 1.5:
        return True
    if old_score > 0 and new_score >= old_score * 1.5:
        return True
    if old_views > 100 and new_views >= old_views * 2:
        return True
    if old_views > 0 and new_views >= old_views * 3:
        return True
    return False


# Reservado para viral spikes dentro del presupuesto (no comen cuota de categoría)
VIRAL_SPIKE_RESERVE = 3
# Posts por llamada Gemini en capa 2 (evita truncar JSON con muchos items)
DEEP_ANALYSIS_BATCH = 8
# Límite de descarga de video CDN (bytes)
MAX_VIDEO_BYTES = 25_000_000

ANALISIS_JSON_KEYS = (
    "tematica", "tipo_angulo", "hook", "hook_hablado", "cta", "cta_hablado",
    "lead_magnet", "problema_resuelto", "aspecto_vida", "formato_descripcion",
    "estructura_guion", "plantilla_detectada", "que_modelar", "por_que_modelar",
    "por_que_funciona", "como_adaptar", "como_adaptar_guion", "enfoque_contenido",
    "scores_tematica",
)


def _extract_json_array(text: str) -> list:
    """Extrae un array JSON de la respuesta de Gemini."""
    if not text:
        return []
    cleaned = text.strip()
    for marker in ("```json", "```JSON", "```"):
        cleaned = cleaned.replace(marker, "")
    cleaned = cleaned.strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end <= start:
        return []
    chunk = cleaned[start:end + 1]
    for attempt in (chunk, re.sub(r",\s*]", "]", chunk), re.sub(r",\s*}", "}", chunk)):
        try:
            data = json.loads(attempt)
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
        except json.JSONDecodeError:
            continue
    return []


def _normalize_idx(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _analysis_from_gemini_item(item: dict) -> tuple[int, dict]:
    """Devuelve (modelabilidad, analisis_json) desde un item del array Gemini."""
    model = item.get("modelabilidad", 5)
    try:
        model = max(1, min(10, int(model)))
    except (TypeError, ValueError):
        model = 5

    tipo = item.get("tipo_angulo") or item.get("tipo") or ""
    enfoque = item.get("enfoque_contenido") or item.get("enfoque") or ""
    if not enfoque and tipo:
        t = str(tipo).lower()
        if t in ("problema", "solución", "solucion"):
            enfoque = "Ventas"
        elif t in ("resultado", "proceso"):
            enfoque = "Educación"
        elif t == "mentalidad":
            enfoque = "Conexión"

    analisis = {}
    for k in ANALISIS_JSON_KEYS:
        if k in item and item[k] is not None:
            analisis[k] = item[k]
    if enfoque and "enfoque_contenido" not in analisis:
        analisis["enfoque_contenido"] = enfoque
    return model, analisis


def _fallback_analisis(post: dict) -> dict:
    """Mínimo útil si Gemini no parseó."""
    trans = (post.get("transcripcion") or "").strip()
    cap = (post.get("caption") or "").strip()
    hook_h = trans.split(".")[0][:200].strip() if trans else ""
    hook = hook_h or (cap.split("\n")[0][:200] if cap else "")
    cat = infer_categoria(post)
    enfoque = {"ventas": "Ventas", "educacion": "Educación", "conexion": "Conexión"}.get(cat, "Educación")
    return {
        "analisis_origen": "fallback",  # heurístico, NO análisis Gemini — la UI puede distinguirlo
        "hook": hook,
        "hook_hablado": hook_h or hook,
        "tipo_angulo": "Problema" if cat == "ventas" else ("Mentalidad" if cat == "conexion" else "Resultado"),
        "enfoque_contenido": enfoque,
        "cta": "Sin CTA explícito",
        "como_adaptar": "",
        "como_adaptar_guion": "",
        "por_que_funciona": "",
        "que_modelar": "Estructura del hook y formato visual" if trans else "Hook del caption",
        "por_que_modelar": "",
    }


def _is_video_post(post: dict) -> bool:
    t = (post.get("type") or "").lower()
    if t in ("video", "reel", "clips"):
        return True
    return bool(post.get("views") or post.get("_video_url"))


def _download_video(url: str) -> bytes | None:
    """Descarga MP4 desde CDN de Instagram (URL temporal del scrape)."""
    if not url:
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RIMA/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read(MAX_VIDEO_BYTES + 1)
            if len(data) > MAX_VIDEO_BYTES:
                print(f"[MarketResearchAgent] Video omitido (> {MAX_VIDEO_BYTES} bytes)")
                return None
            return data
    except Exception as e:
        print(f"[MarketResearchAgent] Warning descarga video: {e}")
        return None


def _needs_deep_analysis(post: dict) -> bool:
    analisis = post.get("analisis_json") or {}
    if isinstance(analisis, str):
        try:
            analisis = json.loads(analisis)
        except Exception:
            analisis = {}
    return not (analisis.get("hook") or analisis.get("como_adaptar"))


def _primary_tematica_key(post: dict) -> str:
    scores = infer_scores_tematica(post)
    return max(TEMATICA_RANK_KEYS, key=lambda k: float(scores.get(k, 0)))


def _deep_priority_key(post: dict) -> tuple:
    """
    Prioriza re-análisis y posts modelables (no solo sensacionalistas).
    Tupla ordenable: (needs_analysis, maturation_score).
    """
    needs = 1 if _needs_deep_analysis(post) else 0
    try:
        mod = float(post.get("modelabilidad") or 5)
    except (TypeError, ValueError):
        mod = 5.0
    metrics = post.get("metrics") or {}
    sv = float(metrics.get("score_ventas") or 0)
    eng = float(metrics.get("engagement_score") or 0)
    maturation = mod * 10.0 + sv * 0.35 - min(eng, 90.0) * 0.08
    return (needs, maturation)


def select_deep_queue(posts: list, budget: dict) -> list:
    """
    Cola capa 2: cuotas por temática RIMA + enfoque, re-analiza posts ya scrapeados
    (prioriza los sin análisis profundo y piezas modelables no solo virales).
    """
    total = budget["total"]
    pool_size = budget["candidate_pool"]
    tematica_quotas = dict(budget.get("tematica_quotas") or {})

    ranked = sorted(
        posts,
        key=lambda p: _deep_priority_key(p),
        reverse=True,
    )
    pool_urls = {p.get("url") for p in ranked[:pool_size] if p.get("url")}

    viral = []
    seen = set()
    for p in ranked:
        url = p.get("url")
        if not url or url in seen or not p.get("_viral_spike"):
            continue
        viral.append(p)
        seen.add(url)
        if len(viral) >= VIRAL_SPIKE_RESERVE:
            break

    def in_pool(p: dict) -> bool:
        url = p.get("url")
        return bool(url and url in pool_urls)

    tematica_buckets: dict[str, list] = {k: [] for k in TEMATICA_RANK_KEYS}

    for p in ranked:
        if not in_pool(p):
            continue
        url = p.get("url")
        if not url or url in seen:
            continue
        tema = _primary_tematica_key(p)
        tematica_buckets.setdefault(tema, []).append(p)

    for bucket in tematica_buckets.values():
        bucket.sort(key=_deep_priority_key, reverse=True)

    selected = list(viral)
    seen.update(p.get("url") for p in selected if p.get("url"))

    for tema, quota in tematica_quotas.items():
        taken = 0
        for p in tematica_buckets.get(tema, []):
            if len(selected) >= total:
                break
            url = p.get("url")
            if not url or url in seen:
                continue
            selected.append(p)
            seen.add(url)
            taken += 1
            if taken >= quota:
                break

    for p in ranked:
        if len(selected) >= total:
            break
        url = p.get("url")
        if not url or url in seen or not in_pool(p):
            continue
        selected.append(p)
        seen.add(url)

    selected.sort(key=_deep_priority_key, reverse=True)
    return selected[:total]


_INTERNAL_KEYS = ("_is_new", "_viral_spike", "_deep_analyzed", "creator_avg_views_10", "_video_url")


def _strip_internal(post: dict) -> dict:
    return {k: v for k, v in post.items() if k not in _INTERNAL_KEYS}


class MarketResearchAgent:
    def __init__(self):
        self.name = "market_research"

    def run(self, brand: str, brand_brief: dict, competitor_profiles: list = None,
            hashtags: list = None, week_label: str = None, cliente_id: str = None) -> dict:

        week = week_label or datetime.now().strftime("W%W_%Y")

        # 1. Scrape Instagram
        scraped = self._scrape_instagram(
            competitor_profiles=competitor_profiles or [],
            hashtags=hashtags or [],
        )
        posts = scraped.get("posts", [])
        scrape_note = scraped.get("note", "")
        profiles_used = [
            p.strip().lstrip("@")
            for p in (competitor_profiles or [])
            if p and str(p).strip()
        ]

        # Metadatos de perfil (seguidores, foto, nicho) vía profile scraper
        profile_meta: dict = {}
        if profiles_used:
            profile_meta = self._fetch_profile_meta(profiles_used)
            for post in posts:
                owner = _norm_username(post.get("owner", ""))
                meta = profile_meta.get(owner)
                if meta and meta.get("followers"):
                    post["owner_followers"] = meta["followers"]

        # 2. Promedios de las últimas ~10 vistas por creador (para relevancia)
        creator_avg_10 = self._calc_creator_avg_views_10(posts)

        # 3. Calcular métricas por post + clasificar capa 1 vs capa 2
        existing_by_url = {}
        if cliente_id:
            from core.db import get_referentes_by_urls, init_db
            init_db(cliente_id)
            urls = [p.get("url") for p in posts if p.get("url")]
            existing_by_url = get_referentes_by_urls(cliente_id, urls)

        metrics_updated = 0
        viral_spikes = 0
        for post in posts:
            url = post.get("url")
            old = existing_by_url.get(url) if url else None
            owner = post.get("owner", "")
            avg10 = creator_avg_10.get(owner, 0)
            post["metrics"] = calculate_metrics(post, avg10)
            post["creator_avg_views_10"] = avg10
            attach_score_ventas(post)
            attach_scores_tematica(post)
            post["_is_new"] = old is None
            post["_viral_spike"] = detect_viral_spike(
                post["metrics"], old, post.get("views", 0)
            )
            if old and not post["_is_new"]:
                metrics_updated += 1
                if not post["_viral_spike"]:
                    post["modelabilidad"] = old.get("modelabilidad")
                    post["analisis_json"] = old.get("analisis_json") or {}
                    if old.get("transcripcion"):
                        post["transcripcion"] = old["transcripcion"]
            if post["_viral_spike"]:
                viral_spikes += 1

        deep_budget = get_deep_analysis_budget(
            brand_brief.get("plan", "pro"),
            brand_brief.get("enfoque"),
        )

        # Capa 2 — cuotas temática RIMA + enfoque + re-análisis de posts maduros
        deep_queue = select_deep_queue(posts, deep_budget)
        transcripts_ok = 0
        if deep_queue:
            transcripts_ok = self._transcribe_deep_queue(deep_queue)
            self._analyze_posts_individually(deep_queue, brand_brief)
            analyzed_urls = {p.get("url"): p for p in deep_queue if p.get("url")}
            for post in posts:
                url = post.get("url")
                if url in analyzed_urls:
                    src = analyzed_urls[url]
                    post["modelabilidad"] = src.get("modelabilidad", post.get("modelabilidad"))
                    post["analisis_json"] = src.get("analisis_json") or post.get("analisis_json")
                    if src.get("transcripcion"):
                        post["transcripcion"] = src["transcripcion"]
                    if src.get("_deep_analyzed"):
                        post["_deep_analyzed"] = True

        deep_parsed = sum(
            1 for p in deep_queue
            if (p.get("analisis_json") or {}).get("hook") and p.get("_deep_analyzed")
        )

        # Recalcular score_ventas tras análisis Gemini / fallback
        for post in posts:
            attach_score_ventas(post)
            attach_scores_tematica(post)
        posts.sort(key=lambda p: p.get("metrics", {}).get("score_ventas", 0), reverse=True)
        top_posts = posts[:20]

        # Insights por referente (para tarjeta de perfil en /mercado)
        profile_insights = self._build_profile_insights(
            posts, profiles_used, profile_meta, brand_brief
        )

        # Análisis general markdown (legacy / export)
        analysis_md = self._analyze_patterns_markdown(top_posts, brand_brief)

        # 7. Persistir en SQLite (métricas siempre; análisis solo capa 2)
        if cliente_id:
            self._save_to_sqlite(cliente_id, posts, top_posts, brand_brief)

        # 8. Backup JSON (compatibilidad con sistema anterior)
        posts_clean = [_strip_internal(p) for p in posts]
        top_clean = [_strip_internal(p) for p in top_posts]
        data = {
            "week": week,
            "timestamp": datetime.now().isoformat(),
            "profiles_scraped": profiles_used or sorted({_norm_username(p.get("owner", "")) for p in posts if p.get("owner")}),
            "posts": posts_clean,
            "top_posts": top_clean,
            "analysis": analysis_md,
            "apify_used": bool(_apify_token() and posts),
            "scrape_note": scrape_note,
            "profiles_requested": profiles_used,
            "profiles_count": len(profiles_used),
            "metrics_updated": metrics_updated,
            "viral_spikes": viral_spikes,
            "deep_analyzed": len(deep_queue),
            "deep_analysis_parsed": deep_parsed,
            "transcripts_ok": transcripts_ok,
            "deep_analysis_budget": deep_budget,
            "profile_meta": profile_meta,
            "profile_insights": profile_insights,
        }
        save_market_research(brand, data, week)

        return {
            "agent": self.name,
            "brand": brand,
            "week": week,
            "posts_analyzed": len(posts),
            "top_referents": len({p.get("owner", "") for p in top_posts}),
            "analysis": analysis_md,
            "top_posts": top_clean,
            "apify_used": bool(_apify_token() and posts),
            "scrape_note": scrape_note,
            "profiles_requested": profiles_used,
            "profiles_count": len(profiles_used),
            "metrics_updated": metrics_updated,
            "viral_spikes": viral_spikes,
            "deep_analyzed": len(deep_queue),
            "deep_analysis_parsed": deep_parsed,
            "transcripts_ok": transcripts_ok,
            "deep_analysis_budget": deep_budget,
            "profile_meta": profile_meta,
            "profile_insights": profile_insights,
        }

    # ── Métricas ──────────────────────────────────────────────────────────────

    def _calc_creator_avg_views_10(self, posts: list) -> dict:
        """Promedio de vistas de las últimas 10 publicaciones por creador."""
        creator_views: dict = defaultdict(list)
        for p in posts:
            owner = p.get("owner", "")
            views = p.get("views", 0) or 0
            if owner and views:
                creator_views[owner].append(views)
        return {
            owner: sum(sorted(views, reverse=True)[:10]) / min(len(views), 10)
            for owner, views in creator_views.items()
            if views
        }

    # ── Scraping ──────────────────────────────────────────────────────────────

    def _fetch_profile_meta(self, usernames: list) -> dict:
        """Foto, seguidores y nicho — instagram-profile-scraper (1 run barato)."""
        cleaned = list(dict.fromkeys(_norm_username(u) for u in usernames if u))
        if not cleaned or not _apify_token():
            return {}
        try:
            items = self._apify_run(
                {"usernames": cleaned},
                limit=len(cleaned) + 5,
                actor_id=ACTOR_PROFILE,
            )
        except Exception:
            return {}
        out: dict = {}
        for item in items:
            user = _norm_username(item.get("username") or "")
            if not user:
                continue
            fc = item.get("followersCount") or item.get("followers") or 0
            pic = item.get("profilePicUrlHD") or item.get("profilePicUrl") or ""
            out[user] = {
                "followers": int(fc) if fc else 0,
                "profile_pic_url": pic,
                "profile_url": item.get("url") or f"https://www.instagram.com/{user}/",
                "full_name": (item.get("fullName") or "").strip(),
                "business_category": (
                    item.get("businessCategoryName") or item.get("category") or ""
                ).strip(),
                "biography": (item.get("biography") or "").strip(),
            }
        return out

    def _scrape_instagram(self, competitor_profiles: list, hashtags: list) -> dict:
        if not _apify_token():
            return {
                "posts": [],
                "note": "Sin APIFY_API_TOKEN — agregá el token en .env y reiniciá el servidor",
            }
        if not competitor_profiles and not hashtags:
            return {"posts": [], "note": "Sin perfiles ni hashtags para scrapear"}

        if competitor_profiles:
            actor_input = {
                "directUrls": [
                    f"https://www.instagram.com/{p.strip().lstrip('@')}/"
                    for p in competitor_profiles if p
                ],
                "resultsType": "posts",
                "resultsLimit": 35,
            }
        elif hashtags:
            actor_input = {
                "hashtags": [h.strip().lstrip("#") for h in hashtags[:5]],
                "resultsType": "posts",
                "resultsLimit": 35,
            }
        else:
            return {"posts": [], "note": "Sin perfiles ni hashtags"}

        try:
            items = self._apify_run(actor_input, limit=max(60, len(competitor_profiles or hashtags or [1]) * 25))
        except Exception as e:
            return {"posts": [], "note": f"Error Apify: {e}"}

        posts = []
        for item in items:
            views = item.get("videoViewCount") or item.get("videoPlayCount") or 0
            if not views:
                # Carruseles/imágenes no reportan views en Apify — proxy con likes
                views = item.get("likesCount") or 0
            posts.append({
                "id": item.get("id") or item.get("shortCode") or item.get("url", ""),
                "owner": item.get("ownerUsername", ""),
                "owner_followers": (
                    item.get("ownerFollowersCount")
                    or (item.get("owner") or {}).get("followersCount")
                    or (item.get("owner") or {}).get("followerCount")
                    or 0
                ),
                "type": item.get("type", "Image"),
                "caption": (item.get("caption") or "")[:600],
                "likes": item.get("likesCount", 0),
                "comments": item.get("commentsCount", 0),
                "saves": item.get("savesCount") or item.get("bookmarksCount") or 0,
                "views": views,
                "timestamp": item.get("timestamp", ""),
                "url": item.get("url", ""),
                "shortCode": item.get("shortCode", ""),
                "_video_url": item.get("videoUrl") or item.get("video_url") or "",
            })

        return {"posts": posts}

    # Espera máxima total por un run de Apify (waitForFinish inicial + polling)
    APIFY_MAX_WAIT_S = 600
    APIFY_POLL_INTERVAL_S = 10

    def _apify_run(self, actor_input: dict, limit: int = 250, actor_id: str = ACTOR_POSTS) -> list:
        """Ejecuta un actor y espera a que TERMINE antes de leer el dataset.

        Antes se leía el dataset tras waitForFinish=120 sin verificar el estado:
        con 5+ perfiles el scrape tarda más y devolvía resultados parciales o
        vacíos en silencio. Ahora se hace polling hasta SUCCEEDED (o error).
        """
        import time as _time
        url = (
            f"https://api.apify.com/v2/acts/{actor_id}/runs"
            f"?token={_apify_token()}&waitForFinish=120"
        )
        payload = json.dumps(actor_input).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=150) as resp:
            run_data = json.loads(resp.read()).get("data", {})

        run_id = run_data.get("id", "")
        status = run_data.get("status", "")
        waited = 120

        while status in ("READY", "RUNNING") and run_id and waited < self.APIFY_MAX_WAIT_S:
            _time.sleep(self.APIFY_POLL_INTERVAL_S)
            waited += self.APIFY_POLL_INTERVAL_S
            status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={_apify_token()}"
            try:
                with urllib.request.urlopen(status_url, timeout=30) as resp:
                    run_data = json.loads(resp.read()).get("data", {})
                status = run_data.get("status", "")
            except Exception as e:
                print(f"[MarketResearchAgent] Warning polling run {run_id}: {e}")
                break

        if status and status != "SUCCEEDED":
            raise RuntimeError(
                f"Run Apify {actor_id} terminó en estado {status} "
                f"(esperado SUCCEEDED tras {waited}s)"
            )

        dataset_id = run_data.get("defaultDatasetId", "")
        if not dataset_id:
            return []

        items_url = (
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?token={_apify_token()}&limit={limit}"
        )
        with urllib.request.urlopen(items_url, timeout=30) as resp:
            return json.loads(resp.read())

    # ── Análisis Gemini ────────────────────────────────────────────────────────

    def _transcribe_deep_queue(self, posts: list) -> int:
        """Capa 1.5 — transcribe reels de la cola capa 2 vía Gemini multimodal.

        Descargas del CDN en paralelo (antes secuenciales: con ~20 videos de
        hasta 25MB era el cuello de botella de toda la corrida); transcripción
        Gemini secuencial para no golpear rate limits.
        """
        from concurrent.futures import ThreadPoolExecutor

        targets = [
            p for p in posts
            if _is_video_post(p) and (p.get("_video_url") or "")
        ]
        if not targets:
            print(f"[MarketResearchAgent] Capa 1.5: 0/{len(posts)} transcripciones")
            return 0

        with ThreadPoolExecutor(max_workers=4) as pool:
            downloads = list(pool.map(
                lambda p: _download_video(p.get("_video_url") or ""), targets
            ))

        ok = 0
        for post, video_bytes in zip(targets, downloads):
            if not video_bytes:
                continue
            try:
                text = gemini.transcribe_video(video_bytes)
                if text:
                    post["transcripcion"] = text[:8000]
                    ok += 1
                    print(f"[MarketResearchAgent] Transcripción OK @{post.get('owner')} ({len(text)} chars)")
            except Exception as e:
                print(f"[MarketResearchAgent] Warning transcripción @{post.get('owner')}: {e}")
        print(f"[MarketResearchAgent] Capa 1.5: {ok}/{len(posts)} transcripciones")
        return ok

    def _analyze_posts_individually(self, posts: list, brand_brief: dict) -> list:
        """
        Capa 2 — Gemini: modelabilidad + analisis_json estructurado.
        Procesa en batches para no truncar JSON con muchos posts.
        """
        analyzed_count = 0
        for batch_start in range(0, len(posts), DEEP_ANALYSIS_BATCH):
            batch = posts[batch_start:batch_start + DEEP_ANALYSIS_BATCH]
            batch_analyses = self._request_post_analyses_batch(
                batch, batch_start, brand_brief
            )
            if not batch_analyses and len(batch) > 1:
                # Batch entero sin parsear (JSON truncado/malformado): reintento
                # en mitades para no perder los 8 análisis de golpe.
                half = len(batch) // 2
                batch_analyses = self._request_post_analyses_batch(
                    batch[:half], batch_start, brand_brief
                )
                batch_analyses.update(self._request_post_analyses_batch(
                    batch[half:], batch_start + half, brand_brief
                ))
            for local_i, post in enumerate(batch):
                global_idx = batch_start + local_i
                item = (
                    batch_analyses.get(global_idx)
                    or batch_analyses.get(local_i)
                    or batch_analyses.get(str(global_idx))
                    or batch_analyses.get(str(local_i))
                )
                if not item:
                    continue
                model, analisis = _analysis_from_gemini_item(item)
                if analisis.get("hook") or analisis.get("hook_hablado") or analisis.get("tipo_angulo"):
                    post["modelabilidad"] = model
                    post["analisis_json"] = analisis
                    post["_deep_analyzed"] = True
                    analyzed_count += 1

        for post in posts:
            if not (post.get("analisis_json") or {}).get("hook"):
                post["analisis_json"] = _fallback_analisis(post)
                post.setdefault("modelabilidad", 5)
            else:
                post.setdefault("modelabilidad", post.get("modelabilidad", 5))

        print(f"[MarketResearchAgent] Capa 2: {analyzed_count}/{len(posts)} posts con analisis_json de Gemini")
        return posts

    def _request_post_analyses_batch(
        self, batch: list, batch_start: int, brand_brief: dict
    ) -> dict:
        """Una llamada Gemini por batch. Retorna {idx_global: item_dict}."""
        posts_for_prompt = []
        for local_i, p in enumerate(batch):
            m = p.get("metrics", {})
            trans = (p.get("transcripcion") or "").strip()
            posts_for_prompt.append({
                "idx": batch_start + local_i,
                "owner": p.get("owner", ""),
                "caption": (p.get("caption") or "")[:300],
                "transcripcion": trans[:1200] if trans else None,
                "tiene_guion_hablado": bool(trans),
                "views": p.get("views", 0),
                "comments": p.get("comments", 0),
                "saves": p.get("saves", 0),
                "fuerza": m.get("fuerza", 0),
                "relevancia": m.get("relevancia", 0),
                "engagement": m.get("engagement", 0),
                "url": p.get("url", ""),
            })

        prompt = f"""
Analiza cada post de Instagram del array POSTS y devolvé un JSON array con un objeto por post.

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
RESULTADO PRINCIPAL: {brand_brief.get('main_result')}

POSTS (caption + transcripcion del audio cuando existe):
{json.dumps(posts_for_prompt, ensure_ascii=False, indent=2)}

IMPORTANTE — modelar el GUION HABLADO, no solo el caption:
- Si hay transcripcion: el valor está en lo que SE DICE en cámara (estructura, plantilla, CTA hablado).
- Muchos reels virales repiten la misma plantilla de guión; detectala si aplica.
- El caption suele ser complemento; priorizá hook_hablado y estructura_guion sobre el caption.

Cada objeto del array debe tener EXACTAMENTE estos campos (usa el mismo idx del post):
{{
  "idx": {batch_start},
  "modelabilidad": 8,
  "tematica": "Problema del cliente",
  "tipo_angulo": "Problema",
  "enfoque_contenido": "Ventas",
  "hook": "Hook principal (hablado si hay transcripcion, si no del caption)",
  "hook_hablado": "Primera frase o pregunta que abre el reel en voz (null si no hay transcripcion)",
  "cta": "CTA del caption o Sin CTA explícito",
  "cta_hablado": "CTA dicho en voz al cierre (null si no aplica)",
  "lead_magnet": null,
  "problema_resuelto": "Descripción en 1 línea",
  "aspecto_vida": "dinero",
  "formato_descripcion": "Talking head directo a cámara",
  "estructura_guion": "Hook → desarrollo → CTA en 1-2 líneas (ej: pregunta provocadora → 3 puntos → invitación a DM)",
  "plantilla_detectada": "Nombre corto si es plantilla repetible (ej: '3 errores que te cuestan X') o null",
  "por_que_funciona": "1 línea — por qué engancha (métricas + psicología del guión)",
  "que_modelar": "Qué copiar/adaptar: estructura del guión, tipo de hook, formato visual — concreto",
  "por_que_modelar": "Por qué conviene modelarlo para ESTE negocio del cliente (1-2 líneas)",
  "como_adaptar": "1 línea — adaptación general al negocio",
  "como_adaptar_guion": "Borrador de guión adaptado al negocio (2-4 frases habladas, tono del cliente)",
  "scores_tematica": {{
    "problema": 75,
    "solucion": 40,
    "resultado": 30,
    "proceso": 55,
    "mentalidad": 20
  }}
}}

scores_tematica: para CADA temática RIMA, 0–100 = qué tan modelable es ESTE video para grabar contenido de ese tipo (estructura + mensaje), independiente del score comercial global.

tipo_angulo: Problema | Solución | Resultado | Proceso | Mentalidad
enfoque_contenido: Ventas | Educación | Conexión

Modelabilidad 1-10:
9-10 = plantilla de guión directamente replicable al nicho | 7-8 = adaptable con cambios menores
5-6 = inspiración de formato | 3-4 = difícil de adaptar | 1-2 = viral por factores no replicables

Devolvé SOLO el array JSON, sin markdown ni texto extra.
"""
        try:
            response = gemini.generate_json(prompt, SYSTEM_PROMPT)
            raw = _extract_json_array(response)
            if not raw:
                raw = _extract_json_array(gemini.generate(prompt, SYSTEM_PROMPT))
            result = {}
            for i, item in enumerate(raw):
                if not isinstance(item, dict):
                    continue
                idx = _normalize_idx(item.get("idx"), batch_start + i)
                result[idx] = item
            return result
        except Exception as e:
            print(f"[MarketResearchAgent] Warning batch análisis idx={batch_start}: {e}")
            return {}

    def _build_profile_insights(
        self, posts: list, profiles_used: list, profile_meta: dict, brand_brief: dict
    ) -> dict:
        """Resumen por referente para la UI de /mercado."""
        out: dict = {}
        biz = (brand_brief.get("service") or "").lower()
        ideal = (brand_brief.get("ideal_client") or "").lower()

        for raw in profiles_used:
            key = _norm_username(raw)
            meta = profile_meta.get(key, {})
            user_posts = [
                p for p in posts if _norm_username(p.get("owner", "")) == key
            ]
            if not user_posts:
                continue

            top = max(
                user_posts,
                key=lambda p: (p.get("metrics") or {}).get("score_ventas", 0),
            )
            enfoques: dict = {}
            mods = []
            for p in user_posts:
                e = (p.get("analisis_json") or {}).get("enfoque_contenido") or "Sin clasificar"
                enfoques[e] = enfoques.get(e, 0) + 1
                if p.get("modelabilidad"):
                    mods.append(int(p.get("modelabilidad")))
            dom_enf = max(enfoques, key=enfoques.get) if enfoques else "—"
            avg_mod = round(sum(mods) / len(mods), 1) if mods else None

            bio = (meta.get("biography") or "").strip()
            cat = (meta.get("business_category") or "").strip()
            name = (meta.get("full_name") or key).strip()
            fol = int(meta.get("followers") or 0)
            if fol >= 1_000_000:
                fol_s = f"{fol / 1_000_000:.1f}M".replace(".0M", "M")
            elif fol >= 1_000:
                fol_s = f"{fol / 1_000:.1f}K".replace(".0K", "K")
            else:
                fol_s = str(fol) if fol else "?"

            resumen = f"{name} · {fol_s} seguidores"
            if cat:
                resumen += f" · {cat}"
            if bio:
                resumen += f". {bio.splitlines()[0][:140]}"

            top_sv = (top.get("metrics") or {}).get("score_ventas", "—")
            para_nicho = (
                f"{len(user_posts)} posts analizados. Enfoque dominante: {dom_enf}. "
                f"Modelabilidad media: {avg_mod or '—'}/10. "
                f"Mejor pieza para modelar: score ventas {top_sv}."
            )

            tips = []
            top_aj = top.get("analisis_json") or {}
            if top_aj.get("que_modelar"):
                tips.append(f"Modelar: {top_aj['que_modelar']}")
            if top_aj.get("por_que_modelar"):
                tips.append(top_aj["por_que_modelar"])
            if avg_mod and avg_mod >= 7:
                tips.append("Alta modelabilidad — estructura fácil de adaptar.")
            elif avg_mod and avg_mod < 5:
                tips.append("Modelabilidad baja — prioriza la dinámica, no el tema viral.")
            if "venta" in dom_enf.lower():
                tips.append("Fuerte en contenido de conversión; ideal para CTAs y ofertas.")
            bio_l = bio.lower()
            cap_l = (top.get("caption") or "").lower()
            ref_kw = ("ia", "ai", "marketing", "tech", "emprend")
            niche_kw = ("fitness", "coach", "entren", "salud", "gym", "nutri")
            if any(k in biz or k in ideal for k in niche_kw):
                if any(k in bio_l or k in cap_l for k in ref_kw):
                    tips.append(
                        "Nicho distinto al tuyo: modela hooks y formato, no el tema literal."
                    )
                else:
                    tips.append("Buen candidato para adaptar ángulos a tu audiencia.")
            if (top.get("metrics") or {}).get("ratio_conversacion", 0) > 2:
                tips.append("Alta conversación en comentarios — replica CTAs de participación.")

            out[key] = {
                "resumen": resumen,
                "para_nicho": para_nicho,
                "considerar": " ".join(tips) if tips else "Revisa sus top posts y adapta el hook a tu oferta.",
            }
        return out

    def _analyze_patterns_markdown(self, top_posts: list, brand_brief: dict) -> str:
        """Análisis general markdown para mostrar en el dashboard (/mercado)."""
        if top_posts:
            posts_summary = []
            for p in top_posts[:15]:
                m = p.get("metrics", {})
                posts_summary.append({
                    "owner": p["owner"],
                    "caption_preview": p["caption"][:200],
                    "views": p["views"],
                    "comments": p["comments"],
                    "saves": p.get("saves", 0),
                    "fuerza": m.get("fuerza", 0),
                    "relevancia": m.get("relevancia", 0),
                    "engagement": m.get("engagement", 0),
                    "modelabilidad": p.get("modelabilidad"),
                    "url": p.get("url", ""),
                })
            data_context = (
                "TOP POSTS (ordenados por engagement_score):\n"
                + json.dumps(posts_summary, ensure_ascii=False, indent=2)
            )
        else:
            data_context = (
                "Sin datos de scraping disponibles. "
                "Analiza el nicho con tu conocimiento general."
            )

        prompt = f"""
Realiza el estudio de mercado semanal de referentes de Instagram para:

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
RESULTADO: {brand_brief.get('main_result')}

{data_context}

Entrega el análisis en este formato:

## TOP REFERENTES DEL NICHO
Cuentas más relevantes con sus métricas (fuerza, relevancia, engagement). Indica
la modelabilidad de cada una (si está disponible).

## HOOKS QUE FUNCIONAN ESTA SEMANA
Los 5 tipos de hook más efectivos con texto exacto o estructura del ejemplo.

## FORMATOS CON MEJOR ENGAGEMENT
3-4 formatos con descripción de setup y por qué funcionan en este nicho.

## ÁNGULOS DE CONTENIDO DOMINANTES
5 temas/problemas con mayor tracción esta semana.

## PATRONES DE CTA
3-5 CTAs más frecuentes y efectivos.

## 5 IDEAS ADAPTADAS AL NEGOCIO
Tomando los patrones exitosos, adaptadas a: {brand_brief.get('business_name')}.
Por idea:
- Tipo: Reel / Carrusel / Historia
- Hook: [texto exacto del hook]
- Ángulo: Problema / Solución / Resultado / Mentalidad
- Formato: [descripción del setup]
- Referente a modelar: [cuenta o URL si aplica]
- Por qué funciona: [1 línea]
"""
        return gemini.generate(prompt, SYSTEM_PROMPT)

    # ── Persistencia SQLite ───────────────────────────────────────────────────

    def _save_to_sqlite(
        self, cliente_id: str, all_posts: list, top_posts: list, brand_brief: dict = None
    ) -> None:
        """
        Capa 1: upsert métricas de todos los posts scrapeados.
        Capa 2: set_referente_analisis solo en posts marcados _deep_analyzed.
        """
        try:
            from core.db import (
                upsert_referente, set_referente_analisis, init_db, create_or_update_cliente,
            )

            init_db(cliente_id)
            brief = brand_brief or {}
            create_or_update_cliente(
                cliente_id,
                nombre=brief.get("business_name") or cliente_id,
                plan=brief.get("plan", "basico"),
                ig_username=brief.get("ig_username"),
                brief=brief,
            )

            saved = 0
            analyzed = 0
            for post in all_posts:
                url = post.get("url", "")
                m = post.get("metrics", {})
                ref = upsert_referente(cliente_id, {
                    "referente_username": post.get("owner", ""),
                    "plataforma": "instagram",
                    "url": url,
                    "tipo": "reel" if post.get("views", 0) > 0 else "carrusel",
                    "fecha_publicacion": post.get("timestamp", ""),
                    "descripcion": post.get("caption", ""),
                    "transcripcion": post.get("transcripcion") or "",
                    "vistas": post.get("views", 0),
                    "likes": post.get("likes", 0),
                    "comentarios": post.get("comments", 0),
                    "guardados": post.get("saves", 0),
                    "seguidores_al_scrape": post.get("owner_followers", 0),
                    "fuerza": m.get("fuerza"),
                    "relevancia": m.get("relevancia"),
                    "engagement": m.get("engagement"),
                    "ratio_conversacion": m.get("ratio_conversacion"),
                    "score_ventas": m.get("score_ventas"),
                })

                if post.get("_deep_analyzed") and ref and post.get("modelabilidad") is not None:
                    set_referente_analisis(
                        cliente_id,
                        ref["id"],
                        post.get("analisis_json") or {},
                        post.get("modelabilidad", 5),
                        transcripcion=post.get("transcripcion") or None,
                    )
                    analyzed += 1
                saved += 1

            print(
                f"[MarketResearchAgent] SQLite {cliente_id}: "
                f"{saved} métricas actualizadas, {analyzed} análisis profundos"
            )
        except Exception as e:
            import traceback
            print(f"[MarketResearchAgent] Warning SQLite: {e}")
            traceback.print_exc()


market_research_agent = MarketResearchAgent()
