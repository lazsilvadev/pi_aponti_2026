#!/usr/bin/env python3
"""
scripts/remove_demo_data.py

Remove dados de demonstração gerados automaticamente (usuário 'admin', sessões de caixa
associadas e finanças de exemplo). O script pede confirmação antes de executar.

Use com cuidado — operação destrutiva.
"""

from models.db_models import (
    CaixaSession,
    Expense,
    Receivable,
    User,
    get_session,
    init_db,
)


def main():
    engine = init_db()
    s = get_session(engine)

    admins = s.query(User).filter(User.username == "admin").all()
    if not admins:
        print("Nenhum usuário 'admin' encontrado. Nada a remover.")
        s.close()
        return

    print("Usuários 'admin' encontrados:")
    for a in admins:
        print(f" - id={a.id} username={a.username} full_name={a.full_name}")

    confirm = input(
        "Deseja realmente remover esses usuários e dados de demonstração? Digite 'yes' para confirmar: "
    )
    if confirm.strip().lower() != "yes":
        print("Aborted by user. Nenhuma alteração realizada.")
        s.close()
        return

    # Deletar sessões de caixa associadas e o usuário
    for a in admins:
        cs_list = s.query(CaixaSession).filter(CaixaSession.user_id == a.id).all()
        for cs in cs_list:
            print(
                f"Removendo CaixaSession id={cs.id} status={cs.status} opening_time={cs.opening_time}"
            )
            s.delete(cs)
        print(f"Removendo usuário id={a.id} username={a.username}")
        s.delete(a)

    # Remover finanças de exemplo por descrição conhecida
    demo_descriptions = [
        "Aluguel Loja",
        "Conta de Luz",
        "Venda Parcelada (Cliente A)",
        "Reembolso Fiscal",
    ]
    for d in demo_descriptions:
        exp_items = s.query(Expense).filter(Expense.descricao == d).all()
        for it in exp_items:
            print(f"Removendo Expense id={it.id} descricao={it.descricao}")
            s.delete(it)
        rec_items = s.query(Receivable).filter(Receivable.descricao == d).all()
        for it in rec_items:
            print(f"Removendo Receivable id={it.id} descricao={it.descricao}")
            s.delete(it)

    s.commit()
    print("Remoção concluída.")
    s.close()


if __name__ == "__main__":
    main()
