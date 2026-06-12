# Contexto — RIMA AI · Sprint Copy E2E (sin VPS)

## Proyecto
RIMA AI = FastAPI + SQLite por cliente + dashboard HTML + agentes Gemini + bot Telegram.
Ruta: C:/Users/Mauricio/projects/rima-ai
Cliente de prueba: negocio_básico / marca "Negocio Básico" — login basico@test.com / uno
Servidor: python main.py → http://localhost:8000

## Estado actual (no reimplementar — Jun 11 2026)
- Monthly Planner escribe slots planificados en SQLite (agents/content/agent.py).
- Weekly agent (start_week) genera 2 propuestas/pieza desde estudio de mercado;
  historias desde estrategia RIMA (HISTORIA_ANGULOS).
- UI /contenido (dashboard/rima-contenido.html): tabs Reels/Carruseles/Historias,
  score_ventas visible, botones "Modelar esta" (elegir-referente), "↻ Otras opciones"
  (refresh-propuesta), "Reiniciar semana" (clear-week), Aprobar (aprobar).
- Ranking R1-R4 cerrado: rotación semanal de URLs, scores_tematica internos (~78%
  temática + 22% score_ventas), filtro ≥35 con relajación progresiva ≥35→≥20→pool
  completo (sin badge "aproximado").
- Helpers: core/weekly_helpers.py, core/market_scores.py, core/week_quota.py.
- format_slot_context_for_copy (R4) ya pasa el "pasaporte del slot" (temática, enfoque,
  ángulo) a los copy agents.
- 28 archivos modificados/nuevos sin commitear (WIP intencional, no revertir).
  Solo commitear si Mauricio lo pide explícitamente.

## REGLAS NO NEGOCIABLES
1. NO desplegar nada al VPS — solo cambios locales.
2. NO correr scripts de scraping (Apify) ni disparar Market Research nuevo —
   usar los datos ya existentes en data/clients/negocio_básico/.
3. NO tocar el ranking R1-R4 ni los umbrales (≥35/≥20/pool) — ya está cerrado y validado.
4. NO commitear salvo que Mauricio lo pida explícitamente.
5. Todos los endpoints nuevos deben usar Depends(get_current_user).
6. Responder siempre en español.
7. Cambios pequeños y verificables, uno a la vez — no reescribir archivos enteros
   salvo que se pida explícitamente.
8. UI cliente solo muestra score_ventas; scores temáticos quedan internos.

## Fase 1 — Diagnóstico (hacer primero, reportar antes de codear)
Recorré el flujo completo en negocio_básico SIN generar datos nuevos:
1. Estado de SQLite hoy: cuántos slots por status (planificado, propuesta_generada,
   copy_generado, copy_aprobado, producción, etc.) para la semana actual.
2. Para cada tipo (reel/carrusel/historia): ¿"Modelar esta" → elegir-referente
   genera copy_json correctamente? ¿qué campos llegan vacíos o con error?
3. ¿generate_copy_for_publicacion usa format_slot_context_for_copy hoy para los 3
   tipos, o solo para algunos?
4. ¿Qué pasa después de "Aprobar"? ¿Hay algo que dispare producción (script_agent,
   image_analysis) o es un callejón sin salida hoy?
5. Diferencias entre publicaciones.status (SQLite) y weekly_state.json — ¿están
   sincronizados o hay dos fuentes de verdad divergentes?

Entregá una tabla: Etapa | Estado (Listo/Parcial/Roto/No existe) | Archivo:línea | Qué falta.

## Fase 2 — Implementación (después de que Mauricio apruebe la Fase 1)
En base al diagnóstico, en este orden:
1. Unificar transiciones de estado: propuesta_aprobada → copy_generado →
   copy_aprobado → producción, consistente entre SQLite y weekly_state.json
   (si éste sigue siendo necesario; si no, marcarlo como deprecado pero no borrarlo
   sin confirmar).
2. Completar/arreglar generate_copy_for_publicacion para reel, carrusel e historia
   usando el pasaporte del slot (R4) en los tres.
3. Producción final mínima tras copy_aprobado:
   - Reel: conectar con script_agent (variante teleprompter si aplica).
   - Carrusel/Historia: dejar gancho hacia image_analysis (no es necesario terminar
     la composición visual completa — eso es Sprint B, fuera de este bloque).
4. UI /contenido: reflejar los nuevos estados de forma coherente (badges/botones).

## Fase 3 — Verificación
Para negocio_básico, semana actual:
1. Al menos 1 reel, 1 carrusel y 1 historia llegan a copy_aprobado sin error.
2. El estado en SQLite y en la UI coincide en todo momento.
3. RIMA_CONTEXT.md actualizado con el estado real post-bloque (hoy desactualizado:
   dice MR pendiente DB y dashboard sin conectar, cuando Contenido ya usa APIs reales).

## Archivos clave
- agents/weekly/agent.py — orquestador, stages
- core/weekly_helpers.py, core/market_scores.py, core/week_quota.py
- agents/reel_copy/agent.py, carousel_copy/agent.py, story_copy/agent.py
- agents/script/agent.py, agents/image_analysis/agent.py
- dashboard/rima-contenido.html
- core/db/database.py (publicaciones.status)
- main.py (endpoints elegir-referente, refresh-propuesta, aprobar, weekly/start, clear-week)
- RIMA_CONTEXT.md

Empezá por la Fase 1 (diagnóstico) y mostrame la tabla antes de tocar código.
