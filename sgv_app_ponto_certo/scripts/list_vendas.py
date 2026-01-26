import os
import sys

# garante que o diretório raiz do projeto esteja no sys.path quando executado isoladamente
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from models.db_models import Venda, get_session, init_db

engine = init_db()
s = get_session(engine)
try:
    vendas = s.query(Venda).order_by(Venda.data_venda.desc()).limit(50).all()
    print(f"Vendas no banco: {len(vendas)}")
    for v in vendas:
        print(v.id, v.data_venda, v.total, v.forma_pagamento, v.status)
finally:
    s.close()
