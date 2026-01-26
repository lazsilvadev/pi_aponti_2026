import sqlite3
import sys
from pathlib import Path

# localizar DB usando resolver de paths
from utils.path_resolver import get_persistent_base_path

base = Path(get_persistent_base_path())
# Possíveis locais do DB em ambiente de desenvolvimento
possible = [
    base / "mercadinho.db",
    base / "data" / "mercadinho.db",
    Path(__file__).parent.parent / "mercadinho.db",
    Path(__file__).parent.parent / "data" / "mercadinho.db",
]
db_path = None
for p in possible:
    if p.exists():
        db_path = p
        break
if db_path is None:
    # fallback para criar no base path
    db_path = base / "mercadinho.db"

if not db_path.exists():
    print(f"Banco não encontrado: {db_path}")
    sys.exit(1)

print(f"Usando banco: {db_path}")
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()


# helper
def has_column(table, column):
    cur.execute(f"PRAGMA table_info({table});")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols


changes = []
# tabelas e colunas a adicionar
additions = {
    "vendas": [
        ("card_fee_percent", "REAL", "0.0"),
        ("card_fee_amount", "REAL", "0.0"),
        ("acquirer", "TEXT", "NULL"),
    ],
    "payment_settings": [
        ("card_fee_percent", "REAL", "0.0"),
        ("acquirer_name", "TEXT", "NULL"),
    ],
}

for table, cols in additions.items():
    for col_name, col_type, default in cols:
        if has_column(table, col_name):
            print(f"{table}.{col_name} já existe, pulando")
            continue
        try:
            sql = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
            # SQLite aceita DEFAULT em ADD COLUMN em versões recentes; para evitar problemas, executar sem DEFAULT
            print(f"Executando: {sql}")
            cur.execute(sql)
            # Se desejar inicializar valores não-nulos, executar UPDATE
            if default not in (None, "NULL"):
                try:
                    cur.execute(
                        f"UPDATE {table} SET {col_name} = ? WHERE {col_name} IS NULL",
                        (float(default),),
                    )
                except Exception:
                    try:
                        cur.execute(
                            f"UPDATE {table} SET {col_name} = ? WHERE {col_name} IS NULL",
                            (default,),
                        )
                    except Exception:
                        pass
            changes.append((table, col_name))
            print(f"Coluna adicionada: {table}.{col_name}")
        except Exception as ex:
            print(f"Erro adicionando coluna {table}.{col_name}: {ex}")

conn.commit()
conn.close()
print("Migração finalizada.")
