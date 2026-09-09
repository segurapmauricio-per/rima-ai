"""
Render de carruseles e historias vía Claude (composición HTML) + Playwright
(HTML -> PNG).

Alternativa a core/slide_renderer.py: en vez de que KIE incruste el texto en
la imagen (modo "texto_integrado") o de dibujar con Pillow, KIE genera solo
el fondo (sin texto, ver spec_a_prompt en core/visual_spec.py) — o el slide
usa una foto real del cliente ya matcheada por agents/visual_composer — y
Claude compone texto + scrim + resaltado sobre ese fondo en un solo
documento HTML con todas las slides de la publicación, para mantener
consistencia visual entre ellas. Ver docs/protocolo-generacion-imagenes-ia.md
para el porqué de este cambio (Gemini no aplicaba el scrim de forma
consistente; el modelo de imagen tampoco es confiable escribiendo texto largo
en español dentro de la imagen — ver skill generar-carrusel).

Sirve tanto a tipo="carrusel" (1080x1080, jerarquía tipográfica editorial)
como tipo="historia" (1080x1920, tipografía uniforme, encuadre más acotado).
Reemplaza el overlay de Pillow (core/slide_renderer.py, _draw_historia_overlay)
como motor por defecto para historias — ese código queda como fallback, no se
borra.
"""
from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright

from core import claude_client
from core.marca_visual import normalizar_marca, paleta_colores

SIZE_POR_TIPO = {
    "carrusel": (1080, 1080),
    "historia": (1080, 1920),
}

# Claude arma un wordmark/paginador leyendo el slug del cliente en la ruta del
# archivo de fondo (fondo_url), aunque el prompt se lo prohíba explícitamente
# — probado con instrucciones cada vez más fuertes, sin efecto, y cada intento
# usa una estructura HTML distinta (a veces un <div> plano, a veces un <span>
# con un ícono anidado adentro), así que un regex sobre texto no alcanza. Para
# historias (que no deben llevar ninguno de los dos, ver _build_system_prompt)
# se parsea el HTML de verdad y se borra cualquier elemento cuyo texto
# COMPLETO (aplanando hijos anidados) sea solo un "@handle" o un "N / M".
_HANDLE_RE = re.compile(r'^@[\w.]{1,60}$')
_PAGER_RE = re.compile(r'^\d{1,3}\s*/\s*\d{1,3}$')


class _ChromeStripper(HTMLParser):
    """Encuentra los spans [inicio, fin] de elementos cuyo texto aplanado
    matchea el wordmark/paginador, para poder cortarlos del HTML original."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self._stack: list[dict] = []  # {tag, start_pos, text_parts}
        self.spans_a_borrar: list[tuple[int, int]] = []

    def handle_starttag(self, tag, attrs):
        self._stack.append({"tag": tag, "start": self.getpos(), "text": []})

    def handle_startendtag(self, tag, attrs):
        pass  # self-closing (ej. <br/>) no aporta texto ni necesita cierre

    def handle_data(self, data):
        for frame in self._stack:
            frame["text"].append(data)

    def handle_endtag(self, tag):
        # Buscamos el frame abierto más cercano con este mismo tag.
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["tag"] == tag:
                frame = self._stack.pop(i)
                texto = "".join(frame["text"]).strip()
                if _HANDLE_RE.match(texto) or _PAGER_RE.match(texto):
                    self._mark_for_removal(frame, tag)
                # Los frames que quedaban por encima de `i` en la pila (tags
                # sin cerrar correctamente, ej. HTML no bien anidado) los
                # descartamos silenciosamente — no deberían darse en HTML
                # generado por Claude, que es válido casi siempre.
                del self._stack[i:]
                return

    def _offset(self, line: int, col: int) -> int:
        lines = self.rawdata.split("\n")
        return sum(len(l) + 1 for l in lines[:line - 1]) + col

    def _mark_for_removal(self, frame: dict, tag: str):
        start_offset = self._offset(*frame["start"])
        # self.getpos() en handle_endtag apunta al inicio del "</tag>"; el
        # fin real del elemento es tras el "</tag>" completo.
        end_offset = self._offset(*self.getpos()) + len(f"</{tag}>")
        self.spans_a_borrar.append((start_offset, end_offset))


def _strip_historia_chrome(html: str) -> str:
    parser = _ChromeStripper()
    parser.feed(html)
    parser.close()
    out = html
    for start, end in sorted(parser.spans_a_borrar, reverse=True):
        out = out[:start] + out[end:]
    return out


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


def _build_system_prompt(marca: dict, wordmark: str, total_slides: int,
                         tipo: str, size: tuple[int, int]) -> str:
    paleta = paleta_colores(normalizar_marca(marca), 5) or ["#111111", "#FFFFFF", "#6366F1"]
    paleta_txt = ", ".join(paleta)

    if tipo == "historia":
        wordmark_linea = ""
        no_wordmark_bullet = (
            '- Agregar wordmark, "@usuario", foto de perfil, indicador de página ("N / total") o '
            "cualquier otro elemento de marca/numeración en la slide. CERO excepciones — Instagram ya "
            "muestra el @usuario, la foto de perfil y la barra de progreso arriba con su propia UI; "
            "agregar los nuestros encima se ve como plantilla y rompe el disimulo de historia nativa. Es "
            "la regla más importante de esta tarea: si dudás, no lo dibujes.\n"
        )
        marca_pagina_txt = None
        formato_txt = f"{size[0]}x{size[1]} px (historia vertical de Instagram, 9:16)"
        jerarquia_txt = (
            "Todas las historias usan UN SOLO tamaño de letra para el texto principal — sin jerarquía "
            "de tamaños entre slides ni dentro de una misma slide, es formato de lectura instantánea, "
            "no editorial. El texto secundario (si existe) va un poco más chico, pero esa relación de "
            "tamaños se mantiene idéntica en las 3-5 slides de la secuencia."
        )
        encuadre_txt = (
            "El encuadre es más acotado que un carrusel: dejá márgenes laterales generosos y no ocupes "
            "el 15% superior ni el 20% inferior del lienzo con texto — Instagram cubre esas franjas con "
            "su propia UI (perfil/progreso arriba, reply abajo). El bloque de texto queda contenido, no "
            "corrido de punta a punta."
        )
    else:
        wordmark_linea = f'- Wordmark de marca a incluir de forma discreta en cada slide: "{wordmark}"\n' if wordmark else ""
        no_wordmark_bullet = ""
        marca_pagina_txt = (
            f'Wordmark de marca (si se te dio una) + indicador de página ("N / {total_slides}") en cada '
            "slide, discretos, con buen contraste."
        )
        formato_txt = f"{size[0]}x{size[1]} px (carrusel cuadrado de Instagram)"
        jerarquia_txt = (
            'Usá jerarquía tipográfica editorial: el "texto" principal en tamaño grande y el '
            '"texto_secundario" notablemente más chico debajo, para que se entienda qué es lo '
            "importante de un vistazo."
        )
        encuadre_txt = "El bloque de texto puede ocupar la mayor parte del ancho del lienzo."

    reglas = [
        'Resuelve el fondo según "fondo_tipo" como se explicó arriba.',
        'Si el slide trae "highlight_words" no vacío, resaltá EXACTAMENTE esas palabras/frases (todas, '
        'no solo la primera) en color de acento de la paleta. El resaltado NO debe verse como un '
        "rectángulo o píldora sólida pegada detrás del texto — usá un efecto de resplandor/aura "
        "difuminada del color de acento (por ejemplo, un fondo semi-transparente con `filter: blur(...)` "
        "o varias capas de `box-shadow`/`text-shadow` difuminadas del color de acento detrás de las "
        "letras), de modo que el color se sienta como luz detrás del texto, con bordes suaves — nunca un "
        'bloque geométrico de bordes duros y esquinas rectas. Si "highlight_words" viene vacío, decidí '
        "vos qué fragmento resaltar según el mensaje de cada slide, mismo tratamiento de aura. Prestá "
        "atención a la puntuación pegada a la frase resaltada (un punto, coma o dos puntos justo antes o "
        "después): ese signo pertenece a la misma palabra vecina y nunca debe quedar huérfano solo al "
        "inicio o final de una línea — ajustá el corte de línea para que el signo de puntuación quede "
        "siempre pegado a su palabra vecina.",
    ]
    if marca_pagina_txt:
        reglas.append(marca_pagina_txt)
    reglas.append(jerarquia_txt)
    reglas.append(encuadre_txt)
    reglas.append(
        "Si el texto de una slide es corto y deja mucho espacio vacío en el lienzo, no ancles el bloque "
        "de texto solo abajo — centralo verticalmente en el espacio disponible (o en el tercio central) "
        'para que la composición se sienta equilibrada, no como si el texto se hubiera "caído" al fondo.'
    )
    reglas_txt = "\n".join(f"{i}. {r}" for i, r in enumerate(reglas, start=1))

    return f"""Eres el paso de "composición" de un pipeline de generación de contenido para redes \
sociales. Cada slide trae su texto ya redactado (campo "texto") y, en algunos casos, una imagen de \
fondo ya generada o una foto real del cliente (campo "fondo_url"). Tu única tarea es componer: ubicar \
la imagen si existe, aplicar tratamiento de contraste y poner el texto encima. NO dibujas íconos ni \
ilustraciones propias — la imagen de fondo, cuando existe, ya viene resuelta.

No debes:
- Inventar ni modificar el texto de cada slide (campos "texto" y "texto_secundario"). Úsalos literales, \
palabra por palabra, tal como vienen (incluido el idioma — nunca traduzcas). No agregues subtítulos, \
bajadas ni ninguna frase que no esté en esos campos.
- Usar imágenes externas ni fuentes vía red — la única imagen permitida por slide es su propio \
"fondo_url" (cuando no es null). Fuentes: solo system-ui, Georgia, Helvetica, Arial.
- Dibujar SVG, íconos o ilustraciones propias de ningún tipo.
- Agregar una etiqueta pequeña o "eyebrow" arriba del texto principal (tipo "Tip 01", "Paso 1", "La \
clave") a menos que el texto de la slide ya la traiga escrita — la jerarquía se logra con tamaño de \
fuente y color, no con etiquetas de categoría inventadas.
{no_wordmark_bullet}
Cada slide trae "fondo_tipo":
- "foto_realista": cubre TODO el lienzo (equivalente a object-fit: cover) y aplica encima un scrim \
degradado (gradiente oscuro semitransparente hacia transparente) sobre la zona de texto, generoso, no \
sutil, para que se lea de inmediato incluso a primera vista rápida en el feed.
- "degradado_marca": sin imagen. El fondo completo es un degradado usando solo la paleta de marca — \
sin foto, sin ilustración, sin ícono.

Paleta de marca (usar únicamente estos colores para fondos, acentos y detalles): {paleta_txt}.
{wordmark_linea}Formato exacto de cada slide: {formato_txt}.

Reglas de composición obligatorias:
{reglas_txt}

Devuelve UN SOLO documento HTML completo. Dentro del <body>, un elemento por slide:
<section class="slide" data-slide="N" style="width:{size[0]}px;height:{size[1]}px;position:relative;overflow:hidden;">
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
    pero compone con Claude + Playwright en vez de Pillow. Sirve carrusel e
    historia (ver SIZE_POR_TIPO)."""
    if not claude_client.is_configured():
        return {"ok": False, "status": "not_configured", "reason": "Falta ANTHROPIC_API_KEY en .env"}

    prod = pub.get("produccion_json") or {}
    if isinstance(prod, str):
        try:
            prod = json.loads(prod)
        except Exception:
            prod = {}

    tipo = pub.get("tipo") or "carrusel"
    size = SIZE_POR_TIPO.get(tipo, SIZE_POR_TIPO["carrusel"])

    slides = prod.get("slides") or []
    if not slides:
        return {"rendered_at": datetime.now().isoformat(), "tipo": tipo,
                "slides": [], "zip_filename": "", "total": 0, "pendientes": 0}

    marca = marca or {}
    wordmark = f"@{marca['ig_username']}" if marca.get("ig_username") else ""

    fondos = [_resolve_local_path(s.get("archivo_url") or "", uploads_dir) for s in slides]
    slides_prompt = [
        _slide_para_prompt(s, i, len(slides), fondos[i]) for i, s in enumerate(slides)
    ]

    system_prompt = _build_system_prompt(marca, wordmark, len(slides), tipo, size)
    user_prompt = "Compón estos slides:\n\n" + json.dumps(slides_prompt, ensure_ascii=False, indent=2)
    html = claude_client.generar_html(system_prompt, user_prompt)
    if tipo == "historia":
        html = _strip_historia_chrome(html)

    out_dir = uploads_dir / "renderizados" / pub_id
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{tipo}.html"
    html_path.write_text(html, encoding="utf-8")

    rendered: list[dict] = []
    png_paths: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": size[0], "height": size[1]})
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

    zip_name = f"{tipo}-{pub_id[:8]}.zip"
    if png_paths:
        with zipfile.ZipFile(out_dir / zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
            for pth in png_paths:
                zf.write(pth, pth.name)

    return {
        "rendered_at": datetime.now().isoformat(),
        "tipo": tipo,
        "motor": "claude",
        "slides": rendered,
        "zip_filename": zip_name if png_paths else "",
        "total": len(rendered),
        "pendientes": max(0, len(slides) - len(rendered)),
    }
