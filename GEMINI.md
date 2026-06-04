# RIMA AI — Contexto del Proyecto

## Qué es RIMA
SaaS de marketing con IA para negocios de servicios en LATAM (coaches, gyms, clínicas, academias).
Automatiza: investigación de referentes → propuesta de ideas → guión → aprobación cliente → edición de video → publicación.

## Stack
- **Backend:** FastAPI (Python) — `main.py`
- **Frontend:** HTML/JS vanilla — `dashboard/` (12 páginas)
- **IA:** Gemini 2.5 Flash via Vertex AI (modelo: `google/gemini-2.5-flash`)
- **Auth IA:** Application Default Credentials (`gcloud auth application-default login`)
- **Storage:** JSON local en `data/rima_data.json` (temporal, migrar a Firestore)
- **Deploy:** localhost:8000, próximamente Google Cloud Run

## Proyecto Google Cloud
- Project ID: `rima-ai-498117`
- Location: `us-central1`
- Créditos: $268.274 CLP activos hasta agosto 2026

## Estructura de archivos clave
```
main.py                  — FastAPI server, todas las APIs, sidebar JS inyectado
core/gemini_client.py    — Cliente Gemini via Vertex AI
core/brand_knowledge.py  — Conocimiento de marca y metodologías
agents/landing/agent.py  — Agente generador de landing pages
agents/content/agent.py  — Agente de contenido Instagram
agents/meta/agent.py     — Agente META Ads
agents/sales/agent.py    — Agente de ventas
agents/prospecting/agent.py — Agente de prospección
dashboard/               — 12 páginas HTML del dashboard
data/                    — Uploads y datos persistentes (NO subir a git)
```

## APIs disponibles en main.py
- `GET/POST /api/brand` — datos de marca
- `GET/POST /api/credentials` — credenciales META/Telegram
- `POST /api/images/upload`, `GET /api/images`, `DELETE /api/images/{cat}/{file}`
- `POST/GET/DELETE /api/videos/{reel_id}/clips`
- `POST/GET /api/videos/{reel_id}/final`
- `GET/POST /api/videos/{reel_id}/state`
- `POST /api/videos/{reel_id}/edit` — stub agente editor
- `POST /api/generate/landing` — genera landing con IA
- `POST /api/generate/contenido` — genera contenido con IA

## Correr el servidor
```bash
cd C:\Users\Mauricio\projects\rima-ai
python main.py
# Abre http://localhost:8000
```

## Reglas importantes
1. NUNCA modificar `.env` — tiene las credenciales
2. NUNCA subir `data/` ni `.env` al repo (están en .gitignore)
3. Antes de cambiar `main.py`, leerlo completo primero
4. El sidebar se inyecta via `SHARED_JS` en `main.py` — no editar el aside en los HTML
5. Usar `google/gemini-2.5-flash` como modelo en Vertex AI

## Concurso
Build with Gemini XPRIZE — deadline 17 agosto 2026
- Necesita: revenue real + Gemini ejecutando funciones core + deploy en Cloud Run
- Categoría: Small Business Services (LATAM)
- Revenue via Lemon Squeezy + Wise

## Próximos pasos pendientes
- [ ] Probar agentes generando contenido real
- [ ] Auth de usuarios (login/registro)
- [ ] Deploy en Cloud Run
- [ ] Integrar Lemon Squeezy webhooks
- [ ] Migrar storage a Firestore
- [ ] Onboarding: landing → plan → brief → dashboard
</content>
</invoke>