"""
Pipeline de historias Instagram — secuencias 3-5 slides (9:16).

1. Copy estructurado por slide (story_copy)
2. Matching biblioteca del cliente (fotos reales) o kie_pending
3. Generación KIE batch para slides pendientes
4. Render overlay Pillow (fondo_limpio)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from core import kie_client
from core.story_plan import build_story_plan
from core.imagenes_biblioteca import cliente_generadas_dir, registrar_imagen_generada
from core.marca_visual import normalizar_marca, paleta_colores, merge_style_guide_from_marca, style_hints_from_marca
from core.db import get_marca_visual
from core.visual_spec import spec_desde_slide, spec_a_prompt

DEFAULT_STYLE = {
    "estilo_visual": "foto auténtica o fondo limpio, estilo stories profesional",
    "tipografia": "sans-serif bold, alto contraste sobre imagen",
    "colores": ["#FFFFFF", "#0F172A"],
}


def build_style_guide(marca: Optional[dict], brief: Optional[dict],
                      copy_json: Optional[dict] = None) -> dict:
    marca = normalizar_marca(marca or {})
    brief = brief or {}
    copy_json = copy_json or {}
    hints = style_hints_from_marca(marca, brief)
    sg = copy_json.get("style_guide") or {}
    base = {
        "estilo_visual": sg.get("estilo_visual") or hints.get("estilo_visual") or DEFAULT_STYLE["estilo_visual"],
        "tipografia": sg.get("tipografia") or hints.get("tipografia") or DEFAULT_STYLE["tipografia"],
        "colores": sg.get("colores") or hints.get("colores") or DEFAULT_STYLE["colores"],
        "negocio": brief.get("business_name") or "",
        "idioma": sg.get("idioma") or hints.get("idioma") or "es",
    }
    return merge_style_guide_from_marca(base, marca, brief)


def refresh_kie_prompts(slides: list, style_guide: dict,
                        slot_context: Optional[dict] = None) -> list:
    slot_context = slot_context or {}
    resolucion = kie_client.default_resolution()
    modelo = kie_client.model_imagen()
    out = []
    for idx, slide in enumerate(slides):
        s = dict(slide)
        spec = spec_desde_slide(s, "historia", slot_context, style_guide.get("colores"))
        s["spec_visual"] = spec
        s["prompt_sugerido"] = spec_a_prompt(spec)
        s["ratio"] = "9:16"
        s["kie_resolution"] = resolucion
        s["kie_model"] = modelo
        s["texto_en_imagen"] = False
        out.append(s)
    return out


def generate_story_batch(
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
    modelo = kie_client.model_imagen()
    resolucion = kie_client.default_resolution()
    marca = get_marca_visual(cliente_id)
    paleta = paleta_colores(marca) or style_guide.get("colores") or []

    if slide_indices is None:
        targets = [
            i for i, s in enumerate(slides)
            if s.get("image_source") == "kie_pending"
            and not (skip_existing and s.get("image_source") == "generada_ia"
                     and s.get("archivo_url"))
        ]
    else:
        targets = [i for i in slide_indices if 0 <= i < len(slides)]

    if not targets:
        return {"ok": True, "generated": 0, "slides": slides,
                "message": "No hay slides pendientes de generación", "modelo_kie": modelo}

    reference_url: Optional[str] = None
    from core.face_profile import get_face_reference_for_kie, prompt_suffix_for_kie
    face_ref = get_face_reference_for_kie(cliente_id)
    face_suffix = prompt_suffix_for_kie(cliente_id)
    for s in slides:
        if s.get("kie_reference_url"):
            reference_url = s["kie_reference_url"]
            break

    generated = 0
    errors = []
    results = []

    for idx in sorted(targets):
        slide = slides[idx]
        prompt = (
            slide.get("prompt_usado")
            or slide.get("prompt_sugerido")
            or spec_a_prompt(slide.get("spec_visual") or {})
        )
        if face_suffix and "kie_pending" in (slide.get("image_source") or ""):
            prompt = (prompt or "") + face_suffix
        ratio = slide.get("ratio") or "9:16"
        ref = reference_url if idx > 0 else face_ref
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

        nombre = (f"{pub_id[:8]}_story{slide.get('slide_number', idx + 1)}"
                  f"_{int(datetime.now().timestamp())}.png")
        destino = cliente_generadas_dir(uploads_dir, cliente_id) / nombre
        dl = kie_client.download_image(res["image_url"], destino)
        if dl.get("status") != "ok":
            errors.append({"slide_index": idx,
                           "reason": f"Descarga fallida: {dl.get('reason')}"})
            continue

        spec = slide.get("spec_visual") or spec_desde_slide(
            slide, "historia", slot_context, paleta)
        bib = registrar_imagen_generada(
            cliente_id, destino, prompt=prompt, spec=spec, paleta=paleta)

        slide.update({
            "image_source": "generada_ia",
            "archivo_url": bib.get("archivo_url")
            or f"/uploads/clientes/{cliente_id}/generadas/{nombre}",
            "image_id": bib.get("id"),
            "texto_en_imagen": False,
            "text_zone": spec.get("zona_texto") or {"zone": "center"},
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
        generated += 1
        results.append({"slide_index": idx, "ok": True, "archivo_url": slide.get("archivo_url")})

    story_plan = build_story_plan(
        pub, copy_json or {}, style_guide, slides, modelo_kie=modelo,
    )
    story_plan["generation"] = {
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
        "modelo_kie": modelo,
        "story_plan": story_plan,
    }
