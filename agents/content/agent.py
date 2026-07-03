from core.gemini_client import gemini
from core.brand_knowledge import CONTENIDO
import json
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta, date

SYSTEM_PROMPT = f"""Eres el Agente de Contenido de RIMA. Generas la ESTRATEGIA mensual de contenido
para negocios de servicios en LATAM — el plan de qué tipo de pieza va cada día y por qué,
NO el contenido final (eso lo arma el Agente Semanal con datos frescos de estudio de mercado).

Metodología que usas:

=== METODOLOGÍA CONTENIDO ===
{CONTENIDO[:5000]}

Reglas de generación (sos un planificador ESTRATÉGICO, no un copywriter):
- NO generas hooks, guiones, ideas desarrolladas ni CTAs — solo la intención estratégica de cada pieza
- Cada pieza define: formato (reel/carrusel), tipo de ángulo psicológico (Problema/Solución/Resultado/Proceso/Mentalidad),
  enfoque de negocio (Ventas/Educación/Conexión) y un ángulo estratégico de UNA línea (sin desarrollar contenido)
- VARÍA los días de la semana: evita que un mismo tipo de contenido siempre caiga el mismo día —
  la repetición predecible cansa a la audiencia y le quita naturalidad al plan
- Hablas SIEMPRE un nivel por encima del cliente objetivo (regla 80/20)
- Escribe en español LATAM"""

# Límites semanales por plan — fuente única: core/plan_limits.py::CONTENT_WEEKLY.
# (Antes había una copia local que podía divergir al cambiar un plan.)
from core.plan_limits import CONTENT_WEEKLY as PLAN_LIMITS

PLAN_DAYS = 30                    # ventana del plan: 30 días corridos anclados al lunes de esta semana
WEEK_DAYS = 7                     # bloque de programación alineado a semanas calendario (lun-dom)

# Pesos base de engagement por día (Lun=0 … Dom=6). Viernes/sábado elevados, no fijos.
_DAY_WEIGHT = [0.82, 0.88, 0.94, 1.00, 1.14, 1.18, 0.92]

# Sesgo por formato: reels/historias favorecen finde; carruseles mid-week (lectura).
_FORMAT_DAY_BIAS = {
    "reel":     [0.95, 0.98, 1.02, 1.05, 1.16, 1.20, 1.00],
    "carrusel": [1.05, 1.12, 1.16, 1.12, 1.00, 0.94, 0.88],
    "historia": [0.98, 1.00, 1.02, 1.05, 1.14, 1.18, 1.06],
}

# Cada bloque semanal rota qué días reciben el pico de engagement (evita patrón idéntico).
_WEEK_PEAK_ROTATION = [
    {4: 1.32, 5: 1.18},
    {5: 1.34, 3: 1.20},
    {4: 1.24, 2: 1.18, 5: 1.14},
    {3: 1.28, 5: 1.26, 4: 1.10},
]

CONTENT_TYPES = ["Problema", "Problema", "Solución", "Resultado", "Mentalidad"]
DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

STORIES_TEMPLATE = {
    "Lunes": "CTA informativo (presentar el programa/servicio)",
    "Martes": "Hand Raiser (lead magnet — 'Respondé [palabra] y te mando [recurso]')",
    "Miércoles": "Hand Raiser (segundo lead magnet de la semana)",
    "Jueves": "Libre / Awareness — victorias de clientes",
    "Viernes": "CTA informativo + urgencia suave",
    "Sábado": "Hand Raiser (lead magnet del fin de semana)",
    "Domingo": "Encuesta (Poll) + Cajita de preguntas (Q&A)",
}


class ContentAgent:
    def __init__(self):
        self.name = "content"

    def run(self, brand_brief: dict, market_research: str = None, month: str = None,
            enfoque: dict = None, cliente_id: str = None) -> dict:
        """
        brand_brief: dict estándar del negocio (incluye "plan": basico|pro|max)
        market_research: texto del análisis de referentes (opcional)
        month: ignorado para la planificación — ventana de 30 días anclada al
               lunes de esta semana; se guarda y muestra solo desde mañana.
        enfoque: {ventas, educacion, conexion} porcentajes
        cliente_id: si se pasa, guarda los slots en SQLite
        """
        business_name = brand_brief.get("business_name", "unknown")
        enfoque = self._normalize_enfoque(enfoque)

        plan_tier = (brand_brief.get("plan") or "pro").lower()
        if plan_tier == "basic":
            plan_tier = "basico"
        limits = PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["pro"])

        # start_date = ESTE lunes (semana calendario actual).
        # Si hoy es miércoles, start_date es el lunes de esta semana (pasado).
        # Los slots anteriores a mañana se saltan al guardar en DB — así la
        # semana 1 queda con contenido proporcional (jue-dom si hoy es miér)
        # y las semanas 2-5 se llenan completas. Sin este anclaje, la semana 1
        # estaría vacía hasta el próximo lunes.
        today = date.today()
        tomorrow = today + timedelta(days=1)
        start_date = today - timedelta(days=today.weekday())  # lunes de esta semana
        end_date = start_date + timedelta(days=PLAN_DAYS - 1)

        calendar = self._generate_strategy_plan(
            brand_brief, market_research, start_date, end_date, enfoque, limits
        )
        historias = self._generate_historias_plan(brand_brief, start_date, limits, enfoque)

        deleted_slots = 0
        if cliente_id:
            try:
                from core.db import delete_publicaciones_regenerables, init_db
                init_db(cliente_id)
                # Pasado + hoy: fuera del calendario visible
                deleted_past = delete_publicaciones_regenerables(
                    cliente_id,
                    end_date=today.strftime("%Y-%m-%d"),
                )
                # Mañana en adelante: reemplazar plan regenerable en la ventana
                deleted_forward = delete_publicaciones_regenerables(
                    cliente_id,
                    start_date=tomorrow.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d"),
                )
                deleted_slots = deleted_past + deleted_forward
                if deleted_slots:
                    print(f"[ContentAgent] Eliminados {deleted_slots} slots regenerables "
                          f"({deleted_past} pasado/hoy, {deleted_forward} ventana futura)")
            except Exception as e:
                print(f"[ContentAgent] Warning: no se pudo limpiar slots regenerables: {e}")
            self._save_to_db(cliente_id, calendar, historias, start_date, brand_brief, tomorrow)

        min_visible_offset = (tomorrow - start_date).days
        visible_calendar = [
            s for s in calendar
            if int(s.get("dia_offset", s.get("offset", 0))) >= min_visible_offset
        ]
        visible_historias = [
            s for s in historias
            if int(s.get("dia_offset", s.get("offset", 0))) >= min_visible_offset
        ]

        result = {
            "agent": self.name,
            "timestamp": datetime.now().isoformat(),
            "brand": business_name,
            "plan_tier": plan_tier,
            "limites_semanales": limits,
            "starts_on": start_date.strftime("%Y-%m-%d"),
            "visible_from": tomorrow.strftime("%Y-%m-%d"),
            "ends_on": end_date.strftime("%Y-%m-%d"),
            "total_piezas": len(visible_calendar) + len(visible_historias),
            "enfoque": enfoque,
            "calendar": visible_calendar,
            "historias_calendar": visible_historias,
            "used_market_research": bool(market_research),
            "deleted_slots": deleted_slots,
        }

        self._save(result, business_name, start_date.strftime("%Y-%m-%d"))
        return result

    def _save_to_db(self, cliente_id: str, calendar: list, historias: list,
                    start_date, brand_brief: dict, tomorrow: date) -> None:
        """Escribe slots estratégicos en SQLite. Solo fechas >= mañana."""
        try:
            from core.db import create_or_update_cliente, create_publicacion, update_publicacion_field, init_db, get_publicaciones
            from datetime import timedelta

            init_db(cliente_id)
            plan_db = (brand_brief.get("plan") or "pro").lower()
            if plan_db == "basic":
                plan_db = "basico"
            create_or_update_cliente(
                cliente_id=cliente_id,
                nombre=brand_brief.get("business_name", "Cliente"),
                plan=plan_db,
                ig_username=brand_brief.get("ig_username", ""),
                brief=brand_brief,
            )

            DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            MESES_NOMBRE = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                            "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

            def datos_de(offset):
                offset = max(0, int(offset or 0))
                f = start_date + timedelta(days=offset)
                mes_str = f"{MESES_NOMBRE[f.month - 1]} {f.year}"
                dia_nombre = DAY_NAMES[f.weekday()]
                semana = (offset // 7) + 1  # solo informativo/visual — NO es el ancla del plan
                return f.strftime("%Y-%m-%d"), mes_str, dia_nombre, semana

            tomorrow_str = tomorrow.strftime("%Y-%m-%d")
            created = 0

            def _week_key(fecha_str: str) -> tuple[str, str]:
                from core.week_quota import week_bounds_for_date
                return week_bounds_for_date(fecha_str)

            def _puede_crear(fecha_str: str, tipo_slot: str) -> bool:
                from core.week_quota import can_create_slot_for_week
                ws, we = _week_key(fecha_str)
                week_pubs = [
                    p for p in get_publicaciones(cliente_id)
                    if ws <= (p.get("fecha") or "") <= we
                ]
                return can_create_slot_for_week(
                    plan_db, week_pubs, tipo_slot,
                    date.fromisoformat(ws), date.fromisoformat(we),
                    tomorrow,
                )

            def _registrar_creado(fecha_str: str, tipo_slot: str) -> None:
                pass  # DB ya registra; no se necesita contador en memoria

            # Reels y carruseles — estrategia, sin copy
            for slot in calendar:
                offset = slot.get("dia_offset", slot.get("offset", 0))
                fecha_str, mes_str, dia_nombre, semana = datos_de(offset)

                if fecha_str < tomorrow_str:
                    continue  # no escribir al pasado

                tipo_slot = slot.get("formato", slot.get("tipo_formato", "reel"))
                if not _puede_crear(fecha_str, tipo_slot):
                    continue
                tematica = slot.get("tipo_contenido", slot.get("tipo", "Problema"))
                enfoque_pieza = slot.get("enfoque", "Ventas")
                angulo = slot.get("angulo_estrategico", "")

                pub = create_publicacion(cliente_id, {
                    "fecha": fecha_str,
                    "semana": semana,
                    "dia": dia_nombre,
                    "mes": mes_str,
                    "tipo": tipo_slot,
                    "tematica": tematica,
                    "enfoque": enfoque_pieza,
                    "status": "planificado",
                    "agente_origen": "monthly",
                })
                if angulo:
                    # Guardamos el ángulo estratégico como insumo para el agente semanal
                    # (no es copy final — es contexto para que arme el contenido con datos de mercado)
                    update_publicacion_field(cliente_id, pub["id"], "propuesta_json",
                                              {"angulo_estrategico": angulo, "fuente": "monthly_planner"})
                _registrar_creado(fecha_str, tipo_slot)
                created += 1

            # Historias — también estratégicas, sin copy desarrollado
            for slot in historias:
                offset = slot.get("dia_offset", slot.get("offset", 0))
                fecha_str, mes_str, dia_nombre, semana = datos_de(offset)

                if fecha_str < tomorrow_str:
                    continue  # no escribir al pasado

                if not _puede_crear(fecha_str, "historia"):
                    continue

                create_publicacion(cliente_id, {
                    "fecha": fecha_str,
                    "semana": semana,
                    "dia": dia_nombre,
                    "mes": mes_str,
                    "tipo": "historia",
                    "tematica": slot.get("tipo_historia", "Awareness"),
                    "enfoque": slot.get("enfoque", "Conexión"),
                    "status": "planificado",
                    "agente_origen": "monthly",
                })
                _registrar_creado(fecha_str, "historia")
                created += 1

            from core.week_quota import trim_excess_planificado
            trimmed = trim_excess_planificado(
                cliente_id, plan_db,
                start_date=tomorrow_str,
                end_date=(start_date + timedelta(days=PLAN_DAYS - 1)).strftime("%Y-%m-%d"),
                quota_from=tomorrow_str,
            )
            if trimmed:
                print(f"[ContentAgent] Recortados {trimmed} slots planificado sobrantes por cuota semanal")

            print(f"[ContentAgent] Guardados {created} slots en DB para {cliente_id} — ventana {start_date} +{PLAN_DAYS}d")
        except Exception as e:
            print(f"[ContentAgent] Warning: no se pudo guardar en DB: {e}")

    def _quota_for_days(self, limits: dict, days: int) -> tuple[int, int, int]:
        """Cuota prorrateada cuando el bloque tiene menos de 7 días."""
        if days >= WEEK_DAYS:
            return limits["reels"], limits["carruseles"], limits["historias"]
        ratio = days / WEEK_DAYS
        return (
            round(limits["reels"] * ratio),
            round(limits["carruseles"] * ratio),
            round(limits["historias"] * ratio),
        )

    def _get_weekly_blocks(self, limits: dict, start_date) -> list:
        """Semanas calendario (lun-dom) con cuota proporcional en la semana en curso.

        Coordina las cantidades del plan por semana real. En la semana en curso
        solo asigna días desde mañana hasta domingo (prorrateado). Semanas
        futuras reciben cuota completa.
        """
        tomorrow = date.today() + timedelta(days=1)
        plan_end = start_date + timedelta(days=PLAN_DAYS - 1)
        blocks = []
        week_mon = start_date
        week_num = 1

        while week_mon <= plan_end:
            week_sun = week_mon + timedelta(days=6)
            write_from = max(week_mon, tomorrow)
            write_to = min(week_sun, plan_end)
            if write_from <= write_to:
                writable_days = (write_to - write_from).days + 1
                reels, carrs, hist = self._quota_for_days(limits, writable_days)
                if reels or carrs or hist:
                    blocks.append({
                        "week": week_num,
                        "offset_start": (write_from - start_date).days,
                        "offset_end": (write_to - start_date).days,
                        "days": writable_days,
                        "reels": reels,
                        "carruseles": carrs,
                        "historias": hist,
                    })
            week_mon += timedelta(days=7)
            week_num += 1
        return blocks

    def _day_weight(self, offset: int, start_date, week_num: int, formato: str) -> float:
        """Peso de un día dentro del bloque: engagement base + formato + rotación semanal + ruido."""
        wd = (start_date + timedelta(days=offset)).weekday()
        w = _DAY_WEIGHT[wd] * _FORMAT_DAY_BIAS.get(formato, _DAY_WEIGHT)[wd]
        for peak_wd, boost in _WEEK_PEAK_ROTATION[(week_num - 1) % len(_WEEK_PEAK_ROTATION)].items():
            if wd == peak_wd:
                w *= boost
        w *= random.uniform(0.86, 1.14)
        return w

    def _pick_varied_offsets(self, offset_start: int, offset_end: int, count: int,
                             week_num: int, formato: str, start_date) -> list:
        """Elige `count` slots en el bloque. Si la cuota supera los días (ej. 9 reels/sem),
        permite 2+ piezas el mismo día priorizando viernes/sábado."""
        candidates = list(range(offset_start, offset_end + 1))
        if count <= 0:
            return []

        weights = [self._day_weight(o, start_date, week_num, formato) for o in candidates]
        chosen = []

        if count <= len(candidates):
            remaining = candidates[:]
            remaining_w = weights[:]
            for _ in range(count):
                total = sum(remaining_w)
                pick = random.uniform(0, total)
                cumulative = 0
                for i, (cand, w) in enumerate(zip(remaining, remaining_w)):
                    cumulative += w
                    if pick <= cumulative:
                        chosen.append(cand)
                        remaining.pop(i)
                        remaining_w.pop(i)
                        break
        else:
            chosen = list(candidates)
            for _ in range(count - len(candidates)):
                total = sum(weights)
                pick = random.uniform(0, total)
                cumulative = 0
                for cand, w in zip(candidates, weights):
                    cumulative += w
                    if pick <= cumulative:
                        chosen.append(cand)
                        break

        return sorted(chosen)

    def _normalize_enfoque(self, enfoque: dict) -> dict:
        enfoque = enfoque or {"ventas": 60, "educacion": 30, "conexion": 10}
        v = float(enfoque.get("ventas", 60))
        e = float(enfoque.get("educacion", 30))
        c = float(enfoque.get("conexion", 10))
        total = v + e + c
        if total <= 0:
            return {"ventas": 60, "educacion": 30, "conexion": 10}
        return {"ventas": v * 100 / total, "educacion": e * 100 / total, "conexion": c * 100 / total}

    def _split_by_percent(self, total: int, enfoque: dict) -> dict:
        """Repone conteos exactos (método de restos mayores) para que sumen `total`."""
        enf = self._normalize_enfoque(enfoque)
        keys = ("ventas", "educacion", "conexion")
        raw = {k: total * enf[k] / 100 for k in keys}
        floors = {k: int(raw[k]) for k in keys}
        remainder = total - sum(floors.values())
        ranked = sorted(((raw[k] - floors[k], k) for k in keys), reverse=True)
        for i in range(remainder):
            floors[ranked[i][1]] += 1
        return floors

    def _interleave(self, pools: list) -> list:
        """Mezcla listas en round-robin para evitar rachas del mismo enfoque."""
        pools = [list(p) for p in pools if p]
        if not pools:
            return []
        result = []
        indices = [0] * len(pools)
        total = sum(len(p) for p in pools)
        while len(result) < total:
            for pi, pool in enumerate(pools):
                if indices[pi] < len(pool):
                    result.append(pool[indices[pi]])
                    indices[pi] += 1
        return result

    def _tipo_assignments(self, total: int, enfoque: dict) -> list:
        """Asigna tipo + enfoque según % del cliente (60/30/10 recomendado o 40/30/30 autoridad)."""
        counts = self._split_by_percent(total, enfoque)
        n_problema = round(counts["ventas"] * 0.60)
        n_solucion = counts["ventas"] - n_problema
        n_resultado = round(counts["educacion"] * 0.65)
        n_proceso = counts["educacion"] - n_resultado
        n_mentalidad = counts["conexion"]
        ventas_pool = [("Problema", "Ventas")] * n_problema + [("Solución", "Ventas")] * n_solucion
        educa_pool = [("Resultado", "Educación")] * n_resultado + [("Proceso", "Educación")] * n_proceso
        conexion_pool = [("Mentalidad", "Conexión")] * n_mentalidad
        random.shuffle(ventas_pool)
        random.shuffle(educa_pool)
        random.shuffle(conexion_pool)
        pool = self._interleave([ventas_pool, educa_pool, conexion_pool])
        while len(pool) < total:
            pool.append(("Problema", "Ventas"))
        return pool[:total]

    def _enfoque_labels(self, total: int, enfoque: dict) -> list:
        """Etiquetas de enfoque de negocio (Ventas/Educación/Conexión) para historias."""
        counts = self._split_by_percent(total, enfoque)
        return self._interleave([
            ["Ventas"] * counts["ventas"],
            ["Educación"] * counts["educacion"],
            ["Conexión"] * counts["conexion"],
        ])

    def _build_reel_carrusel_skeleton(self, limits: dict, start_date, enfoque: dict) -> list:
        skeleton = []
        for block in self._get_weekly_blocks(limits, start_date):
            for o in self._pick_varied_offsets(
                block["offset_start"], block["offset_end"], block["reels"],
                block["week"], "reel", start_date
            ):
                skeleton.append({"dia_offset": o, "formato": "reel", "week": block["week"]})
            for o in self._pick_varied_offsets(
                block["offset_start"], block["offset_end"], block["carruseles"],
                block["week"], "carrusel", start_date
            ):
                skeleton.append({"dia_offset": o, "formato": "carrusel", "week": block["week"]})
        skeleton.sort(key=lambda s: (s["dia_offset"], s["formato"]))
        tipos = self._tipo_assignments(len(skeleton), enfoque)
        for i, sk in enumerate(skeleton):
            tipo, enf = tipos[i]
            sk["tipo_contenido"] = tipo
            sk["enfoque"] = enf
        return skeleton

    def _merge_strategy_skeleton(self, skeleton: list, parsed: list, enfoque: dict) -> list:
        """Alinea Gemini al esqueleto: tipo/enfoque vienen del % del cliente; Gemini solo aporta ángulo."""
        queues = defaultdict(list)
        for slot in parsed or []:
            if not isinstance(slot, dict):
                continue
            try:
                o = int(slot.get("dia_offset", slot.get("offset", 0)))
            except (TypeError, ValueError):
                continue
            fmt = (slot.get("formato") or slot.get("tipo_formato") or "reel").lower()
            queues[(max(0, min(PLAN_DAYS - 1, o)), fmt)].append(slot)

        used = defaultdict(int)
        result = []
        for sk in skeleton:
            key = (sk["dia_offset"], sk["formato"])
            idx = used[key]
            queue = queues.get(key, [])
            ps = queue[idx] if idx < len(queue) else {}
            used[key] += 1
            result.append({
                "dia_offset": sk["dia_offset"],
                "formato": sk["formato"],
                "tipo_contenido": sk["tipo_contenido"],
                "enfoque": sk["enfoque"],
                "angulo_estrategico": ps.get("angulo_estrategico")
                    or "Ángulo estratégico — completar con agente semanal",
            })
        return result

    def _generate_strategy_plan(self, brand_brief: dict, market_research: str, start_date,
                                end_date, enfoque: dict, limits: dict) -> list:
        """Genera la ESTRATEGIA de los próximos 30 días corridos (reels + carruseles, sin copy/ideas).
        El plan NO se organiza por "mes calendario" ni "semana 1" — cada pieza lleva
        un dia_offset (0 = lunes de esta semana .. 29 = último día de la ventana).
        Retorna slots: {dia_offset, formato, tipo_contenido, enfoque, angulo_estrategico}.
        """

        research_context = ""
        if market_research:
            research_context = f"""
ANÁLISIS DE REFERENTES DEL NICHO (úsalo como contexto estratégico, no para copiar contenido):
{market_research[:3000]}
"""

        enfoque = self._normalize_enfoque(enfoque)
        pct_ventas   = round(enfoque["ventas"])
        pct_educa    = round(enfoque["educacion"])
        pct_conexion = round(enfoque["conexion"])

        skeleton = self._build_reel_carrusel_skeleton(limits, start_date, enfoque)
        total = len(skeleton)
        blocks = self._get_weekly_blocks(limits, start_date)
        weekly_rules = "\n".join(
            f"  · Bloque {b['week']} (dia_offset {b['offset_start']}–{b['offset_end']}, {b['days']} días): "
            f"EXACTAMENTE {b['reels']} reels y {b['carruseles']} carruseles"
            for b in blocks
        )
        skeleton_lines = "\n".join(
            f"  - dia_offset {s['dia_offset']}, formato {s['formato']}, "
            f"tipo {s['tipo_contenido']}, enfoque {s['enfoque']}"
            for s in skeleton
        )
        counts = self._split_by_percent(total, enfoque)

        prompt = f"""
Genera la ESTRATEGIA de contenido (reels + carruseles) para los PRÓXIMOS 30 DÍAS CORRIDOS,
desde el {start_date.strftime('%d/%m/%Y')} hasta el {end_date.strftime('%d/%m/%Y')}.

REGLA DE PROGRAMACIÓN SEMANAL (OBLIGATORIA — no negociable):
Cada bloque semanal (lun-dom) debe cumplir la cuota del plan; el bloque 1 puede ser parcial
si la semana en curso ya empezó — respeta los dia_offset asignados.
{weekly_rules}

Los dia_offset, formato, tipo_contenido y enfoque de cada pieza YA ESTÁN DEFINIDOS — NO los cambies:
{skeleton_lines}

Tu trabajo: SOLO completá angulo_estrategico (1 línea) para cada pieza según su tipo y enfoque.
NO desarrolles hooks, guiones ni CTAs.

NEGOCIO: {brand_brief.get('business_name')}
SERVICIO: {brand_brief.get('service')}
CLIENTE IDEAL: {brand_brief.get('ideal_client')}
PROBLEMA QUE RESUELVE: {brand_brief.get('problem')}
RESULTADO PRINCIPAL: {brand_brief.get('main_result')}
PRECIO: {brand_brief.get('price')}
CASOS DE ÉXITO: {brand_brief.get('success_cases', '')}

ENFOQUE DEL PLAN (ya aplicado en la lista — respetá estos totales):
- Ventas {pct_ventas}% ({counts['ventas']} piezas) → Problema + Solución
- Educación {pct_educa}% ({counts['educacion']} piezas) → Resultado + Proceso
- Conexión {pct_conexion}% ({counts['conexion']} piezas) → Mentalidad

{research_context}

Para cada pieza entregá EXACTAMENTE este JSON (sin "ideas", sin "hook", sin "cta"):
{{
  "dia_offset": 0,
  "formato": "reel",
  "tipo_contenido": "Problema",
  "enfoque": "Ventas",
  "angulo_estrategico": "1 línea estratégica alineada al tipo y enfoque, SIN desarrollar el contenido"
}}

Entrega las {total} piezas como un array JSON válido (mismos dia_offset y formato que la lista).
Solo el JSON, sin texto adicional antes ni después.
"""
        response = gemini.generate(prompt, SYSTEM_PROMPT)
        return self._parse_strategy_json(response, skeleton=skeleton, enfoque=enfoque)

    def _parse_strategy_json(self, response: str, skeleton: list, enfoque: dict) -> list:
        """Parsea Gemini y fuerza el esqueleto semanal (cuotas por bloque de 7 días)."""
        text = response.strip()
        text = text.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

        parsed = []
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                raw = json.loads(text[start:end + 1])
                if isinstance(raw, list):
                    parsed = [s for s in raw if isinstance(s, dict)]
            except json.JSONDecodeError:
                pass

        return self._merge_strategy_skeleton(skeleton, parsed, enfoque)

    def _generate_historias_plan(self, brand_brief: dict, start_date, limits: dict,
                                 enfoque: dict = None) -> list:
        """Genera historias (sin copy) repartidas a lo largo de los 30 días según
        la cuota semanal del plan del cliente. Cada slot representa UNA secuencia
        de historias para ese día. Retorna {dia_offset, tipo_historia, enfoque}.
        """
        DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

        views = brand_brief.get("ig_avg_views", 0)
        try:
            views_int = int(str(views).replace(",", "").replace(".", ""))
        except (ValueError, TypeError):
            views_int = 0

        if views_int < 3000:
            template = {
                "Lunes": ("Hand Raiser", "Ventas"),
                "Martes": ("Awareness / Victorias", "Conexión"),
                "Miércoles": ("Hand Raiser", "Ventas"),
                "Jueves": ("Awareness / Victorias", "Conexión"),
                "Viernes": ("Hand Raiser", "Ventas"),
                "Sábado": ("Awareness / Victorias", "Conexión"),
                "Domingo": ("Encuesta / Q&A", "Conexión"),
            }
        else:
            template = {
                "Lunes": ("CTA informativo", "Ventas"),
                "Martes": ("Hand Raiser", "Ventas"),
                "Miércoles": ("Awareness / Victorias", "Conexión"),
                "Jueves": ("Hand Raiser", "Ventas"),
                "Viernes": ("CTA informativo", "Ventas"),
                "Sábado": ("Awareness / Victorias", "Conexión"),
                "Domingo": ("Encuesta / Q&A", "Conexión"),
            }

        enfoque = self._normalize_enfoque(enfoque)
        offsets_all = []
        for block in self._get_weekly_blocks(limits, start_date):
            offsets_all.extend(self._pick_varied_offsets(
                block["offset_start"], block["offset_end"], block["historias"],
                block["week"], "historia", start_date
            ))
        enfoque_tags = self._enfoque_labels(len(offsets_all), enfoque)

        slots = []
        for i, offset in enumerate(offsets_all):
            f = start_date + timedelta(days=offset)
            dia_nombre = DAY_NAMES[f.weekday()]
            tipo_historia, _ = template.get(dia_nombre, ("Awareness / Victorias", "Conexión"))
            slots.append({
                "dia_offset": offset,
                "tipo_historia": tipo_historia,
                "enfoque": enfoque_tags[i],
            })
        return slots

    def _save(self, result: dict, business_name: str, label: str):
        from pathlib import Path
        # Ruta anclada al proyecto — en VPS/systemd el cwd no es la raíz del repo
        log_dir = Path(__file__).resolve().parents[2] / "logs" / "content"
        log_dir.mkdir(parents=True, exist_ok=True)
        label_slug = label.replace(" ", "_").replace("-", "").lower()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = str(log_dir / f"{business_name}_{label_slug}_{ts}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)


content_agent = ContentAgent()
