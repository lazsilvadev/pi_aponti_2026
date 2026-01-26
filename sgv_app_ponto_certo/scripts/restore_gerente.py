# scripts/restore_gerente.py
"""
Script para restaurar o usuário gerente padrão no banco de dados.
"""

from models.db_models import User, get_session, init_db

# Função local para gerar hash de senha (bcrypt > pbkdf2_sha256 > texto plano)
try:
    from passlib.hash import bcrypt
except Exception:
    bcrypt = None
try:
    from passlib.hash import pbkdf2_sha256
except Exception:
    pbkdf2_sha256 = None


def hash_password(password):
    if pbkdf2_sha256:
        return pbkdf2_sha256.hash(password)
    elif bcrypt:
        return bcrypt.hash(password)
    return password  # fallback inseguro


def main():
    engine = init_db()
    session = get_session(engine)

    # Verifica se já existe um gerente
    gerente = session.query(User).filter_by(username="admin").first()
    if gerente:
        print("Usuário admin já existe.")
        return

    novo_gerente = User(
        username="admin",
        password=hash_password("2323"),
        role="gerente",
        full_name="Gerente",
    )
    session.add(novo_gerente)
    session.commit()
    print("Usuário gerente restaurado com sucesso.")


if __name__ == "__main__":
    main()
