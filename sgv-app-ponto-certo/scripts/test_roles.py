"""Lista usuários e testa autenticação via PDVCore.
Imprime username, role e se o login foi bem-sucedido e a rota alvo sugerida.
"""

import os
import sys

from core.sgv import PDVCore
from models.db_models import User, get_session, init_db


def route_for_role(role):
    if role == "caixa":
        return "/caixa"
    if role == "estoque":
        return "/estoque"
    if role == "gerente":
        return "/gerente"
    return "/"


def main():
    # Garantir que o cwd esteja no PYTHONPATH
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    engine = init_db()
    session = get_session(engine)
    users = session.query(User).all()

    if not users:
        print("Nenhum usuário encontrado no banco.")
        return

    pdv = PDVCore(session)

    print(f"Encontrados {len(users)} usuário(s):\n")
    for u in users:
        uname = u.username
        role = u.role
        print(f"- id={u.id} username={uname!r} role={role!r} full_name={u.full_name!r}")

    print("\nTestando autenticação (usando valor atual do campo password):")
    for u in users:
        uname = u.username
        raw_pwd = u.password if u.password is not None else ""
        # tentativa de autenticação (PDVCore deve tratar hashing/legacy)
        auth = None
        try:
            auth = pdv.authenticate_user(uname, raw_pwd)
        except Exception as ex:
            print(f"  Erro ao autenticar {uname}: {ex}")
            continue

        ok = auth is not None
        target = route_for_role(u.role)
        print(f"  -> {uname}: auth={'OK' if ok else 'FAIL'}; route_sugerida={target}")


if __name__ == "__main__":
    main()
