# Contexto — RIMA AI · Sprint: Integración KIE AI real + specs JSON para imágenes/videos

## Proyecto
RIMA AI = FastAPI + SQLite por cliente + dashboard HTML + agentes Gemini + bot Telegram.
Ruta: C:/Users/Mauricio/projects/rima-ai
Cliente de prueba: negocio_básico / marca "Negocio Básico" — login basico@test.com / uno
Servidor: python main.py → http://localhost:8000 (reiniciar, no persiste entre sesiones)

## Ya completado (Jun 12 2026) — NO reimplementar
- Sprint Copy E2E: pipeline propuesta → copy_generado → copy_aprobado → en_produccion →
  produccion_aprobada, funcionando end-to-end (reel/carrusel/historia).
- Sprint B (visual composition):
  - `agents/visual_composer/agent.py` — 100% determinístico (cero LLM):
    `plan_slides(copy_json, tipo, slot_context)` y
    `match_images_to_slides(cliente_id, tipo, slides)`. Para slides sin imagen del
    cliente, devuelve `{"image_source":"kie_pending", "prompt_sugerido": "...", "ratio": "1:1"|"9:16"}`.
  - `core/kie_client.py` — HOY es un STUB: `generate_image()` devuelve
    `{"status":"not_configured","reason":"Falta KIE_API_KEY"}` sin llamadas HTTP.
  - `agents/image_analysis/agent.py` — analiza imágenes subidas con Gemini Vision, guarda
    `analisis_json` (safe zones, paleta, zonas de texto, vibe, categoría) en la tabla
    SQLite `imagenes`.
  - `main.py POST /api/publicaciones/{id}/producir` ya compone `produccion_json.slides`
    para carrusel/historia (cliente o kie_pending).
  - `dashboard/rima-contenido.html produccionSection()` ya muestra thumbnails de imágenes
    del cliente o badge "Imagen IA pendiente" + `prompt_sugerido` para kie_pending.

## Qué cambió hoy (Jun 12 2026, por la tarde)
- Mauricio ya tiene una **API key real de KIE AI** y la agregó a `.env` como `KIE_API_KEY`.
  Solo para pruebas — cuidado con el gasto.
- **Límite de KIE AI: 20 imágenes generadas cada 10 segundos** (rate limit duro de la
  cuenta) — cualquier código que llame a KIE debe respetar esto (cola/throttle), nunca
  disparar generación masiva sin control.

## Objetivo de este sprint
1. Reemplazar el stub de `core/kie_client.py` por una integración real con KIE AI
   (generación de imágenes, y video si la cuenta lo permite — investigar en Fase 1).
2. Definir un **formato JSON unificado de "spec visual"** que sirva tanto para:
   - describir/analizar imágenes existentes (lo que hoy hace `image_analysis` →
     `analisis_json`), como
   - construir el prompt/parámetros de generación para KIE AI (imágenes y video).
   La idea es que el mismo esquema JSON describa "qué hay/debería haber en esta pieza
   visual" sea que venga de análisis (imagen real) o de generación (imagen/video nuevo).
3. Permitir generar imágenes con KIE AI para los slides `kie_pending` de carruseles e
   historias, respetando el rate limit, y guardarlas como assets del cliente.
4. Dejar la puerta abierta para video (reels) con el mismo enfoque JSON, pero sin forzar
   la implementación si KIE AI no soporta video en la cuenta actual — documentarlo como
   pendiente si es el caso.

## REGLAS NO NEGOCIABLES (igual que siempre)
1. NO desplegar nada al VPS — solo cambios locales.
2. NO correr scraping (Apify) ni Market Research nuevo.
3. NO tocar ranking R1-R4 ni el pipeline de copy/Sprint B ya cerrados — solo se EXTIENDE
   lo que pasa con `kie_pending` y la generación de imágenes/video.
4. NO commitear salvo que Mauricio lo pida explícitamente.
5. Todos los endpoints nuevos/modificados deben usar Depends(get_current_user).
6. Responder siempre en español.
7. Cambios pequeños y verificables, uno a la vez.
8. **NO disparar generación de imágenes en masa sin confirmación explícita** — la API
   cuesta dinero y tiene rate limit de 20/10s. En las pruebas, generar como máximo 1-2
   imágenes para validar el flujo.
9. No inventar/adivinar el formato exacto de la API de KIE AI — confirmarlo en Fase 1
   (docs oficiales si están disponibles, o una llamada de prueba mínima con la key real
   para ver el shape real de la respuesta).

## Fase 1 — Diagnóstico (reportar antes de codear)
1. Confirmar que `KIE_API_KEY` está en `.env` y se carga (sin loguear el valor).
2. Investigar la API real de KIE AI: endpoint(s) de generación de imágenes, parámetros
   requeridos (prompt, ratio/tamaño, referencia, etc.), formato de respuesta (¿URL?
   ¿base64? ¿polling de un job?), y si existe generación de video y con qué endpoint/
   parámetros. Si hay documentación accesible, citarla; si no, hacer **una sola** llamada
   mínima de prueba (1 imagen) para ver el shape de la respuesta — avisar antes de
   gastarla.
3. Revisar `analisis_json` real de 1-2 imágenes ya analizadas en `negocio_básico` (tabla
   `imagenes`) para ver qué campos tiene hoy (paleta, vibe, zonas de texto, categoría,
   etc.) y qué tan cerca está de poder ser un "spec visual" reusable para generación.
4. Revisar `prompt_sugerido` que hoy genera `agents/visual_composer/agent.py` para slides
   `kie_pending` — ¿alcanza como prompt de generación o falta estructura (estilo, paleta
   de marca, ratio, elementos obligatorios)?
5. Confirmar cómo y dónde se guardan hoy las imágenes del cliente (`data/uploads/...` y/o
   `data/clients/{cliente_id}/images/...`) para decidir dónde persistir las imágenes
   generadas por KIE.

Entregar tabla: Pieza (análisis imagen / generación imagen / generación video) | Qué hay
hoy | Qué falta | Riesgo/costo.

## Fase 2 — Implementación (tras aprobación de Fase 1)

### 2.1 — Esquema JSON "spec visual" (`docs/visual_spec_schema.md` o similar + validación)
- Definir un esquema JSON común, por ejemplo:
  ```json
  {
    "tipo_pieza": "imagen|video",
    "formato": "1080x1080|1080x1920|...",
    "descripcion": "...",
    "vibe": "...",
    "paleta_colores": ["#..."],
    "elementos_clave": ["..."],
    "zona_texto": {"zone": "center|upper_third|lower_third", "coords": {...}},
    "estilo_fotografico": "...",
    "texto_overlay": "...",
    "duracion_seg": null,
    "escenas": null
  }
  ```
  (ajustar campos según lo que aparezca en Fase 1 — el objetivo es que sirva tanto para
  describir imágenes analizadas como para armar el prompt de generación).
- Adaptar `agents/image_analysis/agent.py` para que, además de `analisis_json` actual,
  pueda emitir/mapear a este esquema (sin romper lo existente — agregar, no reemplazar).
- Adaptar `agents/visual_composer/agent.py` para que `prompt_sugerido` de slides
  `kie_pending` se construya a partir de este esquema (sigue siendo determinístico, sin
  LLM — el esquema lo arma a partir de `copy_json`/`slot_context`/`analisis_json` como ya
  hace hoy, solo más estructurado).

### 2.2 — `core/kie_client.py` real
- Implementar `generate_image(prompt, ratio, reference_image=None) -> dict` con la API
  real de KIE AI confirmada en Fase 1. Devolver algo como
  `{"status":"ok","image_url"|"image_path":..., "raw": {...}}` o
  `{"status":"error","reason":...}` sin crashear.
- Implementar un **rate limiter simple** (ej. cola con `time.sleep` o token bucket) que
  garantice no superar 20 llamadas / 10 segundos, incluso si se piden varias generaciones
  seguidas.
- Si `KIE_API_KEY` no está configurada, mantener el comportamiento actual
  (`not_configured`).
- (Si Fase 1 confirma soporte de video) `generate_video(spec_json) -> dict` con el mismo
  patrón — si no hay soporte, documentar como pendiente y no implementar un mock.

### 2.3 — Endpoint para generar imagen de un slide `kie_pending`
- Nuevo endpoint, ej. `POST /api/publicaciones/{id}/generar-imagen-slide` con
  `Depends(get_current_user)`, body `{"slide_index": N}`:
  - Toma el `prompt_sugerido`/spec del slide N en `produccion_json.slides`.
  - Llama a `kie_client.generate_image(...)`.
  - Si OK: descarga/guarda la imagen generada en `data/clients/{cliente_id}/images/...`
    (o donde corresponda según Fase 1.5), actualiza ese slide a
    `{"image_source":"generada_ia", "archivo_url":..., "spec_usada": {...}}`.
  - Si error o `not_configured`: no romper, devolver el motivo para mostrar en la UI.
- **No** generar automáticamente todos los slides `kie_pending` de una pieza en un solo
  llamado — un slide a la vez, acción explícita del usuario (botón).

### 2.4 — UI `dashboard/rima-contenido.html`
- En `produccionSection()`, para slides `image_source === "kie_pending"`: agregar botón
  "Generar con IA" que llama al nuevo endpoint para ese slide y, al volver OK, refresca el
  render mostrando la imagen generada (igual que las de cliente, pero quizá con un badge
  "Generada con IA").
- Mostrar mensaje claro si KIE devuelve error o `not_configured`.

## Fase 3 — Verificación
1. Confirmar que `core/kie_client.py` con `KIE_API_KEY` real responde `status: ok` (o el
   valor que corresponda) en una llamada de prueba, y que sin la key sigue devolviendo
   `not_configured` (probar ambos casos, p. ej. con una copia del entorno sin la var).
2. Generar **como máximo 1-2 imágenes reales** para un slide `kie_pending` del carrusel
   `d3042e2d` o la historia `63ff7758`, vía el nuevo endpoint — confirmar que se guarda el
   archivo, se actualiza `produccion_json`, y la UI lo muestra.
3. Confirmar que el rate limiter no permite ráfagas > 20/10s aunque se llame en loop
   (test con límites bajos simulados si no se quiere gastar contra la API real).
4. Documentar en `RIMA_CONTEXT.md`: esquema "spec visual" JSON, estado de integración KIE
   (imagen: real; video: según lo que diga Fase 1), y el nuevo endpoint
   `generar-imagen-slide`.

## Archivos clave
- core/kie_client.py (reemplazar stub por integración real + rate limiter)
- agents/visual_composer/agent.py (prompt_sugerido estructurado vía spec JSON)
- agents/image_analysis/agent.py (mapeo opcional a spec JSON común)
- main.py (nuevo endpoint generar-imagen-slide)
- dashboard/rima-contenido.html (botón "Generar con IA", manejo de errores)
- .env (KIE_API_KEY — no loguear, no commitear)
- RIMA_CONTEXT.md

Empezá por la Fase 1 (diagnóstico, incluyendo investigar la API real de KIE AI con la key
ya configurada) y mostrame la tabla antes de tocar código. Si para Fase 1 necesitás hacer
una llamada de prueba a KIE AI que consuma cuota, avisá antes de ejecutarla.
