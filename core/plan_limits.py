"""
Límites por plan contratado — referentes de mercado y actualizaciones manuales.
"""

REF_LIMITS = {
    "basico": {"instagram": 3, "youtube": 1},
    "basic":  {"instagram": 3, "youtube": 1},
    "pro":    {"instagram": 6, "youtube": 2},
    "max":    {"instagram": 10, "youtube": 5},
}

MANUAL_SCRAPE_CREDITS = 1  # actualización manual por semana (se renueva tras el scrape semanal)

# Volumen semanal de contenido por plan (sincronizado con agents/content/agent.py)
CONTENT_WEEKLY = {
    "basico": {"reels": 3, "carruseles": 1, "historias": 3},
    "basic":  {"reels": 3, "carruseles": 1, "historias": 3},
    "start":  {"reels": 3, "carruseles": 1, "historias": 3},
    "pro":    {"reels": 5, "carruseles": 2, "historias": 5},
    "max":    {"reels": 9, "carruseles": 3, "historias": 7},
}

ENFOQUE_DEFAULT = {"ventas": 60, "educacion": 30, "conexion": 10}


def normalize_plan(plan: str) -> str:
    p = (plan or "pro").lower().strip()
    if p in ("basic", "básico", "basico", "plan basico rima ai", "plan básico rima ai"):
        return "basico"
    if p in ("pro", "plan pro rima ai"):
        return "pro"
    if p in ("max", "plan max rima ai"):
        return "max"
    if "basico" in p or "básico" in p or "basic" in p:
        return "basico"
    if "max" in p:
        return "max"
    return "pro"


def get_ref_limits(plan: str) -> dict:
    tier = normalize_plan(plan)
    return dict(REF_LIMITS.get(tier, REF_LIMITS["pro"]))


def normalize_enfoque(enfoque: dict = None) -> dict:
    """Normaliza porcentajes ventas/educación/conexión a suma 100."""
    base = dict(ENFOQUE_DEFAULT)
    if enfoque:
        base.update({
            "ventas": int(enfoque.get("ventas", base["ventas"])),
            "educacion": int(enfoque.get("educacion", base["educacion"])),
            "conexion": int(enfoque.get("conexion", base["conexion"])),
        })
    total = base["ventas"] + base["educacion"] + base["conexion"]
    if total != 100 and total > 0:
        base["ventas"] = round(base["ventas"] * 100 / total)
        base["educacion"] = round(base["educacion"] * 100 / total)
        base["conexion"] = 100 - base["ventas"] - base["educacion"]
    return base


def get_deep_analysis_budget(plan: str, enfoque: dict = None) -> dict:
    """
    Presupuesto semanal de análisis profundo (capa 2 / Gemini).
    Regla: ~2 referentes modelables por cada reel que publica el cliente,
    + carruseles + buffer mínimo. Cuotas repartidas según enfoque del plan.
    """
    tier = normalize_plan(plan)
    limits = CONTENT_WEEKLY.get(tier, CONTENT_WEEKLY["pro"])
    reels = limits["reels"]
    carruseles = limits["carruseles"]

    total = min(24, max(8, reels * 2 + carruseles + 2))
    candidate_pool = min(50, max(20, reels * 3 + carruseles * 2))

    enf = normalize_enfoque(enfoque)
    q_ventas = max(1, round(total * enf["ventas"] / 100))
    q_educa = max(1, round(total * enf["educacion"] / 100))
    q_conex = max(1, total - q_ventas - q_educa)
    if q_ventas + q_educa + q_conex > total:
        q_conex = max(1, q_conex - (q_ventas + q_educa + q_conex - total))
    elif q_ventas + q_educa + q_conex < total:
        q_ventas += total - q_ventas - q_educa - q_conex

    return {
        "plan": tier,
        "reels_semana": reels,
        "total": total,
        "candidate_pool": candidate_pool,
        "quotas": {
            "ventas": q_ventas,
            "educacion": q_educa,
            "conexion": q_conex,
        },
        "enfoque": enf,
    }
