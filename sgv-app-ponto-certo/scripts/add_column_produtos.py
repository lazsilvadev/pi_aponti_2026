import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "mercadinho.db"
if not db.exists():
    # fallback: try relative path
    db = Path("mercadinho.db")

conn = sqlite3.connect(str(db))
cur = conn.cursor()
try:
    cur.execute("PRAGMA table_info('produtos')")
    cols = [r[1] for r in cur.fetchall()]
    if "estoque_minimo" not in cols:
        cur.execute("ALTER TABLE produtos ADD COLUMN estoque_minimo INTEGER DEFAULT 10")
        conn.commit()
        print("Coluna 'estoque_minimo' adicionada com sucesso.")
    else:
        print("Coluna 'estoque_minimo' já existe.")
finally:
    cur.close()
    conn.close()
