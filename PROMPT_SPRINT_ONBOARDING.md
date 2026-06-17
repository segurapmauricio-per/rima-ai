# Sprint Onboarding — RIMA AI
<!-- Prompt para chat hijo · Jun 15 2026 · Copiar desde "## INSTRUCCIÓN" hacia abajo -->

## Contexto del proyecto
- **Repo:** `C:/Users/Mauricio/projects/rima-ai`
- **Stack:** FastAPI + Python, dashboard HTML, SQLite por cliente, agentes Gemini, KIE AI, Apify
- **Memoria:** leer **`RIMA_CONTEXT.md`** completo (actualizado Jun 15 — historias E2E + diseño visual)
- **Servidor local:** `python main.py` → `:8000` · scripts `scripts/start_rima.ps1` / `stop_rima.ps1`
- **Demo prod:** https://rima.n8n-ghl.com/login
- **Objetivo macro:** prototipo vendible — falta **solo secuencia reels en producción**; onboarding es el bloque crítico antes de **prueba cuenta real → deploy**

---

## INSTRUCCIÓN (copiar al chat hijo)

Sos el agente de implementación del **Sprint Onboarding** de RIMA AI.

### Tu misión
1. **Leer el proyecto** (no asumir): `RIMA_CONTEXT.md`, este archivo, y explorar código relevante.
2. **Auditar qué existe, qué funciona y qué falta** en el flujo post-pago → primer contenido.
3. **Armar un plan por fases** (con criterios de “listo para probar” por fase).
4. **Implementar incrementalmente** — cada fase debe poder probarse antes de la siguiente.
5. **Documentar** avances en `RIMA_CONTEXT.md` al cerrar cada fase.

**Reglas:** español LATAM en UI copy · no commitear sin OK de Mauricio · reutilizar convenciones existentes · scope mínimo correcto · probar con comandos reales.

---

### Alcance del onboarding (producto)

#### A. Lo que ya debería existir — VERIFICAR, no reimplementar

| Área | Dónde mirar | Qué validar |
|------|-------------|-------------|
| **Pago Gumroad** | `main.py` → `POST /api/webhooks/gumroad`, `_provision_user_from_payment` | Ping sale → usuario en `data/rima_data.json`, plan normalizado (`normalize_plan`), `status: active` |
| **Contraseña temporal** | `send_welcome_email`, SMTP env vars | Email con password + link `APP_LOGIN_URL` |
| **Cancelación / baja** | Gumroad webhook `cancellation`, `refund`, `dispute`, `refunded=true` | Marca `users[email].status = cancelled` — **¿bloquea login? ¿SQLite? ¿falta UI self-service?** |
| **Login JWT** | `core/auth.py`, `POST /auth/login`, `dashboard/login.html` | `password_hash` sha256; fallback legacy `password == email` si no hay hash |
| **SQLite por cliente** | `core/db/schema.py`, `init_db`, `create_or_update_cliente` | `data/clients/{cliente_id}/rima.db` — tablas: clientes, publicaciones, referentes, imagenes, notificaciones |
| **Brief de marca** | `core/client_store.py` → `brief.json`; `POST/GET /api/brand` | Campos: business_name, service, ideal_client, problem, main_result, price, success_cases… |
| **Marca visual** | `core/marca_visual.py`, `clientes.marca_visual_json`, `GET /api/marca-visual` | Paleta, tono, idioma — usado por copy agents y `slide_renderer` |
| **Scrape Apify IG** | `agents/market_research/agent.py` — `ACTOR_PROFILE`, `ACTOR_POSTS` | Profile scraper ya usado para **competidores** en market research — **NO** onboarding del propio cliente aún |
| **Subida imágenes** | `dashboard/rima-imagenes.html`, `POST /api/images/upload` | Categorías historias/carruseles/branding + análisis Gemini Vision |
| **Pipeline contenido** | `dashboard/rima-contenido.html` | Historias E2E (Jun 15), carruseles KIE, reels copy — **reels producción incompleto** |

#### B. Lo que FALTA o está incompleto — objetivo del sprint

1. **Wizard onboarding paso a paso** (encuesta, no formulario único)
   - Redirect post-login si `onboarding_completed !== true`
   - Pasos sugeridos (ajustar tras auditoría):
     1. Bienvenida + cambio de contraseña obligatorio (si vino de email temporal)
     2. @ Instagram del negocio → **disparar scrape en background** (Apify profile) mientras el usuario sigue
     3. Brief esencial (campos mínimos del `BrandBrief` en `main.py`)
     4. Identidad visual: confirmar/editar paleta inferida del scrape + tono + idioma
     5. Fotos para historias: upload mínimo N (real, no IA con personajes inventados)
     6. **Foto rostro / estilo carnet** → generar `face_profile.json` (o similar) para KIE
     7. Resumen + “Comenzar” → `onboarding_completed`, redirigir a /contenido o /lab

2. **Scrape IG del cliente en paralelo**
   - Reusar `market_research._scrape_profile` / Apify profile actor
   - Persistir en `marca_visual_json` + enriquecer `brief_json`
   - Mostrar progreso en UI (“Analizando tu perfil…”)

3. **Face profile para KIE**
   - Upload 1 foto frontal clara
   - JSON con: referencia imagen URL/path, prompts base, restricciones (“usar este rostro, no inventar personajes”)
   - Integrar en `kie_client` / `story_generator` / `carousel_generator` como `reference_image` o spec

4. **Gestión de contraseña privada**
   - `POST /api/auth/change-password` (actual + nueva)
   - Forzar cambio si `must_change_password: true` en usuario Gumroad nuevo
   - UI en wizard paso 1 y en `/configuracion` (hoy solo mock “Próximamente”)

5. **Sistema de baja del cliente**
   - Webhook Gumroad ya marca `cancelled` — extender:
     - Bloquear login si `status !== active`
     - Opcional: página “Cancelar suscripción” con link Gumroad + confirmación
     - Estado en SQLite `clientes.status`
   - Documentar flujo manual vs automático

6. **Conectar UI existente**
   - `dashboard/rima-marca.html` — **mock sin fetch** → conectar a `/api/brand` + `/api/marca-visual`
   - `dashboard/rima-configuracion.html` — ampliar (password, baja, plan)

---

### Campos clave del brief (prioridad onboarding)

Del modelo `BrandBrief` y uso en agentes:
- `business_name`, `service`, `ideal_client`, `problem`, `main_result`
- `price`, `success_cases`, `guarantee`
- Extra útiles: `ig_username`, `brand_tone`, `brand_language`, `recording_day`, `enfoque_default`

Persistencia dual habitual:
- `rima_data.json` → `users[email].brand`
- SQLite → `clientes.brief_json` + `config_json`
- Filesystem → `data/clients/{slug}/brief.json`

**Sincronizar** al guardar onboarding (patrón ya en `POST /api/brand` + `merge_from_brand`).

---

### Qué se crea por cliente nuevo (Gumroad)

```
data/rima_data.json
  users[email]: { name, plan, password_hash, status, brand: { brand_name, plan }, onboarding_* }

data/clients/{cliente_id}/
  rima.db                    ← init_db(cliente_id)
  brief.json                 ← ensure_client_dirs (al primer save_brief)
  images/{historias,carruseles,branding}/
  memory.json, content/, weekly/, ...

uploads/clientes/{cliente_id}/...
```

`cliente_id` = `cliente_id_from_brand(brand)` en `core/referentes_store.py`.

---

### Integración con pipeline de contenido (post-onboarding)

Onboarding debe dejar listo:
- `marca_visual_json` con paleta → copy en idioma correcto + diseño historias (`slide_renderer`)
- Biblioteca con fotos **reales** del cliente → historias híbridas (match + KIE)
- `face_profile.json` → KIE sin personajes IA genéricos
- Brief completo → monthly planner + weekly orchestrator

**No bloquear** `/contenido` si onboarding incompleto en dev; en prod sí redirect al wizard.

---

### Plan de trabajo esperado (entregable fase 0)

Antes de codear, producir en el chat:

```markdown
## Auditoría onboarding RIMA — [fecha]

### Funciona hoy
- [lista con evidencia: archivo, endpoint, probado sí/no]

### Parcial / roto
- [lista]

### No existe
- [lista]

## Plan por fases
### Fase 1 — … (criterio done: …)
### Fase 2 — …
…

## Riesgos / decisiones para Mauricio
- [preguntas concretas]
```

Luego ejecutar **Fase 1** y pedir prueba manual.

---

### Prueba E2E post-onboarding (objetivo final del sprint)

1. Simular venta Gumroad (ping test o script)
2. Recibir email / anotar password temporal
3. Login → wizard completo
4. Verificar SQLite + brief + marca_visual + imágenes analizadas
5. Lab: market research o weekly start
6. Contenido: generar 1 historia completa hasta ZIP
7. Cambiar password + simular cancelación Gumroad → login bloqueado

---

### Archivos probables a tocar

```
main.py                          # rutas onboarding, change-password, webhook extras
core/auth.py                     # must_change_password, cancelled check
core/db/schema.py + database.py  # onboarding_json, face_profile en clientes
core/marca_visual.py             # sync desde scrape cliente
core/client_store.py             # voice_profile / face_profile paths
agents/market_research/agent.py  # scrape_client_profile (wrapper)
dashboard/onboarding.html        # NUEVO wizard
dashboard/rima-configuracion.html
dashboard/rima-marca.html        # conectar APIs
main.py routes                   # redirect si !onboarding_completed
```

---

### Fuera de scope (pero mencionar en plan)

- Deploy VPS (después de E2E local)
- Secuencia **reels producción** (siguiente sprint tras onboarding)
- Lemon Squeezy (legacy; Gumroad es piloto activo)
- Video KIE / Veo

---

### Referencias internas

- Pagos: `PROMPT_SPRINT_GUMROAD_PAGOS.md`
- Copy E2E: `PROMPT_SPRINT_COPY_E2E.md`
- Visual/KIE: `PROMPT_SPRINT_KIE_JSON_VISUAL.md`
- Historias: `RIMA_CONTEXT.md` sección Sprint Historias E2E
- Conocimiento marca: `Conocimiento/agents/story_copy.md`, `core/marca_visual.py` docstring

---

### Credenciales test (no producción)

- `max@test.com` / `uno` → Negocio Max
- `basico@test.com` / `uno` → Negocio Básico

---

**Empezá leyendo `RIMA_CONTEXT.md` y ejecutá la auditoría (Fase 0). No implementes hasta tener el plan aprobado por Mauricio, salvo fixes críticos obvios encontrados en la auditoría.**
