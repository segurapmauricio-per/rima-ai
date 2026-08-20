"""
Spec Visual JSON — esquema unificado de piezas visuales (Sprint KIE, Fase 2.1).

Un mismo esquema describe "qué hay / qué debería haber" en una pieza visual:
- origen="analisis": construido desde analisis_json de una imagen real
  (agents/image_analysis).
- origen="generacion": construido desde el copy de un slide para generar la
  imagen con KIE AI (agents/visual_composer → core/kie_client).

Todo determinístico, sin LLM. Campos de video (duracion_seg, escenas) quedan
reservados: la generación de video (Veo3.1) está pendiente de implementación.
"""
from __future__ import annotations

from typing import Any, Optional

TIPOS_PIEZA = {"imagen", "video"}
ORIGENES = {"analisis", "generacion"}
ZONAS_TEXTO = {"upper_third", "center", "lower_third"}

RATIO_A_FORMATO = {"1:1": "1080x1080", "9:16": "1080x1920", "16:9": "1920x1080"}
ZONA_LABEL = {"upper_third": "tercio superior", "center": "centro",
              "lower_third": "tercio inferior"}

ROLE_VISUAL_HINTS = {
    "gancho": (
        "Slide de apertura (gancho): imagen de alto impacto que detenga el scroll, "
        "rostro expresivo o escena contundente, contraste fuerte, energía de apertura"
    ),
    "desarrollo": (
        "Slide de desarrollo: imagen de apoyo que refuerce el concepto del texto, "
        "composición clara y profesional, sin elementos que distraigan del mensaje"
    ),
    "cierre": (
        "Slide de cierre/CTA: sensación de resolución e invitación a actuar, "
        "punto focal claro, energía de cierre, espacio generoso para texto superpuesto"
    ),
}

ESTILO_DEFAULT = ("fotografía realista, limpia y profesional, buena "
                  "iluminación natural, composición simple")


def spec_vacia() -> dict:
    return {
        "tipo_pieza": "imagen",
        "origen": "generacion",
        "formato": "1080x1080",
        "ratio": "1:1",
        "descripcion": "",
        "vibe": "",
        "paleta_colores": [],
        "elementos_clave": [],
        "zona_texto": {"zone": "center", "coords": None,
                       "recommended_text_color": "#FFFFFF"},
        "estilo_fotografico": ESTILO_DEFAULT,
        "texto_overlay": "",
        "duracion_seg": None,
        "escenas": None,
    }


def validar_spec(spec: dict) -> list:
    """Lista de errores; [] si la spec es válida."""
    errores = []
    if not isinstance(spec, dict):
        return ["spec debe ser dict"]
    if spec.get("tipo_pieza") not in TIPOS_PIEZA:
        errores.append(f"tipo_pieza inválido: {spec.get('tipo_pieza')!r}")
    if spec.get("origen") not in ORIGENES:
        errores.append(f"origen inválido: {spec.get('origen')!r}")
    if not (spec.get("descripcion") or "").strip():
        errores.append("descripcion vacía")
    zona = (spec.get("zona_texto") or {}).get("zone")
    if zona and zona not in ZONAS_TEXTO:
        errores.append(f"zona_texto.zone inválida: {zona!r}")
    if not isinstance(spec.get("paleta_colores", []), list):
        errores.append("paleta_colores debe ser lista")
    if spec.get("tipo_pieza") == "video" and not spec.get("duracion_seg"):
        errores.append("video requiere duracion_seg")
    return errores


def spec_desde_analisis(analisis: dict, archivo_url: Optional[str] = None) -> dict:
    """Mapea analisis_json (image_analysis/Gemini Vision) al esquema común."""
    analisis = analisis or {}
    spec = spec_vacia()
    dims = analisis.get("dimensions") or {}
    w, h = dims.get("width"), dims.get("height")
    if w and h:
        spec["formato"] = f"{w}x{h}"
        spec["ratio"] = "9:16" if h > w else ("16:9" if w > h else "1:1")
    spec.update({
        "origen": "analisis",
        "descripcion": analisis.get("description", ""),
        "vibe": analisis.get("vibe", ""),
        "paleta_colores": analisis.get("dominant_colors") or [],
        "elementos_clave": analisis.get("tags") or [],
        "estilo_fotografico": (
            f"calidad de producción {analisis.get('production_quality', 'media')}"
            + (", con rostro presente" if analisis.get("is_face_present") else "")
        ),
        "texto_overlay": "",
    })
    zona = (analisis.get("best_text_zone")
            or analisis.get("gesture_text_zone") or "center")
    bloque = next((b for b in analisis.get("text_blocks") or []
                   if b.get("zone") == zona), {})
    spec["zona_texto"] = {
        "zone": zona if zona in ZONAS_TEXTO else "center",
        "coords": bloque.get("coords"),
        "recommended_text_color": bloque.get("recommended_text_color", "#FFFFFF"),
    }
    if archivo_url:
        spec["archivo_url"] = archivo_url
    return spec


def spec_desde_slide(slide: dict, tipo: str,
                     slot_context: Optional[dict] = None,
                     paleta_marca: Optional[list] = None) -> dict:
    """Spec de generación para un slide kie_pending. Determinístico."""
    slot_context = slot_context or {}
    spec = spec_vacia()
    ratio = "9:16" if tipo == "historia" else "1:1"
    role = (slide.get("role") or "desarrollo").lower()
    role_hint = ROLE_VISUAL_HINTS.get(role, ROLE_VISUAL_HINTS["desarrollo"])
    base_desc = (slide.get("visual_suggestion")
                 or slide.get("image_vibe_needed")
                 or slide.get("main_text")
                 or "imagen de marca limpia y profesional").strip()
    descripcion = f"{role_hint}. {base_desc.rstrip('.')}"
    elementos = [v for v in (slot_context.get("tematica"),
                             slot_context.get("enfoque"),
                             role if role != "desarrollo" else None) if v]
    zona = "upper_third" if role == "gancho" else ("lower_third" if role == "cierre" else "center")
    spec.update({
        "origen": "generacion",
        "ratio": ratio,
        "formato": RATIO_A_FORMATO[ratio],
        "descripcion": descripcion,
        "vibe": slot_context.get("vibe", "") or slide.get("visual_suggestion", ""),
        "paleta_colores": list(paleta_marca or []),
        "elementos_clave": elementos,
        "texto_overlay": (slide.get("main_text") or "").strip(),
        "texto_secundario": (slide.get("secondary_text") or "").strip(),
        "texto_bullets": [
            str(b).strip() for b in (slide.get("bullets") or []) if str(b).strip()
        ],
        "zona_texto": {"zone": zona, "coords": None,
                       "recommended_text_color": "#FFFFFF"},
    })
    return spec


ZONA_LABEL_EN = {"upper_third": "upper third", "center": "center",
                 "lower_third": "lower third"}


def spec_a_prompt(spec: dict, estetica: Optional[dict] = None) -> str:
    """Prompt de generación para KIE AI armado por template desde la spec.

    `estetica`: preset de core.marca_visual.estilo_estetico_preset(). Si es
    fotográfico, el prompt sale en inglés con metodología PromptDirector
    (specs de cámara, micro-imperfecciones, negativos, coda fotográfica).
    Sin preset (o preset gráfico) se mantiene el template histórico en español.
    """
    if estetica and estetica.get("tipo") == "fotografico":
        return _spec_a_prompt_fotografico(spec, estetica)
    partes = [
        f"Fotografía para Instagram, formato {spec.get('formato', '1080x1080')}.",
        spec.get("descripcion", "").rstrip(".") + ".",
        (spec.get("estilo_fotografico") or ESTILO_DEFAULT).rstrip(".").capitalize() + ".",
    ]
    if spec.get("vibe"):
        partes.append(f"Transmite un mood {spec['vibe'].rstrip('.')}.")
    if spec.get("elementos_clave"):
        partes.append("Contexto temático: " + ", ".join(spec["elementos_clave"]) + ".")
    if spec.get("paleta_colores"):
        partes.append("Paleta de colores de marca: "
                      + ", ".join(spec["paleta_colores"][:5]) + ".")
    zona = ZONA_LABEL.get((spec.get("zona_texto") or {}).get("zone", "center"),
                          "centro")
    partes.append(f"Dejar el {zona} de la imagen despejado y con fondo uniforme "
                  "para superponer texto.")
    partes.append("Sin texto incrustado, sin logos, sin marcas de agua.")
    return " ".join(p for p in partes if p and p != ".")


def _spec_a_prompt_fotografico(spec: dict, estetica: dict) -> str:
    """Prompt PromptDirector (inglés) para historias con preset fotográfico.

    Estructura: realismo → escena → luz → mood/contexto → paleta →
    imperfecciones → zona de texto despejada (overlay Pillow posterior) →
    negativos → coda fotográfica. La descripción del slide viene en español
    del copy agent: se incluye tal cual como dirección de escena — nano-banana
    la interpreta bien; el vocabulario técnico que sesga el estilo va en inglés.
    """
    desc = (spec.get("descripcion") or "clean professional brand image").rstrip(".")
    partes = [
        estetica.get("realismo", "Real photograph, not a render").rstrip(".") + ".",
        f"Vertical Instagram story frame, {spec.get('formato', '1080x1920')}.",
        f"Scene: {desc}.",
        f"Lit by {estetica.get('luz', 'natural available light')}.",
    ]
    if spec.get("vibe"):
        partes.append(f"Mood: {spec['vibe'].rstrip('.')}.")
    if spec.get("elementos_clave"):
        partes.append("Thematic context: " + ", ".join(spec["elementos_clave"]) + ".")
    if spec.get("paleta_colores"):
        partes.append("Brand color palette guiding wardrobe and props: "
                      + ", ".join(spec["paleta_colores"][:5]) + ".")
    if estetica.get("imperfecciones"):
        partes.append(f"Real-world micro-imperfections: {estetica['imperfecciones']}.")
    partes.append("Subject in sharp focus, background falling into coherent bokeh "
                  "consistent with the stated aperture.")
    zona = ZONA_LABEL_EN.get((spec.get("zona_texto") or {}).get("zone", "center"),
                             "center")
    partes.append(f"Keep the {zona} of the frame clean and uncluttered, with an "
                  "even background, so text can be overlaid there later.")
    if estetica.get("negativos"):
        partes.append(f"Negative: {estetica['negativos']}.")
    partes.append(estetica.get("coda", "Photographic realism, no text") + ".")
    return " ".join(p for p in partes if p and p != ".")


def estetica_fondo_carrusel(estetica: Optional[dict]) -> str:
    """Línea de dirección del FONDO para carruseles con preset fotográfico.

    El carrusel mantiene su lenguaje de diseño con texto horneado; el preset
    solo modula cómo se ve la escena de fondo detrás del layout.
    """
    if not estetica or estetica.get("tipo") != "fotografico":
        return ""
    partes = [
        f"Background scene treatment: {estetica.get('realismo', 'real photograph')}",
        f"lit by {estetica.get('luz', 'natural light')}",
        estetica.get("coda", "photographic realism"),
    ]
    return (". ".join(p.rstrip(".") for p in partes if p)
            + ". The photographic treatment applies ONLY to the background scene; "
              "keep the text layout crisp, flat and legible on top.")


def spec_a_prompt_integrado(spec: dict, style_guide: dict,
                            slide_idx: int = 0, total: int = 7) -> str:
    """Prompt nano-banana-pro: diseño con texto escrito en la imagen (skill /carrusel)."""
    sg = style_guide or {}
    idioma = (sg.get("idioma") or "es").lower()[:2]
    if idioma == "en":
        return _spec_a_prompt_integrado_en(spec, sg, slide_idx, total)
    return _spec_a_prompt_integrado_es(spec, sg, slide_idx, total)


def _spec_a_prompt_integrado_es(spec: dict, sg: dict,
                                slide_idx: int = 0, total: int = 7) -> str:
    main = (spec.get("texto_overlay") or "").strip()
    sec = (spec.get("texto_secundario") or "").strip()
    num = slide_idx + 1
    colores = sg.get("colores") or spec.get("paleta_colores") or []
    colores_txt = ", ".join(colores[:5]) if colores else "rojo, blanco y negro"
    negocio = sg.get("negocio") or ""

    if slide_idx == 0:
        fase = "PORTADA — gancho extremo que detenga el scroll"
    elif slide_idx >= total - 1:
        fase = "CIERRE — call to action claro con palabra clave visible"
    else:
        fase = f"DESARROLLO slide {num} — continúa la narrativa del carrusel"

    partes = [
        f"Slide {num} de {total} de carrusel Instagram, cuadrado 1080x1080, {fase}.",
        f"Estilo visual (coherente en TODAS las slides): {sg.get('estilo_visual', 'diseño gráfico moderno bold')}.",
        f"Formato narrativo: {sg.get('formato_nombre', 'carrusel educativo')}.",
        f"Paleta de colores (estricta, marca del cliente): {colores_txt}.",
        f"Tipografía: {sg.get('tipografia', 'sans-serif bold, alto contraste, legible en móvil')}.",
    ]
    if negocio:
        partes.append(f"Contexto de marca: {negocio}.")
    if main:
        partes.append(
            f'Renderizá este texto principal EXACTO dentro de la imagen con tipografía profesional: "{main}".'
        )
    if sec:
        partes.append(f'Texto secundario debajo, más pequeño: "{sec}".')
    bullets = spec.get("texto_bullets") or []
    if bullets:
        items = "; ".join(f"• {b}" for b in bullets[:5])
        partes.append(
            f"Lista vertical con viñetas legibles en móvil: {items}."
        )
        partes.append("Layout: título arriba, bullets al centro, takeaway abajo si hay espacio.")
    desc = (spec.get("descripcion") or spec.get("vibe") or "").strip().rstrip(".")
    if desc:
        partes.append(f"Escena de fondo y composición: {desc}.")
    fondo = estetica_fondo_carrusel(sg.get("estetica"))
    if fondo:
        partes.append(fondo)
    if slide_idx > 0:
        partes.append(
            "CRÍTICO: Mismo estilo visual, paleta, tipografía y lenguaje de diseño que la slide 1 (portada)."
        )
    partes.append(
        "Diseño profesional de carrusel Instagram con texto integrado (calidad Canva). "
        "Texto nítido y legible en móvil. Sin marcas de agua. Sin logos de terceros. Salida PNG."
    )
    return " ".join(p for p in partes if p and p != ".")


def _spec_a_prompt_integrado_en(spec: dict, sg: dict,
                                slide_idx: int = 0, total: int = 7) -> str:
    main = (spec.get("texto_overlay") or "").strip()
    sec = (spec.get("texto_secundario") or "").strip()
    num = slide_idx + 1
    colores = sg.get("colores") or spec.get("paleta_colores") or []
    colores_txt = ", ".join(colores[:5]) if colores else "rojo, blanco y negro"
    negocio = sg.get("negocio") or ""

    if slide_idx == 0:
        fase = "PORTADA — gancho extremo que detenga el scroll"
    elif slide_idx >= total - 1:
        fase = "CIERRE — call to action claro con palabra clave visible"
    else:
        fase = f"DESARROLLO slide {num} — continúa la narrativa del carrusel"

    partes = [
        f"Instagram carousel slide {num} of {total}, square 1080x1080, {fase}.",
        f"Visual style (consistent across ALL slides): {sg.get('estilo_visual', 'modern bold graphic design')}.",
        f"Narrative format: {sg.get('formato_nombre', 'educational carousel')}.",
        f"Color palette (strict): {colores_txt}.",
        f"Typography: {sg.get('tipografia', 'bold sans-serif, high contrast, mobile-readable')}.",
    ]
    if negocio:
        partes.append(f"Brand context: {negocio}.")
    if main:
        partes.append(
            f'Render this EXACT main text inside the image with professional typography: "{main}".'
        )
    if sec:
        partes.append(
            f'Secondary text below main, smaller size: "{sec}".'
        )
    bullets = spec.get("texto_bullets") or []
    if bullets:
        items = "; ".join(f"• {b}" for b in bullets[:5])
        partes.append(
            f"Render a clean vertical bullet list with icons, legible on mobile: {items}."
        )
        partes.append("Layout: title on top, bullet list in the middle, takeaway at bottom if space.")
    desc = (spec.get("descripcion") or spec.get("vibe") or "").strip().rstrip(".")
    if desc:
        partes.append(f"Background scene and composition: {desc}.")
    fondo = estetica_fondo_carrusel(sg.get("estetica"))
    if fondo:
        partes.append(fondo)
    if slide_idx > 0:
        partes.append(
            "CRITICAL: Match exactly the same visual style, color palette, typography "
            "and design language as slide 1 (cover) of this carousel sequence."
        )
    partes.append(
        "Professional Instagram carousel design with text baked into the image "
        "(Canva-quality). Text must be sharp and legible on mobile. "
        "No watermarks. No third-party logos. PNG output."
    )
    return " ".join(p for p in partes if p and p != ".")
