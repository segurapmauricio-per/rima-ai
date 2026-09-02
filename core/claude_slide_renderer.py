"""
Render de carruseles vía Claude (composición HTML) + Playwright (HTML -> PNG).

Alternativa a core/slide_renderer.py para carruseles únicamente: en vez de que
KIE incruste el texto en la imagen (modo "texto_integrado") o de dibujar con
Pillow, KIE genera solo el fondo (sin texto, ver spec_a_prompt en
core/visual_spec.py) y Claude compone texto + scrim + resaltado sobre ese
fondo en un solo documento HTML con todas las slides del carrusel, para
mantener consistencia visual entre ellas. Ver docs/protocolo-generacion-imagenes-ia.md
para el porqué de este cambio (Gemini no aplicaba el scrim de forma consistente).

No usar para historias: ese pipeline (core/slide_renderer.py, modo_visual
"fondo_limpio") ya tiene su propio overlay de Pillow con scrim y resaltado
funcionando razonablemente bien.
"""
from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright

from core import claude_client
from core.marca_visual import normalizar_marca, paleta_colores

SIZE_CARRUSEL = (1080, 1080)


def _resolve_local_path(archivo_url: str, uploads_dir: Path) -> Optional[Path]:
    if not archivo_url:
        return None
    url = archivo_url.split("?")[0]
    if url.startswith("/uploads/"):
        rel = url[len("/uploads/"):].lstrip("/")
        p = uploads_dir / rel
        return p if p.is_file() else None
    if url.startswith(("http://", "https://")):
        return None
    p = Path(url)
    return p if p.is_file() else None


def _slide_para_prompt(slide: dict, idx: int, total: int, fondo_path: Optional[Path]) -> dict:
    role = (slide.get("role") or "desarrollo").lower()
    rol_es = {"gancho": "portada", "cierre": "cierre"}.get(role, "contenido")
    return {
        "num": idx + 1,
        "total": total,
        "rol": rol_es,
        "texto": (slide.get("main_text") or "").strip(),
        "texto_secundario": (slide.get("secondary_text") or "").strip(),
        "highlight_words": list(slide.get("highlight_words") or []),
        "fondo_url": ("file:///" + str(fondo_path).replace("\\", "/")) if fondo_path else None,
        "fondo_tipo": "foto_realista" if fondo_path else "degradado_marca",
    }


def _build_system_prompt(marca: dict, wordmark: str, total_slides: int) -> str:
    paleta = paleta_colores(normalizar_marca(marca), 5) or ["#111111", "#FFFFFF", "#6366F1"]
    paleta_txt = ", ".join(paleta)
    wordmark_linea = f'- Wordmark de marca a incluir de forma discreta en cada slide: "{wordmark}"\n' if wordmark else ""

    return f"""Eres el paso de "composición" de un pipeline de generación de contenido para redes \
sociales. Cada slide trae su texto ya redactado (campo "texto") y, en algunos casos, una imagen de \
fondo ya generada (campo "fondo_url"). Tu única tarea es componer: ubicar la imagen si existe, aplicar \
tratamiento de contraste y poner el texto encima. NO dibujas íconos ni ilustraciones propias — la \
imagen de fondo, cuando existe, ya viene resuelta.

No debes:
- Inventar ni modificar el texto de cada slide (campos "texto" y "texto_secundario"). Úsalos literales, \
palabra por palabra. No agregues subtítulos, bajadas ni ninguna frase que no esté en esos campos.
- Usar imágenes externas ni fuentes vía red — la única imagen permitida por slide es su propio \
"fondo_url" (cuando no es null). Fuentes: solo system-ui, Georgia, Helvetica, Arial.
- Dibujar SVG, íconos o ilustraciones propias de ningún tipo.

Cada slide trae "fondo_tipo":
- "foto_realista": cubre TODO el lienzo (equivalente a object-fit: cover) y aplica encima un scrim \
degradado (gradiente oscuro semitransparente hacia transparente) sobre la zona de texto, generoso, no \
sutil, para que se lea de inmediato incluso a primera vista rápida en el feed.
- "degradado_marca": sin imagen. El fondo completo es un degradado usando solo la paleta de marca — \
sin foto, sin ilustración, sin ícono.

Paleta de marca (usar únicamente estos colores para fondos, acentos y detalles): {paleta_txt}.
{wordmark_linea}Formato exacto de cada slide: {SIZE_CARRUSEL[0]}x{SIZE_CARRUSEL[1]} px (carrusel \
cuadrado de Instagram).

Reglas de composición obligatorias:
1. Resuelve el fondo según "fondo_tipo" como se explicó arriba.
2. Si el slide trae "highlight_words" no vacío, resalta EXACTAMENTE esas palabras/frases en un color de \
acento de la paleta (fondo tipo píldora/badge detrás de la palabra, no solo cambiar el color del texto). \
Si "highlight_words" viene vacío, decide tú qué frase resaltar según el mensaje del slide, mismo \
tratamiento de píldora.
3. Wordmark de marca (si se te dio una) + indicador de página ("N / {total_slides}") en cada slide, \
discretos, con buen contraste.

Devuelve UN SOLO documento HTML completo. Dentro del <body>, un elemento por slide:
<section class="slide" data-slide="N" style="width:{SIZE_CARRUSEL[0]}px;height:{SIZE_CARRUSEL[1]}px;position:relative;overflow:hidden;">
...
</section>

Todos los slides deben compartir el mismo sistema visual (tipografía, tratamiento de marca) para verse \
como una sola pieza consistente, con variaciones de layout razonables entre portada / contenido / cierre.

Responde solo con el HTML, sin explicaciones antes o después, sin bloques de código markdown."""


def render_publicacion_visual_claude(
    cliente_id: str,
    pub_id: str,
    pub: dict,
    uploads_dir: Path,
    marca: Optional[dict] = None,
) -> dict:
    """Mismo contrato de retorno que slide_renderer.render_publicacion_visual,
    pero compone con Claude + Playwright en vez de Pillow. Solo para carruseles."""
    if not claude_client.is_configured():
        return {"ok": False, "status": "not_configured", "reason": "Falta ANTHROPIC_API_KEY en .env"}

    prod = pub.get("produccion_json") or {}
    if isinstance(prod, str):
        try:
            prod = json.loads(prod)
        except Exception:
            prod = {}

    slides = prod.get("slides") or []
    if not slides:
        return {"rendered_at": datetime.now().isoformat(), "tipo": "carrusel",
                "slides": [], "zip_filename": "", "total": 0, "pendientes": 0}

    marca = marca or {}
    wordmark = f"@{marca['ig_username']}" if marca.get("ig_username") else ""

    fondos = [_resolve_local_path(s.get("archivo_url") or "", uploads_dir) for s in slides]
    slides_prompt = [
        _slide_para_prompt(s, i, len(slides), fondos[i]) for i, s in enumerate(slides)
    ]

    system_prompt = _build_system_prompt(marca, wordmark, len(slides))
    user_prompt = "Compón estos slides:\n\n" + json.dumps(slides_prompt, ensure_ascii=False, indent=2)
    html = claude_client.generar_html(system_prompt, user_prompt)

    out_dir = uploads_dir / "renderizados" / pub_id
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "carrusel.html"
    html_path.write_text(html, encoding="utf-8")

    rendered: list[dict] = []
    png_paths: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": SIZE_CARRUSEL[0], "height": SIZE_CARRUSEL[1]})
        page.goto(f"file:///{str(html_path).replace(chr(92), '/')}")

        for idx, slide in enumerate(slides):
            n = idx + 1
            element = page.query_selector(f'.slide[data-slide="{n}"]')
            if element is None:
                continue
            fname = f"slide-{n:02d}.png"
            dest = out_dir / fname
            element.screenshot(path=str(dest))
            rendered.append({"slide_number": n, "role": slide.get("role", ""), "filename": fname})
            png_paths.append(dest)

        browser.close()

    zip_name = f"carrusel-{pub_id[:8]}.zip"
    if png_paths:
        with zipfile.ZipFile(out_dir / zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
            for pth in png_paths:
                zf.write(pth, pth.name)

    return {
        "rendered_at": datetime.now().isoformat(),
        "tipo": "carrusel",
        "motor": "claude",
        "slides": rendered,
        "zip_filename": zip_name if png_paths else "",
        "total": len(rendered),
        "pendientes": max(0, len(slides) - len(rendered)),
    }
