import sys
import os
# Garantir que o diretório do projeto esteja no sys.path (caminho com espaço tratado)
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

from models.db_models import init_db, get_session
from core.sgv import PDVCore

engine = init_db()
session = get_session(engine)
pdv = PDVCore(session)

user = pdv.authenticate_user('estoque1','estoque123')
print('AUTH_RESULT:', bool(user))
if user:
    print('username:', user.username, 'role:', user.role, 'full_name:', user.full_name)
else:
    # print stored password for debugging
    try:
        u = session.query(__import__('models.db_models', fromlist=['User']).User).filter_by(username='estoque1').first()
        print('stored password repr:', repr(getattr(u,'password',None)))
    except Exception as e:
        print('failed reading stored password:', e)
