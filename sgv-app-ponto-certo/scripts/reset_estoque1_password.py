import sys
import os

# Garantir que o diretório do projeto esteja no sys.path
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

from models.db_models import init_db, get_session
from core.sgv import PDVCore

if __name__ == '__main__':
    engine = init_db()  # garante criação do DB se necessário e retorna engine
    session = get_session(engine)
    core = PDVCore(session)
    user = core.get_user_by_username('estoque1')
    if not user:
        print('Usuário estoque1 não encontrado.')
        raise SystemExit(1)

    print(f"Atualizando senha para usuário id={user.id} username={user.username}")
    ok, msg = core.update_user_settings(user.id, user.full_name or user.username, 'estoque123')
    print('update_user_settings ->', ok, msg)
    # Verificar autenticação logo em seguida
    auth = core.authenticate_user('estoque1', 'estoque123')
    print('authenticate after update ->', bool(auth))
    session.close()