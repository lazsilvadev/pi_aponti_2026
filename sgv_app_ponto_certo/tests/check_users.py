from models.db_models import User, get_session, init_db

engine = init_db()
session = get_session(engine)
users = session.query(User).all()
print(f"Total de usuários: {len(users)}")
for u in users:
    print(f"ID: {u.id}, Username: {u.username}, Role: {getattr(u, 'role', 'N/A')}")
