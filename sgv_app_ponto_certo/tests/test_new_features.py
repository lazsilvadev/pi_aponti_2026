#!/usr/bin/env python3
"""
Script de teste para as novas funcionalidades de filtro de status e pagamento parcial
"""

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.sgv import PDVCore
from models.db_models import Base, Expense, Receivable

# Inicializar database
engine = create_engine("sqlite:///./database.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Inicializar core
core = PDVCore(session)

print("=" * 70)
print("TESTE: Novas Funcionalidades de Filtro de Status e Pagamento Parcial")
print("=" * 70)

# Limpar dados antigos
print("\n[1] Limpando dados de teste antigos...")
core.session.query(Expense).delete()
core.session.query(Receivable).delete()
core.session.commit()
print("[OK] Dados limpados")

# Criar dados de teste
print("\n[2] Criando dados de teste...")
today = datetime.now().date()

# Despesas para teste
exp1 = Expense(
    descricao="Despesa Pendente",
    valor=500.00,
    status="Pendente",
    vencimento=today + timedelta(days=5),
    categoria="Operacional",
)
exp2 = Expense(
    descricao="Despesa Atrasada",
    valor=300.00,
    status="Pendente",
    vencimento=today - timedelta(days=3),  # Vencida
    categoria="Operacional",
)
exp3 = Expense(
    descricao="Despesa Paga",
    valor=200.00,
    status="Pago",
    vencimento=today - timedelta(days=1),
    categoria="Operacional",
    data_pagamento=today,
)

core.session.add_all([exp1, exp2, exp3])
core.session.commit()
print(f"[OK] {3} despesas criadas")

# Receitas para teste
rec1 = Receivable(
    descricao="Receita Pendente",
    valor=1000.00,
    status="Pendente",
    vencimento=today + timedelta(days=10),
    origem="Vendas",
)
rec2 = Receivable(
    descricao="Receita Recebida",
    valor=750.00,
    status="Recebido",
    vencimento=today - timedelta(days=5),
    origem="Serviços",
    data_recebimento=today,
)

core.session.add_all([rec1, rec2])
core.session.commit()
print(f"[OK] {2} receitas criadas")

# Teste 1: Filtro de Status - Despesas
print("\n[3] Teste: get_expenses_by_status()")
print("-" * 50)

print("\n  a) Filtro: Todos")
all_exp = core.get_expenses_by_status("Todos")
print(f"     Encontrados: {len(all_exp)} despesas")
for e in all_exp:
    print(f"     - {e.descricao}: R$ {e.valor:.2f} ({e.status})")

print("\n  b) Filtro: Pendente")
pending_exp = core.get_expenses_by_status("Pendente")
print(f"     Encontrados: {len(pending_exp)} despesas pendentes")
for e in pending_exp:
    print(f"     - {e.descricao}: R$ {e.valor:.2f}")

print("\n  c) Filtro: Atrasado")
overdue_exp = core.get_expenses_by_status("Atrasado")
print(f"     Encontrados: {len(overdue_exp)} despesas atrasadas")
for e in overdue_exp:
    print(f"     - {e.descricao}: R$ {e.valor:.2f} (Vencimento: {e.vencimento})")

print("\n  d) Filtro: Pago")
paid_exp = core.get_expenses_by_status("Pago")
print(f"     Encontrados: {len(paid_exp)} despesas pagas")
for e in paid_exp:
    print(f"     - {e.descricao}: R$ {e.valor:.2f}")

# Teste 2: Filtro de Status - Receitas
print("\n[4] Teste: get_receivables_by_status()")
print("-" * 50)

print("\n  a) Filtro: Todos")
all_rec = core.get_receivables_by_status("Todos")
print(f"     Encontrados: {len(all_rec)} receitas")
for r in all_rec:
    print(f"     - {r.descricao}: R$ {r.valor:.2f} ({r.status})")

print("\n  b) Filtro: Pendente")
pending_rec = core.get_receivables_by_status("Pendente")
print(f"     Encontrados: {len(pending_rec)} receitas pendentes")
for r in pending_rec:
    print(f"     - {r.descricao}: R$ {r.valor:.2f}")

print("\n  c) Filtro: Recebido")
received_rec = core.get_receivables_by_status("Recebido")
print(f"     Encontrados: {len(received_rec)} receitas recebidas")
for r in received_rec:
    print(f"     - {r.descricao}: R$ {r.valor:.2f}")

# Teste 3: Pagamento Parcial
print("\n[5] Teste: pay_expense_partial()")
print("-" * 50)

exp_id = exp1.id
print(f"\n  Despesa original: {exp1.descricao}")
print(f"  ID: {exp_id}, Valor: R$ {exp1.valor:.2f}, Status: {exp1.status}")

print("\n  Registrando pagamento parcial de R$ 200.00...")
success = core.pay_expense_partial(exp_id, 200.00)
print(f"  [OK] Sucesso: {success}")

# Recarregar dados
core.session.refresh(exp1)
pendente_exp = (
    core.session.query(Expense)
    .filter(Expense.descricao.like("%Saldo Restante%"))
    .first()
)

print(f"\n  Status da despesa original após pagamento: {exp1.status}")
print(f"  Valor pago (data_pagamento): {exp1.data_pagamento}")
print("\n  Novo registro criado (saldo restante):")
if pendente_exp:
    print(f"  - Descrição: {pendente_exp.descricao}")
    print(f"  - Valor: R$ {pendente_exp.valor:.2f}")
    print(f"  - Status: {pendente_exp.status}")
else:
    print("  [WARNING] Nenhum registro de saldo restante criado!")

# Teste 4: Recebimento Parcial
print("\n[6] Teste: receive_receivable_partial()")
print("-" * 50)

rec_id = rec1.id
print(f"\n  Receita original: {rec1.descricao}")
print(f"  ID: {rec_id}, Valor: R$ {rec1.valor:.2f}, Status: {rec1.status}")

print("\n  Registrando recebimento parcial de R$ 600.00...")
success = core.receive_receivable_partial(rec_id, 600.00)
print(f"  [OK] Sucesso: {success}")

# Recarregar dados
core.session.refresh(rec1)
pendente_rec = (
    core.session.query(Receivable)
    .filter(Receivable.descricao.like("%Saldo Restante%"))
    .first()
)

print(f"\n  Status da receita original após recebimento: {rec1.status}")
print(f"  Valor recebido (data_recebimento): {rec1.data_recebimento}")
print("\n  Novo registro criado (saldo restante):")
if pendente_rec:
    print(f"  - Descrição: {pendente_rec.descricao}")
    print(f"  - Valor: R$ {pendente_rec.valor:.2f}")
    print(f"  - Status: {pendente_rec.status}")
else:
    print("  [WARNING] Nenhum registro de saldo restante criado!")

# Teste 5: Verificar estado final
print("\n[7] Estado Final dos Dados")
print("-" * 50)

all_exp_final = core.get_expenses_by_status("Todos")
all_rec_final = core.get_receivables_by_status("Todos")

print(f"\n  Total de despesas: {len(all_exp_final)}")
for e in all_exp_final:
    status_str = f"({e.status})"
    venc = f" Venc: {e.vencimento}" if e.vencimento else ""
    print(f"  - {e.descricao}: R$ {e.valor:.2f} {status_str}{venc}")

print(f"\n  Total de receitas: {len(all_rec_final)}")
for r in all_rec_final:
    status_str = f"({r.status})"
    venc = f" Venc: {r.vencimento}" if r.vencimento else ""
    print(f"  - {r.descricao}: R$ {r.valor:.2f} {status_str}{venc}")

print("\n" + "=" * 70)
print("[OK] TESTES CONCLUÍDOS COM SUCESSO!")
print("=" * 70)
