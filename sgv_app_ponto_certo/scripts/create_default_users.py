import os
import sys

# Garante que a pasta raiz (onde está models/) entre no sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.db_models import User, get_session, init_db


def main():
    engine = init_db()
    session = get_session(engine)

    print("USUÁRIOS ATUAIS:")
    for u in session.query(User).all():
        print("-", u.id, u.username, u.role)

    # APAGA todos os usuários atuais (se não quiser isso, comente estas linhas)
    confirm = (
        input("\nApagar TODOS os usuários e recriar padrão? (s/N): ").strip().lower()
    )
    if confirm != "s":
        print("Operação cancelada.")
        return

    session.query(User).delete()
    session.commit()
    print("Todos os usuários existentes foram removidos.")

    # Cria usuários padrão
    # Use special marker for admin so the gerente must set password on first login
    default_users = [
        {
            "username": "admin",
            "password": "__REQUIRE_SET__",
            "role": "gerente",
            "full_name": "Administrador",
        },
        {
            "username": "user_caixa",
            "password": "123",
            "role": "caixa",
            "full_name": "Caixa 1",
        },
        {
            "username": "estoque1",
            "password": "root",
            "role": "estoque",
            "full_name": "Auxiliar de Estoque",
        },
    ]

    for data in default_users:
        user = User(**data)
        session.add(user)

    session.commit()

    print("\nUSUÁRIOS CRIADOS:")
    for u in session.query(User).all():
        print("-", u.id, u.username, u.role)

    print("\nLogin padrão:")
    print("- Gerente: usuário 'admin' | senha: será definida no primeiro login")
    print("- Caixa:   usuário 'user_caixa' | senha '123'")
    print("- Estoque: usuário 'estoque1'   | senha 'root'")


if __name__ == "__main__":
    main()
