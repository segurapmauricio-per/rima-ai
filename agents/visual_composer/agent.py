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
from typing import Any, Optional

from core.db import get_imagenes_para
from core.visual_spec import spec_a_prompt, spec_desde_slide

# Umbral mínimo para aceptar una imagen del cliente como match.
# Equivale a 1 tag coincidente (peso 3) o 3 palabras de descripción/vibe.
MIN_MATCH_SCORE = 3.0

RATIO_POR_TIPO = {"historia": "9:16", "carrusel": "1:1"}

# Pesos del scoring
PESO_TAG = 3.0
PESO_TEXTO = 1.0
BONUS_CALIDAD_ALTA = 1.0

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
    partes = [
        slide.get("main_text", ""),
        slide.get("secondary_text", ""),
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
    """Paleta de marca derivada de los dominant_colors de las imágenes de
    branding del cliente. Determinístico: orden de aparición, sin duplicados."""
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
                "main_text": s.get("main_text", ""),
                "secondary_text": s.get("secondary_text", ""),
                "visual_suggestion": s.get("visual_suggestion", ""),
                "notes": s.get("notes", ""),
            })
        return slides

    if tipo == "historia":
        elegido = copy_json.get("copy_elegido") or {}
        if not elegido:
            propuestas = copy_json.get("propuestas_copy") or []
            elegido = propuestas[0] if propuestas else {}
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
        imagenes = get_imagenes_para(cliente_id, tipo) or []
    except Exception:
        imagenes = []
    paleta_marca = _paleta_marca(cliente_id)

    # Score de todos los pares (slide, imagen) que superan el umbral.
    pares = []
    tokens_por_slide = [_tokens_slide(s) for s in slides]
    for idx, tokens in enumerate(tokens_por_slide):
        for img in imagenes:
            score = _score_imagen(tokens, img)
            if score >= MIN_MATCH_SCORE:
                pares.append((score, idx, img))
    pares.sort(key=lambda p: p[0], reverse=True)

    asignacion: dict = {}
    usadas: set = set()
    for score, idx, img in pares:
        if idx in asignacion or img.get("id") in usadas:
            continue
        asignacion[idx] = (img, score)
        usadas.add(img.get("id"))

    resultado = []
    for idx, slide in enumerate(slides):
        compuesto = dict(slide)
        if idx in asignacion:
            img, score = asignacion[idx]
            analisis = img.get("analisis_json") or {}
            compuesto.update({
                "image_source": "cliente",
                "image_id": img.get("id"),
                "archivo_url": img.get("archivo_url"),
                "text_zone": _text_zone(analisis),
                "match_score": round(score, 1),
            })
        else:
            spec = spec_desde_slide(slide, tipo, slot_context, paleta_marca)
            compuesto.update({
                "image_source": "kie_pending",
                "spec_visual": spec,
                "prompt_sugerido": spec_a_prompt(spec),
                "ratio": spec["ratio"],
            })
        resultado.append(compuesto)
    return resultado
