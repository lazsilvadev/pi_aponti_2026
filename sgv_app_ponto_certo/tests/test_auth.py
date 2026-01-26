from core.sgv import PDVCore
from models.db_models import get_session, init_db

engine = init_db()
session = get_session(engine)
core = PDVCore(session)

# Testando autenticação com admin/root
user = core.authenticate_user("admin", "root")
if user:
    print("✓ Autenticação bem-sucedida!")
    print(f"  Usuário: {user.username}")
    print(f"  Role: {user.role}")
    print(f"  Full name: {user.full_name}")
else:
    print("✗ Autenticação falhou!")

# Testando com outro usuário
user2 = core.authenticate_user("user_caixa", "123")
if user2:
    print("\n✓ Autenticação user_caixa bem-sucedida!")
    print(f"  Usuário: {user2.username}")
    print(f"  Role: {user2.role}")
else:
    print("\n✗ Autenticação user_caixa falhou!")
