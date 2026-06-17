# Contexto — RIMA AI · Auditoría vs. "Build with Gemini XPRIZE"

## Por qué este sprint
RIMA AI no es solo un SaaS de contenido para Instagram: el objetivo de fondo es presentarlo
a la competencia **"Build with Gemini XPRIZE"** (organiza XPRIZE, vía Devpost,
https://xprize.devpost.com/).

## Reglas del concurso (resumen, confirmar detalles en el link si hace falta)
- **Objetivo**: demostrar en 90 días un negocio real operado por agentes de IA, con
  ingresos reales y clientes reales.
- **Categoría objetivo para RIMA AI**: "Servicios para Pequeños Negocios" (gestión de
  contenido en Instagram para negocios locales LATAM).
- **Deadline**: 17 de agosto de 2026, 1:00 PM PDT.
- **Requisito técnico**: al menos un producto de Google Cloud usado en producción (RIMA
  ya usa Gemini API / Vertex — `GEMINI_API_KEY`, `GOOGLE_CLOUD_PROJECT` en `.env`).
- **Criterios de evaluación**:
  1. Viabilidad empresarial — ingresos reales generados durante los 90 días y
     sostenibilidad del modelo.
  2. Operaciones nativas de IA — qué tanto la IA toma decisiones clave en producción
     (no solo asiste).
  3. Impacto en la categoría — cambio significativo para el sector elegido.
- **Entregables finales**:
  1. Repositorio GitHub (público o privado).
  2. Video de 3 minutos mostrando la IA operando en producción.
  3. Narrativa escrita de 500-1000 palabras sobre operaciones diarias.
  4. Evidencia de ingresos reales (dashboard Stripe, estado bancario, P&L).
  5. Registro de gastos (incluyendo marketing).
  6. Evidencia de producto: logs de agentes, registros de llamadas API.
  7. Información de clientes reales con testimonios.

## Estado actual del proyecto (no reimplementar nada aquí — solo auditar)
- Ruta: `C:/Users/Mauricio/projects/rima-ai`. Server: `python main.py` →
  http://localhost:8000. Cliente de prueba: negocio_básico / basico@test.com / uno.
- Pipeline completo funcionando LOCAL (sin deploy, sin commits): Monthly Planner → Weekly
  agent (propuestas desde estudio de mercado) → copy (reel/carrusel/historia) →
  aprobación → producción (script para reels; composición visual con imágenes propias o
  generadas por IA para carrusel/historia).
- Sprint Copy E2E (Jun 11): pipeline de estados unificado en SQLite, verificado E2E.
- Sprint B (Jun 12): `agents/visual_composer/agent.py` — composición determinística de
  slides + matching de imágenes analizadas con Gemini Vision.
- Sprint KIE AI (Jun 12): `core/kie_client.py` — generación real de imágenes con KIE AI
  (nano-banana), 4 créditos/imagen, rate limiter 20/10s. Endpoint
  `POST /api/publicaciones/{id}/generar-imagen-slide` + botón "Generar con IA" en la UI.
- Pendiente conocido: P0 deploy al VPS (pausado, sin confirmar), onboarding automático
  incompleto (Lemon Squeezy webhook no provisiona cliente completo), 30+ archivos WIP sin
  commitear, sin clientes reales pagando todavía.
- `RIMA_CONTEXT.md` en la raíz del repo tiene el estado técnico detallado y actualizado.

## Tarea de este sprint: AUDITORÍA, no implementación
Recorré el código y `RIMA_CONTEXT.md` y entregá un informe (en español) con:

1. **Mapeo criterio → estado actual**, para cada uno de los 3 criterios de evaluación y
   los 7 entregables finales: ¿qué hay hoy que sirva como evidencia? ¿qué falta por
   completo?
2. **Gap de "operaciones nativas de IA"**: ¿qué decisiones del negocio hoy las toma un
   agente (Gemini/KIE) de punta a punta sin intervención humana, y cuáles requieren
   aprobación manual en el dashboard? Esto es central para el criterio 2 — listar
   explícitamente los puntos de "humano en el loop" actuales (aprobar copy, aprobar
   producción, etc.) y si conviene mantenerlos o automatizarlos para la demo.
3. **Gap de "viabilidad empresarial / ingresos reales"**: ¿cómo se cobra hoy?
   (Lemon Squeezy webhook existe pero onboarding incompleto). ¿Hay clientes reales o solo
   de prueba? ¿Qué falta para tener 1+ cliente real pagando antes del 17 de agosto?
4. **Gap de Google Cloud**: confirmar qué producto(s) de Google Cloud están realmente en
   uso en producción (Gemini API ¿vía Vertex AI o API key directa? `GOOGLE_CLOUD_PROJECT`
   está seteado pero ¿se usa Vertex realmente o solo `google-generativeai`?). Si hoy es
   solo API key de Gemini sin Vertex, evaluar si conviene migrar a Vertex AI para reforzar
   el requisito.
5. **Plan de 9 semanas (hoy 15-jun-2026 → 17-ago-2026)**: propuesta de roadmap por
   semana/sprint priorizando lo que más pesa para los criterios de evaluación y los
   entregables — separar "imprescindible para poder aplicar" vs "nice to have". Tener en
   cuenta que YA hay un MVP funcional local; el foco debería ser: (a) deploy + 1ra
   instancia real, (b) conseguir 1-3 clientes reales pagando, (c) instrumentar logs de
   agentes/API para la "evidencia de producto", (d) preparar narrativa + video al final.
6. **Riesgos/bloqueadores** que veas en el código o el modelo de negocio para cumplir los
   criterios (ej: dependencia de Apify para scraping — ¿es legal/sostenible para 90 días
   de operación real?, costos de Gemini/KIE a escala con clientes reales, etc.)

## Reglas (igual que siempre)
- Esto es auditoría/diagnóstico — NO modificar código en este sprint.
- NO desplegar al VPS, NO commitear, NO correr scraping nuevo.
- Responder en español.
- Si necesitás más info del concurso, el link es https://xprize.devpost.com/ (podés
  consultarlo).

Entregá el informe completo en una sola respuesta estructurada con los 6 puntos arriba.
