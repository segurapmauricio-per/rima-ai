"""
Genera el calendario completo (reels + historias + carruseles)
con tipos psicológicos y fechas desde hoy en adelante.
"""
import json
import uuid
from pathlib import Path
from datetime import datetime, date, timedelta
from agents.content.agent import content_agent

DATA_FILE = Path("data/rima_data.json")

brief = {
    'business_name': 'FitBody Studio',
    'service': 'Entrenamiento personalizado para mujeres que quieren bajar de peso sin dietas extremas',
    'ideal_client': 'Mujeres de 28-45 anos, profesionales ocupadas, sin resultados duraderos',
    'problem': 'No tienen tiempo, han probado dietas que no funcionan',
    'main_result': 'Bajar 6-10 kg en 12 semanas',
    'price': '150.000 CLP/mes'
}

print("Generando calendario con Gemini...")
result = content_agent.run(brief)
reel_slots = result['calendar']
print(f"Reels generados: {len(reel_slots)}")

# ── Estructura semanal de tipos psicológicos ───────────────────────────────────
# Por día: qué tipo de contenido va y en qué formato
WEEKLY_STRUCTURE = [
    # (dia_semana 0=lun, formato, tipo_psicologico, content_type_label)
    (0, "reel",     "problema",    "Problema"),
    (1, "reel",     "problema",    "Problema"),
    (1, "historia", "conexion",    "Conexión"),
    (2, "reel",     "solucion",    "Solución"),
    (2, "carrusel", "educacion",   "Educación"),
    (3, "reel",     "testimonio",  "Testimonio"),
    (3, "historia", "lead_magnet", "Lead Magnet"),
    (4, "reel",     "mentalidad",  "Mentalidad"),
    (4, "historia", "venta",       "Venta"),
]

# Mapear tipo de reel a tipo psicológico
TIPO_A_PSICO = {
    "Problema":                          "problema",
    "Solución":                          "solucion",
    "Resultado de cliente / Prueba social": "testimonio",
    "Mentalidad o Proceso":              "mentalidad",
    "Mentalidad":                        "mentalidad",
    "Proceso":                           "mentalidad",
}

# Historias template por tipo psicológico
HISTORIA_HOOKS = {
    "conexion": [
        "Mi mañana real antes de entrenar — sin filtros ☕",
        "Lo que nadie te muestra detrás del proceso 📱",
        "Un día en mi vida siendo entrenadora y mamá 👩‍👧",
    ],
    "lead_magnet": [
        "Comenta GUIA y te mando el plan gratuito de 7 días 🎁",
        "Escribe RUTINA y te envío el entrenamiento completo 💪",
        "DM 'PLAN' y te mando el método paso a paso gratis 📋",
    ],
    "venta": [
        "Últimos 3 cupos del mes — programa premium 🔥",
        "Esta semana cerramos inscripciones. ¿Entras? 📩",
        "Resultados reales de esta semana 👇 ¿Cuándo empiezas tú?",
    ],
}

CARRUSEL_TEMAS = [
    "5 errores que te impiden bajar de peso (y cómo evitarlos)",
    "Por qué las dietas fallan — la ciencia detrás",
    "Cómo comer lo que quieres y seguir bajando de peso",
    "El método FitBody explicado paso a paso",
]

# ── Calcular fechas desde HOY ──────────────────────────────────────────────────
today = date.today()
# Encontrar el lunes de esta semana o el próximo lunes si ya pasó
days_since_monday = today.weekday()
this_monday = today - timedelta(days=days_since_monday)

items = []
reel_idx = 0
historia_counters = {"conexion": 0, "lead_magnet": 0, "venta": 0}
carrusel_idx = 0

for week in range(4):  # 4 semanas
    for day_offset, fmt, psico, psico_label in WEEKLY_STRUCTURE:
        item_date = this_monday + timedelta(weeks=week, days=day_offset)

        # Saltar fechas pasadas
        if item_date < today:
            continue

        item = {
            "id": str(uuid.uuid4()),
            "date": item_date.strftime("%Y-%m-%d"),
            "type": fmt,
            "content_type": psico,
            "content_type_label": psico_label,
            "status": "pendiente",
            "semana": week + 1,
            "dia": ["Lunes","Martes","Miércoles","Jueves","Viernes"][day_offset],
            "created_at": int(datetime.now().timestamp()),
            "hashtags": [],
        }

        if fmt == "reel" and reel_idx < len(reel_slots):
            slot = reel_slots[reel_idx]
            ideas = slot.get("ideas", [])
            main = ideas[0] if ideas else {}
            item["title"] = main.get("titulo", "Reel")
            item["caption"] = main.get("hook", "")
            item["development"] = main.get("development", "")
            item["cta"] = main.get("cta", "")
            item["format"] = main.get("format", "Talking head")
            item["all_ideas"] = ideas
            reel_idx += 1

        elif fmt == "historia":
            hooks = HISTORIA_HOOKS.get(psico, ["Historia del día"])
            c = historia_counters.get(psico, 0)
            hook = hooks[c % len(hooks)]
            historia_counters[psico] = c + 1
            item["title"] = hook
            item["caption"] = hook
            item["format"] = "Historia Instagram"

        elif fmt == "carrusel":
            tema = CARRUSEL_TEMAS[carrusel_idx % len(CARRUSEL_TEMAS)]
            carrusel_idx += 1
            item["title"] = tema
            item["caption"] = tema
            item["format"] = "Carrusel 7 slides"

        items.append(item)

# Ordenar por fecha
items.sort(key=lambda x: x["date"])

# Guardar en rima_data.json
data = {}
if DATA_FILE.exists():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

data["calendar_items"] = items
DATA_FILE.parent.mkdir(exist_ok=True)
DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"Calendario guardado: {len(items)} items (desde hoy {today})")
reels_n = sum(1 for i in items if i["type"] == "reel")
historias_n = sum(1 for i in items if i["type"] == "historia")
carruseles_n = sum(1 for i in items if i["type"] == "carrusel")
print(f"  Reels: {reels_n} | Historias: {historias_n} | Carruseles: {carruseles_n}")
print("\nRecarga el calendario en el browser (Ctrl+R)")
