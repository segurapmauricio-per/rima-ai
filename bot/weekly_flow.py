"""
bot/weekly_flow.py
==================
Conecta el WeeklyAgent con Telegram.

Formato callback_data (máx 64 bytes):
  wf:{tipo}:{brand}:{week}:{datos}

tipos:
  s  = story         datos: "{idx},{opcion}"  0=A, 1=B, 9=ajustar
  C  = carousel ref  datos: "{idx},{ref_idx}" 9=cambiar tema
  c  = carousel copy datos: "{idx}" o "{idx},ajustar"
  R  = reel ref      datos: "{idx},{ref_idx}" 9=cambiar tema
  r  = reel copy     datos: "{idx}" o "{idx},ajustar"
  m  = material      datos: "{item_id},pub" | "{item_id},adj" | "{item_id},rej"
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
from agents.weekly.agent import weekly_agent
import logging

log = logging.getLogger(__name__)

# ── Estado pendiente de ajuste (en memoria, persiste en JSON) ─────────────────
# Estructura: { chat_id: { "tipo": "s", "brand": ..., "week": ..., "idx": int } }
_AJUSTE_FILE = Path(__file__).parent.parent / "data" / "pending_adjustments.json"

def _load_pending() -> dict:
    if _AJUSTE_FILE.exists():
        try:
            return json.loads(_AJUSTE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def _save_pending(data: dict):
    _AJUSTE_FILE.parent.mkdir(exist_ok=True)
    _AJUSTE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def set_pending_adjustment(chat_id: int, context: dict):
    """Marca que el bot está esperando texto de ajuste de este cliente."""
    p = _load_pending()
    p[str(chat_id)] = context
    _save_pending(p)

def get_pending_adjustment(chat_id: int) -> dict | None:
    """Devuelve el contexto de ajuste pendiente si existe."""
    return _load_pending().get(str(chat_id))

def clear_pending_adjustment(chat_id: int):
    p = _load_pending()
    p.pop(str(chat_id), None)
    _save_pending(p)


# ── Iconos por tipo de contenido ──────────────────────────────────────────────
TIPO_ICONS = {
    "venta":        "💰 [VENTA]",
    "educacion":    "🎓 [EDUCACIÓN]",
    "educación":    "🎓 [EDUCACIÓN]",
    "conexion":     "❤️ [CONEXIÓN]",
    "conexión":     "❤️ [CONEXIÓN]",
    "tips":         "💡 [TIPS]",
    "lead_magnet":  "🎁 [LEAD MAGNET]",
    "testimonio":   "⭐ [TESTIMONIO]",
    "default":      "📌",
}

def _tipo_label(slot: dict) -> str:
    t = (slot.get("content_type") or slot.get("tipo_contenido") or
         slot.get("categoria") or "default").lower().replace(" ", "_")
    return TIPO_ICONS.get(t, TIPO_ICONS["default"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cb(tipo: str, brand: str, week: str, datos: str) -> str:
    s = f"wf:{tipo}:{brand}:{week}:{datos}"
    if len(s) > 64:
        # Truncar brand si es necesario
        s = f"wf:{tipo}:{brand[:8]}:{week}:{datos}"
    return s

def parse_weekly_callback(data: str) -> dict | None:
    if not data.startswith("wf:"):
        return None
    parts = data.split(":", 4)
    if len(parts) < 5:
        return None
    return {
        "tipo":  parts[1],
        "brand": parts[2],
        "week":  parts[3],
        "datos": parts[4],
    }


# ── Enviar mensajes por etapa ──────────────────────────────────────────────────

async def enviar_historia(app: Application, chat_id: int,
                          brand: str, week: str,
                          story_idx: int, total: int,
                          slot: dict, proposals: list):
    tipo_label = _tipo_label(slot)
    fecha = slot.get("date", "")

    header = f"🖼 *{tipo_label} Historia {story_idx + 1}/{total}* — {fecha}\n\n"

    lines = []
    for i, p in enumerate(proposals[:2]):
        letra = "A" if i == 0 else "B"
        copy  = p.get("copy", p.get("text", str(p)))[:280]
        lines.append(f"*Opción {letra}:*\n{copy}")

    texto = header + "\n\n".join(lines) + "\n\n¿Cuál prefieres?"

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Opción A",
                callback_data=_cb("s", brand, week, f"{story_idx},0")),
            InlineKeyboardButton("✅ Opción B",
                callback_data=_cb("s", brand, week, f"{story_idx},1")),
        ],
        [
            InlineKeyboardButton("✏️ Ajustar",
                callback_data=_cb("s", brand, week, f"{story_idx},9")),
        ]
    ])

    await app.bot.send_message(
        chat_id=chat_id, text=texto,
        parse_mode="Markdown", reply_markup=teclado
    )


async def enviar_referentes_carrusel(app: Application, chat_id: int,
                                      brand: str, week: str,
                                      carousel_idx: int, total: int,
                                      slot: dict, opciones: list):
    tipo_label = _tipo_label(slot)
    fecha = slot.get("date", "")
    tema  = slot.get("topic", slot.get("tema", ""))

    header = (f"🎠 *{tipo_label} Carrusel {carousel_idx + 1}/{total}* — {fecha}\n"
              f"_{tema}_\n\n*¿Qué estilo modelamos?*\n\n")

    botones = []
    lines   = []
    for i, ref in enumerate(opciones[:2]):
        n       = i + 1
        cuenta  = ref.get("username", ref.get("account", f"Ref {n}"))
        views   = ref.get("views", 0)
        fuerza  = ref.get("engagement_score", ref.get("fuerza", 0))
        hook    = ref.get("hook", ref.get("caption", ""))[:80]
        views_k = f"{int(views/1000)}K" if views >= 1000 else str(views)

        lines.append(
            f"*{n}️⃣ @{cuenta}*\n"
            f"   {views_k} views · Fuerza {round(float(fuerza), 1)}\n"
            f"   _\"{hook}\"_"
        )
        botones.append(
            InlineKeyboardButton(f"{n}️⃣ Este",
                callback_data=_cb("C", brand, week, f"{carousel_idx},{i}"))
        )

    teclado = InlineKeyboardMarkup([
        botones,
        [InlineKeyboardButton("🎯 Cambiar tema",
            callback_data=_cb("C", brand, week, f"{carousel_idx},9"))]
    ])

    await app.bot.send_message(
        chat_id=chat_id,
        text=header + "\n\n".join(lines),
        parse_mode="Markdown", reply_markup=teclado
    )


async def enviar_copy_carrusel(app: Application, chat_id: int,
                                brand: str, week: str,
                                carousel_idx: int, slides: list, slot: dict = None):
    tipo_label = _tipo_label(slot or {})
    header = f"🎠 *{tipo_label} Carrusel {carousel_idx + 1} — Copy generado*\n\n"

    lines = []
    for i, slide in enumerate(slides[:7]):
        titulo = slide.get("titulo", slide.get("title", f"Slide {i+1}"))
        cuerpo = slide.get("cuerpo", slide.get("body", ""))[:120]
        lines.append(f"*Slide {i+1}:* {titulo}\n_{cuerpo}_")

    texto = header + "\n\n".join(lines[:5])
    if len(slides) > 5:
        texto += f"\n\n_...y {len(slides)-5} slides más_"

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprobar",
                callback_data=_cb("c", brand, week, str(carousel_idx))),
            InlineKeyboardButton("✏️ Ajustar",
                callback_data=_cb("c", brand, week, f"{carousel_idx},9")),
        ]
    ])

    await app.bot.send_message(
        chat_id=chat_id, text=texto,
        parse_mode="Markdown", reply_markup=teclado
    )


async def enviar_referentes_reel(app: Application, chat_id: int,
                                  brand: str, week: str,
                                  reel_idx: int, total: int,
                                  slot: dict, opciones: list):
    tipo_label = _tipo_label(slot)
    fecha = slot.get("date", "")
    tema  = slot.get("topic", slot.get("tema", ""))

    header = (f"🎬 *{tipo_label} Reel {reel_idx + 1}/{total}* — {fecha}\n"
              f"_{tema}_\n\n*Top referentes:*\n\n")

    botones_fila = []
    lines        = []
    for i, ref in enumerate(opciones[:3]):
        n      = i + 1
        cuenta = ref.get("username", ref.get("account", f"Ref {n}"))
        fuerza = ref.get("engagement_score", ref.get("fuerza", 0))
        hook   = ref.get("hook", ref.get("caption", ""))[:80]

        lines.append(
            f"*{n}️⃣ @{cuenta}* · Fuerza {round(float(fuerza), 1)}\n"
            f"   _\"{hook}\"_"
        )
        botones_fila.append(
            InlineKeyboardButton(f"{n}️⃣",
                callback_data=_cb("R", brand, week, f"{reel_idx},{i}"))
        )

    teclado = InlineKeyboardMarkup([
        botones_fila,
        [InlineKeyboardButton("🎯 Cambiar tema",
            callback_data=_cb("R", brand, week, f"{reel_idx},9"))]
    ])

    await app.bot.send_message(
        chat_id=chat_id,
        text=header + "\n\n".join(lines),
        parse_mode="Markdown", reply_markup=teclado
    )


async def enviar_idea_reel(app: Application, chat_id: int,
                            brand: str, week: str,
                            reel_idx: int, idea: dict, slot: dict = None):
    tipo_label = _tipo_label(slot or {})
    titulo   = idea.get("titulo", idea.get("title", "Idea"))
    hook     = idea.get("hook", "")[:200]
    cta      = idea.get("cta", "")[:100]
    duracion = idea.get("duracion", "15-25 seg")

    texto = (
        f"🎬 *{tipo_label} Reel {reel_idx + 1} — Idea generada*\n\n"
        f"*Título:* {titulo}\n\n"
        f"*Hook (primeros 3 seg):*\n{hook}\n\n"
        f"*CTA:* {cta}\n\n"
        f"⏱ {duracion}"
    )

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprobar",
                callback_data=_cb("r", brand, week, str(reel_idx))),
            InlineKeyboardButton("✏️ Ajustar",
                callback_data=_cb("r", brand, week, f"{reel_idx},9")),
        ]
    ])

    await app.bot.send_message(
        chat_id=chat_id, text=texto,
        parse_mode="Markdown", reply_markup=teclado
    )


# ── Validación del material final ─────────────────────────────────────────────

async def enviar_material_para_validar(app: Application, chat_id: int,
                                        item_id: str, titulo: str,
                                        tipo_contenido: str,
                                        media_url: str = None,
                                        caption: str = None):
    """
    Envía el material final (imagen o video) para aprobación antes de publicar.
    Llamado desde el dashboard o automáticamente cuando el asset está listo.
    """
    tipo_label = TIPO_ICONS.get(tipo_contenido.lower().replace(" ", "_"),
                                 TIPO_ICONS["default"])

    texto = (
        f"✨ *{tipo_label} Material listo para publicar*\n\n"
        f"*{titulo}*\n"
    )
    if caption:
        texto += f"\n_{caption[:200]}_\n"

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Publicar",
                callback_data=f"wf:m:x:x:{item_id[:20]},pub"),
            InlineKeyboardButton("✏️ Ajustar diseño",
                callback_data=f"wf:m:x:x:{item_id[:20]},adj"),
        ],
        [
            InlineKeyboardButton("❌ Rechazar",
                callback_data=f"wf:m:x:x:{item_id[:20]},rej"),
        ]
    ])

    if media_url and media_url.endswith((".jpg", ".jpeg", ".png", ".webp")):
        try:
            await app.bot.send_photo(
                chat_id=chat_id,
                photo=media_url,
                caption=texto,
                parse_mode="Markdown",
                reply_markup=teclado
            )
            return
        except Exception:
            pass  # fallback a texto si falla la foto

    if media_url and media_url.endswith((".mp4", ".mov")):
        try:
            await app.bot.send_video(
                chat_id=chat_id,
                video=media_url,
                caption=texto,
                parse_mode="Markdown",
                reply_markup=teclado
            )
            return
        except Exception:
            pass

    # Fallback: solo texto
    await app.bot.send_message(
        chat_id=chat_id, text=texto,
        parse_mode="Markdown", reply_markup=teclado
    )


# ── Flujo de ajuste con feedback del cliente ──────────────────────────────────

async def procesar_ajuste(app: Application, chat_id: int,
                           feedback: str, pending: dict):
    """
    Recibe el feedback escrito por el cliente y regenera la pieza.
    `pending` viene de get_pending_adjustment().
    """
    tipo  = pending.get("tipo")
    brand = pending.get("brand")
    week  = pending.get("week")
    idx   = pending.get("idx", 0)
    slot  = pending.get("slot", {})

    clear_pending_adjustment(chat_id)

    await app.bot.send_message(
        chat_id=chat_id,
        text=f"✏️ Regenerando con tu feedback...\n\n_{feedback[:100]}_",
        parse_mode="Markdown"
    )

    try:
        if tipo == "s":
            # Regenerar historia con feedback
            from agents.story_copy.agent import story_copy_agent
            from core.client_store import load_brief
            brief = load_brief(brand) or {}
            story_copy_agent.apply_feedback(brand, feedback, {})
            result = weekly_agent.next_story(brand, week)
            proposals = result.get("proposals", [])
            total = result.get("total_stories", 1)
            await enviar_historia(app, chat_id, brand, week, idx, total, slot, proposals)

        elif tipo in ("c", "C"):
            from agents.carousel_copy.agent import carousel_copy_agent
            carousel_copy_agent.apply_feedback(brand, feedback)
            result = weekly_agent.next_carousel(brand, week)
            await enviar_referentes_carrusel(
                app, chat_id, brand, week,
                result.get("carousel_index", idx),
                result.get("total_carousels", 1),
                result.get("slot", slot),
                result.get("referent_options", [])
            )

        elif tipo in ("r", "R"):
            from agents.reel_copy.agent import reel_copy_agent
            reel_copy_agent.apply_feedback(brand, feedback)
            result = weekly_agent.next_reel(brand, week)
            await enviar_referentes_reel(
                app, chat_id, brand, week,
                result.get("reel_index", idx),
                result.get("total_reels", 1),
                result.get("slot", slot),
                result.get("referent_options", [])
            )
        else:
            await app.bot.send_message(
                chat_id=chat_id,
                text="Feedback guardado. El equipo RIMA lo revisará."
            )

    except Exception as e:
        log.error(f"Error regenerando con feedback: {e}")
        await app.bot.send_message(
            chat_id=chat_id,
            text="Hubo un error regenerando. El equipo RIMA lo revisará pronto."
        )


# ── Resumen final ─────────────────────────────────────────────────────────────

async def enviar_resumen_semanal(app: Application, chat_id: int,
                                  brand: str, week: str):
    await app.bot.send_message(
        chat_id=chat_id,
        text=(
            "🎉 *¡Todo el copy de la semana está aprobado!*\n\n"
            "RIMA está procesando los materiales finales.\n"
            "✅ Historias aprobadas\n"
            "✅ Carruseles aprobados\n"
            "✅ Ideas de reels aprobadas\n\n"
            "Cuando los materiales estén listos te los mando aquí para revisión final.\n"
            "También puedes verlos desde tu dashboard."
        ),
        parse_mode="Markdown"
    )


# ── Handler principal ─────────────────────────────────────────────────────────

async def handle_weekly_callback(query, parsed: dict, app: Application):
    """Procesa callbacks del flujo semanal."""
    tipo  = parsed["tipo"]
    brand = parsed["brand"]
    week  = parsed["week"]
    datos = parsed["datos"]
    chat_id = query.message.chat_id

    await query.answer()

    # ── Material final (m) ────────────────────────────────────────────────────
    if tipo == "m":
        partes  = datos.split(",")
        item_id = partes[0]
        accion  = partes[1] if len(partes) > 1 else "pub"

        if accion == "pub":
            await query.edit_message_caption(
                caption="✅ *Material aprobado para publicar*\n\nRIMA lo programará.",
                parse_mode="Markdown"
            ) if query.message.caption else await query.edit_message_text(
                "✅ *Material aprobado para publicar*",
                parse_mode="Markdown"
            )
            # Actualizar estado en calendar
            from core.client_store import load_weekly_state, save_weekly_state
            # Notificar a main.py via API si es necesario (callback)

        elif accion == "adj":
            set_pending_adjustment(chat_id, {
                "tipo": "material", "item_id": item_id,
                "brand": brand, "week": week
            })
            await query.edit_message_text(
                "✏️ *Ajustar material*\n\n¿Qué quieres cambiar?\n"
                "• ¿El texto encima?\n• ¿Los colores?\n• ¿La imagen?\n\n"
                "Escríbeme y lo ajusto.",
                parse_mode="Markdown"
            )

        elif accion == "rej":
            await query.edit_message_text(
                "❌ *Material rechazado*\n\n"
                "Escríbeme qué no te gustó y lo regeneramos.",
                parse_mode="Markdown"
            )
        return

    # ── Historias (s) ─────────────────────────────────────────────────────────
    if tipo == "s":
        partes = datos.split(",")
        idx    = int(partes[0])
        opcion = int(partes[1])

        if opcion == 9:  # ajustar
            from core.client_store import load_weekly_state
            ws    = load_weekly_state(brand, week)
            slot  = (ws.get("stories") or [{}])[idx] if idx < len(ws.get("stories", [])) else {}
            set_pending_adjustment(chat_id, {
                "tipo": "s", "brand": brand, "week": week,
                "idx": idx, "slot": slot
            })
            await query.edit_message_text(
                f"✏️ *Ajustar Historia {idx+1}*\n\n"
                "¿Qué quieres cambiar?\n"
                "• ¿El tono? (más directo / más suave)\n"
                "• ¿Palabras específicas?\n"
                "• ¿El tema?\n\n"
                "Escríbeme y RIMA regenera al instante.",
                parse_mode="Markdown"
            )
            return

        # Aprobar opción A o B
        from core.client_store import load_weekly_state
        ws       = load_weekly_state(brand, week)
        stories  = ws.get("stories", [])
        total    = len(stories)
        slot     = stories[idx] if idx < len(stories) else {}

        result   = weekly_agent.next_story(brand, week)
        proposals = result.get("proposals", [{}, {}])
        chosen    = proposals[opcion] if opcion < len(proposals) else proposals[0]

        weekly_agent.approve_story(brand, week, idx, chosen)

        tipo_label = _tipo_label(slot)
        await query.edit_message_text(
            f"✅ *{tipo_label} Historia {idx+1}/{total} aprobada*\n\n"
            f"_{str(chosen.get('copy', chosen.get('text', '')))[:120]}_",
            parse_mode="Markdown"
        )

        # Siguiente historia o pasar a carruseles
        next_r = weekly_agent.next_story(brand, week)
        if next_r.get("done"):
            await app.bot.send_message(
                chat_id=chat_id,
                text="✅ *Historias completadas.* Pasamos a los carruseles...",
                parse_mode="Markdown"
            )
            nxt = weekly_agent.next_carousel(brand, week)
            if not nxt.get("done"):
                await enviar_referentes_carrusel(
                    app, chat_id, brand, week,
                    nxt["carousel_index"], nxt["total_carousels"],
                    nxt["slot"], nxt.get("referent_options", [])
                )
            else:
                # Sin carruseles, ir a reels
                nxt = weekly_agent.next_reel(brand, week)
                if not nxt.get("done"):
                    await enviar_referentes_reel(
                        app, chat_id, brand, week,
                        nxt["reel_index"], nxt["total_reels"],
                        nxt["slot"], nxt.get("referent_options", [])
                    )
                else:
                    await enviar_resumen_semanal(app, chat_id, brand, week)
        else:
            await enviar_historia(
                app, chat_id, brand, week,
                next_r["story_index"], next_r["total_stories"],
                next_r["slot"], next_r.get("proposals", [])
            )

    # ── Carousel — referente (C) ──────────────────────────────────────────────
    elif tipo == "C":
        partes  = datos.split(",")
        idx     = int(partes[0])
        ref_idx = int(partes[1])

        if ref_idx == 9:
            set_pending_adjustment(chat_id, {
                "tipo": "C", "brand": brand, "week": week, "idx": idx
            })
            await query.edit_message_text(
                f"🎯 *Carrusel {idx+1} — Cambiar tema*\n\n"
                "¿Sobre qué tema quieres el carrusel? Escríbeme.",
                parse_mode="Markdown"
            )
            return

        state_r  = weekly_agent.next_carousel(brand, week)
        opciones = state_r.get("referent_options", [])
        chosen   = opciones[ref_idx] if ref_idx < len(opciones) else {}

        copy_r = weekly_agent.approve_carousel_referent(brand, week, idx, chosen)

        await query.edit_message_text(
            f"✅ *Referente elegido.* Generando copy del carrusel...",
            parse_mode="Markdown"
        )

        from core.client_store import load_weekly_state
        ws   = load_weekly_state(brand, week)
        slot = (ws.get("carousels") or [])[idx] if idx < len(ws.get("carousels", [])) else {}

        await enviar_copy_carrusel(
            app, chat_id, brand, week, idx,
            copy_r.get("slides", []), slot
        )

    # ── Carousel — copy (c) ───────────────────────────────────────────────────
    elif tipo == "c":
        partes  = datos.split(",")
        idx     = int(partes[0])
        ajustar = len(partes) > 1 and partes[1] == "9"

        if ajustar:
            from core.client_store import load_weekly_state
            ws   = load_weekly_state(brand, week)
            slot = (ws.get("carousels") or [])[idx] if idx < len(ws.get("carousels", [])) else {}
            set_pending_adjustment(chat_id, {
                "tipo": "c", "brand": brand, "week": week,
                "idx": idx, "slot": slot
            })
            await query.edit_message_text(
                f"✏️ *Ajustar Carrusel {idx+1}*\n\n"
                "¿Qué cambiarías? (tono, slide específico, longitud...)\n\n"
                "Escríbeme y lo regenero.",
                parse_mode="Markdown"
            )
            return

        weekly_agent.approve_carousel_copy(brand, week, idx)
        await query.edit_message_text(
            f"✅ *Carrusel {idx+1} aprobado*", parse_mode="Markdown"
        )

        nxt = weekly_agent.next_carousel(brand, week)
        if nxt.get("done"):
            await app.bot.send_message(
                chat_id=chat_id,
                text="✅ *Carruseles listos.* Pasamos a los reels...",
                parse_mode="Markdown"
            )
            nxt = weekly_agent.next_reel(brand, week)
            if not nxt.get("done"):
                await enviar_referentes_reel(
                    app, chat_id, brand, week,
                    nxt["reel_index"], nxt["total_reels"],
                    nxt["slot"], nxt.get("referent_options", [])
                )
            else:
                await enviar_resumen_semanal(app, chat_id, brand, week)
        else:
            await enviar_referentes_carrusel(
                app, chat_id, brand, week,
                nxt["carousel_index"], nxt["total_carousels"],
                nxt["slot"], nxt.get("referent_options", [])
            )

    # ── Reel — referente (R) ──────────────────────────────────────────────────
    elif tipo == "R":
        partes  = datos.split(",")
        idx     = int(partes[0])
        ref_idx = int(partes[1])

        if ref_idx == 9:
            set_pending_adjustment(chat_id, {
                "tipo": "R", "brand": brand, "week": week, "idx": idx
            })
            await query.edit_message_text(
                f"🎯 *Reel {idx+1} — Cambiar tema*\n\n"
                "¿Sobre qué quieres este reel? Escríbeme el tema.",
                parse_mode="Markdown"
            )
            return

        state_r  = weekly_agent.next_reel(brand, week)
        opciones = state_r.get("referent_options", [])
        chosen   = opciones[ref_idx] if ref_idx < len(opciones) else {}

        from core.client_store import load_weekly_state
        ws   = load_weekly_state(brand, week)
        slot = (ws.get("reels") or [])[idx] if idx < len(ws.get("reels", [])) else {}

        idea_r = weekly_agent.approve_reel_referent(brand, week, idx, chosen)

        await query.edit_message_text(
            "✅ *Referente elegido.* Generando idea del reel...",
            parse_mode="Markdown"
        )
        await enviar_idea_reel(
            app, chat_id, brand, week, idx,
            idea_r.get("idea", {}), slot
        )

    # ── Reel — idea/copy (r) ──────────────────────────────────────────────────
    elif tipo == "r":
        partes  = datos.split(",")
        idx     = int(partes[0])
        ajustar = len(partes) > 1 and partes[1] == "9"

        if ajustar:
            from core.client_store import load_weekly_state
            ws   = load_weekly_state(brand, week)
            slot = (ws.get("reels") or [])[idx] if idx < len(ws.get("reels", [])) else {}
            set_pending_adjustment(chat_id, {
                "tipo": "r", "brand": brand, "week": week,
                "idx": idx, "slot": slot
            })
            await query.edit_message_text(
                f"✏️ *Ajustar Reel {idx+1}*\n\n"
                "¿Qué cambiarías? (hook, tema, CTA, tono...)\n\n"
                "Escríbeme y lo regenero.",
                parse_mode="Markdown"
            )
            return

        weekly_agent.approve_reel_copy(brand, week, idx)
        await query.edit_message_text(
            f"✅ *Reel {idx+1} aprobado*", parse_mode="Markdown"
        )

        nxt = weekly_agent.next_reel(brand, week)
        if nxt.get("done"):
            await enviar_resumen_semanal(app, chat_id, brand, week)
        else:
            await enviar_referentes_reel(
                app, chat_id, brand, week,
                nxt["reel_index"], nxt["total_reels"],
                nxt["slot"], nxt.get("referent_options", [])
            )


# ── Envío directo desde dashboard (bypass protocolo secuencial) ───────────────

async def enviar_item_directo(app: Application, chat_id: int,
                               item: dict, brand: str = ""):
    """
    Envía un ítem del calendario directamente a Telegram para validación.
    Llamado desde el botón "Enviar a Telegram" del dashboard.
    No sigue el protocolo secuencial — manda solo ese ítem.
    """
    item_id       = item.get("id", "")
    titulo        = item.get("title", "Contenido")
    tipo_contenido = item.get("content_type", item.get("type", "reel"))
    caption       = item.get("caption", "")
    tipo_label    = TIPO_ICONS.get(
        tipo_contenido.lower().replace(" ", "_"), TIPO_ICONS["default"]
    )
    fecha = item.get("date", "")

    # Si tiene slides (carrusel), mostrar preview
    slides = item.get("slides", [])
    if slides:
        lines = []
        for i, s in enumerate(slides[:4]):
            t = s.get("titulo", s.get("title", f"Slide {i+1}"))
            b = s.get("cuerpo", s.get("body", ""))[:80]
            lines.append(f"*Slide {i+1}:* {t}\n_{b}_")

        texto = (
            f"📋 *{tipo_label} {titulo}* — {fecha}\n\n"
            + "\n\n".join(lines)
            + (f"\n\n_...y {len(slides)-4} slides más_" if len(slides) > 4 else "")
        )
    else:
        texto = (
            f"📋 *{tipo_label} {titulo}* — {fecha}\n\n"
            f"_{caption[:300]}_" if caption else
            f"📋 *{tipo_label} {titulo}* — {fecha}"
        )

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprobar",
                callback_data=f"wf:m:x:x:{item_id[:20]},pub"),
            InlineKeyboardButton("✏️ Ajustar",
                callback_data=f"wf:m:x:x:{item_id[:20]},adj"),
        ],
        [
            InlineKeyboardButton("❌ Rechazar",
                callback_data=f"wf:m:x:x:{item_id[:20]},rej"),
        ]
    ])

    await app.bot.send_message(
        chat_id=chat_id,
        text=texto,
        parse_mode="Markdown",
        reply_markup=teclado
    )
