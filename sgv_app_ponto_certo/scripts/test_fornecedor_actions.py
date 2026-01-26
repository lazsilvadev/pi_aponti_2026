from core.sgv import PDVCore
from models.db_models import get_session, init_db

engine = init_db()
session = get_session(engine)
core = PDVCore(session)

fornecedores = core.get_all_fornecedores()
print(f"Fornecedores encontrados: {len(fornecedores)}")
for f in fornecedores:
    print(f"- id={f.id} nome={getattr(f, 'nome_razao_social', getattr(f, 'nome', ''))}")

if not fornecedores:
    print("Nenhum fornecedor para testar.")
    import sys

    sys.exit(0)

# Escolhe o último fornecedor (mais recentemente criado)
forn = sorted(fornecedores, key=lambda x: getattr(x, "id", 0))[-1]
print(f"\nTestando edição do fornecedor id={forn.id} nome={forn.nome_razao_social}")

novos_dados = {
    "nome_razao_social": forn.nome_razao_social + " (EDITADO)",
    "cnpj_cpf": getattr(forn, "cnpj_cpf", None),
    "contato": (getattr(forn, "contato", None) or "") + " - edit-test",
    "condicao_pagamento": getattr(forn, "condicao_pagamento", None),
    "prazo_entrega_medio": getattr(forn, "prazo_entrega_medio", None),
    "status": getattr(forn, "status", "ativo"),
}

ok, msg = core.cadastrar_ou_atualizar_fornecedor(novos_dados, fornecedor_id=forn.id)
print("Resultado edição:", ok, msg)

# Recarrega e mostra
forn_after = core.get_fornecedor_by_id(forn.id)
print(
    "Depois:",
    forn_after.id,
    getattr(forn_after, "nome_razao_social", None),
    getattr(forn_after, "contato", None),
)

print("\nTestando exclusão do fornecedor (após edição)")
ok2, msg2 = core.excluir_fornecedor(forn.id)
print("Resultado exclusão:", ok2, msg2)

# Lista final
fornecedores_fin = core.get_all_fornecedores()
print(f"\nFornecedores restantes: {len(fornecedores_fin)}")
for f in fornecedores_fin:
    print(f"- id={f.id} nome={getattr(f, 'nome_razao_social', getattr(f, 'nome', ''))}")
