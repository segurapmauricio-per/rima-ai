"""
RIMA AI — Database Manager
Maneja conexiones SQLite por cliente.
Cada cliente tiene su propio archivo: data/clients/{cliente_id}/rima.db
"""

import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Any
from contextlib import contextmanager

from .schema import ALL_STATEMENTS, TABLE_STATEMENTS, INDICES, SCHEMA_VERSION
from core.market_scores import calculate_score_ventas

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent.parent  # rima-ai/
CLIENTS_DIR = BASE_DIR / "data" / "clients"


def get_db_path(cliente_id: str) -> Path:
    client_dir = CLIENTS_DIR / cliente_id
    client_dir.mkdir(parents=True, exist_ok=True)
    return client_dir / "rima.db"


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection(cliente_id: str) -> sqlite3.Connection:
    db_path = get_db_path(cliente_id)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row      # rows as dicts
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db(cliente_id: str):
    """Context manager — commits on success, rolls back on exception."""
    conn = get_connection(cliente_id)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Init ──────────────────────────────────────────────────────────────────────

def init_db(cliente_id: str) -> None:
    """Create all tables and indices for a client. Safe to call multiple times."""
    with db(cliente_id) as conn:
        for statement in TABLE_STATEMENTS:
            conn.execute(statement)
        try:
            conn.execute(
                "ALTER TABLE referentes_contenido ADD COLUMN score_ventas REAL"
            )
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(
                "ALTER TABLE clientes ADD COLUMN marca_visual_json TEXT DEFAULT '{}'"
            )
        except sqlite3.OperationalError:
            pass
        for statement in INDICES:
            conn.execute(statement)
    print(f"[DB] Initialized {cliente_id} — schema v{SCHEMA_VERSION}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def new_id() -> str:
    return str(uuid.uuid4())


def now() -> str:
    return datetime.now().isoformat()


def to_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def from_json(s: str) -> Any:
    if not s:
        return {}
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}


def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a Row to dict, parsing JSON columns automatically."""
    if row is None:
        return None
    d = dict(row)
    for key, val in d.items():
        if key.endswith("_json") and isinstance(val, str):
            d[key] = from_json(val)
    return d


def rows_to_list(rows) -> list:
    return [row_to_dict(r) for r in rows]


# ── CRUD: Publicaciones ───────────────────────────────────────────────────────

def create_publicacion(cliente_id: str, data: dict) -> dict:
    pub_id = data.get("id") or new_id()
    with db(cliente_id) as conn:
        conn.execute("""
            INSERT INTO publicaciones
                (id, cliente_id, fecha, semana, dia, mes, tipo, tematica, enfoque,
                 status, agente_origen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pub_id,
            cliente_id,
            data["fecha"],
            data.get("semana"),
            data.get("dia"),
            data.get("mes"),
            data["tipo"],
            data.get("tematica"),
            data.get("enfoque"),
            data.get("status", "planificado"),
            data.get("agente_origen", "monthly"),
        ))
    return get_publicacion(cliente_id, pub_id)


def get_publicacion(cliente_id: str, pub_id: str) -> Optional[dict]:
    with db(cliente_id) as conn:
        row = conn.execute(
            "SELECT * FROM publicaciones WHERE id = ? AND cliente_id = ?",
            (pub_id, cliente_id)
        ).fetchone()
    return row_to_dict(row)


def get_publicaciones(cliente_id: str, mes: str = None, status: str = None,
                      tipo: str = None) -> list:
    query = "SELECT * FROM publicaciones WHERE cliente_id = ?"
    params = [cliente_id]
    if mes:
        query += " AND mes = ?"; params.append(mes)
    if status:
        query += " AND status = ?"; params.append(status)
    if tipo:
        query += " AND tipo = ?"; params.append(tipo)
    query += " ORDER BY fecha ASC"
    with db(cliente_id) as conn:
        rows = conn.execute(query, params).fetchall()
    return rows_to_list(rows)


def update_publicacion_status(cliente_id: str, pub_id: str, status: str) -> None:
    with db(cliente_id) as conn:
        conn.execute(
            "UPDATE publicaciones SET status = ?, updated_at = ? WHERE id = ? AND cliente_id = ?",
            (status, now(), pub_id, cliente_id)
        )


def update_publicacion_field(cliente_id: str, pub_id: str, field: str,
                              value: Any) -> None:
    """Update a single field. JSON fields are serialized automatically."""
    if field.endswith("_json") and not isinstance(value, str):
        value = to_json(value)
    with db(cliente_id) as conn:
        conn.execute(
            f"UPDATE publicaciones SET {field} = ?, updated_at = ? WHERE id = ? AND cliente_id = ?",
            (value, now(), pub_id, cliente_id)
        )


def add_version_to_publicacion(cliente_id: str, pub_id: str, version_data: dict) -> None:
    """Append a version to the versiones_json array."""
    pub = get_publicacion(cliente_id, pub_id)
    if not pub:
        return
    versiones = pub.get("versiones_json") or []
    version_data["v"] = len(versiones) + 1
    version_data["created_at"] = now()
    versiones.append(version_data)
    update_publicacion_field(cliente_id, pub_id, "versiones_json", versiones)


def get_publicaciones_regenerables(cliente_id: str, mes: str) -> list:
    """Slots del mes que no tienen aprobacion de tematica del cliente."""
    with db(cliente_id) as conn:
        rows = conn.execute("""
            SELECT * FROM publicaciones
            WHERE cliente_id = ? AND mes = ?
            AND json_extract(aprobaciones_json, '$.tematica') = 0
            ORDER BY fecha ASC
        """, (cliente_id, mes)).fetchall()
    return rows_to_list(rows)


def _json_field(pub: dict, key: str) -> dict:
    val = pub.get(key) or {}
    return from_json(val) if isinstance(val, str) else (val or {})


def publicacion_es_protegida(pub: dict) -> bool:
    """Pieza que no debe borrarse al regenerar: tiene avance, aprobaciones o assets."""
    if pub.get("status", "planificado") != "planificado":
        return True

    ap = _json_field(pub, "aprobaciones_json")
    if ap.get("tematica") or ap.get("copy") or ap.get("visual"):
        return True

    if pub.get("programado_at"):
        return True

    copy_j = _json_field(pub, "copy_json")
    if any(copy_j.get(k) for k in ("hook", "desarrollo", "cta", "script_completo", "lead_magnet")):
        return True

    archivos = _json_field(pub, "archivos_json")
    if archivos.get("imagen_url") or archivos.get("video_url") or archivos.get("thumbnail_url"):
        return True
    if archivos.get("secuencia_urls"):
        return True

    prod = _json_field(pub, "produccion_json")
    if prod.get("archivos"):
        return True

    prop = _json_field(pub, "propuesta_json")
    if prop.get("hook_idea") or prop.get("angulo") or prop.get("alternativas"):
        return True

    return False


def delete_publicaciones_regenerables(cliente_id: str, start_date: str = None,
                                      end_date: str = None) -> int:
    """Elimina piezas planificadas sin trabajo avanzado. Retorna cantidad borrada."""
    pubs = get_publicaciones(cliente_id)
    to_delete = []
    for pub in pubs:
        if publicacion_es_protegida(pub):
            continue
        fecha = pub.get("fecha") or ""
        if start_date and fecha < start_date:
            continue
        if end_date and fecha > end_date:
            continue
        to_delete.append(pub["id"])

    if not to_delete:
        return 0
    with db(cliente_id) as conn:
        for pid in to_delete:
            conn.execute(
                "DELETE FROM publicaciones WHERE id = ? AND cliente_id = ?",
                (pid, cliente_id),
            )
    return len(to_delete)


def reset_weekly_work(cliente_id: str, start_date: str, end_date: str) -> int:
    """Reinicia propuesta/copy/aprobaciones semanal sin borrar slots del plan mensual."""
    protected = {
        "copy_aprobado", "en_produccion", "produccion_enviada",
        "produccion_aprobada", "programado", "publicado",
    }
    aprobaciones_limpias = {"tematica": False, "copy": False, "visual": False}
    count = 0
    for pub in get_publicaciones(cliente_id):
        fecha = pub.get("fecha") or ""
        if fecha < start_date or fecha > end_date:
            continue
        if pub.get("status") in protected:
            continue
        pid = pub["id"]
        update_publicacion_field(cliente_id, pid, "propuesta_json", {})
        update_publicacion_field(cliente_id, pid, "copy_json", {})
        update_publicacion_field(cliente_id, pid, "aprobaciones_json", aprobaciones_limpias)
        update_publicacion_field(cliente_id, pid, "archivos_json", {})
        update_publicacion_field(cliente_id, pid, "produccion_json", {})
        update_publicacion_field(cliente_id, pid, "referente_id", "")
        update_publicacion_status(cliente_id, pid, "planificado")
        count += 1
    return count


# ── CRUD: Referentes ──────────────────────────────────────────────────────────

def upsert_referente(cliente_id: str, data: dict) -> dict:
    """Insert if not exists, update only metrics if exists."""
    url = data.get("url")
    existing = None
    if url:
        with db(cliente_id) as conn:
            row = conn.execute(
                "SELECT id FROM referentes_contenido WHERE url = ? AND cliente_id = ?",
                (url, cliente_id)
            ).fetchone()
            existing = row["id"] if row else None

    if existing:
        # Actualiza métricas; transcripción solo si viene del scrape capa 2
        trans = data.get("transcripcion")
        if trans:
            with db(cliente_id) as conn:
                conn.execute("""
                    UPDATE referentes_contenido SET
                        vistas = ?, likes = ?, comentarios = ?, guardados = ?,
                        seguidores_al_scrape = ?,
                        fuerza = ?, relevancia = ?, engagement = ?, ratio_conversacion = ?,
                        score_ventas = ?, transcripcion = ?,
                        updated_at = ?
                    WHERE id = ? AND cliente_id = ?
                """, (
                    data.get("vistas", 0), data.get("likes", 0),
                    data.get("comentarios", 0), data.get("guardados", 0),
                    data.get("seguidores_al_scrape", 0),
                    data.get("fuerza"), data.get("relevancia"),
                    data.get("engagement"), data.get("ratio_conversacion"),
                    data.get("score_ventas"), trans,
                    now(), existing, cliente_id
                ))
        else:
            with db(cliente_id) as conn:
                conn.execute("""
                    UPDATE referentes_contenido SET
                        vistas = ?, likes = ?, comentarios = ?, guardados = ?,
                        seguidores_al_scrape = ?,
                        fuerza = ?, relevancia = ?, engagement = ?, ratio_conversacion = ?,
                        score_ventas = ?,
                        updated_at = ?
                    WHERE id = ? AND cliente_id = ?
                """, (
                    data.get("vistas", 0), data.get("likes", 0),
                    data.get("comentarios", 0), data.get("guardados", 0),
                    data.get("seguidores_al_scrape", 0),
                    data.get("fuerza"), data.get("relevancia"),
                    data.get("engagement"), data.get("ratio_conversacion"),
                    data.get("score_ventas"),
                    now(), existing, cliente_id
                ))
        return get_referente(cliente_id, existing)
    else:
        ref_id = data.get("id") or new_id()
        with db(cliente_id) as conn:
            conn.execute("""
                INSERT INTO referentes_contenido
                    (id, cliente_id, referente_username, plataforma, url, tipo,
                     fecha_publicacion, fecha_scrape, titulo, descripcion,
                     hashtags_json, transcripcion, texto_extraido,
                     vistas, likes, comentarios, guardados, seguidores_al_scrape,
                     fuerza, relevancia, engagement, ratio_conversacion, score_ventas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ref_id, cliente_id,
                data.get("referente_username", ""), data.get("plataforma", "instagram"),
                url, data.get("tipo"), data.get("fecha_publicacion"), now(),
                data.get("titulo"), data.get("descripcion"),
                to_json(data.get("hashtags", [])),
                data.get("transcripcion"), data.get("texto_extraido"),
                data.get("vistas", 0), data.get("likes", 0),
                data.get("comentarios", 0), data.get("guardados", 0),
                data.get("seguidores_al_scrape", 0),
                data.get("fuerza"), data.get("relevancia"),
                data.get("engagement"), data.get("ratio_conversacion"),
                data.get("score_ventas"),
            ))
        return get_referente(cliente_id, ref_id)


def get_referente(cliente_id: str, ref_id: str) -> Optional[dict]:
    with db(cliente_id) as conn:
        row = conn.execute(
            "SELECT * FROM referentes_contenido WHERE id = ? AND cliente_id = ?",
            (ref_id, cliente_id)
        ).fetchone()
    return row_to_dict(row)


def get_referentes_by_urls(cliente_id: str, urls: list) -> dict:
    """Retorna {url: row_dict} para posts ya scrapeados."""
    urls = [u for u in urls if u]
    if not urls:
        return {}
    placeholders = ",".join("?" * len(urls))
    with db(cliente_id) as conn:
        rows = conn.execute(
            f"SELECT * FROM referentes_contenido WHERE cliente_id = ? AND url IN ({placeholders})",
            [cliente_id, *urls],
        ).fetchall()
    return {row["url"]: row_to_dict(row) for row in rows}


def get_top_referentes(cliente_id: str, tipo: str = None, limit: int = 10) -> list:
    """Top referentes por modelabilidad + relevancia para el selector de contenido."""
    query = """
        SELECT * FROM referentes_contenido
        WHERE cliente_id = ? AND analizado_at IS NOT NULL
    """
    params = [cliente_id]
    if tipo:
        query += " AND tipo = ?"; params.append(tipo)
    query += " ORDER BY COALESCE(score_ventas, 0) DESC, modelabilidad DESC, relevancia DESC LIMIT ?"
    params.append(limit)
    with db(cliente_id) as conn:
        rows = conn.execute(query, params).fetchall()
    return rows_to_list(rows)


def get_referentes_market_dashboard(cliente_id: str, limit: int = 20) -> list:
    """Referentes ordenados por engagement_score para el dashboard /mercado."""
    query = """
        SELECT * FROM referentes_contenido
        WHERE cliente_id = ?
        ORDER BY COALESCE(score_ventas, 0) DESC, updated_at DESC
        LIMIT ?
    """
    with db(cliente_id) as conn:
        rows = conn.execute(query, (cliente_id, limit)).fetchall()
    return rows_to_list(rows)


def referente_row_to_post(row: dict) -> dict:
    """Convierte fila SQLite al formato de post esperado por el dashboard."""
    post = {
        "id": row.get("id"),
        "owner": row.get("referente_username", ""),
        "owner_followers": row.get("seguidores_al_scrape", 0),
        "type": row.get("tipo", "reel"),
        "caption": row.get("descripcion", ""),
        "likes": row.get("likes", 0),
        "comments": row.get("comentarios", 0),
        "saves": row.get("guardados", 0),
        "views": row.get("vistas", 0),
        "url": row.get("url", ""),
        "modelabilidad": row.get("modelabilidad"),
        "transcripcion": row.get("transcripcion") or "",
        "analisis_json": row.get("analisis_json") or {},
        "metrics": {
            "fuerza": row.get("fuerza", 0),
            "relevancia": row.get("relevancia", 0),
            "engagement": row.get("engagement", 0),
            "ratio_conversacion": row.get("ratio_conversacion", 0),
            "engagement_score": round(
                (row.get("fuerza") or 0) * (1 + (row.get("relevancia") or 0)), 4
            ),
        },
    }
    sv = row.get("score_ventas")
    if sv is None:
        sv = calculate_score_ventas(post)
    post["metrics"]["score_ventas"] = sv
    return post


def set_referente_analisis(cliente_id: str, ref_id: str, analisis: dict,
                            modelabilidad: int, transcripcion: str = None) -> None:
    """Guarda el analisis del ContentAnalyzer. Solo corre una vez."""
    with db(cliente_id) as conn:
        if transcripcion:
            conn.execute("""
                UPDATE referentes_contenido SET
                    analisis_json = ?, modelabilidad = ?, transcripcion = ?,
                    analizado_at = ?, updated_at = ?
                WHERE id = ? AND cliente_id = ?
            """, (to_json(analisis), modelabilidad, transcripcion, now(), now(), ref_id, cliente_id))
        else:
            conn.execute("""
                UPDATE referentes_contenido SET
                    analisis_json = ?, modelabilidad = ?, analizado_at = ?, updated_at = ?
                WHERE id = ? AND cliente_id = ?
            """, (to_json(analisis), modelabilidad, now(), now(), ref_id, cliente_id))


def clear_referentes_contenido(cliente_id: str) -> int:
    """Elimina todos los referentes scrapeados del cliente. Retorna filas borradas."""
    with db(cliente_id) as conn:
        cur = conn.execute(
            "DELETE FROM referentes_contenido WHERE cliente_id = ?",
            (cliente_id,),
        )
        return cur.rowcount


# ── CRUD: Imagenes ────────────────────────────────────────────────────────────

def create_imagen(cliente_id: str, archivo_url: str, nombre: str = None) -> dict:
    img_id = new_id()
    with db(cliente_id) as conn:
        conn.execute("""
            INSERT INTO imagenes (id, cliente_id, archivo_url, nombre_archivo)
            VALUES (?, ?, ?, ?)
        """, (img_id, cliente_id, archivo_url, nombre))
    return {"id": img_id, "cliente_id": cliente_id, "archivo_url": archivo_url}


def set_imagen_analisis(cliente_id: str, img_id: str, analisis: dict,
                         usable_para: list, tags: list) -> None:
    with db(cliente_id) as conn:
        conn.execute("""
            UPDATE imagenes SET
                analisis_json = ?, usable_para_json = ?, tags_json = ?,
                analizado_at = ?
            WHERE id = ? AND cliente_id = ?
        """, (to_json(analisis), to_json(usable_para), to_json(tags),
              now(), img_id, cliente_id))


def get_imagenes_para(cliente_id: str, uso: str) -> list:
    """Imagenes analizadas y aptas para un uso especifico."""
    with db(cliente_id) as conn:
        rows = conn.execute("""
            SELECT * FROM imagenes
            WHERE cliente_id = ? AND analizado_at IS NOT NULL
            AND json_extract(usable_para_json, '$') LIKE ?
            ORDER BY created_at DESC
        """, (cliente_id, f'%{uso}%')).fetchall()
    return rows_to_list(rows)


def get_imagen(cliente_id: str, img_id: str) -> Optional[dict]:
    with db(cliente_id) as conn:
        row = conn.execute(
            "SELECT * FROM imagenes WHERE id = ? AND cliente_id = ?",
            (img_id, cliente_id),
        ).fetchone()
    return row_to_dict(row)


def get_imagen_por_url(cliente_id: str, archivo_url: str) -> Optional[dict]:
    with db(cliente_id) as conn:
        row = conn.execute(
            "SELECT * FROM imagenes WHERE cliente_id = ? AND archivo_url = ?",
            (cliente_id, archivo_url),
        ).fetchone()
    return row_to_dict(row)


def get_marca_visual(cliente_id: str) -> dict:
    cliente = get_cliente(cliente_id)
    if not cliente:
        return {}
    return cliente.get("marca_visual_json") or {}


def set_marca_visual(cliente_id: str, marca: dict) -> None:
    init_db(cliente_id)
    if not get_cliente(cliente_id):
        create_or_update_cliente(cliente_id, nombre=cliente_id, plan="basico")
    with db(cliente_id) as conn:
        conn.execute(
            "UPDATE clientes SET marca_visual_json = ?, updated_at = ? WHERE id = ?",
            (to_json(marca), now(), cliente_id),
        )


# ── CRUD: Notificaciones ──────────────────────────────────────────────────────

def create_notificacion(cliente_id: str, pub_id: str, tipo: str,
                         etapa: str, mensaje: dict, canal: str = "telegram") -> str:
    notif_id = new_id()
    with db(cliente_id) as conn:
        conn.execute("""
            INSERT INTO notificaciones
                (id, cliente_id, publicacion_id, tipo, etapa, canal, mensaje_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (notif_id, cliente_id, pub_id, tipo, etapa, canal, to_json(mensaje)))
    return notif_id


def update_notificacion_respuesta(cliente_id: str, notif_id: str,
                                   respuesta: str, respuesta_raw: str = None) -> None:
    with db(cliente_id) as conn:
        conn.execute("""
            UPDATE notificaciones SET
                respuesta = ?, respuesta_raw = ?, status = 'respondido',
                responded_at = ?
            WHERE id = ? AND cliente_id = ?
        """, (respuesta, respuesta_raw, now(), notif_id, cliente_id))


# ── CRUD: Cliente ─────────────────────────────────────────────────────────────

def create_or_update_cliente(cliente_id: str, nombre: str, plan: str,
                              ig_username: str = None, brief: dict = None,
                              config: dict = None) -> None:
    init_db(cliente_id)
    with db(cliente_id) as conn:
        conn.execute("""
            INSERT INTO clientes (id, nombre, plan, ig_username, brief_json, config_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                nombre = excluded.nombre,
                plan = excluded.plan,
                ig_username = excluded.ig_username,
                brief_json = excluded.brief_json,
                config_json = excluded.config_json,
                updated_at = datetime('now')
        """, (
            cliente_id, nombre, plan, ig_username,
            to_json(brief or {}), to_json(config or {})
        ))


def get_cliente(cliente_id: str) -> Optional[dict]:
    with db(cliente_id) as conn:
        row = conn.execute(
            "SELECT * FROM clientes WHERE id = ?", (cliente_id,)
        ).fetchone()
    return row_to_dict(row)


def update_cliente_status(cliente_id: str, status: str) -> None:
    init_db(cliente_id)
    if not get_cliente(cliente_id):
        create_or_update_cliente(cliente_id, nombre=cliente_id, plan="basico")
    with db(cliente_id) as conn:
        conn.execute(
            "UPDATE clientes SET status = ?, updated_at = ? WHERE id = ?",
            (status, now(), cliente_id),
        )


def update_cliente_memoria(cliente_id: str, updates: dict) -> None:
    cliente = get_cliente(cliente_id)
    if not cliente:
        return
    memoria = cliente.get("memoria_json") or {}
    memoria.update(updates)
    with db(cliente_id) as conn:
        conn.execute(
            "UPDATE clientes SET memoria_json = ?, updated_at = ? WHERE id = ?",
            (to_json(memoria), now(), cliente_id)
        )
