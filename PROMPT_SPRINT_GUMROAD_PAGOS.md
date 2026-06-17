# Contexto — RIMA AI · Sprint Pagos: integración Gumroad (piloto)

## Proyecto
RIMA AI = FastAPI + SQLite por cliente + dashboard HTML + agentes Gemini + bot Telegram.
Ruta: C:/Users/Mauricio/projects/rima-ai
Servidor: python main.py → http://localhost:8000 (reiniciar, no persiste entre sesiones)

## Por qué este sprint
Vamos a lanzar un **piloto esta semana** con un cliente real (con 80% de descuento a
cambio de feedback), rumbo a la competencia "Build with Gemini XPRIZE" (necesita ingresos
reales verificables). Mauricio ya tiene cuenta en **Gumroad** activa — vamos a usarla para
cobrar el piloto, adaptando el patrón que ya existe para Lemon Squeezy.

En paralelo (fuera de este sprint, lo hace Mauricio): re-verificar la cuenta de Lemon
Squeezy (fue rechazada antes) como opción a mediano plazo, y dejar Whop como alternativa
no implementada por ahora.

## Estado actual relevante (NO reimplementar, solo extender)
- `main.py:1561-1630` — webhook de Lemon Squeezy ya implementado:
  - `_verify_lemon_signature()` valida HMAC-SHA256 con `LEMON_WEBHOOK_SECRET`.
  - `_create_user_from_payment(email, name, plan)` — crea/actualiza usuario en
    `rima_data.json` (`users[email] = {name, plan, status, created_at}`), SIN password,
    SIN `brand_name`, SIN provisionar cliente SQLite. Por eso el onboarding hoy es
    incompleto.
  - `POST /api/webhooks/lemon` — recibe el evento, verifica firma, llama a
    `_create_user_from_payment` para `order_created`/`subscription_created`, y marca
    `cancelled` en `subscription_cancelled`.
- `core/auth.py`:
  - `verify_login(email, password, users_db)` — si el usuario no tiene
    `password_hash`, acepta `password == email` como fallback (ver línea ~91). Repasar si
    conviene mantener ese fallback para el piloto o generar password real.
  - `_hash_password()` / `_verify_password()` disponibles para setear `password_hash`.
- `core/plan_limits.py::normalize_plan(plan)` — normaliza el nombre del producto/plan a
  `"basico"|"pro"|"max"`. Reusar esto para mapear el producto de Gumroad al plan interno.
- `core/referentes_store.py::cliente_id_from_brand(brand)` y `init_db(cliente_id)` (en
  `core/db`) — provisionan la SQLite del cliente automáticamente al primer acceso. Pero
  para que el dashboard funcione, el usuario en `rima_data.json` necesita tener
  `brand_name` (o equivalente) para que `cliente_id_from_brand` tenga algo con qué
  derivar el `cliente_id` — hoy el webhook de Lemon NO setea esto, por lo que cae en
  "default".

## Objetivo de este sprint
1. Implementar `POST /api/webhooks/gumroad` siguiendo el mismo patrón que Lemon, pero con
   el formato real de los webhooks ("pings") de Gumroad (confirmar en Fase 1 — Gumroad
   envía `application/x-www-form-urlencoded`, no JSON, y la verificación de autenticidad
   es distinta a Lemon — confirmarlo en docs, no asumir HMAC igual).
2. Mejorar el flujo de creación de usuario (`_create_user_from_payment` o una versión
   nueva compartida) para que, a partir del pago, el usuario quede **completamente
   provisionado**:
   - Mapear el producto/variante de Gumroad → plan interno (`basico`/`pro`/`max`) vía
     `normalize_plan`.
   - Generar una password temporal (o usar un token de "completar registro") y
     `password_hash` con `_hash_password`.
   - Asociar/derivar un `brand_name`/`cliente_id` inicial (puede quedar pendiente de
     completar por el cliente en un wizard simple — pero el usuario debe poder loguearse
     y llegar a algún lado, no caer en "default" silenciosamente).
   - Llamar a `init_db(cliente_id)` para que la SQLite del cliente quede creada.
3. Dejar un mini-wizard o al menos un endpoint/página simple para que, tras el primer
   login, el cliente piloto complete `brand_name` + datos básicos de su negocio (lo
   mínimo para que el Monthly Planner / Market Research puedan correr). Si ya existe algo
   parecido, extenderlo; si no, lo mínimo viable (puede ser un formulario simple en
   `dashboard/`).
4. Documentar en `RIMA_CONTEXT.md` el nuevo flujo de pago→onboarding (Gumroad) y dejar
   anotado que Lemon sigue existiendo en paralelo (no removerlo).

## REGLAS NO NEGOCIABLES (igual que siempre)
1. NO desplegar nada al VPS en este sprint — eso es un paso aparte que hace Mauricio
   manualmente esta semana.
2. NO correr scraping (Apify) ni Market Research nuevo.
3. NO tocar el pipeline de copy/Sprint B/KIE ya cerrados.
4. NO commitear salvo que Mauricio lo pida explícitamente.
5. Todos los endpoints nuevos/protegidos deben usar `Depends(get_current_user)` donde
   corresponda (el webhook de pagos NO usa JWT — se autentica por firma/secret de
   Gumroad, igual que Lemon).
6. Responder siempre en español.
7. Cambios pequeños y verificables, uno a la vez.
8. **Seguridad de secretos**: cualquier secret de Gumroad (API key, secret de
   verificación) va a `.env` vía `os.environ`, nunca hardcodeado, nunca logueado.
9. No adivinar el formato exacto del webhook de Gumroad — confirmarlo en Fase 1
   (documentación oficial de Gumroad: "Ping" / webhooks, y "License Verification API" si
   aplica).

## Fase 1 — Diagnóstico (reportar antes de codear)
1. Investigar (vía WebFetch/docs oficiales) el formato real del webhook "Ping" de
   Gumroad: qué campos llegan (email del comprador, nombre del producto/variante, precio,
   `sale_id`, etc.), formato (form-urlencoded vs JSON), y cómo se verifica que la
   notificación es legítima (¿comparten un `seller_id` fijo? ¿hay firma? ¿hay que llamar
   a una API de verificación de licencia con `product_permalink` + `license_key`?).
2. Confirmar qué variable de entorno hace falta (ej. `GUMROAD_SELLER_ID`,
   `GUMROAD_ACCESS_TOKEN`, etc. según lo que diga la doc) y dejarla documentada para que
   Mauricio la complete en `.env` (sin pedir el valor real, solo el nombre de la
   variable).
3. Revisar `rima_data.json` (estructura real de `users`) y confirmar qué campos mínimos
   necesita un usuario para que `cliente_id_from_brand` + `init_db` + el dashboard
   funcionen de punta a punta (recorrer `core/referentes_store.py` y `core/db/`).
4. Revisar si existe algún wizard/onboarding parcial ya construido (buscar en
   `dashboard/` y `main.py` por "onboarding", "wizard", "brand_name").

Entregar tabla: Paso del flujo (pago→login→dashboard funcional) | Qué hay hoy | Qué falta
| Riesgo.

## Fase 2 — Implementación (tras aprobación de Fase 1)
En el orden que tenga sentido según el diagnóstico:
1. `POST /api/webhooks/gumroad` con la verificación real confirmada en Fase 1.
2. Función de provisioning compartida (reusar o extender `_create_user_from_payment`)
   que deje al usuario con: plan normalizado, password utilizable, `brand_name`/
   `cliente_id` inicial, SQLite inicializada.
3. Wizard/endpoint mínimo de completar perfil post-pago (si hace falta).
4. Cupón de 80% off para el piloto: esto se configura en el dashboard de Gumroad
   (acción manual de Mauricio, no requiere código) — solo confirmar que el webhook
   funcione igual con un pago con descuento.

## Fase 3 — Verificación
1. Probar el webhook con un payload de ejemplo (el que confirme la doc de Gumroad o un
   test real desde Gumroad si Mauricio dispara un "Ping" de prueba desde su dashboard).
2. Confirmar que el usuario creado puede loguearse (`/login`) y llega a un dashboard
   funcional (aunque sea con `brand_name` por completar).
3. Actualizar `RIMA_CONTEXT.md` con el flujo de pagos Gumroad + estado de Lemon (en
   paralelo, pendiente de re-verificación) + Whop (no implementado).

## Archivos clave
- main.py (webhook Lemon existente ~línea 1561, nuevo webhook Gumroad)
- core/auth.py (hash de password, verify_login)
- core/plan_limits.py (normalize_plan)
- core/referentes_store.py (cliente_id_from_brand)
- core/db/ (init_db)
- rima_data.json (estructura de users)
- dashboard/ (wizard de onboarding si hace falta)
- RIMA_CONTEXT.md
- .env (nombres de variables nuevas, sin valores)

Empezá por la Fase 1 (investigar el webhook real de Gumroad con WebFetch a la
documentación oficial) y mostrame la tabla antes de tocar código.
