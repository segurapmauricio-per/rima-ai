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
    descripcion = (slide.get("visual_suggestion")
                   or slide.get("image_vibe_needed")
                   or slide.get("main_text")
                   or "imagen de marca limpia y profesional").strip()
    elementos = [v for v in (slot_context.get("tematica"),
                             slot_context.get("enfoque")) if v]
    spec.update({
        "origen": "generacion",
        "ratio": ratio,
        "formato": RATIO_A_FORMATO[ratio],
        "descripcion": descripcion,
        "vibe": slot_context.get("vibe", ""),
        "paleta_colores": list(paleta_marca or []),
        "elementos_clave": elementos,
        "texto_overlay": (slide.get("main_text") or "").strip(),
        "zona_texto": {"zone": "center", "coords": None,
                       "recommended_text_color": "#FFFFFF"},
    })
    return spec


def spec_a_prompt(spec: dict) -> str:
    """Prompt de generación para KIE AI armado por template desde la spec."""
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
