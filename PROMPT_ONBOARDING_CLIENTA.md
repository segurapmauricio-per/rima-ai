# Prompt — Onboarding de clienta real en RIMA AI

> Copiá TODO lo que está debajo de la línea y pegalo como primer mensaje en un chat nuevo.
> Reemplazá lo que está entre `[CORCHETES]` con los datos reales de la clienta.

---

## Contexto

Trabajo en **RIMA AI**, un SaaS que genera contenido de Instagram (reels, carruseles e
historias) para pequeños negocios en LATAM. Es FastAPI + SQLite por cliente.

- **Código local:** `C:\Users\Mauricio\projects\rima-ai`
- **Producción:** https://rima-ia-rima-api.yltnhy.easypanel.host (Easypanel/Docker, VPS Hostinger)
- **Repo:** https://github.com/segurapmauricio-per/rima-ai — última versión en `main`, commit `c261b48`
- **Panel de deploy:** Easypanel → proyecto `rima_ia` → servicio `rima-api`
- Servidor local: `python main.py` → http://localhost:8000

**Cómo quiero trabajar:** en paneles de infraestructura (Easypanel, Hostinger, GHL) los clics
los hago yo — guiame de a **un paso por vez** y esperá que te diga qué veo. No manejes mi
navegador. En la app local sí podés levantarla y verificar vos.

## Objetivo de esta sesión

Dar de alta a mi primera clienta real y dejarle el perfil completo para que pruebe el producto.
Esto es una **prueba de usuario con una persona real**, no un test técnico: cada cosa que
generemos la va a ver ella.

Datos de la clienta:
- Nombre: `[NOMBRE Y APELLIDO]`
- Email: `[EMAIL]`
- Negocio / marca: `[NOMBRE DEL NEGOCIO]`
- Instagram: `[@usuario]`
- Rubro y a qué se dedica: `[DESCRIPCIÓN]`
- Plan asignado: `[basico | pro | max]`

## Paso 1 — Crear la cuenta en producción

Se hace desde la terminal del contenedor en Easypanel (ícono `>_` en la barra del servicio
`rima-api`). Este comando ya está probado end-to-end: crea la usuaria, genera contraseña
temporal segura, fuerza el cambio en el primer login, inicializa su base SQLite y su registro
de cliente. Con `ENVIAR_EMAIL = False` **no** manda correo y muestra la clave en pantalla.

```bash
cd /app && python3 - <<'PY'
import asyncio, main

EMAIL  = "[EMAIL]"
NOMBRE = "[NOMBRE Y APELLIDO]"
MARCA  = "[NOMBRE DEL NEGOCIO]"
PLAN   = "[basico|pro|max]"
ENVIAR_EMAIL = False

capt = {}
_orig = main.send_welcome_email
async def _cap(to, name, pwd):
    capt["pwd"] = pwd
    if ENVIAR_EMAIL:
        await _orig(to, name, pwd)
main.send_welcome_email = _cap

cid = asyncio.run(main._provision_user_from_payment(EMAIL, NOMBRE, PLAN, MARCA))
print("\n=========================================")
print("  email      :", EMAIL)
print("  password   :", capt.get("pwd", "(ya existia: sin cambios)"))
print("  plan       :", PLAN)
print("  cliente_id :", cid)
print("  login      :", main.APP_LOGIN_URL)
print("=========================================\n")
PY
```

> **Crítico:** de `MARCA` se deriva el `cliente_id` (ej. "Estudio Ana" → `estudio_ana`), que es
> la carpeta y la base donde vive TODO su contenido. Poner el nombre real desde el arranque —
> cambiarlo después le deja los datos huérfanos.

## Paso 2 — Onboarding (7 pasos en la app)

Entra con el email y la clave temporal. El wizard pide, en orden:

1. **Contraseña** — cambio obligatorio de la temporal (mínimo 8 caracteres).
2. **Instagram** — su `@`. Dispara un scrape con Apify que precarga marca, paleta y tono.
   Si el perfil es privado o falla, se puede continuar y cargar todo a mano.
3. **Brief** — nombre, servicio u oferta, cliente ideal, problema, resultado principal, precio
   y casos de éxito. Los cinco primeros son obligatorios. **Esta es la parte que más define la
   calidad del contenido** — vale la pena redactarla bien con ella, no despacharla.
4. **Identidad visual** — paleta, tono, idioma y **estética de las imágenes**. Hay cinco
   presets: `grafico_bold` (diseño con texto integrado, el look clásico), `hiperrealista`,
   `cinematografico`, `editorial` y `ugc_movil`. Elegir según su rubro; se cambia cuando se
   quiera desde Marca → Identidad visual.
5. **Fotos para historias** — mínimo 3 según el plan. Fotos reales de ella o su negocio.
6. **Foto de rostro** — frontal, tipo carnet. RIMA la usa para no inventar personajes.
7. **Resumen** y confirmación.

## Paso 3 — Activación (después del onboarding)

En este orden, verificando cada uno antes de seguir:

1. **Referentes** — cargar cuentas de Instagram de su nicho que le sirvan de modelo. El límite
   depende del plan (básico 3, pro 6, max 10).
2. **Estudio de mercado** — scrapea y analiza los posts de esos referentes con Apify + Gemini.
   Tarda y **consume créditos reales**.
3. **Calendario mensual** — genera los slots planificados.
4. **Semana** — el orquestador propone piezas concretas por día.
5. **Generación** — copy primero, después las imágenes con KIE AI.

## Costos reales a tener en cuenta

- **KIE AI**: ~4 créditos por imagen generada. Un carrusel de 7 slides son ~28.
- **Apify**: el scrape de referentes cuesta por perfil analizado.
- No hacer generación masiva "para probar". Generar una pieza de cada tipo y evaluar.

## Estado del producto — qué funciona y qué no

**Funciona y está verificado:** pagos por Gumroad con provisión automática, emails por Resend,
onboarding completo, scrape de Instagram, estudio de mercado, calendario, orquestador semanal,
generación de copy, generación de imágenes de carruseles (texto integrado, calidad Canva) e
historias (foto + overlay), presets de estética, biblioteca de imágenes por cliente.

**No existe todavía:** edición automática de video. La página `/videos` deja subir clips pero
`POST /api/videos/{reel_id}/edit` es un stub que solo encola. El plan es integrar la API de
Submagic (cortar silencios, zooms dinámicos, subtítulos) — decidido activarla recién con el
primer cliente pago, y el primer paso es un spike que valide que la API realmente corta
silencios, porque hay evidencia contradictoria en la documentación.

**Bugs conocidos, no bloqueantes para vender:**
- `/openapi.json` devuelve 500 (`PydanticInvalidForJsonSchema`), así que `/docs` queda vacío.
- `/uploads` está montado sin autenticación: cualquiera con la URL exacta lee el archivo.
  Aplica a imágenes y videos. Los nombres de video llevan token aleatorio para mitigar.
- Varias secciones del dashboard todavía muestran datos mock (ver `CAMBIOS_SOLICITADOS.md`).

## Reglas de la sesión

- **No commitear** salvo que lo pida explícitamente.
- Antes de afirmar que algo funciona, verificalo y mostrame la evidencia.
- Si algo falla con la clienta mirando, priorizá dejarla avanzando por otro lado y anotá el
  bug, en vez de frenar la demo para depurar.
