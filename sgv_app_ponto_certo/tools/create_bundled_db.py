"""
Cria um arquivo SQLite `data/mercadinho.db` contendo tabelas e alguns fornecedores
baseados em `exports/fornecedores_novos_5.csv`. Usar antes de empacotar para que o
executável tenha um DB embutido com fornecedores.
"""

import csv
import sys

# Garantir que a raiz do projeto esteja no sys.path para importar o pacote `models`
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.db_models import Base, Fornecedor

DATA_DIR = Path(__file__).parent.parent / "data"
EXPORTS_DIR = Path(__file__).parent.parent / "exports"
CSV_NAME = "fornecedores_novos_5.csv"
DB_PATH = DATA_DIR / "mercadinho.db"

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Ler CSV e inserir fornecedores (se não existirem)
csv_file = EXPORTS_DIR / CSV_NAME
if not csv_file.exists():
    print(f"Arquivo CSV de fornecedores nao encontrado: {csv_file}")
else:
    with open(csv_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        inserted = 0
        for row in reader:
            nome = (
                row.get("Nome / Razão Social")
                or row.get("nome")
                or row.get("Nome")
                or ""
            ).strip()
            if not nome:
                continue
            cnpj = (
                row.get("CNPJ") or row.get("cnpj") or row.get("CNPJ/CPF") or ""
            ).strip()
            # verificar existencia
            exists = (
                session.query(Fornecedor)
                .filter(Fornecedor.nome_razao_social == nome)
                .first()
            )
            if exists:
                continue
            status_val = row.get("Status") or row.get("status") or "ativo"
            status_val = (
                status_val.strip().lower() if isinstance(status_val, str) else "ativo"
            )
            fobj = Fornecedor(
                nome_razao_social=nome,
                cnpj_cpf=cnpj or None,
                contato=(row.get("Contato") or row.get("contato") or None),
                condicao_pagamento=(row.get("Meios") or row.get("meios") or None),
                prazo_entrega_medio=(row.get("Prazo") or None),
                status=status_val,
            )
            session.add(fobj)
            inserted += 1
        if inserted:
            session.commit()
        print(f"Inseridos {inserted} fornecedores em {DB_PATH}")

session.close()

# Normalizar status existentes (minúsculas) para consistência
from sqlalchemy import update

engine2 = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Session2 = sessionmaker(bind=engine2)
session2 = Session2()
try:
    fornecedores = session2.query(Fornecedor).all()
    modified = 0
    for f in fornecedores:
        try:
            val = getattr(f, "status", None)
            if isinstance(val, str) and val.strip() and val.strip().lower() != val:
                f.status = val.strip().lower()
                modified += 1
        except Exception:
            continue
    if modified:
        session2.commit()
    print(f"Normalizados {modified} registros de status em {DB_PATH}")
except Exception as e:
    print(f"Falha ao normalizar status: {e}")
finally:
    session2.close()
