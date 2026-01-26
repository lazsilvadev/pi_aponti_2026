import os
import sys
from datetime import datetime

# Garantir que o diretório do projeto esteja no sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.sgv import PDVCore
from models.db_models import get_session, init_db


def main():
    try:
        engine = init_db()
        session = get_session(engine)
        pdv_core = PDVCore(session)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome = f"Fornecedor Teste AI {ts}"

        dados = {
            "nome_razao_social": nome,
            "cnpj_cpf": None,
            "contato": f"teste+{ts}@exemplo.local",
            "condicao_pagamento": "Pix",
            "prazo_entrega_medio": "5 dias",
            "status": "ativo",
        }

        sucesso, msg = pdv_core.cadastrar_ou_atualizar_fornecedor(dados, None)
        print("Resultado cadastro:", sucesso, msg)

        fornecedores = pdv_core.get_all_fornecedores()
        print(f"Fornecedores encontrados: {len(fornecedores)}")
        for f in fornecedores:
            nome = getattr(f, "nome_razao_social", getattr(f, "nome", ""))
            print(f"- id={getattr(f, 'id', None)} nome={nome}")

    except Exception as e:
        print("Erro durante o teste:", e)
        raise


if __name__ == "__main__":
    main()
