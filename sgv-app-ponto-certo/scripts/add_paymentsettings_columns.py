"""Script utilitário para adicionar colunas ausentes em payment_settings.

Uso: python scripts/add_paymentsettings_columns.py
"""

import os
import sqlite3
import sys

# Garantir que o diretório do projeto esteja no path para importar `models`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from models import db_models


def get_sqlite_path(url: str):
    if not url:
        return None
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "")
    return None


def ensure_columns(db_path: str):
    if not os.path.exists(db_path):
        print(f"DB file not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info('payment_settings')")
        cols = [r[1] for r in cur.fetchall()]
        print("payment_settings columns:", cols)

        if "updated_by" not in cols:
            print("Adding column 'updated_by'")
            cur.execute(
                "ALTER TABLE payment_settings ADD COLUMN updated_by VARCHAR(100)"
            )
        else:
            print("Column 'updated_by' already exists")

        if "qr_image_base64" not in cols:
            print("Adding column 'qr_image_base64'")
            cur.execute("ALTER TABLE payment_settings ADD COLUMN qr_image_base64 TEXT")
        else:
            print("Column 'qr_image_base64' already exists")

        # Adicionar colunas em `vendas` para transações de pagamento
        cur.execute("PRAGMA table_info('vendas')")
        vendas_cols = [r[1] for r in cur.fetchall()]
        print("vendas columns:", vendas_cols)

        if "transaction_id" not in vendas_cols:
            print("Adding column 'transaction_id' to vendas")
            cur.execute("ALTER TABLE vendas ADD COLUMN transaction_id VARCHAR(128)")
        else:
            print("Column 'transaction_id' already exists in vendas")

        if "acquirer" not in vendas_cols:
            print("Adding column 'acquirer' to vendas")
            cur.execute("ALTER TABLE vendas ADD COLUMN acquirer VARCHAR(100)")
        else:
            print("Column 'acquirer' already exists in vendas")

        if "payment_status" not in vendas_cols:
            print("Adding column 'payment_status' to vendas")
            cur.execute("ALTER TABLE vendas ADD COLUMN payment_status VARCHAR(50)")
        else:
            print("Column 'payment_status' already exists in vendas")

        conn.commit()
        print("OK - alterações aplicadas.")
    except Exception as e:
        print("Erro ao aplicar alterações:", e)
    finally:
        conn.close()


if __name__ == "__main__":
    url = getattr(db_models, "DATABASE_URL", None)
    db_path = get_sqlite_path(url)
    if not db_path:
        print(
            f"Não foi possível determinar o caminho do DB a partir de DATABASE_URL='{url}'"
        )
    else:
        ensure_columns(db_path)
