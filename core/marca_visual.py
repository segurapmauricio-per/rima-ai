"""
Identidad visual del cliente — paleta, tipografías, estilo de imagen.

Se persiste en clientes.marca_visual_json (SQLite por cliente).
Origen típico: onboarding (scrape IG del cliente) o carga manual desde /marca.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

MARCA_VISUAL_VACIA = {
    "origen": None,
    "ig_username": "",
    "updated_at": None,
    "comunicacion": {
        "tono": "",
        "muletillas": [],
        "estilo_copy": "",
        "palabras_frecuentes": [],
    },
    "visual": {
        "paleta_colores": [],
        "colores_primarios": [],
        "colores_secundarios": [],
        "tipografias": [],
        "tipografia_estilo": "",
        "estilo_imagen": "",
        "estilo_fotografico": "",
        "imagen_personaje_url": "",
        "tipos_toma": [],
        "imagen_marca_url": "",
    },
    "imagen_marca_id": None,
}

# Catálogo de estilos tipográficos elegibles (Google Fonts, ya cargadas por el
# dashboard) — reemplaza la adivinanza de Gemini sobre el scrape de IG por una
# elección real del cliente. id -> (titular, cuerpo, descripción).
TIPOGRAFIA_ESTILOS = {
    "moderno": {
        "nombre": "Moderno & Bold",
        "titular": "Inter", "titular_peso": "800",
        "cuerpo": "Inter", "cuerpo_peso": "400",
        "descripcion": "Limpio, tech, alto contraste.",
    },
    "editorial": {
        "nombre": "Editorial & Premium",
        "titular": "Playfair Display", "titular_peso": "700",
        "cuerpo": "Inter", "cuerpo_peso": "400",
        "descripcion": "Elegante, tipo revista — servicios profesionales.",
    },
    "cercano": {
        "nombre": "Cercano & Humano",
        "titular": "Poppins", "titular_peso": "700",
        "cuerpo": "Nunito Sans", "cuerpo_peso": "400",
        "descripcion": "Redondeado, cálido — coaching, bienestar, lifestyle.",
    },
    "urbano": {
        "nombre": "Directo & Urbano",
        "titular": "Montserrat", "titular_peso": "800",
        "cuerpo": "Roboto", "cuerpo_peso": "400",
        "descripcion": "Geométrico, alto impacto — fitness, ventas agresivas.",
    },
}

# Estilo fotográfico elegible por el cliente (onboarding / /marca).
ESTILO_FOTOGRAFICO_OPCIONES = {
    "modelo_consistente": "Modelo consistente — un mismo personaje ficticio en todas las piezas",
    "paisajes": "Paisajes/lifestyle — sin personas, escenas y objetos",
    "mixto": "Mixto — sin restricción, según lo que pida cada pieza",
}


def tipografias_de_estilo(estilo_id: str) -> list:
    """Resuelve [titular, cuerpo] desde el catálogo fijo — determinístico, sin LLM."""
    estilo = TIPOGRAFIA_ESTILOS.get(estilo_id)
    if not estilo:
        return []
    return [
        f"{estilo['titular']} {estilo['titular_peso']}",
        f"{estilo['cuerpo']} {estilo['cuerpo_peso']}",
    ]


def normalizar_marca(marca: Optional[dict]) -> dict:
    base = {k: (v.copy() if isinstance(v, dict) else v)
            for k, v in MARCA_VISUAL_VACIA.items()}
    if not marca:
        return base
    for key, val in marca.items():
        if key in ("comunicacion", "visual") and isinstance(val, dict):
            base[key].update(val)
        else:
            base[key] = val
    return base


def paleta_colores(marca: dict, max_colores: int = 5) -> list:
    """Paleta unificada: primarios + secundarios + paleta general."""
    marca = normalizar_marca(marca)
    visual = marca.get("visual") or {}
    paleta = []
    for fuente in ("paleta_colores", "colores_primarios", "colores_secundarios"):
        for color in visual.get(fuente) or []:
            if color and color not in paleta:
                paleta.append(color)
            if len(paleta) >= max_colores:
                return paleta
    return paleta


def merge_from_brand(marca: dict, brand: dict) -> dict:
    """Enriquece marca_visual con campos del brief de /api/brand."""
    marca = normalizar_marca(marca)
    ig = (brand.get("brand_ig") or brand.get("ig_username") or "").strip().lstrip("@")
    if ig:
        marca["ig_username"] = ig
    tono = brand.get("brand_tone") or brand.get("tone") or ""
    if tono:
        marca["comunicacion"]["tono"] = tono
    estilo = brand.get("brand_visual_style") or brand.get("visual_style") or ""
    if estilo:
        marca["visual"]["estilo_imagen"] = estilo
    colores = brand.get("brand_colors") or brand.get("colores_marca")
    if isinstance(colores, str):
        colores = [c.strip() for c in colores.replace(";", ",").split(",") if c.strip()]
    if isinstance(colores, list) and colores:
        marca["visual"]["paleta_colores"] = colores[:8]
        marca["visual"]["colores_primarios"] = colores[:3]
        if len(colores) > 3:
            marca["visual"]["colores_secundarios"] = colores[3:8]
    marca["updated_at"] = datetime.now().isoformat()
    if not marca.get("origen"):
        marca["origen"] = "manual"
    return marca


def build_from_ig_scrape(profile_meta: dict, brand_brief: Optional[dict] = None,
                         posts_sample: Optional[list] = None) -> dict:
    """Construye marca_visual desde meta de IG (onboarding / market research).

    Determinístico: sin LLM. Los colores finos requieren análisis de imagen
    (imagen_marca_url → image_analysis) en un paso posterior.
    """
    marca = normalizar_marca({})
    meta = profile_meta or {}
    user = (meta.get("username") or meta.get("ig_username") or "").strip().lstrip("@")
    if user:
        marca["ig_username"] = user
    bio = (meta.get("biography") or "").strip()
    cat = (meta.get("business_category") or meta.get("businessCategoryName") or "").strip()
    pic = meta.get("profile_pic_url") or meta.get("profilePicUrlHD") or ""

    if bio:
        marca["comunicacion"]["estilo_copy"] = bio.splitlines()[0][:200]
    if cat:
        marca["visual"]["estilo_imagen"] = cat

    if pic:
        marca["visual"]["imagen_marca_url"] = pic

    if brand_brief:
        marca = merge_from_brand(marca, brand_brief)

    posts_sample = posts_sample or []
    captions = " ".join((p.get("caption") or "")[:300] for p in posts_sample[:12])
    if captions:
        marca["comunicacion"]["palabras_frecuentes"] = _palabras_frecuentes(captions, n=12)

    marca["origen"] = "onboarding_ig"
    marca["updated_at"] = datetime.now().isoformat()
    return marca


def sync_from_market_research(cliente_id: str, market_result: dict,
                              brand_brief: Optional[dict] = None) -> dict:
    """Actualiza marca_visual si el scrape incluyó el IG del cliente."""
    from core.db import get_marca_visual, set_marca_visual

    brief = brand_brief or {}
    ig = (brief.get("ig_username") or brief.get("brand_ig") or "").strip().lstrip("@").lower()
    if not ig:
        return get_marca_visual(cliente_id)

    meta_by = market_result.get("profile_meta") or {}
    meta = meta_by.get(ig) or meta_by.get(ig.lstrip("@"))
    posts = [
        p for p in (market_result.get("posts") or [])
        if (p.get("owner") or "").strip().lstrip("@").lower() == ig
    ]
    if not meta and not posts:
        return get_marca_visual(cliente_id)

    nueva = build_from_ig_scrape(meta or {}, brief, posts)
    prev = normalizar_marca(get_marca_visual(cliente_id))
    if prev.get("visual", {}).get("paleta_colores") and not nueva["visual"]["paleta_colores"]:
        nueva["visual"]["paleta_colores"] = prev["visual"]["paleta_colores"]
    if prev.get("imagen_marca_id"):
        nueva["imagen_marca_id"] = prev["imagen_marca_id"]
    set_marca_visual(cliente_id, nueva)
    return nueva


def _palabras_frecuentes(texto: str, n: int = 10) -> list:
    import re
    palabras = re.findall(r"[a-záéíóúñü]{4,}", texto.lower())
    stop = {"para", "como", "esta", "este", "todos", "todas", "más", "mas", "muy",
            "qué", "que", "por", "con", "sin", "son", "sus", "the", "and", "you"}
    freq: dict = {}
    for p in palabras:
        if p in stop:
            continue
        freq[p] = freq.get(p, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:n]]


IDIOMA_LABEL = {
    "es": "español",
    "en": "inglés",
    "pt": "portugués",
    "fr": "francés",
}


def idioma_cliente(brief: Optional[dict] = None, marca: Optional[dict] = None) -> str:
    """Código de idioma del cliente (default español)."""
    brief = brief or {}
    marca = normalizar_marca(marca or {})
    for fuente in (
        brief.get("brand_language"),
        brief.get("idioma"),
        brief.get("language"),
        (marca.get("comunicacion") or {}).get("idioma"),
    ):
        if not fuente:
            continue
        code = str(fuente).strip().lower()[:2]
        if code in IDIOMA_LABEL:
            return code
    return "es"


def idioma_cliente_label(brief: Optional[dict] = None, marca: Optional[dict] = None) -> str:
    return IDIOMA_LABEL.get(idioma_cliente(brief, marca), "español")


def style_hints_from_marca(marca: Optional[dict], brief: Optional[dict] = None) -> dict:
    """Paleta, tipografía y estilo desde onboarding / marca_visual."""
    marca = normalizar_marca(marca or {})
    brief = brief or {}
    visual = marca.get("visual") or {}
    comm = marca.get("comunicacion") or {}
    colores = paleta_colores(marca) or []
    # Elección explícita del cliente (catálogo fijo) tiene prioridad sobre lo
    # adivinado por Gemini del scrape de IG.
    tips_elegidas = tipografias_de_estilo(visual.get("tipografia_estilo") or "")
    tips = tips_elegidas or (visual.get("tipografias") or [])
    tipografia = ", ".join(str(t) for t in tips[:2] if t) if tips else ""
    return {
        "idioma": idioma_cliente(brief, marca),
        "colores": colores[:5],
        "estilo_visual": (
            visual.get("estilo_imagen")
            or brief.get("brand_visual_style")
            or comm.get("estilo_copy")
            or ""
        ),
        "tipografia": tipografia or "sans-serif bold, alto contraste, legible en móvil",
        "tono": comm.get("tono") or brief.get("brand_tone") or "",
        "tipos_toma": visual.get("tipos_toma") or [],
        "origen_marca": marca.get("origen") or "",
        "estilo_fotografico": visual.get("estilo_fotografico") or "mixto",
        "imagen_personaje_url": visual.get("imagen_personaje_url") or "",
    }


def contexto_marca_para_copy(marca: Optional[dict], brief: Optional[dict] = None) -> str:
    """Bloque de prompt: identidad visual del onboarding."""
    hints = style_hints_from_marca(marca, brief)
    ef_activo = hints.get("estilo_fotografico") in ("paisajes", "modelo_consistente")
    if not ef_activo and not any(hints.get(k) for k in ("colores", "estilo_visual", "tono", "tipos_toma")):
        return ""
    lineas = ["IDENTIDAD VISUAL DEL CLIENTE (onboarding / perfil IG — usar en style_guide y visual_suggestion):"]
    if hints["estilo_visual"]:
        lineas.append(f"- Estilo visual: {hints['estilo_visual']}")
    if hints["colores"]:
        lineas.append(f"- Paleta de marca: {', '.join(hints['colores'])}")
    if hints["tipografia"]:
        lineas.append(f"- Tipografía de marca: {hints['tipografia']}")
    if hints["tono"]:
        lineas.append(f"- Tono de comunicación: {hints['tono']}")
    if hints["tipos_toma"]:
        lineas.append(f"- Tipos de toma habituales: {', '.join(hints['tipos_toma'][:4])}")
    ef = hints.get("estilo_fotografico")
    if ef == "paisajes":
        lineas.append(
            "- Estilo fotográfico elegido: PAISAJES/LIFESTYLE — evitar rostros y "
            "personas, priorizar escenas, objetos y texturas con una frase o "
            "pensamiento como elemento central de texto."
        )
    elif ef == "modelo_consistente":
        lineas.append(
            "- Estilo fotográfico elegido: MODELO CONSISTENTE — mantener el mismo "
            "personaje/rostro en todas las piezas generadas (usar imagen de "
            "referencia si está disponible)."
        )
    if hints["origen_marca"]:
        lineas.append(f"- Origen datos: {hints['origen_marca']}")
    return "\n".join(lineas)


def merge_style_guide_from_marca(style_guide: dict, marca: Optional[dict],
                                 brief: Optional[dict] = None) -> dict:
    """Completa style_guide del LLM con datos de marca_visual (onboarding)."""
    hints = style_hints_from_marca(marca, brief)
    sg = dict(style_guide or {})
    if hints["colores"] and not sg.get("colores"):
        sg["colores"] = hints["colores"]
    elif hints["colores"]:
        merged = list(sg.get("colores") or [])
        for c in hints["colores"]:
            if c not in merged:
                merged.append(c)
        sg["colores"] = merged[:5]
    if hints["estilo_visual"] and not sg.get("estilo_visual"):
        sg["estilo_visual"] = hints["estilo_visual"]
    if hints["tipografia"] and sg.get("tipografia", "").startswith("sans-serif bold"):
        sg["tipografia"] = hints["tipografia"]
    sg["idioma"] = hints["idioma"]
    if hints["tono"]:
        sg["tono_marca"] = hints["tono"]
    return sg
