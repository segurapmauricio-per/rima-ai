# Contexto — RIMA AI · Sprint B: Composición visual (historias/carruseles)

## Proyecto
RIMA AI = FastAPI + SQLite por cliente + dashboard HTML + agentes Gemini + bot Telegram.
Ruta: C:/Users/Mauricio/projects/rima-ai
Cliente de prueba: negocio_básico / marca "Negocio Básico" — login basico@test.com / uno
Servidor: python main.py → http://localhost:8000

## Estado actual (no reimplementar — Sprint Copy E2E cerrado Jun 11 2026)
- Pipeline `propuesta → copy_generado → copy_aprobado → en_produccion → produccion_aprobada`
  funciona end-to-end para reel/carrusel/historia (verificado vía HTTP con JWT).
- `POST /api/publicaciones/{id}/producir`:
  - reel → script_agent (guion A/B) ✅ completo.
  - carrusel/historia → HOY solo deja un gancho: `{"etapa":"produccion","tipo":"visual",
    "pendiente":"image_analysis","imagenes_candidatas":[...ids...]}`. ESTE Sprint completa
    esa rama.
- `agents/image_analysis/agent.py` ya existe: analiza imágenes subidas con Gemini Vision,
  detecta safe zones (Stories 1080x1920, Carruseles 1080x1080/1350), paleta de colores,
  zonas libres para texto, vibe, categoría sugerida (`historia`/`carrusel`/`branding`).
  Guarda en tabla `imagenes` (`analisis_json`, `usable_para_json`, `analizado_at`).
- `core/db/database.py::get_imagenes_para(cliente_id, uso)` devuelve imágenes ya analizadas
  y aptas para `"historia"` o `"carrusel"`.
- `core/weekly_helpers.py::sync_weekly_state_from_db()` mantiene SQLite como fuente de
  verdad y refleja en weekly_state.json — reutilizar, no duplicar lógica de sync.
- 30+ archivos sin commitear (WIP intencional). Solo commitear si Mauricio lo pide.

## Dato importante para el diseño
`data/clients/negocio_básico/images/{historias,carruseles,branding}/` están **vacías hoy** —
no hay imágenes subidas ni analizadas para el cliente de prueba. Por lo tanto, en la
verificación, Fase B (match con imagen del cliente) va a devolver 0 candidatas para
negocio_básico — eso es ESPERADO, no es un bug. El pipeline debe manejarlo con elegancia
(no romper, mostrar estado "sin imagen asignada — pendiente subir material o generar con IA").

## REGLAS NO NEGOCIABLES
1. NO desplegar nada al VPS — solo cambios locales.
2. NO correr scraping (Apify) ni Market Research nuevo.
3. NO tocar el ranking R1-R4 del estudio de mercado, ni el pipeline de copy (Sprint
   Copy E2E) — solo se EXTIENDE lo que pasa después de `copy_aprobado`.
4. NO commitear salvo que Mauricio lo pida explícitamente.
5. Todos los endpoints nuevos/modificados deben usar Depends(get_current_user).
6. Responder siempre en español.
7. Cambios pequeños y verificables, uno a la vez.
8. UI cliente solo muestra score_ventas en propuestas; esto no cambia.

## Sobre KIE AI (Fase C) — SIN integración real en este sprint
Mauricio todavía no tiene API key de KIE AI. Para este sprint:
- Crear `core/kie_client.py` como **interfaz/stub**: función `generate_image(prompt, ratio,
  reference_image=None) -> dict`. Si `KIE_API_KEY` no está en el entorno, devolver
  `{"status": "not_configured", "reason": "Falta KIE_API_KEY"}` sin crashear y sin hacer
  ninguna llamada HTTP real.
- En la composición, si Fase B no encuentra imagen candidata, marcar el slide como
  `"image_source": "kie_pending"` con el prompt visual sugerido guardado (para cuando se
  configure la key, generarlo después) — NO intentar llamar a KIE.
- No gastar tiempo en mockear la API de KIE en detalle; el contrato de la función alcanza.

## Fase 1 — Diagnóstico (reportar antes de codear)
1. Leer `agents/image_analysis/agent.py` completo: ¿qué estructura exacta tiene
   `analisis_json` (zonas de texto, colores, safe zones)? ¿hay función pública para
   analizar y persistir una imagen ya subida?
2. Revisar `copy_json` real ya generado en Sprint anterior para carrusel e historia de
   negocio_básico (vía SQLite) — ¿qué campos hay para derivar slides? (carrusel ya trae
   `slides`; historia trae `propuestas_copy`/`copy_elegido` con `body_texts`).
3. Confirmar `get_imagenes_para()` y el endpoint `GET /api/imagenes` — ¿alcanzan para
   listar candidatas por cliente y categoría?
4. Revisar `dashboard/rima-contenido.html` sección `produccionSection()` (agregada en
   Sprint anterior) — punto de extensión para mostrar slides compuestas.

Entregar tabla: Pieza | Qué necesita Fase A | Qué necesita Fase B | Qué hay hoy | Qué falta.

## Fase 2 — Implementación (tras aprobación de Fase 1)

### Fase A — Plan de slides (desde copy_aprobado)
- Nueva función en `agents/image_analysis/agent.py` o módulo nuevo
  `agents/visual_composer/agent.py` (decidir según diagnóstico):
  `plan_slides(copy_json, tipo, slot_context) -> list[dict]`
  - Carrusel: si `copy_json["slides"]` ya existe (Sprint Copy E2E lo genera), usarlo como
    base; si no, derivar 4-6 slides desde hook/desarrollo/cta.
  - Historia: derivar 2-4 slides desde `body_texts`/`copy_elegido` (hook → desarrollo →
    CTA, separado en slides cortos para Stories).
  - Cada slide: `{"index": N, "texto": "...", "tipo_slide": "hook|desarrollo|cta|portada"}`.

### Fase B — Match imagen↔slide
- `match_images_to_slides(cliente_id, tipo, slides) -> list[dict]`
  - Para cada slide, buscar en `get_imagenes_para(cliente_id, uso)` la mejor candidata
    según `analisis_json` (zona de texto libre compatible con `tipo_slide`, vibe, no
    repetir la misma imagen en slides consecutivos si hay alternativas).
  - Si hay candidata: `{"image_id": ..., "image_source": "cliente", "text_zone": {...}}`.
  - Si no hay candidata: `{"image_source": "kie_pending", "prompt_sugerido": "..."}`
    (usar `core/kie_client.py` stub solo para confirmar `not_configured`, no para generar).

### Integración en `/api/publicaciones/{id}/producir`
- Para carrusel/historia: reemplazar el gancho actual por
  `produccion_json = {"etapa": "produccion", "tipo": "visual", "slides": [...resultado
  Fase A+B...], "generated_at": ...}`.
- Mantener `update_publicacion_status(..., "en_produccion")` y
  `sync_weekly_state_from_db(...)` como ya está.

### UI `dashboard/rima-contenido.html`
- Extender `produccionSection(pub)`: para `tipo === "visual"`, mostrar lista de slides
  con su texto y estado de imagen:
  - Si `image_source === "cliente"`: mostrar thumbnail (si `GET /api/imagenes` sirve la
    URL) + texto superpuesto (puede ser simple, texto debajo del thumbnail, no necesita
    composición CSS pixel-perfect en este sprint).
  - Si `image_source === "kie_pending"`: badge "Imagen IA pendiente — falta configurar
    KIE AI" + mostrar el prompt sugerido.
- Botón "Aprobar producción" (ya existe) debe seguir funcionando igual.

## Fase 3 — Verificación
Para negocio_básico, semana actual (sin imágenes subidas — esto es esperado):
1. Carrusel e historia con `copy_aprobado` → "Preparar visual" → `produccion_json.slides`
   tiene entradas para cada slide, todas con `image_source: "kie_pending"` (porque no hay
   imágenes), cada una con `prompt_sugerido` no vacío.
2. UI muestra el badge "Imagen IA pendiente" + texto de cada slide sin romperse.
3. `core/kie_client.py` existe, `generate_image()` devuelve `{"status":"not_configured"...}`
   sin lanzar excepción ni hacer requests HTTP.
4. (Opcional, si hay tiempo) Subir 1-2 imágenes de prueba a
   `data/clients/negocio_básico/images/historias/` vía `POST /api/imagenes/upload` (si
   existe) + correr `image_analysis` sobre ellas, y confirmar que Fase B las asigna en
   lugar de caer a `kie_pending`. Si este paso requiere mucho tiempo o llamadas Gemini
   costosas, dejarlo documentado como pendiente en vez de ejecutarlo.
5. Actualizar `RIMA_CONTEXT.md` con el nuevo sub-pipeline de producción visual y el
   estado de KIE (pendiente de API key).

## Archivos clave
- agents/image_analysis/agent.py
- agents/visual_composer/agent.py (nuevo, si aplica según diagnóstico)
- core/kie_client.py (nuevo, stub)
- core/db/database.py (get_imagenes_para, imagenes table)
- main.py (POST /api/publicaciones/{id}/producir, GET /api/imagenes)
- dashboard/rima-contenido.html (produccionSection)
- core/weekly_helpers.py (sync_weekly_state_from_db — reutilizar)
- RIMA_CONTEXT.md

Empezá por la Fase 1 (diagnóstico) y mostrame la tabla antes de tocar código.
