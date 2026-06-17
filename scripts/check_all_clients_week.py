import sqlite3
import os

base = r"C:\Users\Mauricio\projects\rima-ai\data\clients"
for name in os.listdir(base):
    db = os.path.join(base, name, "rima.db")
    if not os.path.isfile(db):
        continue
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT nombre FROM clientes").fetchone()
    w = conn.execute(
        "SELECT COUNT(*) FROM publicaciones WHERE fecha BETWEEN '2026-06-15' AND '2026-06-21'"
    ).fetchone()[0]
    refs = conn.execute("SELECT COUNT(*) FROM referentes_contenido").fetchone()[0]
    analyzed = conn.execute(
        "SELECT COUNT(*) FROM referentes_contenido WHERE analizado_at IS NOT NULL AND analizado_at != ''"
    ).fetchone()[0]
    st = conn.execute(
        "SELECT status, COUNT(*) FROM publicaciones "
        "WHERE fecha BETWEEN '2026-06-15' AND '2026-06-21' GROUP BY status"
    ).fetchall()
    if w > 0:
        print(f"{n[0]} ({name}) | pubs: {w} | refs: {refs}/{analyzed} | {st}")
    conn.close()
