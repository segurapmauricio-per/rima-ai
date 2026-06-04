"""
bot/weekly_flow.py
==================
Conecta el WeeklyAgent con Telegram.

Formato callback_data (máx 64 bytes):
  wf:{tipo}:{brand}:{week}:{datos}

tipos:
  s  = story — datos: "{idx},{opcion}"  opcion: 0=A, 1=B, 9=ajustar
  C  = carousel referent — datos: "{idx},{ref_idx}"  ref_idx: 0,1,2; 9=cambiar tema
  c  = carousel copy — datos: "{idx}"  (aprobar) o "{idx},ajustar"
  R  = reel referent — datos: "{idx},{ref_idx}"  9=cambiar tema
  r  = reel copy — datos: "{idx}"  (aprobar) o "{idx},ajustar"
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
from agents.weekly.agent import weekly_agent
import logging

log = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _cb(tipo: str, brand: str, week: str, datos: str) -> str:
    """Construye callback_data respetando el límite de 64 bytes."""
    s = f"wf:{tipo}:{brand}:{week}:{datos}"
    assert len(s) <= 64, f"callback_data demasiado largo ({len(s)}): {s}"
    return s

def parse_weekly_callback(data: str) -> dict | None:
    """Parsea un callback_data de flujo semanal. Devuelve None si no es weekly."""
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
    """Manda las 2 propuestas de una historia para que el cliente elija."""
    fecha = slot.get("date", "")
    tipo  = slot.get("story_type", slot.get("categoria", "Historia"))

    header = f"🖼 *Historia {story_idx + 1}/{total}* — {fecha} ({tipo})\n\n"

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
    """Manda 2 referentes de carrusel para que el cliente elija cuál modelar."""
    fecha = slot.get("date", "")
    tema  = slot.get("topic", slot.get("tema", "Carrusel"))

    header = f"🎠 *Carrusel {carousel_idx + 1}/{total}* — {fecha}\n_{tema}_\n\n*¿Qué estilo modelamos?*\n\n"

    botones = []
    lines   = []
    for i, ref in enumerate(opciones[:2]):
        n        = i + 1
        cuenta   = ref.get("username", ref.get("account", f"Referente {n}"))
        views    = ref.get("views", 0)
        fuerza   = ref.get("engagement_score", ref.get("fuerza", 0))
        hook     = ref.get("hook", ref.get("caption", ""))[:80]
        views_k  = f"{int(views/1000)}K" if views >= 1000 else str(views)

        lines.append(
            f"*{n}️⃣ @{cuenta}*\n"
            f"   {views_k} views · Fuerza {round(float(fuerza),1)}\n"
            f"   _\"{hook}\"_"
        )
        botones.append(
            InlineKeyboardButton(f"{n}️⃣ Este",
                callback_data=_cb("C", brand, week, f"{carousel_idx},{i}"))
        )

    texto = header + "\n\n".join(lines)

    teclado = InlineKeyboardMarkup([
        botones,
        [InlineKeyboardButton("🎯 Cambiar tema",
            callback_data=_cb("C", brand, week, f"{carousel_idx},9"))]
    ])

    await app.bot.send_message(
        chat_id=chat_id, text=texto,
        parse_mode="Markdown", reply_markup=teclado
    )


async def enviar_copy_carrusel(app: Application, chat_id: int,
                                brand: str, week: str,
                                carousel_idx: int, slides: list):
    """Manda el copy generado del carrusel para aprobación final."""
    header = f"🎠 *Carrusel {carousel_idx + 1} — Copy generado*\n\n"

    lines = []
    for i, slide in enumerate(slides[:7]):
        titulo = slide.get("titulo", slide.get("title", f"Slide {i+1}"))
        cuerpo = slide.get("cuerpo", slide.get("body", ""))[:120]
        lines.append(f"*Slide {i+1}:* {titulo}\n_{cuerpo}_")

    texto = header + "\n\n".join(lines[:5])  # preview primeros 5 slides
    if len(slides) > 5:
        texto += f"\n\n_...y {len(slides)-5} slides más_"

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprobar",
                callback_data=_cb("c", brand, week, str(carousel_idx))),
            InlineKeyboardButton("✏️ Ajustar",
                callback_data=_cb("c", brand, week, f"{carousel_idx},ajustar")),
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
    """Manda 3 referentes de reel para que el cliente elija."""
    fecha = slot.get("date", "")
    tema  = slot.get("topic", slot.get("tema", "Reel"))

    header = f"🎬 *Reel {reel_idx + 1}/{total}* — {fecha}\n_{tema}_\n\n*Top referentes de la semana:*\n\n"

    botones_fila = []
    lines        = []
    for i, ref in enumerate(opciones[:3]):
        n       = i + 1
        cuenta  = ref.get("username", ref.get("account", f"Ref {n}"))
        fuerza  = ref.get("engagement_score", ref.get("fuerza", 0))
        hook    = ref.get("hook", ref.get("caption", ""))[:80]

        lines.append(
            f"*{n}️⃣ @{cuenta}* · Fuerza {round(float(fuerza),1)}\n"
            f"   _\"{hook}\"_"
        )
        botones_fila.append(
            InlineKeyboardButton(f"{n}️⃣",
                callback_data=_cb("R", brand, week, f"{reel_idx},{i}"))
        )

    texto = header + "\n\n".join(lines)

    teclado = InlineKeyboardMarkup([
        botones_fila,
        [InlineKeyboardButton("🎯 Cambiar tema",
            callback_data=_cb("R", brand, week, f"{reel_idx},9"))]
    ])

    await app.bot.send_message(
        chat_id=chat_id, text=texto,
        parse_mode="Markdown", reply_markup=teclado
    )


async def enviar_idea_reel(app: Application, chat_id: int,
                            brand: str, week: str,
                            reel_idx: int, idea: dict):
    """Manda la idea del reel generada para aprobación."""
    titulo = idea.get("titulo", idea.get("title", "Idea"))
    hook   = idea.get("hook", "")[:200]
    cta    = idea.get("cta", "")[:100]
    duracion = idea.get("duracion", "15-25 seg")

    texto = (
        f"🎬 *Reel {reel_idx + 1} — Idea generada*\n\n"
        f"*Título:* {titulo}\n\n"
        f"*Hook (primeros 3 seg):*\n{hook}\n\n"
        f"*CTA:* {cta}\n\n"
        f"*Duración estimada:* {duracion}"
    )

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprobar",
                callback_data=_cb("r", brand, week, str(reel_idx))),
            InlineKeyboardButton("✏️ Ajustar",
                callback_data=_cb("r", brand, week, f"{reel_idx},ajustar")),
        ]
    ])

    await app.bot.send_message(
        chat_id=chat_id, text=texto,
        parse_mode="Markdown", reply_markup=teclado
    )


async def enviar_resumen_semanal(app: Application, chat_id: int,
                                  brand: str, week: str):
    """Manda un resumen cuando toda la etapa de copy está aprobada."""
    await app.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🎉 *¡Todo el copy de la semana está aprobado!*\n\n"
            f"RIMA ya tiene todo listo para producción:\n"
            f"✅ Historias aprobadas\n"
            f"✅ Carruseles aprobados\n"
            f"✅ Ideas de reels aprobadas\n\n"
            f"Ahora graba tus clips y súbelos desde el dashboard.\n"
            f"Cuando subas los clips, RIMA edita el video automáticamente."
        ),
        parse_mode="Markdown"
    )


async def pedir_ajuste_texto(app: Application, chat_id: int,
                              tipo_pieza: str, brand: str, week: str):
    """Le pide al cliente que escriba qué quiere ajustar."""
    await app.bot.send_message(
        chat_id=chat_id,
        text=(
            f"✏️ *Ajustar {tipo_pieza}*\n\n"
            f"Cuéntame qué cambiarías:\n"
            f"• ¿El tono?\n• ¿El tema?\n• ¿Algo específico del copy?\n\n"
            f"Escríbelo y RIMA lo regenera al instante."
        ),
        parse_mode="Markdown"
    )


# ── Handler principal de callbacks semanales ──────────────────────────────────

async def handle_weekly_callback(query, parsed: dict, app: Application):
    """
    Procesa un callback de flujo semanal y avanza al siguiente paso.
    `parsed` viene de parse_weekly_callback().
    """
    tipo  = parsed["tipo"]
    brand = parsed["brand"]
    week  = parsed["week"]
    datos = parsed["datos"]
    chat_id = query.message.chat_id

    await query.answer()

    # ── Historias ──────────────────────────────────────────────────────────────
    if tipo == "s":
        idx, opcion = datos.split(",")
        idx    = int(idx)
        opcion = int(opcion)

        if opcion == 9:  # ajustar
            await query.edit_message_text(
                f"✏️ *Historia {idx+1} — Ajustar*\n\n"
                "¿Qué cambiarías? Escríbeme (tono, tema, palabras a evitar...)",
                parse_mode="Markdown"
            )
            await pedir_ajuste_texto(app, chat_id, f"Historia {idx+1}", brand, week)
            return

        # Aprobar opción A (0) o B (1)
        state = weekly_agent.get_weekly_status(brand, week)
        total = state["stories"]["total"]

        # Obtener las propuestas para saber cuál fue elegida
        from core.client_store import load_weekly_state
        ws = load_weekly_state(brand, week)
        stories = ws.get("stories", [])
        slot = stories[idx] if idx < len(stories) else {}

        # Regenerar propuestas para saber cuál eligió (o usar lo guardado)
        result = weekly_agent.next_story(brand, week)
        proposals = result.get("proposals", [{}, {}])
        chosen = proposals[opcion] if opcion < len(proposals) else proposals[0]

        weekly_agent.approve_story(brand, week, idx, chosen)

        await query.edit_message_text(
            f"✅ *Historia {idx+1}/{total} aprobada*\n\n"
            f"_{chosen.get('copy', chosen.get('text', ''))[:120]}_",
            parse_mode="Markdown"
        )

        # Enviar siguiente historia o avanzar etapa
        next_result = weekly_agent.next_story(brand, week)
        if next_result.get("done"):
            await app.bot.send_message(
                chat_id=chat_id,
                text="✅ *Todas las historias aprobadas.* Pasamos a los carruseles...",
                parse_mode="Markdown"
            )
            next_carousel = weekly_agent.next_carousel(brand, week)
            if not next_carousel.get("done"):
                await enviar_referentes_carrusel(
                    app, chat_id, brand, week,
                    next_carousel["carousel_index"],
                    next_carousel["total_carousels"],
                    next_carousel["slot"],
                    next_carousel.get("referent_options", [])
                )
        else:
            await enviar_historia(
                app, chat_id, brand, week,
                next_result["story_index"],
                next_result["total_stories"],
                next_result["slot"],
                next_result.get("proposals", [])
            )

    # ── Carrusel — elegir referente ────────────────────────────────────────────
    elif tipo == "C":
        idx, ref_idx = datos.split(",")
        idx     = int(idx)
        ref_idx = int(ref_idx)

        if ref_idx == 9:  # cambiar tema
            await query.edit_message_text(
                f"🎯 *Carrusel {idx+1} — Cambiar tema*\n\n"
                "¿Sobre qué tema quieres el carrusel esta semana? Escríbeme.",
                parse_mode="Markdown"
            )
            return

        # Obtener el referente elegido del estado guardado
        state_result = weekly_agent.next_carousel(brand, week)
        opciones = state_result.get("referent_options", [])
        chosen_ref = opciones[ref_idx] if ref_idx < len(opciones) else {}

        copy_result = weekly_agent.approve_carousel_referent(brand, week, idx, chosen_ref)

        await query.edit_message_text(
            f"✅ *Referente elegido para Carrusel {idx+1}*\n\n"
            f"Generando copy...",
            parse_mode="Markdown"
        )

        await enviar_copy_carrusel(
            app, chat_id, brand, week, idx,
            copy_result.get("slides", [])
        )

    # ── Carrusel — aprobar copy ────────────────────────────────────────────────
    elif tipo == "c":
        partes = datos.split(",")
        idx    = int(partes[0])
        ajustar = len(partes) > 1 and partes[1] == "ajustar"

        if ajustar:
            await query.edit_message_text(
                f"✏️ *Carrusel {idx+1} — Ajustar*\n\nEscríbeme qué cambiar.",
                parse_mode="Markdown"
            )
            return

        weekly_agent.approve_carousel_copy(brand, week, idx)

        await query.edit_message_text(
            f"✅ *Carrusel {idx+1} aprobado*", parse_mode="Markdown"
        )

        next_result = weekly_agent.next_carousel(brand, week)
        if next_result.get("done"):
            await app.bot.send_message(
                chat_id=chat_id,
                text="✅ *Carruseles listos.* Pasamos a los reels...",
                parse_mode="Markdown"
            )
            next_reel = weekly_agent.next_reel(brand, week)
            if not next_reel.get("done"):
                await enviar_referentes_reel(
                    app, chat_id, brand, week,
                    next_reel["reel_index"],
                    next_reel["total_reels"],
                    next_reel["slot"],
                    next_reel.get("referent_options", [])
                )
        else:
            await enviar_referentes_carrusel(
                app, chat_id, brand, week,
                next_result["carousel_index"],
                next_result["total_carousels"],
                next_result["slot"],
                next_result.get("referent_options", [])
            )

    # ── Reel — elegir referente ────────────────────────────────────────────────
    elif tipo == "R":
        idx, ref_idx = datos.split(",")
        idx     = int(idx)
        ref_idx = int(ref_idx)

        if ref_idx == 9:
            await query.edit_message_text(
                f"🎯 *Reel {idx+1} — Cambiar tema*\n\n"
                "¿Sobre qué quieres este reel? Escríbeme el tema.",
                parse_mode="Markdown"
            )
            return

        state_result = weekly_agent.next_reel(brand, week)
        opciones     = state_result.get("referent_options", [])
        chosen_ref   = opciones[ref_idx] if ref_idx < len(opciones) else {}

        idea_result = weekly_agent.approve_reel_referent(brand, week, idx, chosen_ref)

        await query.edit_message_text(
            f"✅ *Referente elegido para Reel {idx+1}*\n\nGenerando idea...",
            parse_mode="Markdown"
        )

        await enviar_idea_reel(
            app, chat_id, brand, week, idx,
            idea_result.get("idea", {})
        )

    # ── Reel — aprobar idea ────────────────────────────────────────────────────
    elif tipo == "r":
        partes  = datos.split(",")
        idx     = int(partes[0])
        ajustar = len(partes) > 1 and partes[1] == "ajustar"

        if ajustar:
            await query.edit_message_text(
                f"✏️ *Reel {idx+1} — Ajustar*\n\nEscríbeme qué cambiar.",
                parse_mode="Markdown"
            )
            return

        weekly_agent.approve_reel_copy(brand, week, idx)

        await query.edit_message_text(
            f"✅ *Reel {idx+1} aprobado*", parse_mode="Markdown"
        )

        next_result = weekly_agent.next_reel(brand, week)
        if next_result.get("done"):
            await enviar_resumen_semanal(app, chat_id, brand, week)
        else:
            await enviar_referentes_reel(
                app, chat_id, brand, week,
                next_result["reel_index"],
                next_result["total_reels"],
                next_result["slot"],
                next_result.get("referent_options", [])
            )
