# RIMA AI — Contexto del Proyecto
<!-- Última actualización: Jun 15 2026 (Sprint Historias + diseño visual enriquecido, local sin deploy) -->

## Datos clave
- **Repo:** https://github.com/segurapmauricio-per/rima-ai
- **Demo en vivo:** https://rima.n8n-ghl.com/login
- **Stack:** FastAPI + Python, dashboard HTML, agentes Gemini, bot Telegram
- **VPS:** Ubuntu 24.04, IP 2.24.73.213, usuario root, Hostinger
- **Credenciales:** ver .env del VPS o preguntar a Mauricio

## Estructura del proyecto
```
rima-ai/
├── main.py              # FastAPI app principal
├── core/
│   ├── auth.py          # JWT + Google OAuth2
│   ├── client_store.py  # Persistencia de clientes
│   ├── gemini_client.py # Cliente Gemini
│   ├── kie_client.py    # KIE AI (nano-banana-pro, image_input, rate limit)
│   ├── visual_spec.py   # Spec visual JSON + prompts ES/EN por idioma
│   ├── marca_visual.py  # Paleta, idioma_cliente, style_hints para copy/KIE
│   ├── carousel_plan.py # Artefacto plan.json carrusel
│   ├── story_plan.py    # Artefacto plan.json historias 9:16
│   ├── slide_renderer.py # Render final Pillow (historias diseño enriquecido)
│   └── db/
│       ├── schema.py    # 5 tablas SQLite: clientes, publicaciones, referentes_contenido, imagenes, notificaciones
│       └── database.py  # CRUD, upsert inteligente, historial de versiones
├── agents/              # 12+ agentes especializados
│   ├── content          # Monthly Planner 30d — genera slots → escribe en DB
│   ├── market_research  # v3 — conectado a DB, scores en SQLite/JSON
│   ├── weekly           # Orquestador: propuestas → copy → producción (SQLite)
│   ├── script, image_analysis, story_copy
│   ├── story_generator  # Batch KIE historias 9:16 (híbrido biblioteca + IA)
│   ├── carousel_generator # Batch KIE carrusel texto integrado + coherencia
│   ├── visual_composer  # Slides + match biblioteca / kie_pending (determinístico)
│   └── carousel_copy, reel_copy, landing, meta, operations, sales, prospecting
├── bot/
│   ├── telegram_bot.py
│   └── weekly_flow.py
├── dashboard/
│   ├── login.html
│   ├── rima-home.html
│   └── rima-contenido.html  # Pipeline E2E reels/carruseles/historias
└── Conocimiento/
```

## Mapa Dashboard → DB (endpoints disponibles)
| Pagina | Elemento | Endpoint |
|--------|----------|----------|
| /home | Publicaciones pendientes | GET /api/publicaciones?status=propuesta_enviada |
| /home | Piezas esta semana | GET /api/publicaciones?mes= |
| /calendario | Slots del mes | GET /api/publicaciones?mes=Julio 2026 |
| /calendario | Detalle al click | GET /api/publicaciones/{id} |
| /contenido | Cards reels/carruseles/historias | GET /api/publicaciones?tipo=reel&semana= |
| /contenido | Aprobar tematica/copy/visual | PATCH /api/publicaciones/{id}/aprobar |
| /contenido | Elegir propuesta copy historia | POST /api/publicaciones/{id}/elegir-copy |
| /contenido | Generar carrusel/historia KIE batch | POST .../generar-carrusel-ia · .../generar-historia-ia |
| /contenido | Descargar ZIP slides finales | GET /api/publicaciones/{id}/descargar-carrusel |
| /mercado | Top referentes | GET /api/referentes/top?tipo=reel |
| /imagenes | Galeria | GET /api/imagenes |
| /lab | Monthly Planner | POST /api/agent/content/run |
| /lab | Market Research | POST /api/agent/market-research |
| /lab | Orquestador semanal | POST /api/agent/weekly/start |

## Pipeline Copy E2E (Jun 11 — verificado local en negocio_básico)
Estados de publicaciones (SQLite es la fuente de verdad; weekly_state.json es espejo derivado vía `sync_weekly_state_from_db`):
```
planificado → propuesta_generada → [elegir-referente] → copy_generado
→ [aprobar campo=copy] → copy_aprobado → [producir] → en_produccion
→ [aprobar campo=visual] → produccion_aprobada → programado → publicado
```
- POST /api/publicaciones/{id}/elegir-referente — genera copy (reel/carrusel/historia) con pasaporte del slot (R4)
- PATCH /api/publicaciones/{id}/aprobar — campo=copy avanza a copy_aprobado; campo=visual a produccion_aprobada
- POST /api/publicaciones/{id}/producir — reel: script_agent (guion teleprompter A/B en produccion_json); carrusel/historia: visual_composer (ver sub-pipeline abajo)
- POST /api/publicaciones/{id}/refresh-propuesta, POST /api/agent/weekly/clear-week
- UI /contenido: botones "Modelar esta", "Aprobar copy", "Generar guion"/"Preparar visual", "Aprobar producción" + badges por estado
- Flujo legacy del bot Telegram (next_story/approve_story en agents/weekly) sigue existiendo pero está desconectado del dashboard — candidato a deprecar

## Sub-pipeline producción visual (actualizado Jun 15)
Al producir carrusel/historia, `agents/visual_composer` (determinístico, cero Gemini):

**Carrusel**
1. `plan_slides` — passthrough de `copy_json.slides` (7 slides del carousel_copy).
2. `slides_kie_integrado` — **no** matchea biblioteca automáticamente; cada carrusel genera imágenes nuevas vía KIE (biblioteca solo asignación manual).
3. `carousel_generator.generate_carousel_batch` — nano-banana-pro, texto integrado, slide 1 → referencia slides 2+.
4. Render: si `texto_en_imagen` → PNG directo de KIE; si no → overlay Pillow simple.

**Historia (Sprint Jun 15 — metodología Santiago Muñoz / Nico Azero)**
1. `plan_slides` — passthrough de `copy_json.slides` (3–5 slides: gancho → desarrollo → cierre). Legacy: hook/body/cta.
2. `match_images_to_slides` — **híbrido**: fotos reales del cliente (historia/branding); excluye `generada_ia` de otras secuencias; faltantes → `kie_pending`.
3. `story_generator.generate_story_batch` — KIE 9:16, coherencia visual, mantiene fotos de biblioteca.
4. `slide_renderer.render_publicacion_visual` — diseño enriquecido al aprobar visual:
   - 2 colores de marca (primario + acento desde `marca_visual`)
   - Palabras `**resaltadas**` → recuadros pill (acento)
   - MAYÚSCULAS / números → color primario
   - Símbolos por rol: ✦ gancho · ▸ desarrollo · → cierre
   - Barra lateral primaria, scrim degradado, punto decorativo terciario
   - Salida: PNG 1080×1920 + ZIP `historia-{pub_id}.zip`

- UI `/contenido`: propuestas A/B de copy (historias), editar slides, batch KIE, preview/descarga final.
- Cliente test: **Negocio Max** (`max@test.com` / pass `uno`).

## Sprint Historias E2E (Jun 15 — implementado local, pendiente E2E completo + deploy)
Flujo dashboard:
```
planificado → propuesta (2 ángulos estratégicos) → elegir-referente + copy
→ copy_generado (2 propuestas secuencia 3–5 slides) → elegir-copy (A/B)
→ [editar-slides] → aprobar copy → copy_aprobado
→ producir / match biblioteca → generar-historia-ia (pendientes KIE)
→ aprobar visual → render Pillow enriquecido → produccion_aprobada → descargar ZIP
```
Archivos clave: `agents/story_copy/`, `agents/story_generator/`, `core/story_plan.py`, `core/slide_renderer.py`.
Endpoints nuevos: `POST /elegir-copy`, `POST /generar-historia-ia`.
Copy: temática/enfoque fijos del plan mensual; idioma desde `marca_visual`; keywords con `**` para diseño.

## Sprint Carrusel KIE + Copy nutritivo (Jun 14–15 — local)
- `carousel_copy`: 7 slides estructurados, bullets, 5 formatos, valor_audience, idioma/marca.
- `carousel_generator` + `POST /generar-carrusel-ia` — nano-banana-pro (~$0.09/slide).
- Fix: carruseles no reutilizan mismas imágenes de biblioteca entre publicaciones.
- UI: botón "Generar carrusel completo con IA", editar slides, descarga ZIP 1080×1080.

## Sprint KIE + spec visual JSON (Jun 12 — base, extendido Jun 15)
- **Spec visual JSON** (`core/visual_spec.py` + `docs/visual_spec_schema.md`): esquema único para describir piezas visuales desde análisis (origen "analisis", mapeo de analisis_json vía `spec_desde_analisis` / `ImageAnalysisAgent.to_visual_spec`) o para generación (origen "generacion", `spec_desde_slide` + `spec_a_prompt`). Campos video reservados (duracion_seg, escenas).
- visual_composer: slides kie_pending llevan `spec_visual` + `prompt_sugerido` derivado, con paleta de marca desde dominant_colors de imágenes branding y elementos_clave desde slot_context.
- **`core/kie_client.py`**: default `nano-banana-pro`, `image_input[]` para coherencia, fallback legacy. RateLimiter 20/10s. ~18 créditos/imagen pro vs ~4 legacy. Download con UA navegador (CDN 403 sin UA).
- **POST /generar-imagen-slide** — un slide por llamada (carrusel/historia).
- **POST /generar-carrusel-ia** · **POST /generar-historia-ia** — batch con `confirmar_costo: true`.

## Endpoints base (Jun 5)
- GET /api/publicaciones?mes=&status=&tipo=
- GET /api/publicaciones/{id}
- PATCH /api/publicaciones/{id}/status
- GET /api/referentes/top?tipo=&limit=
- GET /api/imagenes?uso=

## Estado actual
- [x] Login JWT en produccion con HTTPS
- [x] Deploy en VPS con nginx + systemd
- [x] claude-mem activo (memoria persistente entre sesiones)
- [x] Graphify indexado (868 nodos, 1252 edges)
- [x] Context7 MCP configurado
- [x] Superpowers, Frontend Design, Ralph Loop, Playwright instalados
- [x] Correo enviado a Lemon Squeezy con demo en vivo
- [x] Pagos Gumroad: webhook `/api/webhooks/gumroad` implementado y probado en local
  (main.py, junto al de Lemon) — recibe Ping form-urlencoded, valida `seller_id` contra
  `GUMROAD_SELLER_ID`, mapea `product_name`→plan con `normalize_plan` (incluye "Plan
  Agencia RIMA AI"→max), y usa `_provision_user_from_payment` para dejar al usuario con
  password temporal, `brand_name` inicial (evita cliente_id "default") y SQLite
  provisionada via `init_db`. Al crear el usuario se envía automáticamente un correo
  de bienvenida (`send_welcome_email`, SMTP Gmail vía `smtplib`/`asyncio.to_thread`)
  con el password temporal y el link de login. Probado end-to-end con ping real de
  Gumroad (local + ngrok): 200 OK, usuario creado, SQLite provisionada, correo recibido.
  Variables nuevas en `.env` (local, pendiente copiar al VPS): `GUMROAD_SELLER_ID`,
  `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` (Gmail App Password),
  `EMAIL_FROM`, `APP_LOGIN_URL`. Falta: configurar la URL del Ping en Gumroad
  (Settings → Advanced) apuntando al VPS una vez deployado, y deploy a producción.
  Lemon sigue activo sin cambios; cuenta de Stripe (Gumroad) operativa sin bloqueos
  pendientes — Whop descartado para este sprint.
- [x] Todas las rutas del dashboard protegidas con JWT — 48 endpoints API con Depends(get_current_user) + rutas HTML con require_auth → redirect /login. Deployado y verificado en VPS (Jun 4).
- [x] Login con Google OAuth2 — implementado localmente (authlib + SessionMiddleware + boton en login.html). PENDIENTE: variables .env en VPS + configurar Google Cloud Console + deploy.
- [x] SQLite DB implementada — 5 tablas, CRUD completo, historial de versiones (Jun 5)
- [x] Monthly Planner 30d conectado a DB — genera slots y escribe en publicaciones
- [x] Market Research v3 conectado a DB — ranking R1-R4 cerrado (rotación semanal, scores temáticos internos ~78/22, filtro ≥35→≥20→pool)
- [x] Dashboard conectado a APIs reales: /contenido, /calendario, /mercado, /lab usan SQLite (no datos estáticos)
- [x] **Sprint Copy E2E (Jun 11, local):** pipeline completo propuesta→copy→aprobación→producción para reel/carrusel/historia, verificado con 1 pieza de cada tipo en negocio_básico. weekly_state.json sincronizado desde SQLite.
- [x] **Sprint B (visual) Fases 1–2 (Jun 12, local):** composición slides + match biblioteca + kie_pending.
- [x] **Sprint Carrusel KIE + copy nutritivo (Jun 14–15, local):** carousel_generator, generar-carrusel-ia, texto integrado, fix no-reuso biblioteca, idioma/marca en copy.
- [x] **Sprint Historias E2E (Jun 15, local):** secuencias 3–5 slides 9:16, 2 propuestas copy, elegir-copy, híbrido biblioteca+KIE, generar-historia-ia, render diseño enriquecido (2 colores, pills, símbolos).
- [ ] **E2E historias Negocio Max:** probar flujo completo semana actual (después de onboarding).
- [ ] **Sprint Onboarding (ACTIVO — Jun 15):** wizard paso a paso, scrape IG cliente en paralelo, brief + marca visual, fotos historias, face_profile.json para KIE, change-password, baja/cancelación. Ver **`PROMPT_SPRINT_ONBOARDING.md`**.
- [ ] **Sprint Reels producción:** vista grabación + upload tomas + edición
- [ ] Deploy al VPS (WIP sin commitear — esperar OK de Mauricio)
- [ ] Página de ventas

## Precios
| Plan | Precio |
|---|---|
| Plan Basico | $97/month |
| Plan Pro | $297/month |
| Plan Agencia | $697/month |

## Comandos utiles

### Consultar grafo (local)
```bash
python -m graphify query "TU PREGUNTA" --budget 2000 --graph "C:/Users/Mauricio/projects/rima-ai/graphify-out/graph.json"
```

### Actualizar grafo
```bash
cd "C:/Users/Mauricio/projects/rima-ai" && python -m graphify update . --no-cluster
```

### Deploy en VPS
```bash
ssh root@2.24.73.213
cd /opt/rima-ai && git pull origin main && systemctl restart rima
```

### Ver logs
```bash
journalctl -u rima -f
```

## Smoke test post-deploy (auth)
```bash
# Sin token — debe retornar 401
curl https://rima.n8n-ghl.com/api/brand
# Con token valido (obtener de DevTools > Application > Cookies > access_token)
curl -H "Cookie: access_token=TOKEN" https://rima.n8n-ghl.com/api/brand
# Webhook Lemon — debe seguir funcionando sin token
curl -X POST https://rima.n8n-ghl.com/api/webhooks/lemon
# Rutas publicas que deben responder sin token
curl https://rima.n8n-ghl.com/login
curl https://rima.n8n-ghl.com/api/health
```

## XPrize
- Competencia: https://devpost.com/submit-to/29541-build-with-gemini-xprize
- RIMA usa Gemini como motor principal de IA

## Flujo de trabajo
1. Chat central lee este archivo + consulta grafo + memoria claude-mem
2. Genera prompt especifico para subtarea
3. Chat hijo trabaja subtarea en aislado
4. Chat hijo devuelve resumen (formato abajo)
5. Chat central actualiza RIMA_CONTEXT.md y continua

### Resumen estándar para chat central (Jun 15)
Ver bloque "Entregable chat central" en el último sprint completado, o pegar:
- **Qué se hizo** (1 párrafo)
- **Archivos tocados** (lista)
- **Endpoints/UI nuevos**
- **Verificado / pendiente**
- **Siguiente paso acordado**
