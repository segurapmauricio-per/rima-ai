# RIMA AI — Contexto del Proyecto
<!-- Última actualización: Jun 11 2026 (Sprint Copy E2E completado en local, sin deploy) -->

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
│   └── db/
│       ├── schema.py    # 5 tablas SQLite: clientes, publicaciones, referentes_contenido, imagenes, notificaciones
│       └── database.py  # CRUD, upsert inteligente, historial de versiones
├── agents/              # 12 agentes especializados
│   ├── content          # Monthly Planner 30d — genera slots → escribe en DB
│   ├── market_research  # v3 — conectado a DB, scores en SQLite/JSON
│   ├── weekly           # Orquestador: propuestas → copy → producción (SQLite)
│   ├── script, image_analysis, story_copy
│   ├── visual_composer  # Sprint B — slides + match de imágenes, determinístico (sin LLM)
│   └── carousel_copy, reel_copy, landing, meta, operations, sales, prospecting
├── bot/
│   ├── telegram_bot.py
│   └── weekly_flow.py
├── dashboard/
│   ├── login.html
│   └── rima-home.html
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
| /contenido | Aprobar tematica/copy | PATCH /api/publicaciones/{id}/aprobar |
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

## Sub-pipeline producción visual (Sprint B Fase 2 — Jun 12, verificado local en negocio_básico)
Al producir carrusel/historia, `agents/visual_composer` (100% determinístico, cero Gemini):
1. `plan_slides(copy_json, tipo, slot_context)` — carrusel: passthrough de copy_json.slides; historia: gancho (hook_text) → desarrollo (body_texts) → cierre (cta_text+keyword, solo si existen).
2. `match_images_to_slides(cliente_id, tipo, slides)` — scoring por solapamiento de tokens (tags x3, descripción/vibe/categoría x1, bonus calidad alta, umbral 3.0) contra `get_imagenes_para`; greedy global sin reusar imágenes. best_text_zone null → "center"; coords derivadas de safe_zone_px si Gemini no las guardó.
3. produccion_json = {etapa, tipo:"visual", slides:[...], generated_at}. Cada slide: image_source "cliente" (image_id, archivo_url, text_zone{zone,coords,color}, match_score) o "kie_pending" (prompt_sugerido por template, ratio 1:1/9:16).
- UI /contenido produccionSection: thumbnail 44px vía /uploads (mount estático) o badge "Imagen IA pendiente — falta configurar KIE AI" + prompt. Fallback para produccion_json viejo con `pendiente`.
- Verificado (Jun 12): carrusel d3042e2d → 7 slides (4 cliente + 3 kie_pending), historia 63ff7758 → 2 slides (kie_pending; las imágenes del cliente no matchean ese copy). Thumbnails sirven 200 vía /uploads. weekly_state sincronizado.

## Sprint KIE + spec visual JSON (Jun 12 tarde — verificado local)
- **Spec visual JSON** (`core/visual_spec.py` + `docs/visual_spec_schema.md`): esquema único para describir piezas visuales desde análisis (origen "analisis", mapeo de analisis_json vía `spec_desde_analisis` / `ImageAnalysisAgent.to_visual_spec`) o para generación (origen "generacion", `spec_desde_slide` + `spec_a_prompt`). Campos video reservados (duracion_seg, escenas).
- visual_composer: slides kie_pending llevan `spec_visual` + `prompt_sugerido` derivado, con paleta de marca desde dominant_colors de imágenes branding y elementos_clave desde slot_context.
- **`core/kie_client.py` REAL (imagen)**: nano-banana vía POST api.kie.ai/api/v1/jobs/createTask + polling jobs/recordInfo (state→resultJson.resultUrls). `RateLimiter` ventana deslizante 20/10s (límite duro de la cuenta). Sin KIE_API_KEY → not_configured. Con reference_image URL pública usa nano-banana-edit (no usable desde localhost). Costo medido: **4 créditos/imagen**, ~20-45s. El CDN de KIE rechaza el User-Agent default de urllib (403) — download_image manda UA de navegador.
- **Video: NO implementado** — Veo3.1 existe (POST /api/v1/veo/generate, clips 8s, polling /api/v1/veo/record-info) pero costo sin documentar; pendiente.
- **POST /api/publicaciones/{id}/generar-imagen-slide** (JWT, body {"slide_index": N}): genera UN slide kie_pending por llamada (nunca masivo), guarda en data/uploads/generadas/{cliente_id}/ y actualiza el slide a image_source "generada_ia" (archivo_url, spec_usada, prompt_usado, kie_task_id). Si la descarga falla devuelve task_id+image_url para no perder el crédito.
- UI: botón "Generar con IA" por slide pendiente, badge violeta "Generada con IA", thumbnail igual que imágenes de cliente.
- Verificado (Jun 12): historia 63ff7758 slide 1 generado real (4 créditos, PNG 1.6MB servido por /uploads, persistido en produccion_json, UI renderiza). Rate limiter validado con límites simulados.

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
- [ ] **Sprint Perfil de Voz:** agente de onboarding — scrape Apify de la cuenta del cliente + transcripción + análisis (vocabulario, expresión, temáticas) → voice_profile.json como 3ra fuente de los copy agents
- [x] **Sprint B (visual) Fases 1–2 (Jun 12, local):** composición de slides historias/carruseles — visual_composer determinístico asigna imágenes del cliente analizadas (17 en negocio_básico) y deja kie_pending con prompt_sugerido donde no hay match. UI con thumbnails/badges. PENDIENTE: API key de KIE AI (nano banana) para generar las imágenes faltantes.
- [ ] **Sprint Reels producción:** vista de grabación por líneas + upload de tomas + agente de edición (cortes de silencio, subtítulos, transiciones)
- [ ] Deploy de todo lo anterior al VPS (28+ archivos WIP sin commitear — esperar OK de Mauricio)
- [ ] Pagina de ventas + onboarding — al final

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
4. Chat hijo devuelve resumen
5. Chat central actualiza RIMA_CONTEXT.md y continua
