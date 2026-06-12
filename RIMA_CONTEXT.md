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
- POST /api/publicaciones/{id}/producir — reel: script_agent (guion teleprompter A/B en produccion_json); carrusel/historia: gancho a image_analysis (composición visual = Sprint B)
- POST /api/publicaciones/{id}/refresh-propuesta, POST /api/agent/weekly/clear-week
- UI /contenido: botones "Modelar esta", "Aprobar copy", "Generar guion"/"Preparar visual", "Aprobar producción" + badges por estado
- Flujo legacy del bot Telegram (next_story/approve_story en agents/weekly) sigue existiendo pero está desconectado del dashboard — candidato a deprecar

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
- [x] Todas las rutas del dashboard protegidas con JWT — 48 endpoints API con Depends(get_current_user) + rutas HTML con require_auth → redirect /login. Deployado y verificado en VPS (Jun 4).
- [x] Login con Google OAuth2 — implementado localmente (authlib + SessionMiddleware + boton en login.html). PENDIENTE: variables .env en VPS + configurar Google Cloud Console + deploy.
- [x] SQLite DB implementada — 5 tablas, CRUD completo, historial de versiones (Jun 5)
- [x] Monthly Planner 30d conectado a DB — genera slots y escribe en publicaciones
- [x] Market Research v3 conectado a DB — ranking R1-R4 cerrado (rotación semanal, scores temáticos internos ~78/22, filtro ≥35→≥20→pool)
- [x] Dashboard conectado a APIs reales: /contenido, /calendario, /mercado, /lab usan SQLite (no datos estáticos)
- [x] **Sprint Copy E2E (Jun 11, local):** pipeline completo propuesta→copy→aprobación→producción para reel/carrusel/historia, verificado con 1 pieza de cada tipo en negocio_básico. weekly_state.json sincronizado desde SQLite.
- [ ] **Sprint Perfil de Voz:** agente de onboarding — scrape Apify de la cuenta del cliente + transcripción + análisis (vocabulario, expresión, temáticas) → voice_profile.json como 3ra fuente de los copy agents
- [ ] **Sprint B (visual):** composición de slides historias/carruseles — asignar imágenes del cliente (image_analysis) + fallback KIE AI (nano banana) para completar secuencias
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
