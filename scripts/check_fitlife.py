import sqlite3
import os

base = r"C:\Users\Mauricio\projects\rima-ai\data\clients"
for name in os.listdir(base):
    db = os.path.join(base, name, "rima.db")
    if not os.path.isfile(db):
        continue
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT nombre FROM clientes").fetchone()
    if not row:
        conn.close()
        continue
    nombre = row[0]
    if "fit" not in nombre.lower() and "fit" not in name.lower():
        conn.close()
        continue
    print("===", name, nombre, "===")
    refs = conn.execute("SELECT COUNT(*) FROM referentes_contenido").fetchone()[0]
    analyzed = conn.execute(
        "SELECT COUNT(*) FROM referentes_contenido WHERE analizado_at IS NOT NULL AND analizado_at != ''"
    ).fetchone()[0]
    pubs = conn.execute(
        "SELECT status, COUNT(*) FROM publicaciones "
        "WHERE fecha BETWEEN '2026-06-15' AND '2026-06-21' GROUP BY status"
    ).fetchall()
    print("referentes:", refs, "analizados:", analyzed)
    print("pubs semana:", pubs)
    sample = conn.execute(
        "SELECT fecha, tipo, status, tematica, propuesta_json, copy_json "
        "FROM publicaciones WHERE fecha BETWEEN '2026-06-15' AND '2026-06-21' AND tipo='reel' LIMIT 2"
    ).fetchall()
    for s in sample:
        print(" sample:", s[0], s[1], s[2], s[3], (s[4] or "")[:80])
    conn.close()
