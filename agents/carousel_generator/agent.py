"""
Pipeline de carrusel — skill /carrusel (Santiago Muñoz) en RIMA.

Fases:
1. Plan (plan.json) — copy + style_guide + prompts por slide
2. Prompts nano-banana-pro — texto integrado, estilo coherente
3. Generación KIE — portada primero; slides 2+ con image_input referencia
4. PNGs listos para publicar (sin overlay Pillow)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from core import kie_client
from core.carousel_plan import build_carousel_plan
from core.imagenes_biblioteca import cliente_generadas_dir, registrar_imagen_generada
from core.marca_visual import normalizar_marca, paleta_colores, merge_style_guide_from_marca, style_hints_from_marca
from core.db import get_marca_visual
from core.visual_spec import spec_desde_slide, spec_a_prompt_integrado

DEFAULT_STYLE = {
    "estilo_visual": "diseño gráfico moderno, bold y profesional, optimizado para Instagram",
    "tipografia": "sans-serif bold, alto contraste, legible en móvil",
    "colores": ["#EF4444", "#FFFFFF", "#0F172A"],
    "formato_nombre": "Metafórico cinematográfico",
}


def build_style_guide(marca: Optional[dict], brief: Optional[dict],
                      copy_json: Optional[dict] = None) -> dict:
    copy_json = copy_json or {}
    marca = normalizar_marca(marca or {})
    brief = brief or {}
    hints = style_hints_from_marca(marca, brief)
    colores = hints["colores"] or paleta_colores(marca) or list(DEFAULT_STYLE["colores"])
    if not colores:
        colores = list(DEFAULT_STYLE["colores"])

    sg = copy_json.get("style_guide") or {}
    base = {
        "estilo_visual": (
            sg.get("estilo_visual")
            or hints.get("estilo_visual")
            or DEFAULT_STYLE["estilo_visual"]
        ),
        "tipografia": sg.get("tipografia") or hints.get("tipografia") or DEFAULT_STYLE["tipografia"],
        "colores": sg.get("colores") or colores[:5],
        "formato_nombre": (
            copy_json.get("formato")
            or sg.get("formato_nombre")
            or DEFAULT_STYLE["formato_nombre"]
        ),
        "negocio": brief.get("business_name") or "",
        "idioma": sg.get("idioma") or hints.get("idioma") or "es",
    }
    if hints.get("tono"):
        base["tono_marca"] = hints["tono"]
    if hints.get("estilo_fotografico") in ("paisajes", "modelo_consistente"):
        base["direccion_personaje"] = hints["estilo_fotografico"]
    return merge_style_guide_from_marca(base, marca, brief)


def build_integrated_prompt(slide: dict, style_guide: dict,
                            slide_idx: int, total: int,
                            slot_context: Optional[dict] = None) -> str:
    slot_context = slot_context or {}
    spec = spec_desde_slide(slide, "carrusel", slot_context, style_guide.get("colores"))
    return spec_a_prompt_integrado(spec, style_guide, slide_idx, total)


def refresh_kie_prompts(slides: list, style_guide: dict,
                        slot_context: Optional[dict] = None) -> list:
    total = len(slides)
    slot_context = slot_context or {}
    resolucion = kie_client.default_resolution()
    out = []
    for idx, slide in enumerate(slides):
        s = dict(slide)
        spec = spec_desde_slide(s, "carrusel", slot_context, style_guide.get("colores"))
        s["spec_visual"] = spec
        s["prompt_sugerido"] = build_integrated_prompt(s, style_guide, idx, total, slot_context)
        s["texto_en_imagen"] = True
        s["ratio"] = "1:1"
        s["kie_resolution"] = resolucion
        s["kie_model"] = kie_client.model_imagen()
        out.append(s)
    return out


def attach_carousel_plan(
    pub: dict,
    copy_json: dict,
    style_guide: dict,
    slides: list,
    produccion: Optional[dict] = None,
) -> dict:
    """Adjunta carousel_plan (plan.json) a produccion y copy_json."""
    produccion = dict(produccion or {})
    plan = build_carousel_plan(pub, copy_json, style_guide, slides)
    produccion["carousel_plan"] = plan
    produccion["kie_model"] = plan["modelo_kie"]
    produccion["modo_visual"] = "texto_integrado"
    produccion["style_guide"] = style_guide
    copy_out = dict(copy_json or {})
    copy_out["carousel_plan"] = plan
    return {"produccion": produccion, "copy_json": copy_out, "carousel_plan": plan}


def generate_carousel_batch(
    cliente_id: str,
    pub_id: str,
    pub: dict,
    slides: list,
    uploads_dir,
    style_guide: dict,
    slide_indices: Optional[list[int]] = None,
    skip_existing: bool = True,
    copy_json: Optional[dict] = None,
) -> dict:
    if not kie_client.is_configured():
        return {"ok": False, "status": "not_configured",
                "reason": "Falta KIE_API_KEY en .env"}

    slot_context = {
        "tematica": pub.get("tematica", ""),
        "enfoque": pub.get("enfoque", ""),
        "fecha": pub.get("fecha", ""),
    }
    total = len(slides)
    marca = get_marca_visual(cliente_id)
    paleta = paleta_colores(marca) or style_guide.get("colores") or []
    modelo = kie_client.model_imagen()
    resolucion = kie_client.default_resolution()

    if slide_indices is None:
        targets = [
            i for i, s in enumerate(slides)
            if s.get("image_source") in ("kie_pending", "generada_ia")
            and not (skip_existing and s.get("image_source") == "generada_ia"
                     and s.get("archivo_url"))
        ]
    else:
        targets = [i for i in slide_indices if 0 <= i < total]

    if not targets:
        return {"ok": True, "generated": 0, "slides": slides,
                "message": "No hay slides pendientes de generación",
                "modelo_kie": modelo}

    reference_url: Optional[str] = None
    for s in slides:
        if s.get("kie_reference_url"):
            reference_url = s["kie_reference_url"]
            break

    direccion_personaje = style_guide.get("direccion_personaje") or ""
    personaje_ref = marca.get("visual", {}).get("imagen_personaje_url") or ""
    paisaje_suffix = (
        ", sin personas ni rostros en cuadro, priorizar escena/paisaje/objeto "
        "con una frase o pensamiento como elemento central"
        if direccion_personaje == "paisajes" else ""
    )

    results = []
    generated = 0
    errors = []

    for idx in sorted(targets):
        slide = slides[idx]
        prompt = (
            slide.get("prompt_usado")
            or slide.get("prompt_sugerido")
            or build_integrated_prompt(slide, style_guide, idx, total, slot_context)
        )
        if paisaje_suffix:
            prompt = (prompt or "") + paisaje_suffix
        ratio = slide.get("ratio") or "1:1"
        if direccion_personaje == "modelo_consistente":
            ref = reference_url or personaje_ref or None
        else:
            ref = reference_url if idx > 0 else None

        res = kie_client.generate_image(
            prompt, ratio,
            reference_image=ref,
            resolution=slide.get("kie_resolution") or resolucion,
            model=slide.get("kie_model") or modelo,
        )
        if res.get("status") != "ok":
            errors.append({"slide_index": idx, "reason": res.get("reason", "error KIE")})
            results.append({"slide_index": idx, "ok": False, "reason": res.get("reason")})
            continue

        nombre = (f"{pub_id[:8]}_slide{slide.get('slide_number', idx + 1)}"
                  f"_{int(datetime.now().timestamp())}.png")
        destino = cliente_generadas_dir(uploads_dir, cliente_id) / nombre
        dl = kie_client.download_image(res["image_url"], destino)
        if dl.get("status") != "ok":
            errors.append({"slide_index": idx,
                           "reason": f"Descarga fallida: {dl.get('reason')}"})
            results.append({"slide_index": idx, "ok": False, "reason": dl.get("reason")})
            continue

        spec = slide.get("spec_visual") or spec_desde_slide(
            slide, "carrusel", slot_context, paleta)
        bib = registrar_imagen_generada(
            cliente_id, destino, prompt=prompt, spec=spec, paleta=paleta)

        slide.update({
            "image_source": "generada_ia",
            "archivo_url": bib.get("archivo_url")
            or f"/uploads/clientes/{cliente_id}/generadas/{nombre}",
            "image_id": bib.get("id"),
            "texto_en_imagen": True,
            "text_zone": {"zone": "center"},
            "spec_usada": spec,
            "prompt_usado": prompt,
            "kie_task_id": res.get("task_id"),
            "kie_model": res.get("model") or modelo,
            "kie_resolution": res.get("resolution") or resolucion,
            "kie_reference_url": res.get("image_url"),
            "generated_at": datetime.now().isoformat(),
        })
        slide.pop("match_score", None)
        reference_url = res.get("image_url") or reference_url
        if direccion_personaje == "modelo_consistente" and not personaje_ref and res.get("image_url"):
            from core.db import set_marca_visual
            marca.setdefault("visual", {})["imagen_personaje_url"] = res["image_url"]
            set_marca_visual(cliente_id, marca)
            personaje_ref = res["image_url"]
        generated += 1
        results.append({
            "slide_index": idx,
            "ok": True,
            "archivo_url": slide.get("archivo_url"),
            "credits_consumed": res.get("credits_consumed"),
            "model": res.get("model"),
        })

    carousel_plan = build_carousel_plan(
        pub, copy_json or {}, style_guide, slides, modelo_kie=modelo,
    )
    carousel_plan["generation"] = {
        "generated": generated,
        "errors": errors,
        "completed_at": datetime.now().isoformat(),
    }

    return {
        "ok": generated > 0 or not errors,
        "generated": generated,
        "total_targets": len(targets),
        "results": results,
        "errors": errors,
        "slides": slides,
        "reference_url": reference_url,
        "modelo_kie": modelo,
        "carousel_plan": carousel_plan,
    }
