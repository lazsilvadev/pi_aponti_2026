"""Utility to set a user's password from the project root.

Usage (Windows PowerShell):
  .\.venv\Scripts\python.exe scripts\set_password.py estoque1 estoque123

This script uses the project's models.db_models to initialize the DB and update the
password using the same hashing approach as `init_db()`.
"""

import sys
from typing import Optional

if len(sys.argv) < 3:
    print("Usage: set_password.py <username> <new_password>")
    sys.exit(2)

username = sys.argv[1]
new_password = sys.argv[2]

try:
    from models.db_models import init_db, get_session, User
except Exception as e:
    print(f"ERROR: não foi possível importar models.db_models: {e}")
    sys.exit(1)

engine = init_db()
session = get_session(engine)


def _hash_password(password: str) -> str:
    try:
        from passlib.hash import pbkdf2_sha256

        return pbkdf2_sha256.hash(password)
    except Exception:
        try:
            from passlib.hash import bcrypt

            return bcrypt.hash(password)
        except Exception:
            # fallback: store plain text (não recomendado)
            return password


user = session.query(User).filter_by(username=username).first()
if not user:
    print(f"ERROR: usuário '{username}' não encontrado no banco de dados.")
    session.close()
    sys.exit(1)

user.password = _hash_password(new_password)
session.add(user)
session.commit()
print(f"Senha de '{username}' atualizada com sucesso.")
session.close()
