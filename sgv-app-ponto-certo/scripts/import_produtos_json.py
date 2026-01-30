"""
Script para importar produtos do produtos.json para o banco de dados (SQLite).

- Lê produtos do JSON.
- Insere no banco se não existir (pelo código de barras).
- Atualiza dados se já existir (opcional).

Uso:
    python scripts/import_produtos_json.py
"""

import json
import os

from models.db_models import Produto, get_session, init_db

# Caminho do JSON de produtos
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
JSON_PATH = os.path.join(BASE_DIR, "data", "produtos.json")

if not os.path.exists(JSON_PATH):
    print(f"Arquivo {JSON_PATH} não encontrado!")
    exit(1)

# Inicializa banco e sessão
engine = init_db()
session = get_session(engine)

with open(JSON_PATH, "r", encoding="utf-8") as f:
    produtos_json = json.load(f)

count_inserted = 0
count_updated = 0
for prod in produtos_json:
    codigo_barras = str(prod.get("codigo_barras") or prod.get("codigo") or "").strip()
    if not codigo_barras:
        print(f"Produto sem código de barras: {prod}")
        continue
    nome = prod.get("nome") or prod.get("descricao") or "Produto"
    preco_custo = float(prod.get("preco_custo", prod.get("preco", 0.0)))
    preco_venda = float(prod.get("preco_venda", prod.get("preco", 0.0)))
    estoque_atual = int(prod.get("quantidade", prod.get("estoque", 0)))
    validade = prod.get("validade")

    # Tenta encontrar produto existente
    produto_db = session.query(Produto).filter_by(codigo_barras=codigo_barras).first()
    if produto_db:
        # Atualiza dados básicos
        produto_db.nome = nome
        produto_db.preco_custo = preco_custo
        produto_db.preco_venda = preco_venda
        produto_db.estoque_atual = estoque_atual
        produto_db.validade = validade
        count_updated += 1
    else:
        novo_prod = Produto(
            codigo_barras=codigo_barras,
            nome=nome,
            preco_custo=preco_custo,
            preco_venda=preco_venda,
            estoque_atual=estoque_atual,
            validade=validade,
        )
        session.add(novo_prod)
        count_inserted += 1

session.commit()
print(f"Produtos inseridos: {count_inserted}")
print(f"Produtos atualizados: {count_updated}")
print("Importação concluída!")
