"""
Visual Composer Agent — Sprint B Fase 2.

Compone los slides visuales de carruseles e historias a partir del copy ya
aprobado y de las imágenes analizadas del cliente (tabla `imagenes`).

100% determinístico: CERO llamadas a Gemini/LLM. El matching es scoring por
solapamiento de keywords entre el texto del slide y los metadatos de la imagen
(tags, descripción, vibe, categoría sugerida). Si ninguna imagen supera el
umbral, el slide queda con image_source="kie_pending" y un prompt_sugerido
construido por template a partir de visual_suggestion/image_vibe_needed.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Optional

from core.db import get_imagenes_para
from core.visual_spec import spec_a_prompt, spec_desde_slide

# Umbral mínimo para aceptar una imagen del cliente como match.
MIN_MATCH_SCORE = 3.0
MIN_MATCH_SCORE_CARRUSEL = 2.0

RATIO_POR_TIPO = {"historia": "9:16", "carrusel": "1:1"}

# Pesos del scoring
PESO_TAG = 3.0
PESO_TEXTO = 1.0
BONUS_CALIDAD_ALTA = 1.0

# Tokens para priorizar tipo de imagen según rol del slide (carrusel IG)
IMPACTO_TOKENS = {
    "persona", "retrato", "rostro", "humano", "mirada", "expresion",
    "portrait", "cara", "selfie", "coach", "entrenador",
}
BRANDING_TOKENS = {
    "logo", "marca", "color", "abstract", "minimal", "grafico",
    "tipografia", "fondo", "plano", "simple", "infografia", "icono",
}

STOPWORDS_ES = {
    "para", "con", "una", "uno", "unos", "unas", "del", "las", "los", "que",
    "por", "sin", "sobre", "entre", "como", "más", "mas", "pero", "este",
    "esta", "estos", "estas", "ese", "esa", "esos", "esas", "muy", "donde",
    "cuando", "hacia", "desde", "hasta", "ante", "tras", "vos", "ella",
    "ellos", "ellas", "nosotros", "ustedes", "tiene", "tienen", "hay",
    "ser", "estar", "hace", "hacen", "tipo", "imagen", "foto", "fondo",
}


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos, para comparar tokens de forma estable."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()


def _tokens(texto: str) -> set:
    """Palabras significativas (>= 4 letras, sin stopwords) de un texto."""
    palabras = re.findall(r"[a-záéíóúñü]+", _normalizar(texto))
    return {p for p in palabras if len(p) >= 4 and p not in STOPWORDS_ES}


def _tokens_slide(slide: dict) -> set:
    bullets = " ".join(str(b) for b in (slide.get("bullets") or []))
    partes = [
        slide.get("main_text", ""),
        slide.get("secondary_text", ""),
        bullets,
        slide.get("visual_suggestion", ""),
        slide.get("notes", ""),
    ]
    return _tokens(" ".join(p for p in partes if p))


def _score_imagen(tokens_slide: set, imagen: dict) -> float:
    """Solapamiento determinístico slide↔imagen. Tags pesan más que texto."""
    analisis = imagen.get("analisis_json") or {}
    tags = imagen.get("tags_json") or analisis.get("tags") or []
    tokens_tags = _tokens(" ".join(str(t) for t in tags))
    tokens_texto = _tokens(" ".join([
        analisis.get("description", ""),
        analisis.get("vibe", ""),
        analisis.get("suggested_category", ""),
    ]))
    score = (len(tokens_slide & tokens_tags) * PESO_TAG
             + len(tokens_slide & (tokens_texto - tokens_tags)) * PESO_TEXTO)
    if score > 0 and analisis.get("production_quality") == "alta":
        score += BONUS_CALIDAD_ALTA
    return score


def _es_imagen_ia_biblioteca(img: dict) -> bool:
    tags = img.get("tags_json") or []
    if "generada_ia" in tags:
        return True
    analisis = img.get("analisis_json") or {}
    return analisis.get("origen_biblioteca") == "generada_ia"


def _imagenes_pool(cliente_id: str, tipo: str) -> list:
    """Pool de imágenes analizadas. Carrusel incluye branding e historias."""
    if tipo == "historia":
        vistos: dict = {}
        for uso in ("historia", "branding"):
            for img in get_imagenes_para(cliente_id, uso) or []:
                if _es_imagen_ia_biblioteca(img):
                    continue
                iid = img.get("id")
                if iid and iid not in vistos:
                    vistos[iid] = img
        return list(vistos.values())
    if tipo != "carrusel":
        return get_imagenes_para(cliente_id, tipo) or []
    vistos: dict = {}
    for uso in ("carrusel", "branding", "historia"):
        for img in get_imagenes_para(cliente_id, uso) or []:
            iid = img.get("id")
            if iid and iid not in vistos:
                vistos[iid] = img
    return list(vistos.values())


def _es_impacto(analisis: dict) -> bool:
    desc = _normalizar(analisis.get("description", ""))
    cat = _normalizar(analisis.get("suggested_category", ""))
    tokens = _tokens(desc)
    return bool(tokens & IMPACTO_TOKENS) or any(
        k in cat for k in ("persona", "retrato", "portada", "gancho", "thumbnail")
    )


def _es_branding(analisis: dict) -> bool:
    cat = _normalizar(analisis.get("suggested_category", ""))
    tokens = _tokens(analisis.get("description", ""))
    return "branding" in cat or bool(tokens & BRANDING_TOKENS)


def _bonus_por_rol(role: str, idx: int, total: int, analisis: dict) -> float:
    """Bonus según estructura típica de carrusel IG: portada, slide 2, medio, CTA."""
    calidad = analisis.get("production_quality", "media")
    bonus = 0.0
    impacto = _es_impacto(analisis)
    branding = _es_branding(analisis)
    ultimo = idx == total - 1

    if role == "gancho" or idx == 0:
        if impacto:
            bonus += 3.0
        if calidad == "alta":
            bonus += 2.0
    elif idx == 1 and total > 2:
        if impacto:
            bonus += 2.5
        if calidad == "alta":
            bonus += 1.5
    elif role == "cierre" or ultimo:
        if impacto:
            bonus += 2.5
        if calidad == "alta":
            bonus += 1.0
    else:
        if branding:
            bonus += 3.0
        elif not impacto and calidad in ("media", "baja"):
            bonus += 0.5
    return bonus


def _score_imagen_carrusel(tokens_slide: set, imagen: dict,
                           role: str, idx: int, total: int) -> float:
    base = _score_imagen(tokens_slide, imagen)
    analisis = imagen.get("analisis_json") or {}
    bonus = _bonus_por_rol(role, idx, total, analisis)
    if base == 0 and bonus > 0:
        base = 0.5
    return base + bonus


def _prioridad_asignacion(idx: int, slide: dict, total: int) -> int:
    role = slide.get("role", "desarrollo")
    if role == "gancho" or idx == 0:
        return 0
    if idx == 1:
        return 1
    if role == "cierre" or idx == total - 1:
        return 2
    return 3 + idx


def _coords_zona(analisis: dict, zona: str) -> Optional[dict]:
    """Coords de la zona por tercios de safe_zone_px (misma lógica que
    image_analysis._calc_text_blocks; Gemini devuelve los bloques sin coords)."""
    safe = analisis.get("safe_zone_px") or {}
    if not all(k in safe for k in ("top_px", "bottom_px", "left_px", "right_px")):
        return None
    tercio = (safe["bottom_px"] - safe["top_px"]) // 3
    offsets = {"upper_third": 0, "center": 1, "lower_third": 2}
    if zona not in offsets:
        return None
    y1 = safe["top_px"] + offsets[zona] * tercio
    y2 = safe["bottom_px"] if zona == "lower_third" else y1 + tercio
    return {"x1": safe["left_px"], "y1": y1, "x2": safe["right_px"], "y2": y2}


def _text_zone(analisis: dict) -> dict:
    """Zona de texto recomendada. best_text_zone null → 'center' (no fallar)."""
    zona = (analisis.get("best_text_zone")
            or analisis.get("gesture_text_zone")
            or "center")
    for bloque in analisis.get("text_blocks") or []:
        if bloque.get("zone") == zona:
            return {
                "zone": zona,
                "coords": bloque.get("coords") or _coords_zona(analisis, zona),
                "recommended_text_color": bloque.get("recommended_text_color", "#FFFFFF"),
            }
    return {"zone": zona, "coords": _coords_zona(analisis, zona),
            "recommended_text_color": "#FFFFFF"}


def _paleta_marca(cliente_id: str, max_colores: int = 5) -> list:
    """Paleta de marca: marca_visual_json → imágenes branding → vacío."""
    try:
        from core.marca_visual import paleta_colores
        from core.db import get_marca_visual
        mv = get_marca_visual(cliente_id)
        paleta = paleta_colores(mv, max_colores)
        if paleta:
            return paleta
    except Exception:
        pass
    try:
        imagenes = get_imagenes_para(cliente_id, "branding") or []
    except Exception:
        return []
    paleta = []
    for img in imagenes:
        analisis = img.get("analisis_json") or {}
        for color in analisis.get("dominant_colors") or []:
            if color not in paleta:
                paleta.append(color)
            if len(paleta) >= max_colores:
                return paleta
    return paleta


def plan_slides(copy_json: dict, tipo: str,
                slot_context: Optional[dict] = None) -> list:
    """Plan de slides desde el copy aprobado. Determinístico, sin LLM.

    Carrusel: passthrough de copy_json["slides"] (ya vienen completos del
    Sprint Copy E2E) — no se regenera nada.
    Historia: 3 slides derivados de copy_elegido:
    gancho (hook_text) → desarrollo (body_texts) → cierre (cta_text+keyword).
    """
    copy_json = copy_json or {}
    slot_context = slot_context or {}

    if tipo == "carrusel":
        slides = []
        for i, s in enumerate(copy_json.get("slides") or [], start=1):
            slides.append({
                "slide_number": s.get("slide_number", i),
                "role": s.get("role", "desarrollo"),
                "content_type": s.get("content_type", ""),
                "main_text": s.get("main_text", ""),
                "secondary_text": s.get("secondary_text", ""),
                "bullets": list(s.get("bullets") or []),
                "visual_suggestion": s.get("visual_suggestion", ""),
                "notes": s.get("notes", ""),
            })
        return slides

    if tipo == "historia":
        raw_slides = copy_json.get("slides") or []
        if not raw_slides:
            elegido = copy_json.get("copy_elegido") or {}
            if not elegido:
                propuestas = copy_json.get("propuestas_copy") or []
                elegido = propuestas[0] if propuestas else {}
            raw_slides = elegido.get("slides") or []
        if raw_slides:
            slides = []
            keyword = (copy_json.get("cta_keyword") or copy_json.get("keyword") or "").strip()
            for i, s in enumerate(raw_slides, start=1):
                slide = {
                    "slide_number": s.get("slide_number", i),
                    "role": s.get("role", "desarrollo"),
                    "main_text": s.get("main_text", ""),
                    "secondary_text": s.get("secondary_text", ""),
                    "visual_suggestion": s.get("visual_suggestion", ""),
                    "sticker_type": s.get("sticker_type", ""),
                    "notes": s.get("notes", ""),
                    "highlight_words": list(s.get("highlight_words") or []),
                }
                if slide["role"] == "cierre" and keyword:
                    slide["keyword"] = keyword
                slides.append(slide)
            return slides
        elegido = copy_json.get("copy_elegido") or {}
        vibe = elegido.get("image_vibe_needed", "")
        slides = []
        if elegido.get("hook_text"):
            slides.append({
                "slide_number": len(slides) + 1,
                "role": "gancho",
                "main_text": elegido["hook_text"],
                "secondary_text": "",
                "visual_suggestion": vibe,
                "notes": "",
            })
        body = [b for b in (elegido.get("body_texts") or []) if b]
        if body:
            slides.append({
                "slide_number": len(slides) + 1,
                "role": "desarrollo",
                "main_text": "\n".join(body),
                "secondary_text": "",
                "visual_suggestion": vibe,
                "notes": "",
            })
        cta = (elegido.get("cta_text") or "").strip()
        keyword = (elegido.get("keyword") or "").strip()
        if cta or keyword:
            slides.append({
                "slide_number": len(slides) + 1,
                "role": "cierre",
                "main_text": cta,
                "secondary_text": f"Comentá: {keyword}" if keyword else "",
                "visual_suggestion": vibe,
                "notes": "",
            })
        return slides

    return []


def match_images_to_slides(cliente_id: str, tipo: str, slides: list,
                           slot_context: Optional[dict] = None) -> list:
    """Asigna imágenes analizadas del cliente a cada slide.

    Greedy global por score descendente, sin reusar imágenes. Slide sin
    candidata sobre el umbral → image_source="kie_pending" con spec_visual
    (esquema común de core/visual_spec) y prompt_sugerido derivado de ella.
    """
    try:
        imagenes = _imagenes_pool(cliente_id, tipo)
    except Exception:
        imagenes = []
    paleta_marca = _paleta_marca(cliente_id)
    min_score = MIN_MATCH_SCORE_CARRUSEL if tipo == "carrusel" else MIN_MATCH_SCORE
    total = len(slides)
    tokens_por_slide = [_tokens_slide(s) for s in slides]

    # Matriz de scores slide↔imagen sobre el umbral.
    scores_por_slide: dict[int, list] = {i: [] for i in range(total)}
    for idx, slide in enumerate(slides):
        role = slide.get("role", "desarrollo")
        tokens = tokens_por_slide[idx]
        for img in imagenes:
            if tipo == "carrusel":
                score = _score_imagen_carrusel(tokens, img, role, idx, total)
            else:
                score = _score_imagen(tokens, img)
            if score >= min_score:
                scores_por_slide[idx].append((score, img))

    asignacion: dict = {}
    usadas: set = set()

    if tipo == "carrusel":
        orden = sorted(range(total),
                       key=lambda i: _prioridad_asignacion(i, slides[i], total))
        for idx in orden:
            candidatas = sorted(scores_por_slide[idx], key=lambda p: p[0], reverse=True)
            for score, img in candidatas:
                iid = img.get("id")
                if iid in usadas:
                    continue
                asignacion[idx] = (img, score)
                usadas.add(iid)
                break
    else:
        pares = []
        for idx, candidatas in scores_por_slide.items():
            for score, img in candidatas:
                pares.append((score, idx, img))
        pares.sort(key=lambda p: p[0], reverse=True)
        for score, idx, img in pares:
            if idx in asignacion or img.get("id") in usadas:
                continue
            asignacion[idx] = (img, score)
            usadas.add(img.get("id"))

    resultado = []
    for idx, slide in enumerate(slides):
        compuesto = dict(slide)
        spec = spec_desde_slide(slide, tipo, slot_context, paleta_marca)
        prompt = spec_a_prompt(spec)
        if idx in asignacion:
            img, score = asignacion[idx]
            analisis = img.get("analisis_json") or {}
            compuesto.update({
                "image_source": "cliente",
                "image_id": img.get("id"),
                "archivo_url": img.get("archivo_url"),
                "text_zone": _text_zone(analisis),
                "match_score": round(score, 1),
                "spec_visual": spec,
                "prompt_sugerido": prompt,
            })
        else:
            compuesto.update({
                "image_source": "kie_pending",
                "spec_visual": spec,
                "prompt_sugerido": prompt,
                "ratio": spec["ratio"],
            })
        resultado.append(compuesto)
    return resultado


def slides_kie_integrado(slides: list, tipo: str,
                         slot_context: Optional[dict] = None,
                         paleta_marca: Optional[list] = None) -> list:
    """Carrusel con texto integrado (KIE): sin matching de biblioteca.

    Cada slide queda kie_pending con prompt integrado — imágenes nuevas por carrusel.
    La biblioteca sigue disponible solo si el usuario elige manualmente una foto.
    """
    slot_context = slot_context or {}
    paleta_marca = paleta_marca or []
    resultado = []
    for slide in slides:
        compuesto = dict(slide)
        spec = spec_desde_slide(slide, tipo, slot_context, paleta_marca)
        compuesto.update({
            "image_source": "kie_pending",
            "spec_visual": spec,
            "prompt_sugerido": spec_a_prompt(spec),
            "ratio": spec.get("ratio") or RATIO_POR_TIPO.get(tipo, "1:1"),
            "texto_en_imagen": True,
        })
        compuesto.pop("image_id", None)
        compuesto.pop("archivo_url", None)
        compuesto.pop("match_score", None)
        resultado.append(compuesto)
    return resultado


def compose_produccion(cliente_id: str, copy_json: dict, tipo: str,
                       slot_context: Optional[dict] = None,
                       modo: str = "produccion",
                       modo_composicion: str = "texto_integrado") -> dict:
    """Plan de slides + matching de biblioteca. modo=previsual tras generar copy.

    modo_composicion (solo aplica a tipo="carrusel"):
    - "texto_integrado" (default, comportamiento histórico): KIE genera cada
      slide con el texto ya incrustado en la imagen.
    - "fondo_limpio" (opt-in, no activado por defecto en ningún flujo todavía):
      KIE genera solo el fondo, sin texto, y la composición final (texto,
      scrim, resaltado) la hace Claude + Playwright vía
      core/claude_slide_renderer — ver docs/protocolo-generacion-imagenes-ia.md
      del proyecto Rima IA para el porqué. Requiere ANTHROPIC_API_KEY y
      Playwright con Chromium instalado en el servidor; no probado todavía
      contra la base de datos real, solo de forma aislada.
    """
    slot_context = slot_context or {}
    slides = plan_slides(copy_json, tipo, slot_context)
    if not slides:
        return {}
    if tipo == "carrusel" and modo_composicion == "fondo_limpio":
        matched = match_images_to_slides(cliente_id, tipo, slides, slot_context)
    elif tipo == "carrusel":
        paleta = _paleta_marca(cliente_id)
        matched = slides_kie_integrado(slides, tipo, slot_context, paleta)
    else:
        matched = match_images_to_slides(cliente_id, tipo, slides, slot_context)
    if tipo == "carrusel" and modo_composicion == "fondo_limpio":
        from agents.carousel_generator.agent import build_style_guide
        from core.db import get_marca_visual
        try:
            from core.marca_visual import normalizar_marca
            marca = normalizar_marca(get_marca_visual(cliente_id))
        except Exception:
            marca = {}
        style_guide = build_style_guide(marca, {}, copy_json)
        return {
            "etapa": "previsual" if modo == "previsual" else "produccion",
            "tipo": "visual",
            "modo": modo,
            "modo_visual": "fondo_limpio",
            "style_guide": style_guide,
            "slides": matched,
            "generated_at": datetime.now().isoformat(),
        }
    if tipo == "carrusel":
        from agents.carousel_generator.agent import (
            attach_carousel_plan,
            build_style_guide,
            refresh_kie_prompts,
        )
        from core.db import get_marca_visual
        try:
            from core.marca_visual import normalizar_marca
            marca = normalizar_marca(get_marca_visual(cliente_id))
        except Exception:
            marca = {}
        style_guide = build_style_guide(marca, {}, copy_json)
        matched = refresh_kie_prompts(matched, style_guide, slot_context)
        pub_stub = {
            "tematica": slot_context.get("tematica", ""),
            "enfoque": slot_context.get("enfoque", ""),
            "fecha": slot_context.get("fecha", ""),
        }
        plan_data = attach_carousel_plan(
            pub_stub, copy_json, style_guide, matched,
        )
        return {
            "etapa": "previsual" if modo == "previsual" else "produccion",
            "tipo": "visual",
            "modo": modo,
            "modo_visual": "texto_integrado",
            "style_guide": style_guide,
            "kie_model": plan_data["carousel_plan"].get("modelo_kie"),
            "carousel_plan": plan_data["carousel_plan"],
            "slides": matched,
            "generated_at": datetime.now().isoformat(),
        }
    if tipo == "historia":
        from agents.story_generator.agent import build_style_guide, refresh_kie_prompts
        from core.story_plan import build_story_plan
        from core.db import get_marca_visual
        from core import kie_client
        try:
            from core.marca_visual import normalizar_marca
            marca = normalizar_marca(get_marca_visual(cliente_id))
        except Exception:
            marca = {}
        style_guide = build_style_guide(marca, {}, copy_json)
        matched = refresh_kie_prompts(matched, style_guide, slot_context)
        pub_stub = {
            "tematica": slot_context.get("tematica", ""),
            "enfoque": slot_context.get("enfoque", ""),
            "fecha": slot_context.get("fecha", ""),
        }
        story_plan = build_story_plan(
            pub_stub, copy_json, style_guide, matched,
            modelo_kie=kie_client.model_imagen(),
        )
        return {
            "etapa": "previsual" if modo == "previsual" else "produccion",
            "tipo": "visual",
            "modo": modo,
            "modo_visual": "fondo_limpio",
            "style_guide": style_guide,
            "kie_model": story_plan.get("modelo_kie"),
            "story_plan": story_plan,
            "slides": matched,
            "generated_at": datetime.now().isoformat(),
        }
    return {
        "etapa": "previsual" if modo == "previsual" else "produccion",
        "tipo": "visual",
        "modo": modo,
        "modo_visual": "fondo_limpio",
        "slides": matched,
        "generated_at": datetime.now().isoformat(),
    }
