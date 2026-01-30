"""Script de migração: altera usuários com role 'iro' para 'estoque'.

- Faz backup dos usuários afetados em JSON (pasta `backups/`).
- Por padrão pede confirmação interativa; use `--yes` para aplicar sem prompt.

Uso:
  python scripts/migrate_roles_iro_to_estoque.py         # mostra e pede confirmação
  python scripts/migrate_roles_iro_to_estoque.py --yes  # aplica sem prompt
"""

import argparse
import json
import os
from datetime import datetime

from models.db_models import User, get_session, init_db


def dump_backup(users, path):
    data = [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
        }
        for u in users
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"timestamp": datetime.now().isoformat(), "users": data},
            f,
            ensure_ascii=False,
            indent=2,
        )


def main(apply: bool = False):
    engine = init_db()
    session = get_session(engine)

    users = session.query(User).filter(User.role == "iro").all()

    if not users:
        print("Nenhum usuário com role 'iro' encontrado. Nada a fazer.")
        return 0

    print(f"Encontrados {len(users)} usuário(s) com role 'iro':")
    for u in users:
        print(
            f" - id={u.id} username={u.username!r} full_name={u.full_name!r} role={u.role!r}"
        )

    # Backup
    backups_dir = os.path.join(os.getcwd(), "backups")
    os.makedirs(backups_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backups_dir, f"usuarios_iro_backup_{stamp}.json")
    dump_backup(users, backup_path)
    print(f"Backup salvo em: {backup_path}")

    if not apply:
        ans = (
            input("Deseja aplicar a migração (alterar 'iro' -> 'estoque')? [y/N]: ")
            .strip()
            .lower()
        )
        if ans != "y":
            print("Operação abortada pelo usuário. Nenhuma alteração foi feita.")
            return 0

    # Aplicar alteração
    for u in users:
        u.role = "estoque"
    session.commit()

    print(f"Migração aplicada: {len(users)} usuário(s) atualizados para 'estoque'.")
    print("Recomenda-se reiniciar a aplicação e testar logins.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrar usuários com role 'iro' para 'estoque'."
    )
    parser.add_argument(
        "--yes", dest="yes", action="store_true", help="Aplicar sem pedir confirmação"
    )
    args = parser.parse_args()
    raise SystemExit(main(apply=args.yes))
