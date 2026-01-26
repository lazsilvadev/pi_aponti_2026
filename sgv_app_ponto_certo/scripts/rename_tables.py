import os
import sys

from sqlalchemy import create_engine, text

from models.db_models import DATABASE_URL  # já está funcionando com o sys.path ajustado


def main():
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Lista índices antes
        idx_before = conn.execute(
            text("SELECT name, tbl_name FROM sqlite_master WHERE type='index';")
        ).fetchall()
        print("Índices antes da limpeza:")
        for name, tbl in idx_before:
            print("-", name, "=>", tbl)

        # Remove índices antigos ligados às tabelas renomeadas (se existirem)
        for idx_name in ("ix_receivables_status", "ix_expenses_status"):
            try:
                conn.execute(text(f"DROP INDEX IF EXISTS {idx_name};"))
                print(f"Índice '{idx_name}' removido (se existia).")
            except Exception as e:
                print(f"Erro ao remover índice '{idx_name}':", e)

        # Lista índices depois
        idx_after = conn.execute(
            text("SELECT name, tbl_name FROM sqlite_master WHERE type='index';")
        ).fetchall()
        print("\nÍndices depois da limpeza:")
        for name, tbl in idx_after:
            print("-", name, "=>", tbl)


if __name__ == "__main__":
    # Garante que a pasta raiz (onde está models/) entre no sys.path
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    main()
