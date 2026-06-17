import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "data/clients/negocio_max/rima.db"
conn = sqlite3.connect(db)
print("cliente:", conn.execute("SELECT nombre, plan FROM clientes").fetchone())
rows = conn.execute(
    "SELECT fecha, tipo, status FROM publicaciones "
    "WHERE fecha BETWEEN '2026-06-15' AND '2026-06-22' ORDER BY fecha"
).fetchall()
print("semana 15-22:", rows)
conn.close()
