"""
Script de migração para encriptar `chave_pix` do registro ativo em `payment_settings`.

Uso:
  - Defina `PIX_FERNET_KEY` no ambiente e reinicie o terminal/serviço.
  - Execute: `python scripts/encrypt_paymentsettings.py`

O script verifica se `chave_pix` parece já encriptada (prefixo Fernet "gAAAA")
antes de regravar. Também faz um backup simples do valor antigo no campo
`qr_image_base64` (não alteramos esse campo aqui).
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Garantir que o diretório raiz do projeto esteja no sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models import db_models
from utils.crypto import encrypt_str


def main():
    url = getattr(db_models, "DATABASE_URL", None)
    if not url:
        print("Não foi possível determinar DATABASE_URL. Verifique sua configuração.")
        return

    engine = create_engine(url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        setting = (
            session.query(db_models.PaymentSettings).filter_by(active=True).first()
        )
        if not setting:
            print("Nenhum registro ativo de PaymentSettings encontrado.")
            return

        chave = (setting.chave_pix or "").strip()
        if not chave:
            print("Chave PIX vazia — nada a fazer.")
            return

        # Detecta prefixo típico de Fernet (base64 começa com 'gAAAA' quando gerado pelo Fernet)
        if chave.startswith("gAAAA"):
            print("Chave já parece estar encriptada — nada a fazer.")
            return

        print("Chave encontrada (texto claro). Tentando encriptar...")
        novo = encrypt_str(chave)
        if novo == chave:
            print(
                "encrypt_str não encriptou o valor — verifique PIX_FERNET_KEY e se a biblioteca 'cryptography' está instalada."
            )
            return

        # opcional: guardar backup simples no campo qr_image_base64 (não sobrescreve se já existir)
        try:
            if not setting.qr_image_base64:
                setting.qr_image_base64 = f"__backup_chave_plain__:{chave}"
        except Exception:
            pass

        setting.chave_pix = novo
        session.add(setting)
        session.commit()
        print("Chave regravada com sucesso (agora encriptada).")

    except Exception as e:
        print(f"Erro durante migração: {e}")
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        session.close()


if __name__ == "__main__":
    main()
