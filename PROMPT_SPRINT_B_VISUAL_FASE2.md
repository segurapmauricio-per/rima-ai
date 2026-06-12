# Contexto — RIMA AI · Sprint B Fase 2 (continuación, composición visual)

## Proyecto
RIMA AI = FastAPI + SQLite por cliente + dashboard HTML + agentes Gemini + bot Telegram.
Ruta: C:/Users/Mauricio/projects/rima-ai
Cliente de prueba: negocio_básico / marca "Negocio Básico" — login basico@test.com / uno
Servidor: python main.py → http://localhost:8000 (reiniciar hoy, el de ayer no persiste)

## Ya completado (Jun 11 2026) — NO reimplementar
- Sprint Copy E2E: pipeline propuesta → copy_generado → copy_aprobado → en_produccion →
  produccion_aprobada, funcionando end-to-end (reel/carrusel/historia) con SQLite como
  fuente de verdad (`sync_weekly_state_from_db` en `core/weekly_helpers.py`).
- Sprint B Fase 1 (diagnóstico) + Fase B.0 (hidratación de imágenes): las 17 imágenes de
  `data/uploads/{historias,carruseles}/` fueron analizadas con Gemini Vision y persistidas
  en la tabla SQLite `imagenes` para `negocio_básico` vía `scripts/analyze_uploads_to_db.py`
  (idempotente, ya corrido completo, 0 errores). Resultado: 8 usables para historia, 11 para
  carrusel, 6 para branding.
- `get_imagenes_para(cliente_id, uso)` en `core/db/database.py` devuelve estas imágenes
  analizadas (con `analisis_json`, `usable_para_json`).
- Piezas de prueba con copy real en negocio_básico: carrusel `d3042e2d`
  (status produccion_aprobada... revisar status actual) e historia `63ff7758`
  (status en_produccion).

## Decisiones de diseño confirmadas (de la Fase 1)
- Nuevo módulo `agents/visual_composer/agent.py` — debe ser 100% determinístico, CERO
  llamadas a Gemini/LLM.
  - `plan_slides(copy_json, tipo, slot_context)`:
    - Carrusel: pasar directo `copy_json["slides"]` (ya vienen 7 slides con
      slide_number/role/main_text/secondary_text/visual_suggestion/notes desde Sprint
      Copy E2E) — no regenerar.
    - Historia: derivar de `copy_elegido` → hook_text → body_texts → cta_text+keyword.
  - `match_images_to_slides(cliente_id, tipo, slides)`:
    - Buscar candidata en `get_imagenes_para(cliente_id, uso)` según `analisis_json`.
    - Si `analisis_json.best_text_zone` es null, usar zona "center" por defecto (no fallar).
    - Si hay candidata: `{"image_id":..., "image_source":"cliente", "text_zone":{...}}`.
    - Si no hay candidata: `{"image_source":"kie_pending", "prompt_sugerido": "..."}`
      construido por TEMPLATE (no LLM) usando `image_vibe_needed`/`visual_suggestion` del slide.
    - Nota: `usable_para` puede incluir categorías extra desde `suggested_category`
      (por eso 11 candidatas para carrusel aunque hay 9 imágenes raw de esa categoría).

## REGLAS NO NEGOCIABLES (igual que siempre)
1. NO desplegar nada al VPS — solo cambios locales.
2. NO correr scraping (Apify) ni Market Research nuevo.
3. NO tocar ranking R1-R4 ni el pipeline de copy (Sprint Copy E2E) — solo se EXTIENDE
   lo que pasa después de copy_aprobado.
4. NO commitear salvo que Mauricio lo pida explícitamente.
5. Todos los endpoints nuevos/modificados deben usar Depends(get_current_user).
6. Responder siempre en español.
7. Cambios pequeños y verificables, uno a la vez.
8. UI cliente solo muestra score_ventas en propuestas; esto no cambia.
9. `core/kie_client.py` (stub) — `generate_image()` devuelve
   `{"status":"not_configured","reason":"Falta KIE_API_KEY"}` sin llamadas HTTP reales.

## Fase 2 — Implementación (arrancar directo en paso 1)

1. Crear `agents/visual_composer/agent.py`:
   - `plan_slides(copy_json, tipo, slot_context) -> list[dict]` (ver reglas arriba).
   - `match_images_to_slides(cliente_id, tipo, slides) -> list[dict]` (ver reglas arriba).

2. Crear `core/kie_client.py`:
   - `generate_image(prompt, ratio, reference_image=None) -> dict` — stub, sin HTTP,
     devuelve `{"status":"not_configured","reason":"Falta KIE_API_KEY"}` si no hay
     `KIE_API_KEY` en entorno.

3. Modificar `POST /api/publicaciones/{id}/producir` en `main.py`:
   - Para carrusel/historia: reemplazar el gancho actual
     `{"pendiente":"image_analysis",...}` por
     `produccion_json = {"etapa":"produccion","tipo":"visual",
     "slides":[...resultado plan_slides + match_images_to_slides...], "generated_at":...}`.
   - Mantener `update_publicacion_status(..., "en_produccion")` y
     `sync_weekly_state_from_db(...)` (ya existen, reutilizar).

4. Extender `produccionSection(pub)` en `dashboard/rima-contenido.html`:
   - Para `tipo === "visual"`: listar slides con su texto.
   - `image_source === "cliente"`: mostrar thumbnail (vía `GET /api/imagenes` si sirve URL)
     + texto.
   - `image_source === "kie_pending"`: badge "Imagen IA pendiente — falta configurar
     KIE AI" + `prompt_sugerido`.
   - Botón "Aprobar producción" (ya existe) sigue funcionando igual.

5. Fase 3 — Verificación, para negocio_básico:
   - Re-correr "Preparar visual" sobre carrusel `d3042e2d` e historia `63ff7758` (o piezas
     equivalentes en estado copy_aprobado de la semana actual).
   - Confirmar `produccion_json.slides` con mezcla de `image_source: "cliente"` (ahora que
     hay 17 imágenes analizadas, debería haber matches reales, no solo kie_pending) y/o
     `kie_pending` con `prompt_sugerido` no vacío.
   - UI muestra thumbnails y/o badges sin romperse.
   - `core/kie_client.py` no lanza excepciones ni hace requests HTTP.
   - Actualizar `RIMA_CONTEXT.md` con el sub-pipeline de producción visual y estado de KIE
     (pendiente de API key).

## Archivos clave
- agents/visual_composer/agent.py (nuevo)
- core/kie_client.py (nuevo, stub)
- core/db/database.py (get_imagenes_para, tabla imagenes — ya tiene datos para
  negocio_básico)
- main.py (POST /api/publicaciones/{id}/producir, GET /api/imagenes)
- dashboard/rima-contenido.html (produccionSection)
- core/weekly_helpers.py (sync_weekly_state_from_db — reutilizar, no duplicar)
- RIMA_CONTEXT.md
- scripts/analyze_uploads_to_db.py (referencia, ya ejecutado, no volver a correr salvo
  imágenes nuevas)

Empezá directo en el paso 1 (agents/visual_composer/agent.py). Cambios chicos y
verificables, uno a la vez — mostrame el diff de cada paso antes de seguir con el
siguiente.
