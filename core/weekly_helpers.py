"""
Utilidades del Orquestador Semanal: slots SQLite, matching de referentes, adapters.
"""
from __future__ import annotations

from collections import defaultdict
from core.market_scores import score_tematica_for_slot
from datetime import date, datetime, timedelta
import json
import re

_TRADUCCION_CACHE: dict[str, str] = {}


ENFOQUE_ALIASES = {
    "ventas": ("ventas", "venta", "conversion", "conversión"),
    "educacion": ("educacion", "educación", "education", "educativo"),
    "conexion": ("conexion", "conexión", "connection", "comunidad"),
}

TIPO_POST_MAP = {
    "reel": ("video", "reel", "xdt_graph_video"),
    "carrusel": ("sidecar", "carousel", "image"),
    "historia": ("video", "reel", "image", "sidecar", "historia"),
}

CARRUSEL_POST_TYPES = frozenset({"sidecar", "carousel", "image"})
VIDEO_POST_TYPES = frozenset({"video", "reel", "xdt_graph_video", "clips"})

TEMATICA_KEYS = ("problema", "mentalidad", "proceso", "solucion", "resultado")

TEMA_SCORE_STRONG = 35.0
TEMA_SCORE_RELAXED = 20.0

TEMATICA_SYNONYMS = {
    "problema": ("problema", "dolor", "objecion", "pain", "friccion"),
    "mentalidad": ("mentalidad", "mindset", "creencia", "motivacion", "actitud"),
    "proceso": ("proceso", "metodo", "paso", "sistema", "rutina"),
    "solucion": ("solucion", "solución", "como", "tutorial", "guia"),
    "resultado": ("resultado", "transformacion", "testimonio", "antes", "despues"),
}

# Ángulos estratégicos para historias (no vienen del estudio de mercado).
HISTORIA_ANGULOS: dict[str, list[dict]] = {
    "hand_raiser": [
        {
            "titulo": "Recurso gratuito + palabra clave",
            "idea_principal": (
                "Hand Raiser: invitá a responder una palabra clave para recibir un recurso "
                "de alto valor (guía, checklist o rutina). Cerrá con pregunta abierta sobre su bloqueo."
            ),
        },
        {
            "titulo": "Excusa #1 + lead magnet",
            "idea_principal": (
                "Nombrá la excusa principal del cliente ideal y ofrecé un recurso que la resuelva "
                "en un paso. Palabra clave visible + pregunta: ¿te pasa esto?"
            ),
        },
        {
            "titulo": "Mini demo + recurso",
            "idea_principal": (
                "Mostrá en 1 historia el resultado del recurso (antes/después rápido) y pedí "
                "comentar la palabra clave para enviarlo por DM."
            ),
        },
        {
            "titulo": "Pregunta directa + entrega",
            "idea_principal": (
                "Abrí con pregunta sobre el dolor del nicho. Ofrecé recurso gratuito específico "
                "a quienes respondan la palabra clave. Sin vender en la historia."
            ),
        },
    ],
    "awareness": [
        {
            "titulo": "Victoria de cliente",
            "idea_principal": (
                "Awareness: caso real con número concreto (resultado medible). "
                "Foto/captura + 1 línea de proceso. Sin CTA de venta."
            ),
        },
        {
            "titulo": "Día a día / detrás de escena",
            "idea_principal": (
                "Mostrá un momento auténtico del negocio o transformación de clientes. "
                "Conexión humana, cero pitch."
            ),
        },
        {
            "titulo": "Mito vs realidad",
            "idea_principal": (
                "Desmentí una creencia común del nicho con un dato o ejemplo breve. "
                "Genera confianza sin pedir acción."
            ),
        },
        {
            "titulo": "Micro-resultado rápido",
            "idea_principal": (
                "Un logro pequeño pero específico (7 días, 20 min, 1 hábito). "
                "Formato victoria + prueba social ligera."
            ),
        },
    ],
    "encuesta": [
        {
            "titulo": "Poll de segmentación",
            "idea_principal": (
                "Encuesta: 2 opciones que revelen el bloqueo o deseo del avatar. "
                "Usá el resultado para abrir chat con quienes voten."
            ),
        },
        {
            "titulo": "Encuesta + cajita de preguntas",
            "idea_principal": (
                "Combiná sticker de encuesta con cajita Q&A. Invitá a preguntar "
                "sobre el tema de la semana."
            ),
        },
        {
            "titulo": "¿Cuál te representa más?",
            "idea_principal": (
                "Poll emocional (tiempo, energía, resultados). Después respondé "
                "por DM a quienes elijan la opción 'problemática'."
            ),
        },
        {
            "titulo": "Votá y te cuento",
            "idea_principal": (
                "Encuesta binaria + promesa de profundizar en la historia siguiente "
                "según la opción ganadora."
            ),
        },
    ],
    "cta_informativo": [
        {
            "titulo": "CTA honesto",
            "idea_principal": (
                "CTA informativo: avisá que es invitación al programa/servicio. "
                "Explicá en 2 líneas a quién es y cómo responder."
            ),
        },
        {
            "titulo": "Cupos / plazas",
            "idea_principal": (
                "Mencioná disponibilidad real (cupos, fechas). Invitá a escribir "
                "palabra clave si quieren info sin presión."
            ),
        },
        {
            "titulo": "Para quién es / no es",
            "idea_principal": (
                "Filtrá al avatar ideal: 'esto es para vos si… / no es para vos si…'. "
                "CTA suave a conversación."
            ),
        },
        {
            "titulo": "Urgencia suave",
            "idea_principal": (
                "Why-now light: cambio próximo (precio, cierre, temporada). "
                "CTA informativo sin hype vacío."
            ),
        },
    ],
}


def week_bounds(ref: date = None) -> tuple[str, str, str]:
    ref = ref or date.today()
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    iso = ref.isocalendar()
    label = f"W{iso.week:02d}_{iso.year}"
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d"), label


def _norm_text(val: str) -> str:
    v = (val or "").lower().strip()
    return v.replace("ó", "o").replace("ú", "u").replace("í", "i").replace("á", "a").replace("é", "e")


def normalize_tematica(val: str) -> str:
    """Normaliza temática del slot (Problema, Mentalidad, Awareness / Victorias, etc.)."""
    raw = _norm_text(val)
    for key in TEMATICA_KEYS:
        if key in raw:
            return key
    first = re.split(r"[/|·\-]", val or "")[0].strip()
    return _norm_text(first) or "general"


def _parse_analisis(post: dict) -> dict:
    analisis = post.get("analisis_json") or {}
    if isinstance(analisis, str):
        try:
            analisis = json.loads(analisis)
        except Exception:
            analisis = {}
    return analisis or {}


def pub_to_slot(pub: dict) -> dict:
    prop = pub.get("propuesta_json") or {}
    if isinstance(prop, str):
        try:
            prop = json.loads(prop)
        except Exception:
            prop = {}
    return {
        "id": pub.get("id"),
        "date": pub.get("fecha"),
        "fecha": pub.get("fecha"),
        "type": pub.get("tipo"),
        "tipo": pub.get("tipo"),
        "topic": pub.get("tematica", ""),
        "tematica": pub.get("tematica", ""),
        "content_type": pub.get("tematica", ""),
        "story_type": pub.get("tematica", ""),
        "carousel_type": pub.get("tematica", ""),
        "enfoque": pub.get("enfoque", ""),
        "angulo_estrategico": (
            prop.get("angulo_estrategico", "")
            or (prop.get("slot_resumen") or {}).get("angulo_estrategico", "")
            or pub.get("angulo_estrategico", "")
        ),
        "semana": pub.get("semana"),
        "dia": pub.get("dia"),
    }


def get_week_publicaciones(get_publicaciones_fn, cliente_id: str,
                           week_start: str = None, week_end: str = None,
                           status: str = None) -> list:
    if not week_start or not week_end:
        week_start, week_end, _ = week_bounds()
    pubs = get_publicaciones_fn(cliente_id, status=status)
    return [
        p for p in pubs
        if week_start <= (p.get("fecha") or "") <= week_end
    ]


# Orden canónico de estados de una publicación (pipeline E2E).
STATUS_ORDER = [
    "planificado", "propuesta_generada", "propuesta_enviada", "propuesta_aprobada",
    "copy_generado", "copy_enviado", "copy_aprobado",
    "en_produccion", "produccion_enviada", "produccion_aprobada",
    "programado", "publicado",
]


def status_rank(status: str) -> int:
    try:
        return STATUS_ORDER.index(status or "planificado")
    except ValueError:
        return 0


def sync_weekly_state_from_db(cliente_id: str, brand: str, ref_fecha: str = None) -> dict:
    """Refleja en weekly_state.json el estado real de SQLite (fuente de verdad).

    Deriva stage / copy_stage_done / production_done de publicaciones.status
    para la semana de ref_fecha (o la actual). weekly_state queda como espejo
    de solo lectura; no crea estado si la semana nunca arrancó.
    """
    from core.db import get_publicaciones
    from core.client_store import load_weekly_state, save_weekly_state

    ref = None
    if ref_fecha:
        try:
            ref = date.fromisoformat(ref_fecha)
        except ValueError:
            ref = None
    week_start, week_end, week = week_bounds(ref)

    state = load_weekly_state(brand, week)
    if not state or state.get("stage") == "not_started":
        return {}

    pubs = [
        p for p in get_publicaciones(cliente_id)
        if week_start <= (p.get("fecha") or "") <= week_end
        and p.get("status") != "cancelado"
    ]
    if not pubs:
        return state

    ranks = [status_rank(p.get("status")) for p in pubs]
    copy_done = min(ranks) >= status_rank("copy_aprobado")
    prod_done = min(ranks) >= status_rank("produccion_aprobada")
    if copy_done:
        stage = "produccion"
    elif max(ranks) >= status_rank("copy_generado"):
        stage = "copy"
    else:
        stage = "propuesta"

    state["stage"] = stage
    state["copy_stage_done"] = copy_done
    state["production_done"] = prod_done
    state["source_of_truth"] = "sqlite"
    state["updated_at"] = datetime.now().isoformat()
    save_weekly_state(brand, week, state)
    return state


def _norm_enfoque(val: str) -> str:
    v = _norm_text(val)
    for key, aliases in ENFOQUE_ALIASES.items():
        if v in aliases or v == key:
            return key
    return v


def normalize_historia_tipo(tematica: str) -> str:
    """Mapea temática del calendario al tipo de estrategia de historia."""
    raw = _norm_text(tematica)
    if "hand raiser" in raw or "handraiser" in raw:
        return "hand_raiser"
    if "encuesta" in raw or "poll" in raw or "q&a" in raw or "q a" in raw:
        return "encuesta"
    if "cta" in raw and "informativo" in raw:
        return "cta_informativo"
    if "why now" in raw or "whynow" in raw:
        return "cta_informativo"
    if "awareness" in raw or "victoria" in raw or "libre" in raw:
        return "awareness"
    return "awareness"


def _looks_english(text: str) -> bool:
    lower = (text or "").lower()
    en_markers = (
        " comment ", " using ", " the ", " with ", " create ", " guide ",
        " follow for", " click ", " download ", " instantly ", " claude code",
        " free ", " dm ", " link in bio",
    )
    if any(m in lower for m in en_markers):
        return True
    return bool(re.search(
        r"\b(the|with|using|create|comment|your|this|that|for|from|what|how to)\b",
        lower,
    ))


def _looks_spanish(text: str) -> bool:
    if not text or len(text.strip()) < 8:
        return False
    if _looks_english(text):
        return False
    lower = text.lower()
    if re.search(r"[áéíóúñ]", lower):
        return True
    es_markers = (
        " que ", " qué ", " cómo ", " para ", " con ", " los ", " las ", " del ",
        " tu ", " tus ", " estás ", " estes ", " rutina ", " minutos ", " comentá ",
        " entrenar ", " profesional", " iniciar", " sueñas", " negocio", " emprend",
        " ventas", " guía", " gratis", " mirá", " podés", " tenés", " empezá",
    )
    return any(w in lower for w in es_markers)


def _raw_field(analisis: dict, key: str, min_len: int = 12) -> str:
    val = (analisis.get(key) or "").strip()
    return val if len(val) >= min_len else ""


def _raw_caption(post: dict) -> str:
    cap = (post.get("caption") or "").strip()
    for chunk in cap.split("\n"):
        chunk = chunk.strip().strip(".")
        if len(chunk) >= 12:
            return chunk[:500]
    return ""


def _a_texto_cliente(text: str, max_len: int = 280) -> str:
    """Texto en español del cliente: conserva si ya está en ES, si no traduce."""
    text = (text or "").strip()
    if not text or len(text) < 8:
        return ""
    if _looks_spanish(text):
        return text[:max_len]
    cache_key = text[:240]
    cached = _TRADUCCION_CACHE.get(cache_key)
    if cached:
        return cached[:max_len]
    try:
        from core.gemini_client import gemini
        out = gemini.generate(
            "Traducí al español rioplatense (Argentina, vos). "
            "Devolvé SOLO la traducción, sin comillas ni explicación.\n\n"
            + text[:900],
            system_prompt=(
                "Traductor de copy de Instagram. Natural, conciso, marketing. "
                "No agregues prefijos ni notas."
            ),
        ).strip().strip('"').strip("'")
        if out and len(out) >= 8:
            _TRADUCCION_CACHE[cache_key] = out
            return out[:max_len]
    except Exception:
        pass
    return text[:max_len]


def _raw_idea_source(post: dict) -> str:
    analisis = _parse_analisis(post)
    keys = (
        "como_adaptar",
        "como_adaptar_guion",
        "que_modelar",
        "por_que_modelar",
        "problema_resuelto",
        "estructura_guion",
        "plantilla_detectada",
        "por_que_funciona",
    )
    for key in keys:
        val = _field_es(analisis, key, min_len=15, limit=500)
        if val:
            return val
    for key in keys:
        val = _raw_field(analisis, key, min_len=15)
        if val:
            return val
    return _caption_es(post) or _raw_caption(post)


def _raw_titulo_source(post: dict) -> str:
    analisis = _parse_analisis(post)
    for key in ("como_adaptar", "como_adaptar_guion"):
        val = _field_es(analisis, key, min_len=12, limit=500)
        if val:
            return val
        val = _raw_field(analisis, key, min_len=12)
        if val:
            return val
    for key in ("que_modelar", "problema_resuelto", "hook"):
        val = _field_es(analisis, key, min_len=12, limit=500)
        if val:
            return val
        val = _raw_field(analisis, key, min_len=12)
        if val:
            return val
    return _caption_es(post) or _raw_caption(post)


def _caption_es(post: dict) -> str:
    cap = (post.get("caption") or "").strip()
    if not cap:
        return ""
    for chunk in cap.split("\n"):
        chunk = chunk.strip().strip(".")
        if len(chunk) >= 12 and _looks_spanish(chunk):
            return chunk[:280]
    return ""


def _field_es(analisis: dict, key: str, min_len: int = 15, limit: int = 280) -> str:
    val = (analisis.get(key) or "").strip()
    if len(val) >= min_len and _looks_spanish(val):
        return val[:limit]
    return ""


def _post_tipo_matches(slot_tipo: str, post_type: str, strict: bool = False) -> bool:
    allowed = TIPO_POST_MAP.get((slot_tipo or "").lower(), ())
    pt = (post_type or "").lower()
    if not allowed:
        return True
    if pt in allowed or pt == slot_tipo:
        return True
    if strict:
        return False
    if slot_tipo == "carrusel" and pt in CARRUSEL_POST_TYPES:
        return True
    return False


def _normalize_post_type(post_type: str) -> str:
    return (post_type or "").lower().strip()


def _es_post_carrusel(post: dict) -> bool:
    return _normalize_post_type(post.get("type")) in CARRUSEL_POST_TYPES


def market_has_carousel_posts(market_data: dict) -> bool:
    posts = market_data.get("posts") or market_data.get("top_posts") or []
    return any(_es_post_carrusel(p) for p in posts)


def _alternativas_validas_carrusel(alternativas: list, posts_by_url: dict) -> bool:
    """Válido si hay carrusel nativo o reel marcado como adaptable."""
    for alt in alternativas or []:
        if alt.get("adaptado_desde_reel"):
            return True
        pt = _normalize_post_type(alt.get("formato_post") or "")
        if pt in CARRUSEL_POST_TYPES:
            return True
        url = alt.get("url") or ""
        post = posts_by_url.get(url) or {}
        if _es_post_carrusel(post):
            return True
    return False


def _propuesta_carrusel_necesita_regenerar(pub: dict, market_data: dict) -> bool:
    if (pub.get("tipo") or "").lower() != "carrusel":
        return False
    prop = _parse_propuesta(pub)
    alts = prop.get("alternativas") or []
    if not alts:
        return True
    posts = {
        p.get("url"): p
        for p in (market_data.get("posts") or market_data.get("top_posts") or [])
        if p.get("url")
    }
    return not _alternativas_validas_carrusel(alts, posts)


def _reel_es_adaptable_a_carrusel(post: dict) -> bool:
    """Reel/video con estructura modelable → candidato a convertir en carrusel."""
    if _normalize_post_type(post.get("type")) not in VIDEO_POST_TYPES:
        return False
    return _is_modelable_post(post, "carrusel")


def _modo_referente_carrusel(alternativas: list) -> str | None:
    if not alternativas:
        return None
    adaptados = sum(1 for a in alternativas if a.get("adaptado_desde_reel"))
    if adaptados == 0:
        return "carrusel_nativo"
    if adaptados == len(alternativas):
        return "reel_adaptado"
    return "mixto"


def _enfoque_score(slot_enfoque: str, post: dict) -> float:
    slot_e = _norm_enfoque(slot_enfoque)
    if not slot_e:
        return 0.0
    analisis = _parse_analisis(post)
    post_e = _norm_enfoque(analisis.get("enfoque_contenido") or analisis.get("tipo_angulo") or "")
    if post_e == slot_e:
        return 12.0
    compat = {
        "ventas": ("solucion", "problema", "resultado"),
        "educacion": ("solucion", "proceso", "mentalidad"),
        "conexion": ("mentalidad", "proceso", "conexion"),
    }
    tematica = _norm_text(analisis.get("tematica") or "")
    if tematica in compat.get(slot_e, ()):
        return 6.0
    return 0.0


CROSS_LANG_TEMA = {
    "problema": ("problema", "problem", "pain", "struggle", "objection", "excuse"),
    "mentalidad": ("mentalidad", "mindset", "belief", "motivation", "attitude"),
    "proceso": ("proceso", "process", "method", "step", "system", "workflow"),
    "solucion": ("solucion", "solution", "how to", "tutorial", "guide", "create", "build", "professional"),
    "resultado": ("resultado", "result", "transformation", "testimonial", "before", "after"),
}


def _tematica_blob(post: dict) -> str:
    analisis = _parse_analisis(post)
    parts = [
        analisis.get("tematica") or "",
        analisis.get("tipo_angulo") or "",
        analisis.get("aspecto_vida") or "",
        analisis.get("problema_resuelto") or "",
        analisis.get("que_modelar") or "",
        analisis.get("como_adaptar") or "",
        _raw_caption(post),
    ]
    return _norm_text(" ".join(parts))


def tematica_match_score(slot_tematica: str, post: dict) -> float:
    """Qué tan bien el referente calza con la temática del slot (ES o EN)."""
    slot_key = normalize_tematica(slot_tematica)
    if slot_key == "general":
        return 0.0
    blob = _tematica_blob(post)
    if not blob.strip():
        return 0.0
    if slot_key in blob:
        return 40.0
    for syn in TEMATICA_SYNONYMS.get(slot_key, ()):
        if syn in blob:
            return 24.0
    for syn in CROSS_LANG_TEMA.get(slot_key, ()):
        if syn in blob:
            return 20.0
    # Sin match claro: neutral (no penalizar por idioma ni analisis vacío)
    return 0.0


def enrich_market_posts(market_data: dict) -> list:
    """Recalcula score_ventas y scores_tematica en memoria antes de rankear."""
    from core.market_scores import attach_score_ventas, attach_scores_tematica

    posts = list(market_data.get("posts") or market_data.get("top_posts") or [])
    for post in posts:
        attach_score_ventas(post)
        attach_scores_tematica(post)
    return posts


def format_slot_context_for_copy(slot: dict, referent: dict | None = None) -> str:
    """Pasaporte del slot para agents de copy (temática, enfoque, ángulo estratégico)."""
    from core.market_scores import _norm_tematica_key

    tematica = slot.get("tematica") or slot.get("topic") or "—"
    enfoque = slot.get("enfoque") or "—"
    lines = [
        "CONTEXTO DEL SLOT (respetar al adaptar el referente):",
        f"- Temática RIMA: {tematica}",
        f"- Enfoque: {enfoque}",
    ]
    angulo = (slot.get("angulo_estrategico") or "").strip()
    if angulo:
        lines.append(f"- Ángulo estratégico: {angulo}")
    lines.append(
        "Modelá la dinámica del referente (hook, ritmo, estructura) pero el mensaje "
        "debe encajar con la temática y el enfoque del slot — no cambies el ángulo del calendario."
    )
    if referent:
        ref_tema = (referent.get("tematica_referente") or "").strip()
        if ref_tema:
            lines.append(f"- Referente originalmente clasificado como: {ref_tema}")
            slot_key = normalize_tematica(tematica)
            ref_key = _norm_tematica_key(ref_tema)
            if slot_key != "general" and ref_key != slot_key:
                lines.append(
                    f"- Adaptación obligatoria: reencuadrar el contenido del referente "
                    f"({ref_tema}) hacia la temática del slot ({tematica})."
                )
        if referent.get("que_modelar"):
            lines.append(f"- Qué tomar del referente: {referent.get('que_modelar')}")
    return "\n".join(lines)


def _rank_score(post: dict, slot: dict) -> float:
    """Ranking: encaje temático (78%) + score_ventas visible (22%) + bonuses menores."""
    tematica_score = score_tematica_for_slot(post, slot.get("tematica", ""))
    metrics = post.get("metrics") or {}
    ventas = float(metrics.get("score_ventas") or 0)
    enfoque_bonus = _enfoque_score(slot.get("enfoque", ""), post)
    tipo_bonus = 0.0
    slot_tipo = (slot.get("tipo") or slot.get("type") or "reel").lower()
    pt = (post.get("type") or "").lower()
    if slot_tipo == "carrusel" and pt in ("sidecar", "carousel"):
        tipo_bonus = 8.0
    return tematica_score * 0.78 + ventas * 0.22 + enfoque_bonus + tipo_bonus


def _video_titulo(post: dict) -> str:
    """Título en español: adaptación o traducción del referente."""
    raw = _raw_titulo_source(post)
    if not raw:
        return ""
    sent = re.split(r"[.!?]\s", raw)[0].strip()
    return _a_texto_cliente(sent or raw, max_len=100)


def _idea_principal(post: dict) -> str:
    """Idea central en español del cliente (traduce si hace falta)."""
    raw = _raw_idea_source(post)
    return _a_texto_cliente(raw, max_len=280)


def _is_modelable_post(post: dict, slot_tipo: str = "") -> bool:
    if _raw_idea_source(post):
        return True
    pt = (post.get("type") or "").lower()
    if (slot_tipo or "").lower() == "carrusel" and pt in ("sidecar", "carousel", "image"):
        return bool(_raw_caption(post))
    return bool(_raw_caption(post))


def post_to_alternativa(post: dict, slot_tipo: str = "") -> dict:
    analisis = _parse_analisis(post)
    metrics = post.get("metrics") or {}
    idea = _idea_principal(post)
    titulo = _video_titulo(post)
    guion_raw = _raw_field(analisis, "como_adaptar_guion", 12) or _raw_field(analisis, "como_adaptar", 12)
    guion_es = _a_texto_cliente(guion_raw, max_len=500) if guion_raw else ""
    que_raw = _raw_field(analisis, "que_modelar", 12)
    que_es = _a_texto_cliente(que_raw, max_len=280) if que_raw else idea
    formato = _normalize_post_type(post.get("type"))
    slot = (slot_tipo or "").lower()
    adaptado_reel = (
        slot == "carrusel"
        and formato not in CARRUSEL_POST_TYPES
        and formato in VIDEO_POST_TYPES
    )
    if adaptado_reel:
        nota = (
            "Referente reel viral — adaptar gancho, desarrollo y CTA "
            "a un carrusel de 7 slides con la misma idea central."
        )
        que_es = f"{(que_es or idea).rstrip('.')}. {nota}"
        guion_es = (
            f"{(guion_es or idea).rstrip('.')}. "
            "Convertir la estructura narrativa del reel en slides secuenciales."
        )
    return {
        "referente_id": post.get("id"),
        "owner": post.get("owner", ""),
        "url": post.get("url", ""),
        "titulo": titulo or idea[:100],
        "views": post.get("views") or 0,
        "comments": post.get("comments") or 0,
        "seguidores": post.get("owner_followers") or 0,
        "score_ventas": round(float(metrics.get("score_ventas") or 0), 1),
        "modelabilidad": post.get("modelabilidad"),
        "fuerza": metrics.get("fuerza"),
        "tematica_referente": analisis.get("tematica") or analisis.get("tipo_angulo") or "",
        "que_modelar": que_es,
        "idea_principal": idea,
        "hook_hablado": _a_texto_cliente(analisis.get("hook_hablado", ""), max_len=200),
        "como_adaptar_guion": guion_es or idea,
        "transcripcion_preview": (post.get("transcripcion") or "")[:280],
        "justificacion": _a_texto_cliente(
            analisis.get("por_que_modelar") or analisis.get("por_que_funciona", ""),
            max_len=200,
        ),
        "caption_preview": (post.get("caption") or "")[:160],
        "tipo_propuesta": "referente",
        "formato_post": formato,
        "adaptado_desde_reel": adaptado_reel,
        "traducido": not _looks_spanish(_raw_idea_source(post)),
    }


def _carousel_es_adaptable(post: dict) -> bool:
    """Carrusel con guía de adaptación (no solo imágenes sin contexto)."""
    analisis = _parse_analisis(post)
    for key in (
        "como_adaptar", "como_adaptar_guion", "estructura_guion",
        "que_modelar", "plantilla_detectada", "por_que_modelar",
    ):
        if _raw_field(analisis, key, 20):
            return True
    return len(_raw_caption(post).strip()) >= 60


def rank_posts_for_slot(slot: dict, posts: list, exclude_urls: set | None = None) -> list:
    exclude = exclude_urls or set()
    slot_tematica = slot.get("tematica", "")
    slot_tipo = (slot.get("tipo") or slot.get("type") or "reel").lower()
    candidates = []
    for strict in (True, False):
        for p in posts:
            url = p.get("url") or ""
            if url in exclude:
                continue
            if not _post_tipo_matches(slot_tipo, p.get("type", ""), strict=strict):
                continue
            if _is_modelable_post(p, slot_tipo):
                candidates.append(p)
        if candidates:
            break

    # Sin carruseles en el estudio → mejores reels adaptables a carrusel.
    if slot_tipo == "carrusel" and not candidates:
        for p in posts:
            url = p.get("url") or ""
            if url in exclude:
                continue
            if _reel_es_adaptable_a_carrusel(p):
                candidates.append(p)

    def sort_key(p: dict) -> float:
        score = _rank_score(p, slot)
        ts = score_tematica_for_slot(p, slot_tematica)
        if ts >= TEMA_SCORE_STRONG:
            score += 50.0
        elif ts >= TEMA_SCORE_RELAXED:
            score += 18.0
        if slot_tipo == "carrusel":
            if _es_post_carrusel(p):
                score += 18.0 if _carousel_es_adaptable(p) else 8.0
            elif _reel_es_adaptable_a_carrusel(p):
                score += 12.0 if _carousel_es_adaptable(p) else 4.0
        return score

    candidates.sort(key=sort_key, reverse=True)
    return candidates


def _pick_market_alternatives(
    ranked: list,
    slot: dict,
    week_used: set,
    limit: int = 2,
) -> list:
    """
    Elige hasta `limit` alternativas con rotación semanal.
    Relaja umbral temático si no hay suficientes opciones fuertes.
    """
    slot_tematica = slot.get("tematica", "")
    picked: list = []
    blocked = set(week_used)

    def try_from(pool: list) -> None:
        for p in pool:
            if len(picked) >= limit:
                return
            url = p.get("url") or ""
            if url in blocked:
                continue
            alt = post_to_alternativa(p, slot.get("tipo") or slot.get("type") or "")
            if not alt.get("idea_principal"):
                continue
            picked.append(alt)
            blocked.add(url)

    available = [p for p in ranked if (p.get("url") or "") not in week_used]
    strong = [
        p for p in available
        if score_tematica_for_slot(p, slot_tematica) >= TEMA_SCORE_STRONG
    ]
    try_from(strong)
    if len(picked) < limit:
        relaxed = [
            p for p in available
            if score_tematica_for_slot(p, slot_tematica) >= TEMA_SCORE_RELAXED
        ]
        try_from(relaxed)
    if len(picked) < limit:
        try_from(available)

    return picked


def match_referentes_for_slot(slot: dict, market_data: dict, limit: int = 2,
                              exclude_urls: set | None = None) -> list:
    posts = market_data.get("posts") or market_data.get("top_posts") or []
    ranked = rank_posts_for_slot(slot, posts, exclude_urls)
    return [post_to_alternativa(p) for p in ranked[:limit]]


def assign_historia_propuestas(pubs: list, exclude_angulos: set | None = None) -> dict[str, list]:
    """Propuestas de historias desde estrategia RIMA, no estudio de mercado."""
    chosen = set(exclude_angulos or [])
    groups: dict[str, list] = defaultdict(list)

    for pub in pubs:
        if (pub.get("tipo") or "").lower() != "historia":
            continue
        key = normalize_historia_tipo(pub.get("tematica", ""))
        groups[key].append(pub)

    assignments: dict[str, list] = {}

    for tipo_key, group in groups.items():
        angulos = HISTORIA_ANGULOS.get(tipo_key, HISTORIA_ANGULOS["awareness"])
        group_used = set(chosen)
        cursor = 0
        for pub in sorted(group, key=lambda p: p.get("fecha", "")):
            slot = pub_to_slot(pub)
            alts = []
            scanned = 0
            while len(alts) < 2 and scanned < len(angulos) * 3:
                ang = angulos[cursor % len(angulos)]
                ang_id = f"estrategia:{tipo_key}:{cursor % len(angulos)}"
                cursor += 1
                scanned += 1
                if ang_id in group_used:
                    continue
                alts.append({
                    "tipo_propuesta": "estrategia",
                    "referente_id": ang_id,
                    "story_type": tipo_key,
                    "owner": "",
                    "url": "",
                    "titulo": ang["titulo"],
                    "idea_principal": ang["idea_principal"],
                    "que_modelar": ang["idea_principal"],
                    "tematica_referente": slot.get("tematica", ""),
                    "score_ventas": None,
                })
                group_used.add(ang_id)
            assignments[pub["id"]] = alts

    return assignments


def assign_market_propuestas(pubs: list, market_data: dict,
                             exclude_urls: set | None = None) -> dict[str, list]:
    """Propuestas de reels/carruseles — rotación semanal única de URLs (R1)."""
    posts = enrich_market_posts(market_data)
    week_used = set(exclude_urls or [])
    assignments: dict[str, list] = {}

    market_pubs = [
        p for p in pubs
        if (p.get("tipo") or "reel").lower() != "historia"
    ]
    for pub in sorted(market_pubs, key=lambda p: p.get("fecha", "")):
        slot = pub_to_slot(pub)
        ranked = rank_posts_for_slot(slot, posts, week_used)
        alts = _pick_market_alternatives(ranked, slot, week_used, limit=2)
        for alt in alts:
            url = alt.get("url") or ""
            if url:
                week_used.add(url)
        assignments[pub["id"]] = alts

    return assignments


def assign_propuestas_rotating(pubs: list, market_data: dict,
                               exclude_urls: set | None = None,
                               exclude_angulos: set | None = None) -> dict[str, list]:
    """
    Asigna 2 alternativas por pieza.
    Historias → estrategia RIMA. Reels/carruseles → mercado con rotación A/B · C/D.
    """
    assignments: dict[str, list] = {}
    historia_pubs = [p for p in pubs if (p.get("tipo") or "").lower() == "historia"]
    market_pubs = [p for p in pubs if (p.get("tipo") or "").lower() != "historia"]

    if historia_pubs:
        assignments.update(
            assign_historia_propuestas(historia_pubs, exclude_angulos=exclude_angulos),
        )
    if market_pubs:
        assignments.update(
            assign_market_propuestas(market_pubs, market_data, exclude_urls=exclude_urls),
        )
    return assignments


def _parse_propuesta(pub: dict) -> dict:
    prop = pub.get("propuesta_json") or {}
    if isinstance(prop, str):
        try:
            prop = json.loads(prop)
        except Exception:
            prop = {}
    return prop


def collect_used_referente_urls(pubs: list) -> set:
    """URLs de referentes ya elegidos en la semana (copy o propuesta aprobada)."""
    used = set()
    for pub in pubs:
        prop = _parse_propuesta(pub)
        elegida = prop.get("elegida") or {}
        url = elegida.get("url") or prop.get("referente_url") or ""
        if url:
            used.add(url)
            continue
        copy_j = pub.get("copy_json") or {}
        if isinstance(copy_j, str):
            try:
                copy_j = json.loads(copy_j)
            except Exception:
                copy_j = {}
        curl = copy_j.get("referente_url") or ""
        if curl:
            used.add(curl)
    return used


def collect_used_historia_angulos(pubs: list) -> set:
    """IDs de ángulos estratégicos ya elegidos en historias de la semana."""
    used = set()
    for pub in pubs:
        if (pub.get("tipo") or "").lower() != "historia":
            continue
        prop = _parse_propuesta(pub)
        elegida = prop.get("elegida") or {}
        if elegida.get("tipo_propuesta") == "estrategia":
            ang_id = elegida.get("referente_id") or ""
            if ang_id:
                used.add(ang_id)
    return used


def collect_propuesta_excludes(pubs: list, pub_id: str) -> tuple[set, set]:
    """
    URLs y ángulos a excluir al refrescar: elegidos en la semana +
    alternativas actuales de esta pieza (las que el cliente descarta).
    """
    urls = collect_used_referente_urls(pubs)
    angulos = collect_used_historia_angulos(pubs)

    for pub in pubs:
        if pub.get("id") != pub_id:
            continue
        prop = _parse_propuesta(pub)
        for alt in prop.get("alternativas") or []:
            if alt.get("url"):
                urls.add(alt["url"])
            if alt.get("tipo_propuesta") == "estrategia" and alt.get("referente_id"):
                angulos.add(alt["referente_id"])

    return urls, angulos


def refresh_propuesta_for_pub(cliente_id: str, pub_id: str, market_data: dict) -> dict:
    """
    Descarta las alternativas visibles y asigna las 2 siguientes del pool.
    Solo aplica en etapa propuesta (sin copy generado).
    """
    from datetime import datetime as dt
    from core.db import get_publicacion, update_publicacion_field, update_publicacion_status

    pub = get_publicacion(cliente_id, pub_id)
    if not pub:
        return {"ok": False, "error": "Publicación no encontrada"}

    status = pub.get("status") or "planificado"
    if status not in ("planificado", "propuesta_generada"):
        return {
            "ok": False,
            "error": "Solo podés cambiar opciones antes de generar el copy",
        }

    fecha = pub.get("fecha") or ""
    if not fecha:
        return {"ok": False, "error": "Pieza sin fecha"}

    try:
        ref = dt.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        return {"ok": False, "error": "Fecha inválida"}

    week_start, week_end, _ = week_bounds(ref)
    from core.db import get_publicaciones
    all_pubs = get_week_publicaciones(get_publicaciones, cliente_id, week_start, week_end)

    exclude_urls, exclude_angulos = collect_propuesta_excludes(all_pubs, pub_id)
    prop_prev = _parse_propuesta(pub)
    descartes = int(prop_prev.get("descartes") or 0) + 1

    assignments = assign_propuestas_rotating(
        [pub], market_data, exclude_urls=exclude_urls, exclude_angulos=exclude_angulos,
    )
    alts = assignments.get(pub_id) or []

    if not alts:
        return {
            "ok": False,
            "error": "No hay más opciones en el pool para esta pieza. Probá otra semana o contactá soporte.",
            "descartes": descartes,
        }

    slot = pub_to_slot(pub)
    propuesta = build_propuesta_json(alts, slot)
    propuesta["descartes"] = descartes
    propuesta["etapa"] = "propuesta"

    update_publicacion_field(cliente_id, pub_id, "propuesta_json", propuesta)
    if status == "planificado":
        update_publicacion_status(cliente_id, pub_id, "propuesta_generada")

    return {
        "ok": True,
        "pub_id": pub_id,
        "alternativas": alts,
        "descartes": descartes,
        "adaptable_hint": (pub.get("tipo") or "").lower() == "carrusel",
    }


def build_propuesta_json(alternativas: list, slot: dict) -> dict:
    angulo = slot.get("angulo_estrategico", "")
    prop = {
        "etapa": "propuesta",
        "alternativas": alternativas,
        "angulo_estrategico": angulo,
        "slot_resumen": {
            "fecha": slot.get("fecha") or slot.get("date"),
            "tipo": slot.get("tipo") or slot.get("type"),
            "tematica": slot.get("tematica") or slot.get("topic"),
            "enfoque": slot.get("enfoque"),
            "angulo_estrategico": angulo,
        },
    }
    if (slot.get("tipo") or slot.get("type") or "").lower() == "carrusel":
        modo = _modo_referente_carrusel(alternativas)
        if modo:
            prop["modo_referente"] = modo
    return prop


def ensure_week_propuestas(cliente_id: str, week_start: str, week_end: str) -> dict:
    """Genera propuestas faltantes para la semana (sin borrar copy ni plan mensual).

    Se invoca al cargar Contenido cuando hay piezas planificado sin alternativas
    y el cliente ya tiene estudio de mercado.
    """
    from core.client_store import load_latest_market_research
    from core.db import (
        get_publicaciones, update_publicacion_field, update_publicacion_status, init_db,
    )

    init_db(cliente_id)
    market = load_latest_market_research(cliente_id) or {}
    posts = market.get("posts") or market.get("top_posts") or []
    if not posts:
        return {"ok": False, "reason": "sin_estudio_mercado", "generated": 0}

    all_week_pubs = get_week_publicaciones(get_publicaciones, cliente_id, week_start, week_end)
    pending = []
    for pub in all_week_pubs:
        status = pub.get("status") or "planificado"
        prop = _parse_propuesta(pub)
        if status == "planificado":
            if prop.get("warning") == "sin_referentes" and (pub.get("tipo") or "").lower() != "carrusel":
                continue
            pending.append(pub)
            continue
        if status == "propuesta_generada":
            if not (prop.get("alternativas") or []):
                pending.append(pub)
            elif _propuesta_carrusel_necesita_regenerar(pub, market):
                pending.append(pub)

    if not pending:
        return {"ok": True, "generated": 0, "skipped": 0}

    used_urls = collect_used_referente_urls(all_week_pubs)
    used_angulos = collect_used_historia_angulos(all_week_pubs)
    assignments = assign_propuestas_rotating(
        pending, market, exclude_urls=used_urls, exclude_angulos=used_angulos,
    )

    generated = 0
    sin_ref = 0
    for pub in pending:
        alternativas = assignments.get(pub["id"]) or []
        slot = pub_to_slot(pub)
        prop_prev = _parse_propuesta(pub)

        if not alternativas:
            propuesta_vacia = build_propuesta_json([], slot)
            propuesta_vacia["warning"] = "sin_referentes"
            if prop_prev.get("fuente"):
                propuesta_vacia["fuente"] = prop_prev["fuente"]
            update_publicacion_field(cliente_id, pub["id"], "propuesta_json", propuesta_vacia)
            update_publicacion_status(cliente_id, pub["id"], "planificado")
            sin_ref += 1
            continue

        propuesta = build_propuesta_json(alternativas, slot)
        if prop_prev.get("fuente"):
            propuesta["fuente"] = prop_prev["fuente"]
        update_publicacion_field(cliente_id, pub["id"], "propuesta_json", propuesta)
        update_publicacion_status(cliente_id, pub["id"], "propuesta_generada")
        generated += 1

    return {
        "ok": True,
        "generated": generated,
        "sin_referentes": sin_ref,
        "pending": len(pending),
    }


def refresh_pending_propuestas(cliente_id: str, week_start: str, week_end: str,
                               market_data: dict, skip_pub_id: str = None,
                               tipo: str = None) -> list:
    """
    Recalcula alternativas de piezas en propuesta_generada, excluyendo referentes ya elegidos.
    """
    from core.db import get_publicaciones, update_publicacion_field

    all_pubs = get_week_publicaciones(get_publicaciones, cliente_id, week_start, week_end)
    pending = [
        p for p in all_pubs
        if p.get("status") == "propuesta_generada" and p.get("id") != skip_pub_id
    ]
    if tipo:
        tipo_l = tipo.lower()
        pending = [p for p in pending if (p.get("tipo") or "").lower() == tipo_l]
    if not pending:
        return []

    used = collect_used_referente_urls(all_pubs)
    used_angulos = collect_used_historia_angulos(all_pubs)
    assignments = assign_propuestas_rotating(
        pending, market_data, exclude_urls=used, exclude_angulos=used_angulos,
    )

    refreshed = []
    for pub in pending:
        pub_id = pub["id"]
        alts = assignments.get(pub_id) or []
        if not alts:
            continue
        slot = pub_to_slot(pub)
        update_publicacion_field(
            cliente_id, pub_id, "propuesta_json", build_propuesta_json(alts, slot),
        )
        refreshed.append({
            "pub_id": pub_id,
            "fecha": pub.get("fecha"),
            "tematica": pub.get("tematica"),
            "alternativas": alts,
        })
    return refreshed
