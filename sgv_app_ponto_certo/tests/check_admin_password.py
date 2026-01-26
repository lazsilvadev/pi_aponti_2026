from models.db_models import User, get_session, init_db

engine = init_db()
session = get_session(engine)
admin = session.query(User).filter_by(username="admin").first()
if admin:
    print(f"Usuário: {admin.username}")
    print(f"Role: {admin.role}")
    print(f"Password armazenada: {admin.password}")
else:
    print("Usuário admin não encontrado")
