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

---

## ETAPA 4 — Feedback de prueba en vivo (onboarding + dashboard, con Carolina/@tuabogada.carolina, 3/6-jul-2026)

Encontrado recorriendo el onboarding y el dashboard real en el VPS (Easypanel) como si fuéramos un cliente nuevo.

### Ya implementado (6-jul-2026, con luz verde del usuario)
- **4.2** — botón "Omitir por ahora" en el paso de fotos del onboarding + fix del bloqueo server-side real que se hubiera encontrado (`core/onboarding.py::onboarding_assets_status` ya no exige fotos mínimas para completar el onboarding, solo lo reporta como informativo).
- **4.3** — texto del tour "Contenido" cambiado a "Las mejores ideas y tu contenido, listo para modelar."
- **4.4** — revertido, sin cambios (decisión final: se mantiene como está).
- **4.5** — tarjetas de META Ads / Ventas / Landing en `/home` ya no muestran números inventados — badge "Desconectado" + valores en "—".
- **4.9** — fix del bug de `core/referentes_verify.py::fetch_profile_meta` (ya no cuenta como verificado un perfil sin seguidores ni nombre — verificado con caso real).
- **Favicon** generado (gradiente violeta→cian, "R") y servido en `/favicon.ico`, inyectado en el `<head>` de todas las páginas vía `serve_html()`.
- **Confirmación al eliminar** — se encontró y arregló un punto sin protección: eliminar un clip de video (`rima-videos.html`) ahora pide confirmación (los demás DELETE del dashboard ya la tenían).
- **Conexión automática de datos al cargar referentes** — `POST /api/referentes/confirm-activation` y `POST /api/referentes/profiles` ahora disparan el estudio de mercado en background apenas se guardan perfiles nuevos (sin gastar el crédito semanal de actualización manual), en vez de esperar a que el cliente lo dispare a mano en el paso 2 de activación.
- **4 referentes reales verificados para Carolina** (vía Apify hashtag scraper, no adivinanza de Gemini): `@legalmente.empoderadas`, `@abogada.claudiamontecinos`, `@anniealmazan.abogada`, `@legalmente.cl`.

### Pendiente de implementar (documentado abajo, no tocado todavía)
- **4.6** (IG real) — proyecto de Meta App Review, no es un fix rápido.
- **4.7** — más grande de lo pedido originalmente: el panel entero de "Pendientes" es mockup estático (no solo falta el ítem de referentes), ver detalle abajo.
- **4.8** — textos educativos post-onboarding (qué va dónde, límite de 1 actualización mensual del calendario).

### 4.1 Paso "Tu Instagram" del onboarding — confirmar que quede obligatorio (sin cambios de código, solo verificación)

**Contexto:** `dashboard/onboarding.html` step-2 ("Tu Instagram", botón "Analizar y continuar") ya es obligatorio hoy — no tiene botón de "Omitir" visible, a diferencia del step-6 (foto de rostro) que sí lo tiene (`id="skip-face"`).

**Decisión tomada en la sesión:** dejarlo así, sin agregar un skip. El único "salto" que existe hoy es automático y solo ocurre si el scrape de Instagram FALLA técnicamente (perfil privado, no encontrado, error de Apify) — `submitInstagram()` en ese caso muestra el error y hace `setTimeout(() => goStep(3), 1000-1500)` para no dejar al cliente trabado. Se decidió **mantener ese fallback tal cual** — no es un skip elegido por el cliente, es una salida de emergencia ante un error técnico.

**Qué hacer:** nada — este punto queda cerrado, era una verificación, no un cambio.

### 4.2 Agregar botón "Omitir" en el paso "Fotos para historias" (step-5 del onboarding)

**Problema:** `dashboard/onboarding.html` step-5 ("Fotos para historias") obliga a subir el mínimo de fotos del plan (`STATE.minPhotos`, hoy 3 para Básico) antes de dejar continuar — `submitPhotos()` bloquea con error si `STATE.photosCount < STATE.minPhotos`. No hay forma de saltear este paso, a diferencia del step-6 (foto de rostro) que sí tiene `id="skip-face"` → `goStep(7)`.

**Qué hacer:**
1. En `dashboard/onboarding.html`, dentro del `step-panel` `id="step-5"`, agregar un botón igual en estilo al de `skip-face` (línea ~133), justo debajo del botón `id="btn-photos"`:
   ```html
   <button type="button" class="w-full mt-2 py-2 text-[11px] text-slate-500" id="skip-photos" onclick="skipPhotos()">Omitir por ahora →</button>
   ```
2. Agregar la función JS `skipPhotos()` (cerca de `submitPhotos()`):
   ```js
   async function skipPhotos(){
     await fetch('/api/onboarding/step',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({step:6})});
     goStep(6);
   }
   ```
   (mismo patrón que usa `submitPhotos()` para avanzar, solo que sin la validación de `minPhotos`).
3. **Verificar en backend** (`main.py`, endpoint que arma el `summary-list` del step-7 "Resumen", y cualquier lógica que dependa de `onboarding_completed`/`photos_count`) que no exista una validación server-side que vuelva a bloquear el `finishOnboarding()` si hay 0 fotos — si existe, decidir si también se relaja o si el cliente simplemente empieza sin fotos de historias en su biblioteca (y las sube después desde `/imagenes`).
4. Probar: onboarding completo saltando fotos → llegar a `/home` sin fotos en biblioteca → confirmar que el dashboard no rompe (ej. `visual_composer` ya maneja bien la ausencia de fotos con `kie_pending`, según Sprint B — no debería requerir cambios ahí).

### 4.3 Cambiar el texto del paso "Contenido" en el tour del dashboard (3/9)

**Dónde:** `main.py`, array `TOUR_STEPS` (línea ~1094):
```js
{ slug: 'contenido', title: 'Contenido', text: 'Piezas generadas listas para validar: historias, carruseles y reels.' },
```

**Qué hacer:** cambiar el campo `text` de ese objeto a la frase pedida: *"Las mejores ideas, y tu contenido, listo para modelar."* (ajustar puntuación/redacción final con Mauricio antes de commitear — la frase tal cual la dictó suena a fragmento, capaz conviene algo como "Las mejores ideas y tu contenido, listo para modelar" sin la segunda coma). Confirmar wording exacto antes de aplicar.

### 4.4 Tour de bienvenida (9 pasos) — **REVERTIDO: dejar el comportamiento actual, sin cambios**

**Decisión original de la sesión (superada):** se había pedido que el tour se muestre una sola vez en la vida del usuario.

**Decisión final (misma sesión, tras seguir probando):** dejarlo como está hoy — el tour se muestra hasta **2 veces** (`core/activation_flow.py::get_tour_state`, `"should_show": not dismissed and seen < 2`), y recién deja de mostrarse cuando el cliente, cansado de verlo, marca "No volver a mostrar". **No tocar este archivo.**

**Qué hacer:** nada — punto cerrado, no requiere cambios de código.

### 4.5 Dashboard "Estado de los agentes" — sacar datos inventados de Ventas / META Ads / Landing

**Problema:** en `/home` (Dashboard), la sección "Estado de los agentes" muestra tarjetas con métricas 100% mockeadas para features que **todavía no existen** (confirmado: en el sidebar, "META Ads", "Ventas" y "Landing" ya llevan el badge "Próximamente" — pero la tarjeta del dashboard para esas mismas 3 áreas muestra números falsos como si estuvieran en producción):
- **META Ads**: "Activo", "$30/día · 3 campañas", "$0.04 CPV", "1 aprendizaje MOFU", "$1,500 Gasto".
- **Ventas**: "$18K · Jun", "48 DMs", "30 Setting", "12 Cierres".
- **Landing**: "Live", "3 propuestas · Propuesta A activa", "1.1% conv. rate", "4,812 visitas", "53 agendas".

Esto es engañoso para un cliente real — ve números de negocio (plata, conversiones) que nunca ocurrieron.

**Qué hacer:**
1. Ubicar en el HTML/JS de `dashboard/rima-home.html` (o donde arme estas 3 tarjetas — revisar si son estáticas en el HTML o vienen de algún endpoint mock) el bloque de cada tarjeta.
2. **META Ads**: cambiar el badge "Activo" → "Desconectado" (mismo estilo que "Próximamente" del sidebar), y las 3 métricas ($0.04 CPV, 1 aprendizaje, $1,500 Gasto) → mostrar "—" o "Sin conectar" en vez de números falsos.
3. **Ventas**: mismo tratamiento — badge "Desconectado" o "Próximamente", números en "—" (no 0, porque 0 sugiere "hubo actividad y dio cero" cuando en realidad no existe el feature aún).
4. **Landing**: mismo tratamiento.
5. Confirmar que **Calendario, Contenido y Estudio de mercado** (las 3 tarjetas que sí son reales, ya conectadas a SQLite) no se toquen — sólo las 3 "Próximamente".
6. Verificar si estos mismos 3 bloques (u otros parecidos) aparecen en algún otro lado del dashboard además de `/home`.

### 4.6 Métricas reales de Instagram del cliente — no es un fix rápido, es un ítem de roadmap

**Pregunta de la sesión:** "¿cómo obtenemos sus métricas de Instagram, cómo podemos hacer real esto?"

**Respuesta corta:** no es un cambio de código chico — requiere integrar la **API de Instagram Graph / Insights** (Meta for Developers), que exige:
1. Que el negocio del cliente tenga una **cuenta de Instagram Business o Creator** (no personal) vinculada a una Página de Facebook.
2. Una **Meta App** propia de RIMA revisada y aprobada por Meta para el permiso `instagram_manage_insights` (proceso de "App Review" de Meta — típicamente 1-4 semanas, ya documentado como riesgo en `ROADMAP.md` Fase 2 "Publicación automática Instagram").
3. Que el cliente autorice esa conexión (flujo OAuth) desde el dashboard — pantalla nueva en "Credenciales".
4. Recién ahí se pueden traer métricas reales (seguidores, alcance, engagement por publicación) para reemplazar cualquier número de ejemplo.

**Ya está en el roadmap** (`ROADMAP.md`, Fase 1 "Revisión periódica del perfil IG" y Fase 2 "Publicación automática Instagram") — no se resuelve como parte de esta Etapa 4/5 de fixes rápidos. Anotado acá para que quede explícito el "por qué no hoy".

### 4.7 "Pendientes" del dashboard — **hallazgo: todo el panel es mockup estático, no solo falta el ítem de referentes**

**Contexto original:** se pidió agregar un ítem "Tus referentes" a la lista de Pendientes cuando el cliente no tiene referentes cargados.

**Hallazgo al revisar el código (`dashboard/rima-home.html` líneas 273-325):** el panel completo de "Pendientes" — los 5 ítems que se ven hoy ("3 piezas esperando validación", "5 reels pendientes de grabar", "Pixel META — verificar", "CSV de clientes — Lookalike", "Brief de marca — 55% completo") — es **HTML 100% estático, sin ningún fetch/JS que lo conecte a datos reales**. A diferencia de las tarjetas "Estado de los agentes" (Calendario/Contenido/Estudio de mercado), que sí traen datos reales vía JS, este panel nunca se toca en runtime.

Por eso, agregar solo el ítem de "Tus referentes" dejaría un panel con 1 ítem real mezclado con 4 inventados (pixel META, CSV lookalike y el brief al 55% son datos de ejemplo, no reales de la cuenta de Carolina) — una mezcla más confusa que útil.

**Qué hacer (alcance real, más grande que lo pedido originalmente):**
1. Decidir qué ítems de Pendientes son viables HOY con datos reales existentes en el sistema:
   - "Referentes" (< 3 cargados) → viable ya (dato real: `referentes_profiles.instagram`).
   - "Piezas esperando validación" → viable ya (dato real: publicaciones con status `propuesta_generada`/`copy_generado`/similar en SQLite, ya usado en otras partes del dashboard).
   - "Brief de marca — X% completo" → viable ya (`brief_missing_fields()` de `core/onboarding.py` ya calcula esto).
   - "Pixel META" y "CSV de clientes — Lookalike" → **no viables** (features de Fase 2/3 del roadmap, ni siquiera construidas) — sacar del panel hasta que existan, no dejarlos como mockup.
2. Construir un endpoint (o extender `core/dashboard_stats.py::get_dashboard_stats`) que arme la lista real de pendientes con los 3 ítems viables de arriba, cada uno con su link de acción.
3. Reemplazar el HTML estático de `rima-home.html` por un contenedor vacío + JS que puebla la lista desde ese endpoint (mismo patrón que ya usan Calendario/Contenido/Estudio de mercado en esta misma página).
4. Para el ítem de referentes específicamente: reusar el copy de `ACT.step===1` (`renderActivationStep()`, línea ~1291) y linkear a `/referencias` o disparar `maybeShowActivation()` directo.
5. Verificar que cada ítem desaparezca de la lista apenas se resuelve (3 referentes cargados, brief 100%, piezas validadas).

### 4.8 Enseñar la secuencia post-onboarding: estudio de mercado → calendario mensual → límite de 1 actualización/mes

**Contexto:** el flujo de activación (`ACT.step` 1→4: referentes → estudio de mercado → calendario → plan semanal) ya ejecuta estos pasos en orden, pero no explica bien al cliente:
1. Que tiene que **esperar el resultado** del estudio de mercado (paso 2) antes de que el paso 3 tenga sentido (el agente corre en background — confirmar que la UI comunique claramente "esto puede tardar" y no dé la sensación de que quedó colgado).
2. Una vez en el **Calendario/Contenido mensual**, enseñarle **qué va en qué lugar** (reels/carruseles/historias, qué significa cada estado — planificado, en validación, publicado) y **cómo verlo** — esto es contenido para el tour (`TOUR_STEPS`) de las secciones `calendario` y `contenido`, revisar si el texto actual ya alcanza o hay que ampliarlo con una explicación más didáctica.
3. **Aclarar explícitamente que el calendario mensual solo se puede regenerar 1 vez al mes** — hoy esto es una regla de negocio que vive en el código (`ContentAgent`, ventana de 30 días) pero no hay ningún texto en la UI que se lo diga al cliente. Agregar un aviso visible (ej. en el botón "Generar plan del mes" de `/calendario`, o en el tour) tipo: "Podés regenerar tu plan mensual 1 vez al mes — la próxima actualización estará disponible el [fecha]". Verificar primero si existe alguna limitación real en el backend para regenerar el calendario más de una vez al mes, o si hoy no hay ningún límite técnico (en cuyo caso, antes de poner el aviso en la UI, hay que decidir si se agrega el límite real en el backend o si el aviso es solo informativo/honor-system).

### 4.9 Bug confirmado: `core/referentes_verify.py::verify_usernames()` no filtra usernames inexistentes

**Encontrado probando en vivo** (buscando referentes reales para Carolina): se le pidieron a Gemini 8 sugerencias de perfiles de abogadas de familia en Chile (`suggest_referentes()`), y las 8 pasaron `verify_usernames()` como "existentes" — pero al revisar el detalle, 5 de las 8 tenían `followers: 0` y `full_name: ""` (vacío), exactamente el mismo patrón que devuelve `apify~instagram-profile-scraper` para un username **inventado que no existe** (se confirmó con la prueba `esteusuarionoexistenuncaxyz123`, que también "existe" según la función).

**Causa raíz:** `fetch_profile_meta()` en `core/referentes_verify.py` arma el diccionario de salida con `out[user] = {...}` para **cualquier** username que el actor de Apify haya procesado, incluso cuando el perfil no existe (el actor devuelve un item "vacío" en vez de omitirlo). `verify_usernames()` solo chequea `if u in meta` — nunca chequea que los datos dentro tengan contenido real.

**Impacto:** el pipeline completo de sugerencia+verificación de Etapa 2 (`core/referentes_discovery.py`, `suggest_verified_referentes`) puede estar devolviendo perfiles que **no existen** como si estuvieran verificados — justo el problema que la Etapa 2.1 original ya sospechaba ("perfiles inexistentes: usernames alucinados que el scraper no encuentra"), confirmado ahora con datos reales.

**Qué hacer:**
1. En `core/referentes_verify.py::verify_usernames()`, cambiar el filtro de `if not u or u not in meta` a algo como `if not u or u not in meta or not (meta[u].get('followers') or meta[u].get('full_name'))` — solo contar como verificado un perfil con al menos seguidores > 0 o nombre completo no vacío.
2. Revisar si conviene mover ese chequeo a `fetch_profile_meta()` directamente (no agregar el username al diccionario de salida si el item viene vacío), para que **cualquier** consumidor de esa función (no solo `verify_usernames`) quede protegido — más seguro que parchear solo el segundo.
3. **Alternativa más robusta a futuro** (no implementar ahora, solo dejar registrado): en vez de que Gemini "adivine" usernames y Apify los verifique uno por uno, usar el actor `apify/instagram-hashtag-scraper` con hashtags del nicho (ej. `#abogadadefamiliachile`, `#derechodefamiliachile`) para traer posts reales y extraer los `ownerUsername` directamente — se probó en vivo con Carolina y dio 51 posts reales de ~35 cuentas distintas en un solo run, muchísimo más confiable que la adivinanza + verificación. Podría reemplazar o complementar `suggest_referentes()` para nichos donde Gemini no conoce cuentas reales de memoria.

### Referentes reales encontrados para Carolina (@tuabogada.carolina) — vía `apify/instagram-hashtag-scraper`

Usando la alternativa de hashtag (punto 3 de arriba) sobre `#abogadadefamilia #derechodefamiliachile #divorciochile`, se encontraron estas 4 cuentas chilenas reales, activas, con contenido de derecho de familia/divorcio verificable hoy mismo en Instagram:

1. **@legalmente.empoderadas** — Constanza Gómez Sáez, abogada de familia con perspectiva de género. La más fuerte de las 4: posts con 2,677 y 14,859 likes, altísimo engagement, ángulo de "empoderamiento femenino" muy modelable para hooks.
2. **@abogada.claudiamontecinos** — Claudia Montecinos, contenido específico sobre régimen de relación directa y regular (visitas), tono técnico-educativo.
3. **@anniealmazan.abogada** — Annie Almazán, abogada de familia joven, tono personal/auténtico (ideal para modelar cercanía, similar al tono que podría querer Carolina).
4. **@legalmente.cl** — "Abogada Chile · Mediadora Familiar", contenido práctico sobre pensión de alimentos, buen ángulo informativo.

Candidatas alternativas si se quiere variar: @soleferabogada (muy activa, posts recurrentes sobre divorcio), @abogadamariajoseopazo, @claridadlegal_cl, @divisionjuridica.cl.

### 4.10 Guía contextual del Estudio de Mercado (post-onboarding) — YA implementado el detalle chico, falta la guía grande

**Feedback de la sesión:** "me gustó el estudio de mercado, muy equilibrado" (positivo — el ranking/score/análisis por post funciona bien). Pero se pidió agregar una **revisión guiada** de los puntos principales al llegar por primera vez a `/mercado`: qué contenido funciona, dónde hacer clic, cómo ver el copy, y una pestaña/panel con el resumen de lo que está viendo — como una guía contextual (no el tour genérico de 9 pasos, sino algo específico de esta página con sus datos reales).

**Ya implementado (6-jul-2026):** el link "Ver en Instagram →" del modal de detalle de post ahora tiene el logo oficial de Instagram + gradiente de marca (rosa/violeta/naranja), para que la transición a Instagram se sienta oficial y esperada.

**Qué falta (más grande, no implementado):**
1. Diseñar un panel/tooltip contextual para `/mercado` que aparezca la primera vez que el cliente entra con datos reales ya cargados (después del estudio de mercado inicial del onboarding) — explicando: qué es el "Score ventas", cómo leer el ranking de referentes, qué hace el botón "Ver copy", y qué significa cada tag (Conexión/Ventas/Educación, Vir. Nx, Fuerza %, Model. N/10).
2. Podría reusar el mecanismo de `TOUR_STEPS`/`showTourStep()` ya existente (agregando un paso específico de `/mercado` con más detalle que el genérico actual), o ser un componente nuevo tipo "guía de primera vez" separado del tour de 9 pasos — a decidir cuál encaja mejor sin duplicar UI.
3. Confirmar con Mauricio el copy exacto de cada explicación antes de implementar (evitar tecnicismos — "Score ventas" y "Fuerza" ya tienen definición interna en `agents/market_research/agent.py`, reusar esas definiciones en el copy).

### 4.11 CTA hacia Calendario apenas termina el primer Estudio de Mercado

**Feedback de la sesión:** después de tener el estudio de mercado listo, el sistema debería recomendar explícitamente ir a generar el Calendario de contenido — "la bienvenida es que ejecute su primer estudio de mercado [y después] recomiende ir a calendario de contenido".

**Contexto:** el flujo de activación (`ACT.step` 1→4) ya avanza de "Estudio de mercado" (paso 2) a "Plan mensual" (paso 3) en ese orden — pero eso vive dentro del modal de activación (`#rima-activation`), que el cliente puede haber cerrado u omitido. El pedido es que, además, la propia página `/mercado` — una vez que el estudio ya tiene datos reales — muestre un CTA visible tipo "Tu estudio de mercado está listo → Generar mi calendario mensual" (no solo depender del modal de activación).

**Qué hacer:**
1. En `dashboard/rima-mercado.html`, cuando `loadMercado()` detecta que hay datos reales (`posts_analyzed > 0`) Y el cliente todavía no generó su calendario mensual (chequear vía `/api/activation/status` o el estado real de publicaciones), mostrar un banner/CTA en la parte superior de la página: "Tu estudio de mercado está listo — generá tu calendario mensual" con botón que dispare `/api/agent/content/run` (o lleve a `/calendario` con el botón "Generar plan del mes" ya resaltado).
2. Verificar que el banner desaparezca una vez que el calendario ya fue generado (no debe seguir apareciendo en visitas futuras).
3. Coordinar con 4.10 — si se implementa la guía contextual de `/mercado`, este CTA puede ser el cierre natural de esa guía ("ya viste lo importante del estudio → siguiente paso: calendario").

### 4.12 Guía del Calendario mensual (primera vez) + mejorar espera del agente semanal — **IMPLEMENTADO 6-jul-2026**

**Pedido de la sesión:** una vez generado el plan mensual, mostrar una guía de qué significa cada cosa (colores por tipo de pieza, distribución en el mes, selector de mes, dónde ver cada pieza) y después invitar a ejecutar el agente semanal (el que mezcla estudio de mercado + calendario mensual). Se preguntó primero para aclarar el diseño antes de tocar código — respuestas de Mauricio:

1. **Formato de la guía:** modal/tooltip guiado que aparece **una sola vez** (como un mini-tour con highlights sobre los elementos reales de `/calendario` — mismo mecanismo que `TOUR_STEPS`/`showTourStep()`, no un panel permanente).
2. **CTA al agente semanal:** se queda como está — el modal de activación actual (`ACT.step===4`) ya lo dispara automáticamente después del calendario. No se agrega un banner nuevo en la página. Lo que sí hay que mejorar: la espera mientras corre (hoy es bastante discreta: solo el botón cambia a "Iniciando semana…" y el status a "Generando propuestas semanales…") — agregar algo más claro tipo "Cargando... esto puede tardar unos minutos" hasta que el resultado esté listo para revisar en `/contenido`.
3. **El tour que se está programando** (la guía de este punto 4.12) debe **terminar llevando al cliente a la sección Contenido** — no quedarse en `/calendario`, sino cerrar el guiado dirigiendo/resaltando el link a `/contenido` como próximo lugar a mirar.
4. **Frecuencia:** solo la primera vez (onboarding) — no se repite en regeneraciones mensuales futuras.

**Contexto técnico ya confirmado (sin tocar todavía):**
- `/calendario` ya tiene una leyenda chica de colores (● Reel ● Carrusel ● Historia, `dashboard/rima-calenadrio.html` línea ~178-180) — la guía nueva puede apoyarse en esos mismos colores/labels, no inventar un esquema nuevo.
- El flujo de activación (`main.py`, `ACT.step===4`, línea ~1430) ya llama `POST /api/agent/weekly/start` de forma síncrona (`await fetch(...)`, botón deshabilitado con texto "Iniciando semana…") y al terminar hace `rimaToast('¡Listo! Revisá tu contenido en Contenido.')` — ya apunta a Contenido, pero como toast efímero, no como parte de un guiado.

**Qué hacer (paso a paso, para implementar después):**
1. Agregar un nuevo flag de estado por usuario (similar a `dashboard_tour`/`activation_flow` en `core/activation_flow.py`) para trackear si ya vio la guía de `/calendario` — ej. `calendario_guide_seen: bool`, con endpoint `GET/POST` análogo a `/api/dashboard/tour`.
2. Diseñar la guía como una secuencia corta de 3-5 pasos con highlights sobre elementos reales de `/calendario`: (a) leyenda de colores por tipo de pieza, (b) selector de mes/navegación, (c) cómo hacer clic en una pieza para ver su detalle, (d) dónde se ven las piezas ya aprobadas vs pendientes. Confirmar el copy exacto de cada paso con Mauricio antes de codear (evitar tecnicismos).
3. Disparar esta guía automáticamente la primera vez que `/calendario` carga con piezas generadas (`total en el calendario > 0`) Y el flag `calendario_guide_seen` es `false` — parecido a como se dispara el tour de 9 pasos hoy.
4. Al terminar la guía (último paso), en vez de solo cerrarse, debe **resaltar o llevar directamente** al ítem "Contenido" del sidebar (reusar el mismo mecanismo de `data-rima-tour`/highlight que ya usa el tour genérico) — comunicando "cuando el agente semanal termine, tu contenido va a aparecer acá".
5. Mejorar la UX de espera del paso `ACT.step===4` (agente semanal): agregar un estado de carga más visible (ej. un spinner + texto "Preparando tu contenido de la semana... esto puede tardar unos minutos" en vez de solo el botón deshabilitado), manteniendo el toast final que ya existe.
6. Marcar `calendario_guide_seen: true` apenas se complete o se cierre la guía (no depende de completar los 5 pasos, similar a como el tour genérico también cuenta "Omitir" como visto).
7. Probar: cliente nuevo → onboarding completo → calendario generado por primera vez → aparece la guía de `/calendario` → cerrarla → confirmar que no vuelve a aparecer en visitas futuras ni en regeneraciones mensuales.

### 4.13 Bloqueo visual al elegir referente + ocultar costo de generación IA + upload directo en biblioteca + avatar real del perfil — **IMPLEMENTADO 6-jul-2026**

**Feedback de la sesión (probando /contenido):**
1. Al hacer clic en "Modelar esta" para una opción, la otra alternativa debía bloquearse al instante (pero seguir visible, no ocultarse).
2. El costo de generación KIE (~$0.09/slide, ~$0.27 total) no debe mostrarse al cliente — va incluido en la suscripción.
3. En el modal "Buscar en la biblioteca" (asignar imagen a un slide), agregar opción de **subir** una imagen directo ahí (ej. screenshot del propio Instagram) en vez de tener que ir a otra sección primero.
4. La advertencia de generación con IA debía ser más sutil/elegante, no un `confirm()` crudo del navegador con foco en el costo.
5. El avatar del sidebar (círculo "CP" con iniciales) — confirmado que hoy NUNCA muestra una foto real, solo iniciales. Se pidió extraer automáticamente la foto de perfil de Instagram durante el primer scrape del onboarding.

**Implementado:**
- `dashboard/rima-contenido.html::elegirReferente` — ahora bloquea (`disabled` + opacidad reducida) **todos** los botones del bloque de propuesta (incluido "↻ Otras opciones") apenas se elige una alternativa, usando el nuevo atributo `data-propuesta-block="{pub.id}"` en el contenedor. Se reactivan solos si falla la request.
- Costo (`~$0.09 USD por slide`, `~$X.XX` en el label del botón) eliminado de: el texto de los botones "Generar carrusel/historia completa con IA" y de los diálogos de confirmación.
- Reemplazado el `confirm()` nativo por un modal propio (`#modal-confirm-ia`, función `confirmarConIA()` con Promise) con copy educativo: *"Vas a generar imágenes con inteligencia artificial, a la medida de tu carrusel/historia..."*.
- Modal de biblioteca (`#modal-biblioteca`) — agregado dropzone "+ Subir imagen" que sube vía `/api/images/upload` (categoría inferida de `pub.tipo`), recarga la biblioteca y **auto-selecciona** la imagen recién subida. `main.py::upload_images` ahora devuelve el `id` de cada imagen subida (antes no lo incluía, necesario para el auto-select).
- **Avatar real del perfil**: nueva función `_save_profile_picture_from_scrape()` en `main.py`, llamada desde `_background_scrape()` justo después de `apply_scrape_to_brand()` — descarga la foto de perfil de IG (la URL de Instagram es temporal, por eso se persiste localmente en `data/uploads/clientes/{cid}/branding/`) y la guarda en `brand["brand_avatar_url"]`. No sobreescribe un avatar ya existente. El sidebar (`_apply_session_to_sidebar` + `_user_bootstrap_script`) ahora muestra ese avatar real (`<img id="rima-user-avatar-img">`) en vez de las iniciales cuando existe. Verificado con descarga real de una URL de CDN de Instagram.

### 4.14 Lightbox de imagen en producción — **IMPLEMENTADO 6-jul-2026**

Clic en la miniatura de un slide (44×44) en la sección de producción de `/contenido` ahora abre la imagen en grande, centrada, con fondo oscuro — clic afuera para cerrar. `dashboard/rima-contenido.html`: nuevo `#modal-imagen-grande` + `abrirImagenGrande()`/`cerrarImagenGrande()`, reusa la clase `.rima-modal-overlay` que ya existía para los otros modales.

### 4.15 Extensión de la "memoria de marca" — tipografía elegible, estilo fotográfico, y roadmap Ads/Ventas/Landing — **A y B IMPLEMENTADOS 6-jul-2026, C queda documentado (roadmap futuro)**

**Implementado:**
- `core/marca_visual.py`: catálogo `TIPOGRAFIA_ESTILOS` (4 estilos, mismos que la tabla de abajo) + `tipografias_de_estilo()`; nuevos campos `visual.tipografia_estilo`, `visual.estilo_fotografico`, `visual.imagen_personaje_url`. `style_hints_from_marca()` prioriza la elección del cliente sobre lo adivinado del scrape; `contexto_marca_para_copy()` agrega la directiva de estilo fotográfico al prompt de los agentes de copy.
- `agents/carousel_generator/agent.py` y `agents/story_generator/agent.py`: `build_style_guide()` propaga `direccion_personaje` (paisajes/modelo_consistente) al `style_guide`; en generación KIE, modo `paisajes` agrega sufijo al prompt evitando personas/rostros; modo `modelo_consistente` reutiliza `imagen_personaje_url` ya fijada como referencia (o la fija con la primera imagen generada, para que sea consistente en generaciones futuras — mismo patrón que ya usaba `face_profile` para la foto real del cliente).
- `dashboard/rima-marca.html`: nueva pestaña "11 · Identidad Visual" con 4 tarjetas de tipografía (preview real con Google Fonts cargadas dinámicamente) y 3 tarjetas de estilo fotográfico, wireadas de forma independiente al resto de la página (que sigue siendo mockup sin persistencia — ver nota abajo) contra `GET/POST /api/marca-visual`, ya existente.
- Verificado con test aislado: `tipografias_de_estilo()`, `style_hints_from_marca()` y `contexto_marca_para_copy()` devuelven los valores esperados.

**Nota importante encontrada:** el resto de `dashboard/rima-marca.html` (tabs 1-10: Negocio, Oferta, Cliente ideal, etc.) es **100% mockup sin persistencia** — `saveForm()` solo muestra un indicador visual, no hay ningún `fetch` de carga ni guardado real en toda la página excepto la pestaña nueva 11 que se agregó ahora. Es un hallazgo grande, consistente con otros mockups ya detectados en la Etapa 1 (`rima-home.html`) — **no se tocó en este sprint** (fuera de alcance de lo pedido), pero es candidato fuerte para una futura Etapa dedicada a conectar `/marca` a datos reales.

**Sin implementar (roadmap, según lo documentado abajo):** la sección C completa (campos `comercial: {...}` para Ads/Ventas/Landing) — queda como diseño para cuando se aborden esas fases.

**Pregunta de la sesión:** qué tiene hoy la memoria del cliente (`marca_visual`), qué se puede mejorar pensando en el producto completo (Meta Ads, guion de ventas de la sección Ventas, presentación/colores de Landing).

**Estado actual (`core/marca_visual.py`, persistido en `clientes.marca_visual_json` por cliente + brief en `data/rima_data.json`):**
```
marca_visual = {
  origen, ig_username, updated_at,
  comunicacion: { tono, muletillas, estilo_copy, palabras_frecuentes },
  visual: { paleta_colores, colores_primarios, colores_secundarios,
            tipografias, estilo_imagen, tipos_toma, imagen_marca_url },
  imagen_marca_id,
}
brief (brand) = { brand_name, brand_service, brand_ideal_client, brand_problem,
                   brand_result, brand_price, brand_success_cases, brand_tone,
                   brand_language, brand_ig, brand_avatar_url (nuevo, 4.13) }
```
Hoy `tipografias` es solo lo que Gemini **cree** haber visto en el IG scrapeado (ej. "Inter Bold", "Montserrat SemiBold") — nunca es una elección real del cliente, y no hay ningún campo de dirección fotográfica (modelo ficticia vs. paisajes/lifestyle vs. mixto) ni de datos para Ads/Ventas/Landing más allá del brief básico.

**Decisiones tomadas en la sesión:**
1. Tipografía: diseñar primero 4 estilos con 2 fuentes c/u (abajo) para aprobar antes de programar la sección en `/marca`.
2. Estilo fotográfico: **elección explícita del cliente** (no inferencia automática) — 3 opciones: "Modelo consistente", "Paisajes/lifestyle sin personas", "Mixto".

#### A) Propuesta de 4 estilos tipográficos (a confirmar antes de implementar)
Usando únicamente Google Fonts (mismas que ya carga el dashboard vía `fonts.googleapis.com`, sin licencias nuevas):

| Estilo | Titulares | Texto/cuerpo | Sensación |
|---|---|---|---|
| **Moderno & Bold** | Inter (700/800) | Inter (400/500) | Limpio, tech, alto contraste — el default actual del dashboard |
| **Editorial & Premium** | Playfair Display (700) | Inter (400) | Elegante, revista, ideal para servicios profesionales/legales (encaja con Carolina) |
| **Cercano & Humano** | Poppins (600/700) | Nunito Sans (400) | Redondeado, cálido, cercano — coaching/bienestar/lifestyle |
| **Directo & Urbano** | Montserrat (800) | Roboto (400) | Geométrico, impacto, ventas agresivas — fitness/negocios/agresivo |

Cada estilo se guardaría como `marca_visual.visual.tipografia_estilo` (id: `moderno`/`editorial`/`cercano`/`urbano`) + `tipografias: [titular, cuerpo]` ya resueltas — reemplaza el campo actual `tipografias` que hoy es solo texto libre adivinado.

**Qué hacer (implementar después de aprobar la tabla de arriba):**
1. Nueva sección en `dashboard/rima-marca.html` — 4 tarjetas con preview visual de cada estilo (texto de muestra renderizado con las fuentes reales vía `@import` de Google Fonts), selección única.
2. Endpoint `PATCH /api/brand` ya existente puede recibir el nuevo campo `tipografia_estilo`; `core/marca_visual.py::merge_from_brand` debe mapearlo a `visual.tipografia_estilo` + resolver `visual.tipografias` desde una tabla fija en código (no vía Gemini).
3. `style_hints_from_marca()`/`contexto_marca_para_copy()` ya arman el bloque de prompt con tipografía — solo hay que asegurarse de que prioricen `tipografia_estilo` elegido sobre lo adivinado del scrape.

#### B) Estilo fotográfico — nuevo campo `visual.estilo_fotografico`
**Qué hacer:**
1. Agregar pregunta al onboarding (candidato: entre el paso de marca visual y fotos — step 4/5 de `dashboard/onboarding.html`) o a `/marca`: 3 opciones con explicación breve de cada una.
2. Nuevo campo `marca_visual.visual.estilo_fotografico`: `"modelo_consistente" | "paisajes" | "mixto"`.
3. Si es `"modelo_consistente"`: usar el mismo mecanismo de `face_profile` (`core/face_profile.py`, ya existe para la foto real del cliente) pero para un **personaje ficticio** — generar/fijar una primera imagen de referencia y pasarla como `image_input` a KIE en generaciones sucesivas para mantener el mismo rostro/apariencia entre slides (mismo patrón que ya usa `carousel_generator` para coherencia de estilo entre slide 1 y siguientes, extendido a coherencia de personaje).
4. Si es `"paisajes"`: los prompts de KIE (`agents/story_generator`, `agents/carousel_generator`) deben evitar pedir personas/rostros y priorizar escenas, objetos, texturas, con una frase/pensamiento como elemento de texto — ajustar las plantillas de prompt en esos agentes.
5. Si es `"mixto"`: comportamiento actual (sin restricción), o alternar según el tipo de pieza.

#### C) Roadmap: qué le falta a la memoria de marca para Ads / Ventas / Landing
No implementar ahora — son features de Fase 2/3 del `ROADMAP.md`, pero conviene que el **esquema de datos** ya prevea estos campos para no tener que migrar después:

- **Meta Ads (Fase 2):** hoy el brief ya tiene `brand_ideal_client` (targeting básico) — faltaría: presupuesto objetivo, objetivo de campaña (leads/ventas/reconocimiento), y un banco de creativos preferidos (qué tipo de imagen convierte mejor, dato que en teoría ya se acumula en `agents/market_research` via `score_ventas` pero no está conectado a Ads todavía).
- **Guion de ventas / sección Ventas:** el brief ya cubre oferta/precio/resultado/casos de éxito (insumos básicos para un guion tipo Hormozi) — faltaría explícitamente: banco de objeciones frecuentes del nicho (hoy el skill `hormozi-sales`/`sales-dialogue` genera esto en documentos aparte, no queda guardado como memoria persistente del cliente en el sistema), y el **tono de cierre** preferido (agresivo/consultivo/educativo) como campo separado del `brand_tone` general de contenido (el tono de un reel no es necesariamente el tono de una llamada de ventas).
- **Landing (Fase 2):** la paleta de colores y tipografía de 4.15-A ya cubren "colores y estilos" — faltaría un campo de **estructura de oferta** tipo Value Stack (qué incluye el programa/servicio en capas) para que la landing no repita el mismo copy genérico que el contenido de Instagram, y un campo de **CTA principal** (agendar llamada / comprar directo / dejar WhatsApp) que hoy no existe en ningún lado del brief.
- **Recomendación general:** cuando se aborden estas 3 fases, extender `marca_visual`/brief con un bloque nuevo `comercial: { objecciones: [], tono_cierre: "", value_stack: [], cta_principal: "", presupuesto_ads_mensual: "", objetivo_ads: "" }` en vez de mezclarlo con `comunicacion`/`visual` — separa claramente "cómo hablo en redes" de "cómo vendo/cierro", que son cosas relacionadas pero distintas.

### 4.16 Dashboard `/home` conectado a datos reales — **IMPLEMENTADO 7-jul-2026**

**Hallazgo:** la sección principal de `/home` (Estado de los agentes, Pendientes, Esta semana) era **100% HTML estático** — cero JS, cero fetch. Un cliente real (Carolina, abogada) veía contenido de fitness inventado ("Rutina 5AM", "Mitos fitness", "@alexfit_mx") en su propio dashboard.

**Implementado:**
- `core/dashboard_stats.py::get_dashboard_stats()` extendido — ahora calcula, además de los KPIs que ya tenía: `calendario` (piezas del mes calendario actual + próxima pieza), `contenido` (conteos reales por tipo entre piezas en pipeline de validación), `mercado_top` (mejor referente real por score_ventas), `pendientes` (lista real: piezas esperando validación, reels por grabar, piezas programadas sin publicar — **en rojo/warning** —, y brief incompleto con % real), `esta_semana` (piezas de la semana lunes-domingo actual, con piezas atrasadas resaltadas en rojo).
- `dashboard/rima-home.html` reescrito: las 3 tarjetas reales (Calendario/Contenido/Estudio de mercado) ahora muestran datos reales y son **clickeables** (llevan a `/calendario`, `/contenido`, `/mercado` respectivamente). Los paneles "Pendientes" y "Esta semana" se renderizan 100% desde el endpoint `/api/dashboard/stats` — ya no hay HTML estático con datos de otro cliente.
- META Ads/Ventas/Landing siguen "Desconectado" (ya arreglado en 4.5, confirmado que sigue vivo tras el deploy).
- Verificado con test aislado de `get_dashboard_stats()` — sin errores, estructura correcta.

**Pendiente (no implementado):** "Zona 3" de `/home` (Actividad reciente + "Reel de la semana") sigue siendo mockup ("Rutina 5AM" repetido) — no se tocó en esta ronda, mismo patrón a aplicar después.

### 4.17 "Ver en Instagram" también en la lista del Estudio de Mercado — **IMPLEMENTADO 7-jul-2026**

El botón con el logo/gradiente de Instagram (ya agregado al modal en 4.13) ahora también aparece **al lado de "Ver copy"** en cada fila de la lista de análisis de `/mercado` — no hace falta abrir el modal para ir directo al post real.

### 4.18 "Información de la marca" (`/marca`, pestaña 1 · Negocio) conectada a datos reales — **IMPLEMENTADO 7-jul-2026**

**Hallazgo:** toda la página `/marca` (pestañas 1-10) es mockup sin persistencia (ya documentado en 4.15) — mostraba datos de "FitLife Studio / Carlos Mendoza" fijos en el HTML, sin relación con la cuenta real logueada.

**Implementado (solo pestaña 1 · Negocio, alcance acordado):**
- Campos conectados a datos reales ya existentes en el brief: nombre del negocio, Instagram, a quién ayudás, dolor principal — se cargan con `GET /api/brand` y quedan **en blanco** si no hay dato (no más "FitLife Studio" hardcodeado).
- Campos nuevos que el brief no tenía (`brand_owner_name`, `brand_city_country`, `brand_niche_industria`, `brand_business_model`, `brand_time_market`, `brand_clients_count`, `brand_previous_attempts`, `brand_origin_story`) — quedan en blanco/sin seleccionar, el cliente los completa; se guardan con `POST /api/brand` al hacer clic en "Guardar cambios" (`saveForm()` ahora llama a un guardado real, antes solo mostraba el indicador visual sin persistir nada).
- Se agregó el chip "Legal" a Industria/Nicho (antes solo tenía nichos de fitness/coaching — Carolina no tenía ninguna opción real para elegir).
- **Pestañas 2-10 siguen sin persistencia real** — fuera de alcance de esta ronda, documentado para una etapa futura dedicada.

### 4.19 `/credenciales` — sacados los datos ficticios que mostraban integraciones falsas — **IMPLEMENTADO 7-jul-2026**

**Hallazgo:** Telegram e Instagram API mostraban badge "Conectado" con valores fijos falsos (`@fitlifestudio_mx`, tokens de ejemplo) — parecía una integración real y activa sin serlo. Además se encontró un **bug de arquitectura**: el endpoint existente `GET/POST /api/credentials` (`main.py` línea ~2090) guarda todo en `data["credentials"]` **global, sin namespace por cliente** — en un sistema multi-tenant, todos los clientes compartirían las mismas credenciales guardadas ahí. No se usó ese endpoint todavía (no hay wiring real), pero hay que corregir el scoping antes de conectarlo de verdad.

**Implementado (solo lo seguro/rápido):**
- Badges cambiados a "Desconectado" (Telegram) y "Pendiente" (Instagram, con nota explicando que requiere cuenta Business + revisión de app de Meta).
- Valores fijos falsos eliminados — inputs vacíos con placeholder, o `disabled` en el caso de Instagram (todavía no hay forma de conectarlo).

**No implementado (requiere trabajo real de OAuth, roadmap):**
- Conectar Telegram de verdad (guardar chat_id/token por cliente — corregir primero el scoping de `/api/credentials`).
- Instagram Graph API real — depende de la revisión de app de Meta (ya documentado en 4.6/ROADMAP.md Fase 2).
- META Ads OAuth — mismo bloqueo, Fase 2.

### Orden sugerido de implementación (Etapa 4-5)
1. 4.5 (dashboard con datos falsos) — más urgente: un cliente real no debe ver plata/conversiones inventadas.
2. 4.3 (cambio de texto del tour, un string, cero riesgo).
3. 4.2 (botón Omitir en fotos).
4. 4.7 (pendiente "Tus referentes").
5. 4.8 (textos educativos post-onboarding + aclarar límite mensual).
6. 4.9 (fix del filtro de verificación de Apify) — afecta la calidad real de la Etapa 2 completa.
7. 4.6 (IG real) queda para más adelante — es un proyecto propio (Meta App Review), no un fix de esta lista.
8. 4.4 y 4.1 no requieren acción — decisiones ya cerradas.
