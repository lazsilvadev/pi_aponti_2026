"""Arquivo de configuração principal do Alembic (lado Python).

Aqui o Alembic decide **como** rodar as migrações, lendo as
configurações do `alembic.ini` e conectando no banco de dados.

Pontos principais:
- Lê o `alembic.ini` para saber URL do banco e pasta de versões
- Carrega o `Base.metadata` dos modelos para suportar `autogenerate`
- Expõe duas formas de rodar migração: "offline" e "online"
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Objeto principal de configuração do Alembic.
# Ele lê as opções da seção [alembic] do arquivo `alembic.ini`.
config = context.config

# Configura o logging do Alembic com base no `alembic.ini`.
# Assim, logs de migração aparecem no console/arquivo conforme definido lá.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# target_metadata: mapeia as tabelas/colunas usadas no autogenerate
# ---------------------------------------------------------------------------
# Importamos o `Base` (SQLAlchemy) definido em `models/db_models.py`.
# O Alembic usa essa metadata para comparar o estado atual do modelo
# com o estado do banco e, assim, gerar migrações automaticamente.
try:
    from models.db_models import Base

    # Metadados de todas as tabelas do projeto (usado em autogenerate)
    target_metadata = Base.metadata
except Exception:
    # Se o import falhar, deixamos target_metadata como None.
    # Nesse caso, ainda é possível rodar migrações escritas "na mão",
    # mas o recurso de `alembic revision --autogenerate` fica limitado.
    target_metadata = None

# Outras opções adicionais poderiam ser lidas do `alembic.ini` aqui, se
# necessário, usando por exemplo:
# my_important_option = config.get_main_option("my_important_option")


def run_migrations_offline() -> None:
    """Executa migrações em modo "offline".

    Nesse modo, o Alembic NÃO abre uma conexão real com o banco.
    Ele só precisa da URL (string) e gera o SQL das migrações,
    normalmente para ser salvo em arquivo ou só exibido.

    Útil, por exemplo, para inspecionar o SQL antes de aplicar
    em produção.
    """
    url = config.get_main_option("sqlalchemy.url")
    # Configura o contexto passando apenas a URL (sem Engine).
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrações em modo "online".

    Nesse modo, o Alembic cria um `Engine` real, abre uma conexão
    com o banco e aplica as migrações diretamente.
    """
    # Cria um Engine SQLAlchemy a partir das opções definidas no `alembic.ini`
    # (seção [alembic], prefixadas com "sqlalchemy.").
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Passa a conexão aberta e a metadata dos modelos para o Alembic.
        # Assim, as migrações são executadas diretamente no banco alvo.
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
