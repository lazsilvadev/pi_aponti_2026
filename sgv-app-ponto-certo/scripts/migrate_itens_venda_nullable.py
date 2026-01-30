"""
Migração SQLite: tornar `itens_venda.produto_id` opcional (nullable).

Uso:
  - Feche o executável/app antes de rodar.
  - Execute com o Python do venv:
      .\.venv\Scripts\python.exe scripts\migrate_itens_venda_nullable.py

O script detecta se `produto_id` está com NOT NULL; se sim, recria a
tabela preservando todos os dados e índices, permitindo valores NULL.
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional


def _get_db_path_from_url(url: str) -> Optional[Path]:
    if not url:
        return None
    # Esperado formato sqlite:///C:/.../mercadinho.db
    if url.startswith("sqlite:///"):
        return Path(url.replace("sqlite:///", ""))
    return None


def get_db_path() -> Path:
    try:
        from models.db_models import DATABASE_URL

        p = _get_db_path_from_url(DATABASE_URL)
        if p is None:
            raise RuntimeError(f"DATABASE_URL inesperado: {DATABASE_URL}")
        return p
    except Exception:
        # Fallback: banco ao lado do projeto
        return Path("mercadinho.db").absolute()


def coluna_produto_notnull(conn: sqlite3.Connection) -> bool:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(itens_venda)")
    cols = cur.fetchall()
    for cid, name, ctype, notnull, dflt, pk in cols:
        if name == "produto_id":
            return bool(notnull)
    # Se coluna não existe, considerar sem notnull
    return False


def migrate(conn: sqlite3.Connection):
    cur = conn.cursor()
    print("→ Desativando foreign_keys…")
    cur.execute("PRAGMA foreign_keys=OFF")
    print("→ Iniciando transação…")
    cur.execute("BEGIN TRANSACTION")

    print("→ Renomeando tabela antiga…")
    cur.execute("ALTER TABLE itens_venda RENAME TO itens_venda_old")

    print("→ Criando nova tabela (produto_id NULL)…")
    cur.execute("""
        CREATE TABLE itens_venda (
            id INTEGER PRIMARY KEY,
            venda_id INTEGER NOT NULL,
            produto_id INTEGER,
            quantidade INTEGER NOT NULL,
            preco_unitario REAL NOT NULL,
            FOREIGN KEY(venda_id) REFERENCES vendas(id),
            FOREIGN KEY(produto_id) REFERENCES produtos(id)
        )
        """)

    print("→ Copiando dados…")
    cur.execute("""
        INSERT INTO itens_venda (id, venda_id, produto_id, quantidade, preco_unitario)
        SELECT id, venda_id, produto_id, quantidade, preco_unitario FROM itens_venda_old
        """)

    print("→ Removendo tabela antiga…")
    cur.execute("DROP TABLE itens_venda_old")

    print("→ Recriando índices…")
    try:
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_itens_venda_venda_id ON itens_venda(venda_id)"
        )
    except Exception:
        pass
    try:
        cur.execute(
            "CREATE INDEX IF NOT EXISTS ix_itens_venda_produto_id ON itens_venda(produto_id)"
        )
    except Exception:
        pass

    print("→ Commit…")
    cur.execute("COMMIT")
    print("→ Reativando foreign_keys…")
    cur.execute("PRAGMA foreign_keys=ON")
    conn.commit()
    print("✅ Migração concluída com sucesso.")


def main():
    db_path = get_db_path()
    print(f"Banco: {db_path}")
    if not db_path.exists():
        print("⚠️ Banco não encontrado. Abortando.")
        return

    conn = sqlite3.connect(str(db_path))
    try:
        needs = coluna_produto_notnull(conn)
        if not needs:
            print(
                "ℹ️ Migração não necessária (produto_id já é NULL ou coluna ausente)."
            )
            return
        migrate(conn)
        # Verificar resultado
        print("→ Verificando schema atualizado…")
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(itens_venda)")
        print(cur.fetchall())
    finally:
        conn.close()


if __name__ == "__main__":
    main()
