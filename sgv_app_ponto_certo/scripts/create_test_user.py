"""Script para testar criação de usuário via PDVCore e capturar possíveis erros relacionados ao bcrypt."""

import os
import sys

from core.sgv import PDVCore
from models.db_models import get_session, init_db


def main():
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    engine = init_db()
    session = get_session(engine)
    pdv = PDVCore(session)

    username = "teste_estoque_1"
    password = "senha123"
    role = "estoque"
    full_name = "Teste Estoque"

    try:
        ok, result = pdv.create_user(username, password, role, full_name)
        print("ok:", ok)
        print("result:", result)
    except Exception as e:
        print("Exception during create_user:", repr(e))


if __name__ == "__main__":
    main()
