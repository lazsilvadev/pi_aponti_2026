import os
import sys
from datetime import datetime, timedelta

# garante import local
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from models.db_models import ItemVenda, Produto, User, Venda, get_session, init_db

engine = init_db()
s = get_session(engine)

try:
    # Garantia rápida: adicionar colunas faltantes na tabela produtos se necessário (migração simples)
    try:
        conn = engine.connect()
        # Verifica se a coluna existe; se não, adiciona (SQLite permite ADD COLUMN)
        res = conn.execute("PRAGMA table_info('produtos')").fetchall()
        cols = [r[1] for r in res]
        if "estoque_minimo" not in cols:
            try:
                conn.execute(
                    "ALTER TABLE produtos ADD COLUMN estoque_minimo INTEGER DEFAULT 10"
                )
                print("Migração: coluna 'estoque_minimo' adicionada à tabela produtos")
            except Exception as ex:
                print(f"Migração falhou ao adicionar coluna estoque_minimo: {ex}")
        else:
            print("Migração: coluna 'estoque_minimo' já existe")
        conn.close()
    except Exception:
        # Se falhar, ignora — provavelmente a coluna já existe ou DB não permite alteração
        pass

    # cria um usuário 'caixa' se não existir
    user = s.query(User).filter_by(username="caixa").first()
    if not user:
        user = User(
            username="caixa", password="root", role="caixa", full_name="Usuário Caixa"
        )
        s.add(user)
        s.commit()
        print(f"Usuário criado: {user.username} (id={user.id})")
    else:
        print(f"Usuário existente: {user.username} (id={user.id})")

    # cria produtos se não existirem
    produtos_existentes = s.query(Produto).count()
    if produtos_existentes == 0:
        p1 = Produto(
            codigo_barras="0001",
            nome="Produto A",
            preco_custo=1.0,
            preco_venda=3.5,
            estoque_atual=100,
        )
        p2 = Produto(
            codigo_barras="0002",
            nome="Produto B",
            preco_custo=2.0,
            preco_venda=5.0,
            estoque_atual=100,
        )
        s.add_all([p1, p2])
        s.commit()
        print(f"Produtos criados: {p1.id} - {p1.nome}, {p2.id} - {p2.nome}")
    else:
        print(
            f"Existe(m) {produtos_existentes} produto(s) no banco; serão usados para as vendas de teste."
        )

    produtos = s.query(Produto).limit(2).all()
    if len(produtos) < 1:
        raise SystemExit("Sem produtos para criar vendas")

    # cria 3 vendas: ontem 11:00, hoje 10:00 e hoje 15:30
    hoje = datetime.now()
    venda_datas = [
        hoje - timedelta(days=1, hours=hoje.hour - 11),
        hoje.replace(hour=10, minute=0, second=0, microsecond=0),
        hoje.replace(hour=15, minute=30, second=0, microsecond=0),
    ]

    created = []
    for i, vd in enumerate(venda_datas, start=1):
        venda = Venda(
            total=0.0,
            usuario_responsavel=user.username,
            forma_pagamento=("Dinheiro" if i % 2 == 1 else "Cartão"),
            valor_pago=0.0,
            status="CONCLUIDA",
            data_venda=vd,
        )
        s.add(venda)
        s.flush()

        # adiciona um item
        produto = produtos[i % len(produtos)]
        qtd = 2 if i == 1 else 1
        item = ItemVenda(
            venda_id=venda.id,
            produto_id=produto.id,
            quantidade=qtd,
            preco_unitario=produto.preco_venda,
        )
        s.add(item)
        venda.total = produto.preco_venda * qtd
        s.commit()
        created.append((venda.id, venda.data_venda, venda.total, venda.forma_pagamento))
        print(
            f"Criada Venda id={venda.id} data={venda.data_venda} total={venda.total} pagamento={venda.forma_pagamento}"
        )

    print(f"Resumo: {len(created)} vendas criadas")

finally:
    s.close()
