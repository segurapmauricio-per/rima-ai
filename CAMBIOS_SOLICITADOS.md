# Prompt para Cursor — Plan por etapas, RIMA AI

Implementar en **3 etapas, en orden**. No saltar a la Etapa 2 sin cerrar la 1, ni a la 3 sin cerrar la 2 — cada etapa depende de que la anterior quede funcional, no solo "con código".

---

## Contexto del proyecto

RIMA AI es un SaaS FastAPI (monolito: `main.py` + `core/` + `agents/`) para generación de contenido de Instagram con IA (Gemini vía Vertex AI + KIE para imágenes). Multi-tenant por `cliente_id`. Datos de usuario/marca en `data/rima_data.json`; publicaciones en SQLite por cliente (`core/db/`). Deploy en VPS con Easypanel (Docker). El dashboard **no es una SPA** — cada sección (`/home`, `/calendario`, `/contenido`, `/mercado`, `/marca`, `/referencias`, `/videos`, `/credenciales`) es su propio HTML servido por ruta.

Todo lo de este documento surgió de una sesión de pruebas E2E con una cuenta real (provisionada vía webhook de Gumroad) recorriendo onboarding y dashboard.

---

## Ya implementado y probado — NO tocar salvo que rompa algo

1. **Gemini vía Vertex AI con Service Account** — `core/gemini_client.py` y `agents/image_analysis/agent.py` usan `genai.Client(vertexai=True, project="rima-ai-498117", location="us-central1")`, autenticado con `GOOGLE_APPLICATION_CREDENTIALS` (Service Account JSON, rol "Usuario de Agent Platform" / `roles/aiplatform.user`). Usa créditos de prueba de GCP del proyecto `rima-ai`, no la facturación de AI Studio. Probado funcionando.
2. **Aislamiento de datos entre clientes** — `core/referentes_store.py` (`get_user_brand`/`set_user_brand`) ya no cae a un `data["brand"]` global legacy. Cada usuario solo ve su propia marca.
3. **Análisis real de oferta en onboarding (Detalle 1 original)** — `core/onboarding.py` (`apply_scrape_to_brand`) + `core/brief_analysis.py` (`analyze_brief_from_ig`) infieren servicio/oferta, cliente ideal, problema, resultado y **nombre del negocio** desde el perfil de IG scrapeado, usando Gemini. Probado funcionando con cuenta real.
4. **Borrado de fotos en onboarding (Detalle 2 original)** — `dashboard/onboarding.html` ya tiene botón de eliminar (`.thumb-del`) por foto subida en el paso "Fotos para historias", llama a `DELETE /api/images/historias/{nombre}`.
5. **Subida de foto de rostro asíncrona** — `POST /api/onboarding/face-profile` en `main.py` ya no bloquea la respuesta esperando el análisis de Gemini; el análisis corre en `BackgroundTasks` y la respuesta vuelve de inmediato.
6. **Flujo de activación post-onboarding (Detalle 4 original)** — implementado en `main.py` (objeto `ACT`, funciones `maybeShowActivation`, `renderActivationStep`, `runActivationPrimary`): guía al usuario por 4 pasos (confirmar referentes → estudio de mercado → calendario mensual → plan semanal) con un modal (`#rima-activation`). Botones ya rediseñados: "Continuar" grande/verde/centrado, "Omitir →→→" chico/gris abajo a la derecha, y una "×" arriba a la izquierda para saltar el paso sin restricciones.
7. Varios fixes menores de UI: toggle mostrar/ocultar password en login, botón "Omitir por ahora" en foto de rostro siempre visible.

---

## ETAPA 1 — Arreglar lo que está roto a medias (bloqueante)

### 1.1 Tour del dashboard no funciona

**Problema real (verificado en código):** en `main.py` ya existe un sistema de tour (`TOUR_STEPS`, `ensureTourDom`, `showTourStep`, `clearTourHighlight`) que intenta resaltar elementos con `querySelector('[data-rima-tour="' + step.slug + '"]')`. **Ese atributo `data-rima-tour` no existe en ningún archivo de `dashboard/`** — se confirmó por grep en todo el proyecto. Resultado: el tour nunca resalta nada, y tampoco navega a las páginas reales (solo intenta resaltar en la página actual).

**Qué hacer:**
1. Agregar `data-rima-tour="<slug>"` a cada ítem del sidebar en **todas** las páginas del dashboard que comparten el menú (`rima-home.html`, `rima-calenadrio.html`, `rima-contenido.html`, `rima-mercado.html`, `rima-marca.html`, `rima-referencias.html`, `rima-imagenes.html`, `rima-videos.html`, `rima-credenciales.html`), usando los slugs ya definidos en `TOUR_STEPS` (`dashboard`, `calendario`, `contenido`, `mercado`, `marca`, `referencias`, `imagenes`, `videos`, `credenciales`).
2. Cambiar el comportamiento de "Siguiente" para que **navegue de verdad** (`window.location.href`) a la página real de la siguiente pestaña en vez de solo resaltar en la página actual — el usuario debe ver la pestaña real funcionando mientras se le explica, no una ilustración aislada del menú.
3. Persistir el progreso del tour (ya hay lógica de "No volver a mostrar" — confirmar que el flag se guarda server-side o en `localStorage` y se respeta en cada carga).

### 1.2 `dashboard/rima-home.html` es un mockup estático

**Problema:** la página servida en `/home` (`main.py:1530`, `serve_html("rima-home.html", ...)`) tiene datos 100% hardcodeados: "FitLife Studio", "Carolina Parra", "$18,000", "12,437 seguidores", etc. No varían por usuario ni vienen de ninguna API.

**Qué hacer:** conectar esta página a datos reales — usar `/api/brand` para nombre/handle del negocio, y los KPIs reales del cliente (publicaciones del mes, seguidores si están disponibles, etc.) en vez de los valores fijos en el HTML.

### 1.3 Marcar como "Próximamente" las pestañas no construidas

Las pestañas **META Ads**, **Ventas** y **Landing** del sidebar son Fase 2/3 del roadmap, todavía no construidas. Deshabilitarlas visualmente (opacity reducida, badge "Próximamente", sin acción al click) en vez de dejarlas como links muertos.

---

## ETAPA 2 — Completar el flujo de referentes (depende de que la Etapa 1 esté funcionando)

### 2.1 Sugerencias de referentes sin foto ni verificación

**Problema:** en el paso "Referentes de tu nicho" del flujo de activación (`main.py`, `loadRefSuggestions()`), las sugerencias vienen de `core/referentes_suggestions.py` → `suggest_referentes()`, que le pide a Gemini que **invente** usernames plausibles de Instagram. No hay foto de perfil, no hay garantía de que el username exista, y toda la card es clickeable para seleccionar (no se puede ver el perfil antes de elegir).

**Costo verificado de la solución (no es bloqueante):** el actor `apify~instagram-profile-scraper` cuesta ~$0.0026/perfil en plan gratuito de Apify (~$0.0016 en planes superiores) → ~$0.01 USD por usuario para 4 sugerencias. El costo real a manejar es **latencia** (varios segundos de scraping) y **perfiles inexistentes** (usernames alucinados que el scraper no encuentra).

**Qué hacer:**
1. Al cargar este paso, scrapear en paralelo el perfil (solo `instagram-profile-scraper`, no el de posts) de las 4 sugerencias de Gemini.
2. Mostrar loading/skeleton mientras se resuelve.
3. Descartar silenciosamente las que no se encuentren.
4. Mostrar foto + nombre (click → abre IG en pestaña nueva) + **casilla de selección a la derecha**, separada del click de ver perfil.

### 2.2 Cambiar el momento en que aparecen las sugerencias (decisión de producto)

En vez de mostrar las sugerencias de IA durante el onboarding/activación inicial:

1. **En el onboarding**, en el paso de referentes: no mostrar sugerencias de IA todavía. Mostrar en su lugar una **inducción breve** (mismo estilo visual del tour) explicando qué tipo de perfiles conviene agregar (mismo nicho o nicho adyacente, cuentas medianas, buen contenido educativo/de ventas) y cómo (`@usuario`). El usuario agrega los suyos manualmente o lo omite.
2. **A partir del 3er día de uso** (usar `created_at` del usuario para calcularlo), correr en segundo plano `suggest_referentes()` + la verificación de Apify (punto 2.1) y mostrarle al usuario un aviso tipo "RIMA encontró estos referentes para vos" — como un descubrimiento autónomo de la IA, no un paso más del formulario. Requiere un mecanismo de notificación in-app (banner/toast) que se dispare la primera vez que el usuario entra después de cumplirse esa ventana.

---

## ETAPA 3 — Recordatorios de contenido listo (feature nueva, infraestructura ya existe)

**Problema:** cuando una pieza (historia, reel, carrusel) queda lista para que el cliente la suba/publique, no hay ningún aviso — el cliente tiene que revisar manualmente.

**Ya existe, sin conectar:**
- Tabla `notificaciones` en `core/db/schema.py` (línea ~130), con tipo `aviso_reel` ya previsto pero **nunca insertado** en el código actual.
- `bot/telegram_bot.py` ya envía mensajes por Telegram (usado en el flujo semanal) — reusar el mismo canal.
- Estado `produccion_aprobada` en la máquina de estados de `publicaciones` (`core/db/schema.py` línea ~43) marca cuando la pieza está lista y falta acción del cliente.

**Qué hacer:**
1. Cuando una publicación pasa a `produccion_aprobada`, insertar una fila en `notificaciones` y disparar el envío por Telegram y/o email (SMTP ya configurado).
2. Un solo recordatorio inicial; evaluar un segundo recordatorio de seguimiento si pasan N días sin que el estado avance a `programado`/publicado.
3. Definir si el canal es Telegram, email, o ambos, configurable por el usuario en "Credenciales"/ajustes de cuenta.

---

## Notas generales para Cursor

- No reescribir desde cero el tour ni el flujo de activación — ya existe la base en `main.py`, el trabajo de la Etapa 1 es **conectarlos correctamente**, no reconstruirlos.
- Cada etapa debe quedar verificada funcionando (no solo "código escrito") antes de pasar a la siguiente.
- Si encontrás más mockups estáticos como `rima-home.html` en otras páginas del dashboard durante la Etapa 1, reportarlo antes de la Etapa 2 — afecta el alcance real del tour.
