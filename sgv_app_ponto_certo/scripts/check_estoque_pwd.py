from models.db_models import init_db, get_session, User

engine = init_db()
s = get_session(engine)
user = s.query(User).filter_by(username="estoque1").first()
if not user:
    print("NOT_FOUND")
else:
    print("FOUND")
    print(user.username)
    print(user.password)
s.close()
