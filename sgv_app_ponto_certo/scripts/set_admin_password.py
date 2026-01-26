#!/usr/bin/env python3
import os
import sys

# Garantir que o diretório do projeto esteja no PYTHONPATH
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

try:
    from core.sgv import PDVCore
    from models.db_models import get_session, init_db
except Exception as e:
    print("Erro ao importar módulos do projeto:", e)
    sys.exit(2)

engine = init_db()
session = get_session(engine)
pdv = PDVCore(session)

admin = pdv.get_user_by_username("admin")
if not admin:
    print("Usuário admin não encontrado")
    sys.exit(1)

ok, msg = pdv.update_user_settings(admin.id, admin.full_name or "", "root")
print("Resultado:", ok, msg)
if not ok:
    sys.exit(3)
print("Senha do admin alterada para: root")
