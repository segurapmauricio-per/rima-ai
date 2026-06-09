# RIMA AI — Contexto del Proyecto
<!-- Última actualización: Jun 9 2026 -->

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
│   ├── content          # Monthly Planner — genera 20 reels + stories → escribe en DB
│   ├── market_research  # Pendiente: conectar a DB con upsert de referentes
│   ├── script, weekly, image_analysis, story_copy
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

## Endpoints nuevos (Jun 5, listos en backend, pendiente conectar dashboard)
- GET /api/publicaciones?mes=&status=&tipo=
- GET /api/publicaciones/{id}
- PATCH /api/publicaciones/{id}/status
- PATCH /api/publicaciones/{id}/aprobar
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
- [x] Monthly Planner conectado a DB — genera slots y escribe en publicaciones (Jun 5)
- [x] Endpoints /api/publicaciones, /api/referentes, /api/imagenes listos (Jun 5)
- [ ] **LUNES P1:** Probar flujo completo — Lab → Monthly Planner → ver slots en /calendario y /contenido
- [ ] **LUNES P2:** Refactorizar agentes: distribucion rotativa por semana, Market Research → DB, ContentAnalyzer como sub-agente
- [ ] **LUNES P3:** Construir: ContentSelector, StoryCreator, Notifier (Telegram con historial)
- [ ] Conectar cada pagina del dashboard a su endpoint real (reemplazar datos estaticos)
- [ ] Flujo Telegram — despues de que agentes tengan estructura de datos
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
