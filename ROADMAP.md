# RIMA AI — Roadmap de Producto
<!-- Última actualización: Sep 8 2026 -->

## Visión
Sistema completo de adquisición de clientes con IA para negocios hispanohablantes.
No es una herramienta de contenido — es un empleado digital que genera contenido, convierte leads y cierra ventas.

## Pricing por fase

| Fase | Básico | Pro | Max |
|------|--------|-----|-----|
| 0 — Lanzamiento | $397 MXN | $697 MXN | $1,197 MXN |
| 2 — Con video + ads | $97 USD | $297 USD | $697 USD |
| 3 — Sistema completo | $97 USD | $297 USD | $697 USD + GHL add-on |

---

## Fase 0 — Lanzamiento (ahora)
**Objetivo:** cubrir costos KIE, validar retención con 5–10 usuarios de prueba.

### Ya implementado ✅
- Webhook Gumroad → provisión automática de usuario + SQLite por cliente
- Login JWT con cookie, cambio de contraseña
- Onboarding multi-step: brief de marca, scrape IG propio, assets (fotos + face profile)
- Brief gate: bloquea dashboard hasta completar brief
- Marca visual: paleta, tipografía, estilo; sync desde scrape IG y market research
- Market Research Agent: scrape competitors, scoring de engagement, análisis por nicho
- Monthly Planner: 46 piezas/mes con mix reel/carrusel/historia según plan
- Orquestador semanal: propuestas por semana con referentes rankeados
- Pipeline carrusel E2E: copy (7 slides) → KIE 1080×1080 → ZIP
- Pipeline historia E2E: copy A/B (3–5 slides) → KIE 1080×1920 → ZIP
- Biblioteca de imágenes del cliente para historias
- Face profile: referencia visual para KIE image_input
- **(8-sep-2026)** Composición visual carrusel + historia vía Claude+Playwright por defecto
  (`core/claude_slide_renderer.py`) — reemplaza texto horneado por KIE para carrusel; resaltado
  en aura, no píldora; historias sin wordmark/paginador. Detalle en `SESION_2026-09-08.md`.
- **(8-sep-2026)** `cliente_id` estable por cuenta (`core/referentes_store.py::ensure_cliente_id`)
  — ya no se recalcula del `brand_name` vigente, así que renombrar la marca no desconecta a la
  cuenta de su historial.
- **(8-sep-2026)** Sugerencias de referentes inline en Estudio de Mercado (ya no popup) +
  contador de referentes sincronizado con lo que el estudio de mercado realmente scrapeó.
- **(9-sep-2026)** Modo día/noche en las 17 páginas del dashboard + login + onboarding, con
  toggle persistido en localStorage. Ver `PASO 4` en la skill `rima-ia`.
- **(9-sep-2026)** `save_data()` escribe atómico (temp file + replace) y `load_data()` respalda
  en vez de descartar un `rima_data.json` corrupto — corta el modo de falla que borraba datos
  en silencio al matar el proceso a mitad de un guardado.
- **(9-sep-2026)** `cliente_id` nunca cae en el slug compartido "default" — ver
  `ensure_cliente_id` en `core/referentes_store.py`.
- **(9-sep-2026)** Correo de bienvenida con plantilla HTML de marca (antes texto plano). Logo
  servido desde `/assets/logo_email.png` (mount de StaticFiles) — Gmail bloquea imagenes
  data:base64 en correos recibidos, tiene que ser una URL publica real.
- **(9-sep-2026)** Sentry conectado en producción (`SENTRY_DSN` en Easypanel, solo error
  monitoring). Verificado end-to-end con `/sentry-debug` — ver PYTHON-FASTAPI en sentry.io.
- **(9-sep-2026)** Cache local de fotos de referentes (`core/referentes_photo_cache.py`) —
  descarga la foto de perfil una vez a `data/uploads/referentes_fotos/` (ya montado como
  `/uploads`) y guarda esa URL local estable en vez de la URL firmada de Instagram, que expira
  en horas. Corre en los 4 puntos donde se sincroniza `profile_pic_url` desde Apify
  (`sync_ig_profiles_from_meta`), siempre fuera de cualquier lock/`data_session()` porque hace
  I/O de red. Si la descarga falla pero ya había una foto cacheada de antes, la mantiene en vez
  de perderla.
- **(9-sep-2026)** `data_session()` — lock real (`threading.Lock`) para pares load→modify→save
  con riesgo confirmado: scrape de IG en background vs. su propio polling de estado;
  descubrimiento de referentes similares en background vs. edición del usuario en simultáneo; y
  el propio endpoint de polling (`/api/referentes/discovery`) contra sí mismo, para que dos
  polls casi simultáneos no disparen el mismo scrape en background dos veces. Ver nota de
  alcance en "Pendiente antes de primer usuario" — se auditó el resto de call-sites del archivo
  y no quedó ninguno más con riesgo real por ahora.
- **(9-sep-2026)** Dashboard home (`rima-home.html`) revisado: KPIs, "Estado de los agentes",
  Pendientes y "Esta semana" YA eran reales (datos del backend), contrario a lo que decía este
  mismo roadmap. Se eliminaron las 3 secciones que sí eran mockup sin datos reales detrás
  ("Actividad reciente", "Insight RIMA", "Reel de la semana" — ventas y reels inventados) para no
  mostrarle a un cliente pagando métricas falsas. Se reponen cuando exista un log de actividad
  real y el módulo de Ventas deje de ser mock.

### Pendiente antes de primer usuario ⚠️
- [ ] Deploy VPS nuevo (en curso — 23 jun 2026)
- [ ] **Auto-deploy por webhook roto** (confirmado 9-sep-2026): pushear a `main` NO dispara el
      build en Easypanel — el ultimo deploy automatico fue hace 8 dias, los commits de hoy
      quedaron sin desplegar hasta hacer clic manual en "Implementar". Revisar si el webhook de
      GitHub->Easypanel sigue conectado (Dominios/Fuente del servicio `rima-api`) o si nunca
      estuvo, y alguien deployaba a mano.
- [ ] Cloudflare para DNS + SSL del dominio en el VPS nuevo
- [ ] **Lock de escritura — falta migrar el resto de los call-sites (parcial, revisado 9-sep-2026).**
      Migrados con `data_session()`: `_background_scrape` vs. `api_onboarding_status` (scrape de
      onboarding); `_run_referentes_discovery_background` (fetch_profile_meta/discover_similar_referentes
      tardan segundos con el registro del usuario cargado en memoria); y `api_referentes_discovery`
      (dos polls casi simultáneos podían leer "pending" antes de que cualquiera guardara
      "running" y disparar el scrape en background dos veces). Se auditaron los ~50 usos
      restantes de `load_data()`/`save_data()` en main.py: ninguno tiene hoy una operación lenta
      real entre el load y el save (los webhooks de pago guardan ANTES del await lento; el scrape
      manual `_run_scrape_for_user` ya relee justo antes de guardar; los endpoints de generación
      KIE guardan en SQLite vía `update_publicacion_field`, no en rima_data.json) — quedan sin
      lock por ahora, migrar de a uno si un cambio futuro introduce una espera real ahí.

---

## Fase 1 — Retención
**Objetivo:** que el cliente vea resultados y no cancele.
**Precio:** mismo de Fase 0.

- [ ] **Revisión periódica del perfil IG** (cada 2 semanas)
  - Métricas reales de la cuenta del cliente vs. benchmark del nicho
  - Panel: "Esto está funcionando / Esto hay que mejorar"
  - Requiere: conectar IG Insights API (read-only, sin publish)

- [ ] **Script de ventas auto-ajustable**
  - Generado desde el brief: oferta, precio, resultado, cliente ideal
  - Se ajusta con cada ciclo basándose en objeciones detectadas
  - Presentado en el dashboard como documento vivo editable

- [ ] **Dashboard home rediseñado**
  - Vista central: "Esta semana publicás estas 3 piezas"
  - Indicador de estado del sistema (plan activo, próxima publicación, métricas)
  - Acciones en 1 click desde home

---

## Fase 2 — Conversión
**Objetivo:** el cliente no solo publica, convierte leads.
**Sube precio a USD.**

- [ ] **Publicación automática Instagram**
  - OAuth: cliente conecta su cuenta IG Business desde el dashboard
  - RIMA publica automáticamente según el calendario generado
  - Soporta: feed posts, carruseles, stories
  - Requiere: Meta Developer App + app review (1–4 semanas de proceso)
  - Nota: Reels requieren video; RIMA genera imágenes hoy → integrar con editor de video primero

- [ ] **Editor de video automático para Reels**
  - Input: guion generado por reel_copy agent + fotos/clips del cliente
  - Output: Reel listo para publicar
  - Integración: Creatomate API o Runway (no construido desde cero)
  - Habilita auto-publish de Reels

- [ ] **Trial Reels (variaciones para atraer clientes)**
  - Mismo patrón que `visual_composer`/KIE para imágenes: Claude analiza un reel con buen
    desempeño (transcript, timing, hook) y genera una spec de edición (intro distinta, recorte,
    texto overlay, orden de clips) — Claude no renderiza video, solo decide qué cambiar
  - Ejecución del render: ffmpeg (barato, propio, evaluar primero) o Submagic (ya en stack para
    otros usos de video, costo por minuto) — decidir cuál alcanza antes de sumar dependencia
  - Uso: generar variantes reales (no duplicados) de un reel que ya funcionó, para publicar como
    contenido de prueba/gancho y atraer clientes nuevos
  - Depende de: Publicación automática Instagram (arriba) para publicar las variantes solas

- [ ] **Landing page pre-armada con VSL**
  - Estructura Hormozi: problema → mecanismo → oferta → CTA
  - Generada desde el brief del cliente (propuesta de valor, precio, resultado, cliente ideal)
  - VSL: video de ventas con guion generado por RIMA
  - Ajuste automático según métricas de conversión
  - Hosting: subdominio del cliente en infraestructura RIMA

- [ ] **Meta Ads integrado**
  - Creativos generados desde el mismo pipeline KIE (carrusel + historia adaptados a paid)
  - Copy de ad generado con estructura probada por nicho
  - Sugerencia de segmentación basada en cliente ideal del brief
  - Exporta creativos listos para subir al Ads Manager

---

## Fase 3 — Sistema completo
**Objetivo:** loop cerrado contenido → lead → llamada → cierre → datos al sistema.

- [ ] **Análisis de llamadas de ventas**
  - Opciones de integración: Fireflies.ai API o tl;dv (corto plazo) / Whisper + Claude (control total)
  - Transcribe llamada → detecta objeciones reales del nicho → actualiza script de ventas
  - Detecta qué contenido generó la conversación → refuerza ese tipo de post
  - Panel: "Objeciones más frecuentes esta semana"

- [ ] **GHL CRM integrado**
  - Al completar onboarding en RIMA → crea sub-cuenta GHL automáticamente via API
  - Instala snapshot por nicho: pipeline CRM + automations + templates de mensajes
  - Inyecta datos del brief: nombre negocio, propuesta de valor, cliente ideal, precio
  - Conecta número WhatsApp o email del cliente
  - Crea landing page del cliente desde template con datos del brief
  - Requiere: cuenta Agency GHL o SaaS Mode

- [ ] **TOFU / MOFU / BOFU conectado**
  - Contenido IG (TOFU) → landing (MOFU) → seguimiento GHL (BOFU)
  - El sistema sabe en qué etapa del funnel está cada lead
  - Sugerencias de contenido basadas en qué etapa necesita más refuerzo

- [ ] **Sugerencias de videos externos (TOFU/MOFU/BOFU)**
  - Análisis de qué videos del nicho están funcionando en YouTube/TikTok
  - Sugerencias de temas para crear basadas en búsquedas del cliente ideal
  - Clasificados por etapa del funnel

---

## Estrategia de contenido propio (RIMA vendiéndose a sí misma)
**Objetivo:** usar RIMA IA para generar el contenido de RIMA IA — dogfooding como prueba social
y como canal de adquisición hacia infoproductores/coaches (el segmento que más necesita publicar
seguido y menos tiempo tiene).

- [ ] **Árbol de contenido temático** — pilares de tema para decidir qué genera más leads,
  medido por cuenta propia antes de generalizarlo a clientes:
  - ManyChat / automatización de DMs
  - Claude / IA aplicada a marketing
  - Marketing y adquisición de clientes
  - Generación de imágenes con IA (KIE, resultado del propio producto)
  - Recursos gratuitos (lead magnets, plantillas, mini-guías)
  - Pendiente: instrumentar qué pilar convierte mejor (leads/DMs por pilar) para retroalimentar
    el Monthly Planner con pesos reales en vez de la distribución genérica actual

---

## Diferencial competitivo

Ninguna herramienta entrega esto junto hoy:
1. Market research real del nicho (no hashtag research genérico)
2. Imágenes AI custom desde cero — no templates (KIE nano-banana-pro)
3. Pipeline completo en español nativo para LATAM
4. Loop cerrado: contenido → lead → venta → retroalimentación al sistema

Competencia real: agencias de contenido LATAM ($2,000–$8,000 MXN/mes, manual).
Propuesta de valor Fase 3: sistema de agencia completo a precio de herramienta.

---

## Stack técnico

- **Backend:** FastAPI + Python, SQLite por cliente
- **Agentes:** Gemini (copy, research, planning) + KIE AI (imágenes)
- **Dashboard:** HTML vanilla, endpoints REST
- **Infra:** Ubuntu 24.04 VPS Hostinger, nginx, systemd
- **Pagos:** Gumroad webhook → provisión automática
- **Email:** Resend (transaccional — bienvenida, recuperación de contraseña)
- **Errores:** Sentry (tracking producción)
- **DNS/SSL:** Cloudflare
- **Futuro:** Meta Graph API (publish + ads), GHL API, Fireflies/tl;dv API, Creatomate/Runway

### Stack evaluado y descartado (23 jun 2026)
Lista de herramientas "stack para startups" revisada contra la arquitectura real de RIMA (monolito FastAPI con tareas async de fondo en VPS, no serverless):
- **Vercel** — no aplica, RIMA usa tareas largas (scraping, KIE) incompatibles con timeouts serverless
- **Supabase / Clerk** — no aplica, ya hay SQLite por cliente + JWT + Google OAuth funcionando
- **Stripe / Hotmart** — no urgente, Gumroad ya validado end-to-end; reevaluar en Fase 2 al subir a USD
- **PostHog / Upstash / Pinecone** — prematuro, requiere usuarios reales o rediseño de arquitectura
