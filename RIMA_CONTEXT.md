# RIMA AI — Contexto del Proyecto

## Datos clave
- **Repo:** https://github.com/segurapmauricio-per/rima-ai
- **Demo en vivo:** https://rima.n8n-ghl.com/login
- **Stack:** FastAPI + Python, dashboard HTML, agentes Gemini, bot Telegram
- **VPS:** Ubuntu 24.04, IP 2.24.73.213, usuario root, Hostinger
- **Credenciales:** ver .env del VPS o preguntar a Mauricio

## Estructura del proyecto
```
rima-ai/
├── main.py              # FastAPI app principal (~1800 lineas)
├── core/
│   ├── auth.py          # JWT login (NUEVO)
│   ├── client_store.py  # Persistencia de clientes
│   └── gemini_client.py # Cliente Gemini
├── agents/              # 12 agentes especializados
│   ├── content, sales, prospecting, market_research
│   ├── script, weekly, image_analysis, story_copy
│   └── carousel_copy, reel_copy, landing, meta, operations
├── bot/
│   ├── telegram_bot.py  # Bot Telegram
│   └── weekly_flow.py   # Flujo semanal de aprobacion
├── dashboard/           # HTML del dashboard
│   ├── login.html       # Pagina de acceso (NUEVO)
│   └── rima-home.html   # Home principal
└── Conocimiento/        # Docs de negocio (markdown)
```

## Estado actual
- [x] Login JWT en produccion con HTTPS
- [x] Deploy en VPS con nginx + systemd
- [x] claude-mem activo (memoria persistente entre sesiones)
- [x] Graphify indexado (868 nodos, 1252 edges)
- [x] Context7 MCP configurado
- [x] Superpowers, Frontend Design, Ralph Loop, Playwright instalados
- [x] Correo enviado a Lemon Squeezy con demo en vivo
- [x] Todas las rutas del dashboard protegidas con JWT
- [ ] Login con Google (OAuth2) — necesita GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET de console.cloud.google.com
- [ ] Pagina de ventas + onboarding automatico post-pago
- [ ] Flujo Telegram aprobaciones (pulir)
- [ ] Agregar API keys al .env del VPS

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

## XPrize
- Competencia: https://devpost.com/submit-to/29541-build-with-gemini-xprize
- RIMA usa Gemini como motor principal de IA

## Flujo de trabajo
1. Chat central lee este archivo + consulta grafo + memoria claude-mem
2. Genera prompt especifico para subtarea
3. Chat hijo trabaja subtarea en aislado
4. Chat hijo devuelve resumen
5. Chat central actualiza RIMA_CONTEXT.md y continua
