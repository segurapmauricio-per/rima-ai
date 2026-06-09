"""
RIMA AI — Database Schema
SQLite con columnas JSON para datos ricos.
Un archivo .db por cliente en: data/clients/{cliente_id}/rima.db
"""

SCHEMA_VERSION = "1.0.0"

# ── Tablas ────────────────────────────────────────────────────────────────────

CREATE_CLIENTES = """
CREATE TABLE IF NOT EXISTS clientes (
    id              TEXT PRIMARY KEY,
    nombre          TEXT NOT NULL,
    ig_username     TEXT,
    plan            TEXT NOT NULL DEFAULT 'basico',  -- basico | pro | max
    status          TEXT NOT NULL DEFAULT 'activo',
    -- Rich JSON fields
    brief_json      TEXT DEFAULT '{}',  -- brand brief completo
    memoria_json    TEXT DEFAULT '{}',  -- aprendizajes acumulados del agente
    config_json     TEXT DEFAULT '{}',  -- {timezone, ig_avg_views, enfoque_default, autopublish}
    metricas_cuenta_json TEXT DEFAULT '{}',  -- performance de la cuenta del cliente
    -- Timestamps
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
"""

CREATE_PUBLICACIONES = """
CREATE TABLE IF NOT EXISTS publicaciones (
    id              TEXT PRIMARY KEY,
    cliente_id      TEXT NOT NULL,
    -- Planificacion (Monthly Planner)
    fecha           TEXT NOT NULL,          -- YYYY-MM-DD
    semana          INTEGER,                -- 1-4
    dia             TEXT,                   -- Lunes, Martes...
    mes             TEXT,                   -- Julio 2026
    tipo            TEXT NOT NULL,          -- reel | carrusel | historia
    tematica        TEXT,                   -- Problema | Solucion | Resultado | Mentalidad | Proceso
    enfoque         TEXT,                   -- Ventas | Educacion | Conexion
    -- Estado (maquina de estados del Weekly Orchestrator)
    status          TEXT NOT NULL DEFAULT 'planificado',
    -- planificado -> propuesta_generada -> propuesta_enviada -> propuesta_aprobada
    -- -> copy_generado -> copy_enviado -> copy_aprobado
    -- -> en_produccion -> produccion_enviada -> produccion_aprobada
    -- -> programado | cancelado
    -- Referencias
    referente_id    TEXT,                   -- FK referentes_contenido.id
    -- Contenido generado (JSON)
    propuesta_json  TEXT DEFAULT '{}',      -- {angulo, hook_idea, referente_url, justificacion}
    copy_json       TEXT DEFAULT '{}',      -- {hook, desarrollo, cta, lead_magnet, script_completo}
    produccion_json TEXT DEFAULT '{}',      -- {archivos: [], instrucciones_editor: ''}
    archivos_json   TEXT DEFAULT '{}',      -- {imagen_url, video_url, secuencia_urls: [], thumbnail_url}
    -- Historial de versiones (Notifier)
    versiones_json  TEXT DEFAULT '[]',      -- array de {v, etapa, contenido, feedback, status, created_at}
    -- Aprobaciones del cliente
    aprobaciones_json TEXT DEFAULT '{"tematica": false, "copy": false, "visual": false}',
    -- Programacion
    programado_at   TEXT,
    hora_publicacion TEXT,                  -- HH:MM (random en ventana permitida)
    publicado_at    TEXT,
    -- Metadata
    agente_origen   TEXT DEFAULT 'monthly', -- monthly | weekly | manual
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);
"""

CREATE_REFERENTES_CONTENIDO = """
CREATE TABLE IF NOT EXISTS referentes_contenido (
    id                  TEXT PRIMARY KEY,
    cliente_id          TEXT NOT NULL,
    referente_username  TEXT NOT NULL,
    plataforma          TEXT DEFAULT 'instagram',  -- instagram | youtube
    url                 TEXT UNIQUE,
    tipo                TEXT,               -- reel | carrusel | video
    fecha_publicacion   TEXT,
    fecha_scrape        TEXT,
    -- Datos crudos
    titulo              TEXT,
    descripcion         TEXT,
    hashtags_json       TEXT DEFAULT '[]',  -- array de strings
    transcripcion       TEXT,               -- audio/video transcrito
    texto_extraido      TEXT,               -- texto de carrusel/slides
    -- Metricas basicas (se actualizan en cada scrape)
    vistas              INTEGER DEFAULT 0,
    likes               INTEGER DEFAULT 0,
    comentarios         INTEGER DEFAULT 0,
    guardados           INTEGER DEFAULT 0,
    seguidores_al_scrape INTEGER DEFAULT 0,
    -- Metricas personalizadas (calculadas)
    fuerza              REAL,   -- (vistas + comentarios*2) / seguidores
    relevancia          REAL,   -- vistas / avg_vistas_ultimas_10 del referente
    engagement          REAL,   -- (likes + comentarios*2 + guardados*3) / vistas
    ratio_conversacion  REAL,   -- comentarios / vistas
    modelabilidad       INTEGER, -- 1-10, asignado por ContentAnalyzer
    score_ventas        REAL,   -- 0-100, prioridad modelado comercial
    -- Analisis (JSON rico, generado 1 sola vez por ContentAnalyzer)
    analisis_json       TEXT DEFAULT '{}',
    -- {tematica, tipo_angulo, hook, cta, lead_magnet, recurso_ofrecido,
    --  problema_resuelto, aspecto_vida, elementos_visuales, elementos_sonido,
    --  enfoque, notas_modelacion, que_vende, que_no_funciona}
    analizado_at        TEXT,
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);
"""

CREATE_IMAGENES = """
CREATE TABLE IF NOT EXISTS imagenes (
    id              TEXT PRIMARY KEY,
    cliente_id      TEXT NOT NULL,
    archivo_url     TEXT NOT NULL,
    nombre_archivo  TEXT,
    tamano_bytes    INTEGER,
    -- Analisis (generado por ImageAnalyzer al subir)
    analisis_json   TEXT DEFAULT '{}',
    -- {estilo, paleta_colores, tiene_personas, tiene_texto, mood,
    --  calidad_score, profundidad_campo, iluminacion, notas}
    usable_para_json TEXT DEFAULT '[]',    -- ['historia', 'carrusel']
    tags_json       TEXT DEFAULT '[]',     -- tags de estilo para busqueda
    analizado_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
);
"""

CREATE_NOTIFICACIONES = """
CREATE TABLE IF NOT EXISTS notificaciones (
    id              TEXT PRIMARY KEY,
    cliente_id      TEXT NOT NULL,
    publicacion_id  TEXT,                   -- FK opcional
    tipo            TEXT NOT NULL,
    -- propuesta | copy | produccion | aviso_reel | sistema
    etapa           TEXT,                   -- etapa del workflow al momento de enviar
    canal           TEXT DEFAULT 'telegram', -- telegram | whatsapp
    mensaje_json    TEXT DEFAULT '{}',      -- contenido enviado al cliente
    respuesta       TEXT,                   -- respuesta del cliente
    respuesta_raw   TEXT,                   -- respuesta original sin procesar
    status          TEXT DEFAULT 'enviado', -- enviado | respondido | expirado | error
    intentos        INTEGER DEFAULT 1,
    sent_at         TEXT DEFAULT (datetime('now')),
    responded_at    TEXT,
    expira_at       TEXT,                   -- cuando expira la espera de respuesta
    FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    FOREIGN KEY (publicacion_id) REFERENCES publicaciones(id)
);
"""

# ── Indices ───────────────────────────────────────────────────────────────────

INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_pub_cliente_fecha   ON publicaciones(cliente_id, fecha);",
    "CREATE INDEX IF NOT EXISTS idx_pub_cliente_status  ON publicaciones(cliente_id, status);",
    "CREATE INDEX IF NOT EXISTS idx_pub_cliente_mes     ON publicaciones(cliente_id, mes);",
    "CREATE INDEX IF NOT EXISTS idx_ref_cliente_user    ON referentes_contenido(cliente_id, referente_username);",
    "CREATE INDEX IF NOT EXISTS idx_ref_modelabilidad   ON referentes_contenido(cliente_id, modelabilidad DESC);",
    "CREATE INDEX IF NOT EXISTS idx_ref_score_ventas   ON referentes_contenido(cliente_id, score_ventas DESC);",
    "CREATE INDEX IF NOT EXISTS idx_img_cliente_usable  ON imagenes(cliente_id);",
    "CREATE INDEX IF NOT EXISTS idx_notif_pub           ON notificaciones(publicacion_id);",
    "CREATE INDEX IF NOT EXISTS idx_notif_status        ON notificaciones(cliente_id, status);",
]

ALL_STATEMENTS = [
    CREATE_CLIENTES,
    CREATE_PUBLICACIONES,
    CREATE_REFERENTES_CONTENIDO,
    CREATE_IMAGENES,
    CREATE_NOTIFICACIONES,
]

TABLE_STATEMENTS = ALL_STATEMENTS.copy()
ALL_STATEMENTS = TABLE_STATEMENTS + INDICES
