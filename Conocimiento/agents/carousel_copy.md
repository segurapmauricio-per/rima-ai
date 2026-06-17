# Conocimiento: Agente Carousel Copy

## Objetivo del carrusel

Carruseles que **nutren**: quien los lee debe sentir que aprendió tips, pasos o insights
aplicables. No es motivación vacía — es micro-educación con conversión al final.

## Idioma e identidad visual

- **Idioma:** Todo el copy visible (`main_text`, `bullets`, CTA) en el idioma del cliente
  (default español). Configurable vía `brand_language` en el brief o onboarding.
- **Marca:** Usar paleta, tipografía y estilo de `marca_visual_json` (onboarding / perfil IG)
  en el `style_guide` y en las `visual_suggestion` de cada slide.

## Estructura base (7 slides)

**Slide 1 — Gancho:**
- Pregunta incómoda o afirmación polarizante
- main_text potente; secondary_text opcional (contexto)

**Slides 2-5 — Desarrollo con valor:**
- Cada slide enseña algo concreto: mito desmontado, contraste, tips, pasos, dato
- **bullets obligatorios** (2-4 ítems cortos, accionables, máx. 12 palabras c/u)
- main_text = titular del slide; secondary_text = takeaway o puente al siguiente

**Slide 6 — Resumen / insight:**
- Sintetiza lo aprendido; bullets opcionales (2 puntos clave)

**Slide 7 — CTA:**
- Entregable concreto + palabra clave ("Comentá [PALABRA] y te lo mando")

## Campos por slide

| Campo | Uso |
|---|---|
| `main_text` | Titular potente (1 frase, máx. ~15 palabras) |
| `bullets` | Lista de tips/pasos/errores/datos (slides 2-5 obligatorio) |
| `secondary_text` | Frase complementaria, takeaway o dato extra |
| `content_type` | gancho, mito, consecuencia, metodo, profundidad, resumen, cta |
| `visual_suggestion` | Layout para IA — incluir "lista vertical con bullets" si aplica |

## 5 formatos probados

**Metafórico:** gancho → mito vs realidad con bullets → tips accionables → resumen → CTA
**Noticia urgente:** titular breaking → desarrollo con datos → solución → CTA
**Cómic:** historia con diálogos → descubrimiento → transformación → CTA
**Minimalista premium:** confesión → aprendizajes en lista → amateur vs pro → CTA
**Recursos ocultos:** curiosidad → recursos descritos parcialmente → CTA DMs

## Reglas de copy

**Densidad de valor:**
- Al menos 3 slides con bullets
- Cada bullet debe ser específico — nada genérico ("esforzate más", "creé en vos")
- Reacción buscada: "No sabía eso" o "Lo puedo aplicar hoy"

**Balance valor / CTA:**
- Dar aprendizaje real en slides 2-6
- El entregable del CTA profundiza o systematiza — no regalarlo todo en el carrusel

**Lenguaje:**
- Directo, claro, verdad incómoda
- Un concepto central por carrusel
- Frases cortas con ritmo
