# RIMA AI — Roadmap de Producto
<!-- Última actualización: Jun 17 2026 -->

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

### Pendiente antes de primer usuario ⚠️
- [ ] Deploy VPS nuevo (en curso — 23 jun 2026)
- [ ] Resend para email de bienvenida con temp_password (reemplaza SMTP manual, 3,000 emails/mes gratis)
- [ ] Sentry para tracking de errores en producción (KIE, scraping, agentes background)
- [ ] Cloudflare para DNS + SSL del dominio en el VPS nuevo
- [ ] Dashboard home rediseñado: pantalla de acciones claras, no solo lista de publicaciones
- [ ] Fix race condition scrape IG background (save_data concurrente con brief)

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
