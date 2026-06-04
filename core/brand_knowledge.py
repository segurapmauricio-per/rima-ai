import os

KNOWLEDGE_PATH = os.path.join(os.path.dirname(__file__), '..', 'Conocimiento')
AGENTS_KNOWLEDGE_PATH = os.path.join(KNOWLEDGE_PATH, 'agents')


def load_knowledge(module: str) -> str:
    """Load a full knowledge module from Conocimiento/."""
    filename = f"{module}.md"
    filepath = os.path.join(KNOWLEDGE_PATH, filename)
    if not os.path.exists(filepath):
        return f"[Módulo {module} no encontrado]"
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def load_agent_knowledge(agent: str) -> str:
    """Load focused knowledge for a specific agent from Conocimiento/agents/."""
    filename = f"{agent}.md"
    filepath = os.path.join(AGENTS_KNOWLEDGE_PATH, filename)
    if not os.path.exists(filepath):
        return f"[Conocimiento de agente {agent} no encontrado]"
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


# Full module knowledge (for reference or fallback)
VENTAS = load_knowledge('ventas')
PROSPECCION = load_knowledge('prospeccion')
CONTENIDO = load_knowledge('contenido')
META_ADS = load_knowledge('meta-ads')
OFERTA = load_knowledge('oferta-nicho')
OPERACIONES = load_knowledge('operaciones')
LANDING = load_knowledge('landing')

# Focused agent knowledge (lean, no info extra)
K_MARKET_RESEARCH = load_agent_knowledge('market_research')
K_CONTENT_CALENDAR = load_agent_knowledge('content_calendar')
K_STORY_COPY = load_agent_knowledge('story_copy')
K_CAROUSEL_COPY = load_agent_knowledge('carousel_copy')
K_REEL_COPY = load_agent_knowledge('reel_copy')
K_SCRIPT = load_agent_knowledge('script')
K_SALES_DM = load_agent_knowledge('sales_dm')
