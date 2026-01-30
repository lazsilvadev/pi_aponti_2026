from models.db_models import User, get_session, init_db

try:
    from passlib.hash import pbkdf2_sha256
except ImportError:
    pbkdf2_sha256 = None

engine = init_db()
session = get_session(engine)

# Encontrar admin
admin = session.query(User).filter_by(username="admin").first()
if admin:
    print("Admin atual:")
    print(f"  Username: {admin.username}")
    print(f"  Role: {admin.role}")

    # Atualizar a senha para "2323"
    print("\nAtualizando senha para '2323'...")
    if pbkdf2_sha256:
        admin.password = pbkdf2_sha256.hash("2323")
        session.commit()
        print("✓ Senha hasheada e atualizada!")
        print(f"  Novo hash: {admin.password}")
    else:
        print("✗ pbkdf2_sha256 não disponível!")
else:
    print("Admin não encontrado!")
