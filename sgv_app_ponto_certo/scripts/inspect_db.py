import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from models.db_models import init_db

engine = init_db()
conn = engine.raw_connection()
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:")
for row in cur.fetchall():
    print("-", row[0])

# show columns for produtos if exists
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='produtos'")
if cur.fetchone():
    cur.execute("PRAGMA table_info('produtos')")
    print("\nColumns in produtos:")
    for r in cur.fetchall():
        print(r)
else:
    print("\nTabela produtos não existe")

cur.close()
conn.close()
