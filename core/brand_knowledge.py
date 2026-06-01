import os

KNOWLEDGE_PATH = os.path.join(os.path.dirname(__file__), '..', 'Conocimiento')

def load_knowledge(module: str) -> str:
    filename = f"{module}.md"
    filepath = os.path.join(KNOWLEDGE_PATH, filename)
    if not os.path.exists(filepath):
        return f"[Módulo {module} no encontrado]"
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def load_all_knowledge() -> dict:
    modules = ['ventas', 'prospeccion', 'contenido', 'meta-ads', 'oferta-nicho', 'operaciones', 'landing']
    return {m: load_knowledge(m) for m in modules}

VENTAS = load_knowledge('ventas')
PROSPECCION = load_knowledge('prospeccion')
CONTENIDO = load_knowledge('contenido')
META_ADS = load_knowledge('meta-ads')
OFERTA = load_knowledge('oferta-nicho')
OPERACIONES = load_knowledge('operaciones')
LANDING = load_knowledge('landing')