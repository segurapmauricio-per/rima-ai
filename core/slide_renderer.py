"""
Render de slides finales: imagen de fondo + copy superpuesto (Pillow).

Se ejecuta al aprobar producción visual (carrusel/historia).
Salida: PNG 1080×1080 (carrusel) o 1080×1920 (historia) en uploads del cliente.

Historias: diseño enriquecido con 2 colores de marca, palabras resaltadas,
recuadros pill y símbolos por rol (gancho / desarrollo / cierre).
"""
from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from core.marca_visual import normalizar_marca, paleta_colores

SIZE_CARRUSEL = (1080, 1080)
SIZE_HISTORIA = (1080, 1920)

FONT_CANDIDATES = [
    ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
     "/System/Library/Fonts/Supplemental/Arial.ttf"),
]

ZONE_ANCHORS = {
    "upper_third": 0.22,
    "center": 0.46,
    "lower_third": 0.70,
}

ROLE_SYMBOLS = {
    "gancho": ("✦", "accent"),
    "desarrollo": ("▸", "primary"),
    "cierre": ("→", "accent"),
}

DEFAULT_PALETTE = {
    "primary": "#6366F1",
    "accent": "#FBBF24",
    "tertiary": "#34D399",
    "text": "#FFFFFF",
    "text_muted": "#E2E8F0",
}

_STOPWORDS = frozenset(
    "de la el en y a que es un una los las del al con por para".split()
)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for bold_path, regular_path in FONT_CANDIDATES:
        path = Path(bold_path if bold else regular_path)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = (hex_color or "#FFFFFF").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 255, 255, 255


def _hex_to_rgba(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    r, g, b = _hex_to_rgb(hex_color)
    return r, g, b, max(0, min(255, alpha))


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = [c / 255.0 for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_text_on(bg_hex: str) -> str:
    return "#0F172A" if _luminance(_hex_to_rgb(bg_hex)) > 0.55 else "#FFFFFF"


def _story_palette(marca: Optional[dict]) -> dict:
    cols = paleta_colores(normalizar_marca(marca or {}))
    primary = cols[0] if len(cols) > 0 else DEFAULT_PALETTE["primary"]
    accent = cols[1] if len(cols) > 1 else DEFAULT_PALETTE["accent"]
    tertiary = cols[2] if len(cols) > 2 else DEFAULT_PALETTE["tertiary"]
    return {
        "primary": primary,
        "accent": accent,
        "tertiary": tertiary,
        "text": DEFAULT_PALETTE["text"],
        "text_muted": DEFAULT_PALETTE["text_muted"],
        "text_on_accent": _contrast_text_on(accent),
        "text_on_primary": _contrast_text_on(primary),
    }


def _resolve_local_path(archivo_url: str, uploads_dir: Path) -> Optional[Path]:
    if not archivo_url:
        return None
    url = archivo_url.split("?")[0]
    if url.startswith("/uploads/"):
        rel = url[len("/uploads/"):].lstrip("/")
        p = uploads_dir / rel
        return p if p.is_file() else None
    if url.startswith("http://") or url.startswith("https://"):
        return None
    p = Path(url)
    return p if p.is_file() else None


def _canvas_size(tipo: str) -> tuple[int, int]:
    return SIZE_HISTORIA if tipo == "historia" else SIZE_CARRUSEL


def _text_color_for_zone(text_zone: dict, marca: dict) -> str:
    color = (text_zone or {}).get("recommended_text_color") or "#FFFFFF"
    if color and str(color).startswith("#"):
        return color
    paleta = paleta_colores(normalizar_marca(marca))
    return paleta[0] if paleta else "#FFFFFF"


def _draw_text_block(draw: ImageDraw.ImageDraw, lines: list[str], xy: tuple[int, int],
                     font, fill: str, max_width: int, line_spacing: int = 8):
    x, y = xy
    for line in lines:
        if not line.strip():
            y += line_spacing
            continue
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y += (bbox[3] - bbox[1]) + line_spacing


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = (text or "").replace("\r", "").split()
    if not words:
        return []
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        w = draw.textlength(trial, font=font)
        if w <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def _tokenize_plain(text: str, extra_highlights: set[str]) -> list[dict]:
    segments: list[dict] = []
    for raw_word in text.split():
        if not raw_word:
            continue
        word = raw_word
        punct_after = ""
        while word and word[-1] in ".,!?;:":
            punct_after = word[-1] + punct_after
            word = word[:-1]
        punct_before = ""
        while word and word[0] in "¿¡":
            punct_before += word[0]
            word = word[1:]
        style = "normal"
        check = word.lower()
        if word.isupper() and len(word) >= 2:
            style = "accent"
        elif re.search(r"[\d%$€]", word):
            style = "accent"
        elif check in extra_highlights:
            style = "pill"
        display = punct_before + word + punct_after
        if display.strip():
            segments.append({"text": display, "style": style})
    return segments


def _parse_segments(text: str, extra_highlights: Optional[list] = None) -> list[dict]:
    """Parsea **resaltado**, MAYÚSCULAS, números y palabras clave."""
    if not (text or "").strip():
        return []
    extra = {h.lower() for h in (extra_highlights or []) if h}
    segments: list[dict] = []
    pattern = re.compile(r"\*\*(.+?)\*\*")
    last = 0
    for match in pattern.finditer(text):
        if match.start() > last:
            segments.extend(_tokenize_plain(text[last:match.start()], extra))
        inner = match.group(1).strip()
        if inner:
            segments.append({"text": inner, "style": "pill"})
        last = match.end()
    if last < len(text):
        segments.extend(_tokenize_plain(text[last:], extra))
    if not segments:
        segments.extend(_tokenize_plain(text, extra))
    return segments


def _extract_keyword(secondary: str, slide: dict) -> Optional[str]:
    kw = (slide.get("keyword") or slide.get("cta_keyword") or "").strip()
    if kw:
        return kw
    m = re.search(r"(?:coment[aá]|escrib[ií]|dm|mensaje)\s*:?\s*(\S+)", secondary, re.I)
    return m.group(1).strip(".,!?") if m else None


def _segment_width(draw: ImageDraw.ImageDraw, seg: dict, fonts: dict) -> float:
    font = fonts["accent"] if seg["style"] != "normal" else fonts["main"]
    return draw.textlength(seg["text"], font=font)


def _wrap_rich_lines(
    segments: list[dict],
    fonts: dict,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[list[dict]]:
    if not segments:
        return []
    lines: list[list[dict]] = []
    current: list[dict] = []
    current_w = 0.0
    space_w = draw.textlength(" ", font=fonts["main"])

    for seg in segments:
        seg_w = _segment_width(draw, seg, fonts)
        need = seg_w + (space_w if current else 0)
        if current and current_w + need > max_width:
            lines.append(current)
            current = [seg]
            current_w = seg_w
        else:
            if current:
                current_w += space_w
            current.append(seg)
            current_w += seg_w
    if current:
        lines.append(current)
    return lines


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int],
):
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill)
    except AttributeError:
        draw.rectangle(xy, fill=fill)


def _draw_rich_line(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    line: list[dict],
    fonts: dict,
    palette: dict,
    pill_pad_x: int = 12,
    pill_pad_y: int = 6,
) -> int:
    cx = x
    max_h = 0
    for seg in line:
        style = seg["style"]
        font = fonts["accent"] if style != "normal" else fonts["main"]
        text = seg["text"]
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        if style == "pill":
            bg = _hex_to_rgba(palette["accent"], 235)
            fill = palette["text_on_accent"]
            px1 = cx - pill_pad_x
            py1 = y - pill_pad_y
            px2 = cx + tw + pill_pad_x
            py2 = y + th + pill_pad_y
            _draw_rounded_rect(draw, (px1, py1, px2, py2), 10, bg)
            draw.text((cx, y), text, font=font, fill=fill)
        elif style == "accent":
            draw.text((cx, y), text, font=font, fill=palette["primary"])
        else:
            draw.text((cx, y), text, font=font, fill=palette["text"])

        cx += tw + draw.textlength(" ", font=font)
        max_h = max(max_h, th)
    return max_h


def _draw_gradient_scrim(
    overlay: Image.Image,
    size: tuple[int, int],
    box: tuple[int, int, int, int],
    zone: str,
):
    """Scrim degradado detrás del bloque de texto (más cinematográfico que caja plana)."""
    x1, y1, x2, y2 = box
    pad_y = int(size[1] * 0.04)
    gy1 = max(0, y1 - pad_y)
    gy2 = min(size[1], y2 + pad_y)
    draw = ImageDraw.Draw(overlay)
    steps = max(1, gy2 - gy1)
    for i in range(steps):
        yy = gy1 + i
        t = i / steps
        if zone == "upper_third":
            alpha = int(200 * (1 - t * 0.65))
        elif zone == "lower_third":
            alpha = int(200 * (0.35 + t * 0.65))
        else:
            alpha = int(160 * (1 - abs(t - 0.5) * 1.2))
        alpha = max(40, min(210, alpha))
        draw.line([(0, yy), (size[0], yy)], fill=(8, 10, 20, alpha))


def _draw_accent_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y1: int,
    y2: int,
    color: str,
    width: int = 6,
):
    _draw_rounded_rect(
        draw,
        (x, y1, x + width, y2),
        width // 2,
        _hex_to_rgba(color, 255),
    )


def _draw_historia_overlay(
    canvas: Image.Image,
    slide: dict,
    marca: Optional[dict],
    text_zone: dict,
) -> Image.Image:
    size = canvas.size
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    palette = _story_palette(marca)
    zone = (text_zone or {}).get("zone") or "center"
    anchor_y = ZONE_ANCHORS.get(zone, ZONE_ANCHORS["center"])
    role = (slide.get("role") or "desarrollo").lower()

    main_text = (slide.get("main_text") or "").strip()
    secondary = (slide.get("secondary_text") or "").strip()
    keyword = _extract_keyword(secondary, slide)
    highlights = list(slide.get("highlight_words") or [])
    if keyword:
        highlights.append(keyword)

    margin_x = int(size[0] * 0.09)
    max_width = size[0] - 2 * margin_x
    bar_gap = 18

    if role == "gancho":
        main_size, sub_size = 56, 32
    elif role == "cierre":
        main_size, sub_size = 50, 34
    else:
        main_size, sub_size = 46, 30

    fonts = {
        "main": _load_font(main_size, bold=True),
        "accent": _load_font(main_size, bold=True),
        "sub": _load_font(sub_size, bold=False),
        "sub_accent": _load_font(sub_size, bold=True),
        "symbol": _load_font(int(main_size * 1.15), bold=True),
    }

    main_segments = _parse_segments(main_text, highlights)
    main_lines = _wrap_rich_lines(main_segments, fonts, max_width, draw)

    sub_segments: list[dict] = []
    sub_lines: list[list[dict]] = []
    if secondary:
        if keyword and keyword.lower() in secondary.lower():
            parts = re.split(re.escape(keyword), secondary, maxsplit=1, flags=re.I)
            if len(parts) == 2:
                sub_segments.extend(_parse_segments(parts[0].strip(), highlights))
                sub_segments.append({"text": keyword, "style": "pill"})
                sub_segments.extend(_parse_segments(parts[1].strip(), highlights))
            else:
                sub_segments = _parse_segments(secondary, highlights)
        else:
            sub_segments = _parse_segments(secondary, highlights)
        sub_lines = _wrap_rich_lines(sub_segments, {
            "main": fonts["sub"],
            "accent": fonts["sub_accent"],
        }, max_width, draw)

    symbol, sym_color_key = ROLE_SYMBOLS.get(role, ("▸", "primary"))
    sym_color = palette[sym_color_key]
    sym_bbox = draw.textbbox((0, 0), symbol, font=fonts["symbol"])
    sym_h = sym_bbox[3] - sym_bbox[1]

    line_spacing = int(main_size * 0.28)
    sub_spacing = int(sub_size * 0.35)
    symbol_block = sym_h + 16 if main_lines else 0

    main_block_h = 0
    for ln in main_lines:
        font = fonts["main"]
        lh = max(
            draw.textbbox((0, 0), s["text"],
                          font=fonts["accent"] if s["style"] != "normal" else font)[3]
            for s in ln
        ) if ln else main_size
        main_block_h += lh + line_spacing
    sub_block_h = 0
    for ln in sub_lines:
        lh = sub_size + 8
        if any(s["style"] == "pill" for s in ln):
            lh = sub_size + 20
        sub_block_h += lh + sub_spacing

    block_h = symbol_block + main_block_h + (sub_block_h + 20 if sub_lines else 0)
    y_start = int(size[1] * anchor_y - block_h / 2)
    y_start = max(int(size[1] * 0.07), min(y_start, size[1] - block_h - int(size[1] * 0.07)))

    text_x = margin_x + bar_gap + 8
    box_x1 = margin_x - 12
    box_y1 = y_start - 24
    box_x2 = size[0] - margin_x + 12
    box_y2 = y_start + block_h + 28

    _draw_gradient_scrim(overlay, size, (box_x1, box_y1, box_x2, box_y2), zone)
    draw = ImageDraw.Draw(overlay)
    _draw_accent_bar(draw, margin_x, box_y1 + 8, box_y2 - 8, palette["primary"])

    cy = y_start
    draw.text((text_x, cy), symbol, font=fonts["symbol"], fill=sym_color)
    cy += sym_h + 14

    for ln in main_lines:
        lh = _draw_rich_line(draw, text_x, cy, ln, fonts, palette)
        cy += lh + line_spacing

    if sub_lines:
        cy += 8
        sub_fonts = {"main": fonts["sub"], "accent": fonts["sub_accent"]}
        sub_palette = dict(palette)
        sub_palette["text"] = palette["text_muted"]
        for ln in sub_lines:
            lh = _draw_rich_line(
                draw, text_x, cy, ln, sub_fonts, sub_palette,
                pill_pad_x=10, pill_pad_y=5,
            )
            cy += lh + sub_spacing

    # Detalle: punto decorativo en color terciario
    dot_r = 5
    draw.ellipse(
        (size[0] - margin_x - dot_r * 2, box_y1 + 12,
         size[0] - margin_x, box_y1 + 12 + dot_r * 2),
        fill=_hex_to_rgba(palette["tertiary"], 220),
    )

    return Image.alpha_composite(canvas, overlay)


def render_slide_image(
    slide: dict,
    tipo: str,
    uploads_dir: Path,
    marca: Optional[dict] = None,
) -> Optional[Image.Image]:
    """Compone un slide: fondo + copy. None si falta imagen."""
    path = _resolve_local_path(slide.get("archivo_url") or "", uploads_dir)
    if not path:
        return None

    size = _canvas_size(tipo)
    try:
        bg = Image.open(path).convert("RGBA")
    except OSError:
        return None

    bg = bg.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 255))
    canvas.paste(bg, (0, 0))

    if slide.get("texto_en_imagen"):
        return canvas.convert("RGB")

    main_text = (slide.get("main_text") or "").strip()
    secondary = (slide.get("secondary_text") or "").strip()
    if not main_text and not secondary:
        return canvas.convert("RGB")

    text_zone = slide.get("text_zone") or {}

    if tipo == "historia":
        composed = _draw_historia_overlay(canvas, slide, marca, text_zone)
        return composed.convert("RGB")

    # Carrusel / fallback: overlay simple
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    zone = text_zone.get("zone") or "center"
    anchor_y = ZONE_ANCHORS.get(zone, ZONE_ANCHORS["center"])
    margin_x = int(size[0] * 0.08)
    max_width = size[0] - 2 * margin_x
    main_font = _load_font(52, bold=True)
    sub_font = _load_font(34, bold=False)
    fill = _text_color_for_zone(text_zone, marca or {})
    main_lines = _wrap_text(main_text, main_font, max_width, draw)
    sub_lines = _wrap_text(secondary, sub_font, max_width, draw) if secondary else []
    line_h_main = 58
    line_h_sub = 42
    block_h = len(main_lines) * line_h_main + (len(sub_lines) * line_h_sub if sub_lines else 0) + 40
    y_start = int(size[1] * anchor_y - block_h / 2)
    y_start = max(int(size[1] * 0.06), min(y_start, size[1] - block_h - int(size[1] * 0.06)))
    pad = 28
    draw.rectangle(
        (margin_x - pad, y_start - pad, size[0] - margin_x + pad, y_start + block_h + pad),
        fill=(0, 0, 0, 140),
    )
    _draw_text_block(draw, main_lines, (margin_x, y_start), main_font, fill, max_width)
    if sub_lines:
        sub_y = y_start + len(main_lines) * line_h_main + 12
        sub_fill = fill if fill != "#FFFFFF" else "#E2E8F0"
        _draw_text_block(draw, sub_lines, (margin_x, sub_y), sub_font, sub_fill, max_width)
    composed = Image.alpha_composite(canvas, overlay)
    return composed.convert("RGB")


def render_publicacion_visual(
    cliente_id: str,
    pub_id: str,
    pub: dict,
    uploads_dir: Path,
    marca: Optional[dict] = None,
) -> dict:
    """
    Renderiza todos los slides con imagen y guarda PNG + ZIP.
    Devuelve metadata para produccion_json['rendered'].
    """
    prod = pub.get("produccion_json") or {}
    if isinstance(prod, str):
        import json
        try:
            prod = json.loads(prod)
        except Exception:
            prod = {}

    slides = prod.get("slides") or []
    tipo = pub.get("tipo") or "carrusel"
    modo_visual = prod.get("modo_visual") or ""

    # Carruseles en modo "fondo_limpio" (KIE genera solo el fondo, sin texto)
    # se componen con Claude + Playwright, no con este overlay de Pillow.
    # Ver docs/protocolo-generacion-imagenes-ia.md — Gemini no aplicaba el
    # scrim de contraste de forma consistente en pruebas reales (2026-09-01).
    if tipo == "carrusel" and modo_visual == "fondo_limpio":
        from core.claude_slide_renderer import render_publicacion_visual_claude
        return render_publicacion_visual_claude(cliente_id, pub_id, pub, uploads_dir, marca)
    out_dir = uploads_dir / "renderizados" / pub_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rendered: list[dict] = []
    png_paths: list[Path] = []

    for idx, slide in enumerate(slides):
        s = dict(slide)
        if modo_visual == "texto_integrado" and not s.get("texto_en_imagen"):
            s["texto_en_imagen"] = s.get("image_source") == "generada_ia"
        img = render_slide_image(s, tipo, uploads_dir, marca)
        if img is None:
            continue
        num = slide.get("slide_number") or (idx + 1)
        fname = f"slide-{int(num):02d}.png"
        dest = out_dir / fname
        img.save(dest, "PNG", optimize=True)
        rendered.append({
            "slide_number": num,
            "role": slide.get("role", ""),
            "filename": fname,
        })
        png_paths.append(dest)

    zip_name = f"carrusel-{pub_id[:8]}.zip" if tipo == "carrusel" else f"historia-{pub_id[:8]}.zip"
    zip_path = out_dir / zip_name
    if png_paths:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in png_paths:
                zf.write(p, p.name)

    return {
        "rendered_at": datetime.now().isoformat(),
        "tipo": tipo,
        "slides": rendered,
        "zip_filename": zip_name,
        "total": len(rendered),
        "pendientes": max(0, len(slides) - len(rendered)),
    }
