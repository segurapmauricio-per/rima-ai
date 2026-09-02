"""
Cliente de Claude (Anthropic API directa, no Vertex) — usado únicamente por el
paso de composición visual de carruseles (core/claude_slide_renderer.py).

El resto de RIMA IA sigue en Gemini vía Vertex AI (core/gemini_client.py); esta
es la única pieza que usa Claude, porque en pruebas reales (2026-09-01, ver
docs/protocolo-generacion-imagenes-ia.md) Gemini 2.5 Flash y Pro no aplicaron
de forma consistente el scrim de contraste pedido en el prompt, mientras que
Claude sí lo hizo en todas las corridas.
"""
from __future__ import annotations

import os

import anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

MODEL = "claude-opus-5"


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def generar_html(system_prompt: str, user_prompt: str, max_tokens: int = 16000) -> str:
    """Llama a Claude y devuelve el texto de respuesta, sin fences de markdown."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    return text.strip()
