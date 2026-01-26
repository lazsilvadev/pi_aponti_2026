import os
import sys

# Garante que a pasta raiz (onde está models/) entre no sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.db_models import User, get_session, init_db

engine = init_db()
session = get_session(engine)

print("USUÁRIOS ATUAIS NO BANCO:")
for u in session.query(User).all():
    print(f"- id={u.id} username={u.username} role={u.role} nome={u.full_name}")

session.close()
