"""
Bot de Telegram de RIMA AI
- Los clientes escriben /start para vincularse
- RIMA les manda contenido para aprobar
- Responden con botones: Aprobar / Rechazar / Ajustar
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)

load_dotenv(override=True)

from bot.weekly_flow import (parse_weekly_callback, handle_weekly_callback,
                             get_pending_adjustment, clear_pending_adjustment,
                             procesar_ajuste)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATA_FILE  = Path(__file__).parent.parent / "data" / "rima_data.json"


# ── Helpers de datos ──────────────────────────────────────────────────────────

def load_data() -> dict:
    DATA_FILE.parent.mkdir(exist_ok=True)
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_data(data: dict):
    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def vincular_cliente(chat_id: int, username: str = None):
    """Guarda el chat_id de Telegram vinculado a un cliente."""
    d = load_data()
    d.setdefault("telegram_users", {})[str(chat_id)] = {
        "chat_id": chat_id,
        "username": username or "",
        "activo": True,
        "vinculado_en": int(time.time())
    }
    save_data(d)


def get_cliente_por_chat(chat_id: int) -> dict | None:
    d = load_data()
    return d.get("telegram_users", {}).get(str(chat_id))


# ── Comandos ──────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cliente escribe /start → RIMA lo vincula."""
    chat_id  = update.effective_chat.id
    username = update.effective_user.username or update.effective_user.first_name

    vincular_cliente(chat_id, username)

    await update.message.reply_text(
        f"¡Hola {username}! 👋\n\n"
        "Soy RIMA, tu asistente de marketing con IA.\n\n"
        "A través de este chat recibirás:\n"
        "✅ Tus reels y contenido para revisar\n"
        "✅ Guiones listos para grabar\n"
        "✅ Notificaciones cuando tu video esté listo\n\n"
        "Solo necesitas aprobar o pedir ajustes con un click.\n\n"
        "Tu cuenta está vinculada. ¡Listo para empezar! 🚀"
    )


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandos disponibles:\n\n"
        "/start — Vincular tu cuenta\n"
        "/estado — Ver estado de tus reels\n"
        "/ayuda — Ver esta ayuda\n\n"
        "También puedes escribirme cualquier mensaje y lo revisaré."
    )


async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado de los reels del cliente."""
    chat_id = update.effective_chat.id
    cliente = get_cliente_por_chat(chat_id)

    if not cliente:
        await update.message.reply_text(
            "No encontré tu cuenta. Escribe /start para vincularla."
        )
        return

    d = load_data()
    reels = d.get("reels", {})

    if not reels:
        await update.message.reply_text(
            "Aún no tienes reels esta semana. "
            "Tu equipo RIMA está preparando tu calendario 📅"
        )
        return

    texto = "📊 *Estado de tus Reels esta semana:*\n\n"
    iconos = {1: "🔵", 2: "🟡", 3: "🟠", 4: "✅"}

    for reel_id, reel in reels.items():
        state  = reel.get("state", {})
        step   = state.get("step", 1)
        nombre = reel_id.upper()
        icono  = iconos.get(step, "🔵")
        pasos  = {
            1: "Selección de guión",
            2: "Guión generado",
            3: "Videos pendientes",
            4: "Video final listo"
        }
        texto += f"{icono} *{nombre}*: {pasos.get(step, 'En proceso')}\n"

    await update.message.reply_text(texto, parse_mode="Markdown")


async def mensaje_libre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe todos los mensajes — maneja comandos y texto libre."""
    chat_id = update.effective_chat.id
    texto   = (update.message.text or "").strip()

    # Rutear comandos manualmente (fix para python-telegram-bot v22 + Python 3.14)
    if texto.startswith("/start"):
        await start(update, context)
        return
    if texto.startswith("/estado"):
        await estado(update, context)
        return
    if texto.startswith("/ayuda") or texto.startswith("/help"):
        await ayuda(update, context)
        return

    # ── Verificar si hay un ajuste pendiente ─────────────────────────────────
    pending = get_pending_adjustment(chat_id)
    if pending:
        await procesar_ajuste(context.application, chat_id, texto, pending)
        return

    # Mensaje libre
    cliente = get_cliente_por_chat(chat_id)
    if not cliente:
        await update.message.reply_text(
            "Primero vincúlate escribiendo /start"
        )
        return

    # Guardar el feedback del cliente
    d = load_data()
    d.setdefault("telegram_feedback", []).append({
        "chat_id": chat_id,
        "mensaje": texto,
    })
    save_data(d)

    await update.message.reply_text(
        "Recibido ✅ Tu comentario fue guardado.\n\n"
        "Comandos: /estado /ayuda"
    )


async def callback_aprobacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los botones — flujo semanal y reels individuales."""
    query = update.callback_query
    data  = query.data
    logging.info(f"CALLBACK recibido: {data}")
    print(f">>> CALLBACK: {data}")

    # ── Flujo semanal (wf:...) ─────────────────────────────────────────────────
    parsed = parse_weekly_callback(data)
    if parsed:
        await handle_weekly_callback(query, parsed, context.application)
        return

    # ── Flujo reel individual (aprobar:r1, rechazar:r1, ajustar:r1) ────────────
    await query.answer()
    partes = data.split(":", 1)
    if len(partes) < 2:
        return
    accion, reel_id = partes
    chat_id = query.message.chat_id

    d = load_data()
    d.setdefault("reels", {}).setdefault(reel_id, {}).setdefault("state", {})

    if accion == "aprobar":
        d["reels"][reel_id]["state"]["script_approved"] = True
        d["reels"][reel_id]["state"]["step"] = 3
        save_data(d)
        await query.edit_message_text(
            f"✅ *{reel_id.upper()} aprobado*\n\n"
            "¡Perfecto! Ya puedes grabar los clips. "
            "Cuando los tengas, súbelos desde tu dashboard en RIMA.",
            parse_mode="Markdown"
        )

    elif accion == "rechazar":
        save_data(d)
        await query.edit_message_text(
            f"❌ *{reel_id.upper()} rechazado*\n\n"
            "Entendido. RIMA generará una nueva propuesta. "
            "¿Qué no te gustó? Escríbeme y lo ajustamos.",
            parse_mode="Markdown"
        )

    elif accion == "ajustar":
        await query.edit_message_text(
            f"✏️ *Ajustar {reel_id.upper()}*\n\n"
            "Cuéntame qué cambiarías:\n"
            "• ¿El tono?\n• ¿El hook?\n• ¿El CTA?\n\n"
            "Escríbeme y RIMA lo ajusta al instante.",
            parse_mode="Markdown"
        )


# ── Función para enviar contenido a un cliente ────────────────────────────────

async def enviar_contenido_para_aprobar(
    app: Application,
    chat_id: int,
    reel_id: str,
    titulo: str,
    hook: str,
    copy: str
):
    """
    Llama a esta función desde main.py para mandar contenido al cliente.
    Ejemplo:
        await enviar_contenido_para_aprobar(app, 123456, "r1", "Rutina 5AM", "...", "...")
    """
    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprobar", callback_data=f"aprobar:{reel_id}"),
            InlineKeyboardButton("❌ Rechazar", callback_data=f"rechazar:{reel_id}"),
        ],
        [
            InlineKeyboardButton("✏️ Pedir ajuste", callback_data=f"ajustar:{reel_id}"),
        ]
    ])

    texto = (
        f"🎬 *{titulo}* — Revisión de guión\n\n"
        f"*Hook (primeros 3 seg):*\n{hook}\n\n"
        f"*Copy completo:*\n{copy}\n\n"
        "¿Apruebas este guión para grabar?"
    )

    await app.bot.send_message(
        chat_id=chat_id,
        text=texto,
        parse_mode="Markdown",
        reply_markup=teclado
    )


# ── Main ──────────────────────────────────────────────────────────────────────

async def debug_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Captura TODOS los updates para debug."""
    print(f">>> UPDATE: {update}")
    logging.info(f"UPDATE recibido: {update.update_id}")

def crear_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    # Handler debug — captura todo
    app.add_handler(MessageHandler(filters.ALL, debug_handler), group=-1)
    app.add_handler(CallbackQueryHandler(debug_handler), group=-1)
    # Handlers reales
    app.add_handler(MessageHandler(filters.TEXT, mensaje_libre))
    app.add_handler(CallbackQueryHandler(callback_aprobacion))
    return app


if __name__ == "__main__":
    print("🤖 Bot RIMA iniciando...")
    app = crear_app()
    print("✅ Bot activo — esperando mensajes. Ctrl+C para detener.")
    app.run_polling(allowed_updates=["message", "callback_query"])
