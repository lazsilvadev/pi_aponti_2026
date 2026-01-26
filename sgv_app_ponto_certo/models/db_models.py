# db_models.py

import os
import sys
from datetime import date, datetime

import flet as ft
from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

from utils.path_resolver import get_database_url


# Impressão segura em UTF-8 para ambientes Windows/empacotados
def safe_print(msg: str):
    try:
        # Tenta escrever diretamente no buffer com utf-8
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write((str(msg) + "\n").encode("utf-8"))
            sys.stdout.buffer.flush()
        else:
            # Fallback para streams que não expõem buffer
            sys.stdout.write(str(msg) + "\n")
            sys.stdout.flush()
    except Exception:
        try:
            # Último recurso: escrever no stderr codificando e substituindo caracteres inválidos
            sys.stderr.write(
                str(msg).encode("utf-8", errors="replace").decode("utf-8") + "\n"
            )
            sys.stderr.flush()
        except Exception:
            pass


# Carrega variáveis de ambiente (se existirem) ou usa SQLite local
load_dotenv()
# Forçar uso do SQLite local por padrão (evita usar DATABASE_URL do ambiente)
# Para usar MariaDB/MySQL novamente, exporte/defina explicitamente DATABASE_URL
# e altere aqui se desejar suportar prioridade para variáveis de ambiente.
DATABASE_URL = get_database_url()

Base = declarative_base()


class User(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # gerente, caixa, iro
    full_name = Column(String(100), nullable=True)

    # Relação bidirecional com CaixaSession
    caixa_sessions = relationship(
        "CaixaSession", back_populates="user", cascade="all, delete-orphan"
    )


class Fornecedor(Base):
    __tablename__ = "fornecedores"
    id = Column(Integer, primary_key=True)
    nome_razao_social = Column(String(200), nullable=False, index=True)
    cnpj_cpf = Column(String(20), unique=True, nullable=True, index=True)
    contato = Column(String(100), nullable=True)
    condicao_pagamento = Column(
        String(100), nullable=True
    )  # "Débito, Dinheiro, Crédito, Pix"
    prazo_entrega_medio = Column(String(50), nullable=True)  # ex: "7 dias úteis"
    status = Column(
        String(20), nullable=False, default="ativo", index=True
    )  # ativo, inativo
    # Avaliação interna (inteiro 0-5) e observações internas do fornecedor
    avaliacao_interna = Column(Integer, nullable=True, default=0)
    observacoes_internas = Column(Text, nullable=True)

    # Relação bidirecional com Produto
    produtos = relationship(
        "Produto", back_populates="fornecedor", cascade="all, delete-orphan"
    )


class Produto(Base):
    __tablename__ = "produtos"
    id = Column(Integer, primary_key=True)
    codigo_barras = Column(String(50), unique=True, nullable=False, index=True)
    nome = Column(String(200), nullable=False, index=True)
    preco_custo = Column(Float, nullable=False)
    preco_venda = Column(Float, nullable=False)
    estoque_atual = Column(Integer, default=0, nullable=False)
    estoque_minimo = Column(
        Integer, default=10, nullable=True
    )  # Para controle de estoque mínimo
    validade = Column(String(20), nullable=True)

    # Chave estrangeira e relação bidirecional
    fornecedor_id = Column(
        Integer, ForeignKey("fornecedores.id"), nullable=True, index=True
    )
    fornecedor = relationship("Fornecedor", back_populates="produtos")

    # Propriedade para compatibilidade com código legado que usa 'estoque'
    @property
    def estoque(self):
        """Alias para compatibilidade com código legado"""
        return self.estoque_atual

    @estoque.setter
    def estoque(self, value):
        """Alias para compatibilidade com código legado"""
        self.estoque_atual = value


class Venda(Base):
    __tablename__ = "vendas"
    id = Column(Integer, primary_key=True)
    data_venda = Column(DateTime, default=datetime.now, nullable=False, index=True)
    total = Column(Float, nullable=False)
    usuario_responsavel = Column(String(100), nullable=False, index=True)
    forma_pagamento = Column(String(50), nullable=False, default="Dinheiro")
    valor_pago = Column(Float, nullable=False, default=0.0)
    status = Column(
        String(20), nullable=False, default="CONCLUIDA", index=True
    )  # CONCLUIDA, ESTORNADA, PENDENTE
    # Campos para integração de pagamentos/TEF
    transaction_id = Column(String(128), nullable=True, index=True)
    payment_status = Column(String(50), nullable=True, index=True)

    # Relação bidirecional
    itens = relationship(
        "ItemVenda", back_populates="venda", cascade="all, delete-orphan"
    )


class ItemVenda(Base):
    __tablename__ = "itens_venda"
    id = Column(Integer, primary_key=True)
    venda_id = Column(Integer, ForeignKey("vendas.id"), nullable=False, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False, index=True)
    quantidade = Column(Integer, nullable=False)
    preco_unitario = Column(Float, nullable=False)

    # Relações bidirecionais
    venda = relationship("Venda", back_populates="itens")
    produto = relationship("Produto")


class MovimentoFinanceiro(Base):
    __tablename__ = "movimentos_financeiros"
    id = Column(Integer, primary_key=True)
    data = Column(DateTime, default=datetime.now, nullable=False, index=True)
    descricao = Column(String(200), nullable=False)
    tipo = Column(
        String(50), nullable=False, index=True
    )  # RECEITA, DESPESA, FECHAMENTO_CAIXA
    valor = Column(Float, nullable=False)
    usuario_responsavel = Column(String(100), nullable=False, index=True)


class CaixaSession(Base):
    __tablename__ = "caixa_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    opening_time = Column(DateTime, default=datetime.now, nullable=False)
    opening_balance = Column(Float, nullable=False)

    closing_time = Column(DateTime)
    closing_balance_system = Column(Float)
    closing_balance_actual = Column(Float)

    status = Column(
        String(20), default="Open", nullable=False, index=True
    )  # Open, Closed
    notes = Column(Text, nullable=True)

    # Relação bidirecional
    user = relationship("User", back_populates="caixa_sessions")

    @property
    def difference(self):
        """Calcula a quebra/sobra de caixa."""
        if (
            self.closing_balance_system is not None
            and self.closing_balance_actual is not None
        ):
            return round(self.closing_balance_actual - self.closing_balance_system, 2)
        return 0.0

    @property
    def current_balance(self):
        """Calcula saldo atual (aberto + vendas do dia)"""
        # TODO: Implementar cálculo real incluindo vendas do dia
        return self.opening_balance if hasattr(self, "opening_balance") else 0.0


class Expense(Base):
    """Tabela de Contas a Pagar / Despesas"""

    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    descricao = Column(String(200), nullable=False)
    valor = Column(Float, nullable=False)
    vencimento = Column(String(10), nullable=False)  # formato dd/mm/aaaa
    categoria = Column(String(50), nullable=True)
    status = Column(
        String(20), default="Pendente", nullable=False, index=True
    )  # Pendente, Pago
    data_cadastro = Column(DateTime, default=datetime.now, nullable=False)
    data_pagamento = Column(DateTime, nullable=True)


class Receivable(Base):
    """Tabela de Contas a Receber / Receitas"""

    __tablename__ = "receivables"
    id = Column(Integer, primary_key=True)
    descricao = Column(String(200), nullable=False)
    valor = Column(Float, nullable=False)
    vencimento = Column(String(10), nullable=False)  # formato dd/mm/aaaa
    origem = Column(String(50), nullable=True)
    status = Column(
        String(20), default="Pendente", nullable=False, index=True
    )  # Pendente, Recebido
    data_cadastro = Column(DateTime, default=datetime.now, nullable=False)
    data_recebimento = Column(DateTime, nullable=True)


class CaixaSchedule(Base):
    """Tabela de Agendamento de Fechamento/Reabertura Automática do Caixa"""

    __tablename__ = "caixa_schedules"
    id = Column(Integer, primary_key=True)
    data_vigencia = Column(String(10), nullable=False, index=True)  # formato dd/mm/aaaa
    hora_fechamento = Column(String(5), nullable=False)  # formato HH:MM
    hora_reabertura = Column(String(5), nullable=False)  # formato HH:MM
    status = Column(
        String(20), default="Ativo", nullable=False, index=True
    )  # Ativo, Pausado, Cancelado
    criado_em = Column(DateTime, default=datetime.now, nullable=False)
    criado_por = Column(String(100), nullable=False)  # username do gerente
    override_count = Column(Integer, default=0)  # Quantas vezes foi pausado/retomado
    notas = Column(Text, nullable=True)

    # Flags de estado
    caixa_foi_fechado = Column(Boolean, default=False)  # Se já foi fechado hoje
    caixa_foi_reaberto = Column(Boolean, default=False)  # Se já foi reaberto hoje


class PaymentSettings(Base):
    """Configurações de pagamento (PIX) armazenadas no banco.

    - `chave_pix` deve ser guardada com cuidado (criptografada em produção).
    - Apenas um registro `active=True` será considerado como configuração ativa.
    """

    __tablename__ = "payment_settings"
    id = Column(Integer, primary_key=True)
    merchant_name = Column(
        String(100), nullable=False, default="Mercadinho Ponto Certo"
    )
    chave_pix = Column(String(255), nullable=True)
    cpf_cnpj = Column(String(30), nullable=True)
    cidade = Column(String(50), nullable=True)
    tipo_pix = Column(String(20), nullable=False, default="dinamico")
    active = Column(Boolean, default=True, index=True)
    updated_at = Column(DateTime, default=datetime.now)
    # Auditoria: usuário que aprovou/alterou a configuração
    updated_by = Column(String(100), nullable=True)
    # Armazenamento opcional de QR (PNG/JPEG) em base64 para mostrar QR fornecido pelo gerente
    qr_image_base64 = Column(Text, nullable=True)
    # (sem campos de taxa por enquanto - restauração ao estado anterior)


# ====================================================================
# Funções de inicialização
# ====================================================================
def init_db():
    """Cria o engine e as tabelas se não existirem. Também cria usuários padrão e carrega produtos."""
    engine = create_engine(DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)

    # Verificar se colunas opcionais existem e, se não, tentar adicioná-las (SQLite fallback)
    try:
        with engine.connect() as conn:
            try:
                res = conn.execute(text("PRAGMA table_info(fornecedores);"))
                cols = [r[1] for r in res.fetchall()]
            except Exception:
                cols = []

            # adicionar coluna avaliacao_interna se inexistente
            if "avaliacao_interna" not in cols:
                try:
                    conn.execute(
                        text(
                            "ALTER TABLE fornecedores ADD COLUMN avaliacao_interna INTEGER DEFAULT 0;"
                        )
                    )
                except Exception:
                    pass

            # adicionar coluna observacoes_internas se inexistente
            if "observacoes_internas" not in cols:
                try:
                    conn.execute(
                        text(
                            "ALTER TABLE fornecedores ADD COLUMN observacoes_internas TEXT;"
                        )
                    )
                except Exception:
                    pass
    except Exception:
        # se não for possível executar migração automática, continuar silenciosamente
        pass

    # Criar usuários padrão se o banco estiver vazio
    Session = sessionmaker(bind=engine)
    session = Session()

    def _hash_password(password: str) -> str:
        try:
            from passlib.hash import pbkdf2_sha256

            return pbkdf2_sha256.hash(password)
        except Exception:
            try:
                from passlib.hash import bcrypt

                return bcrypt.hash(password)
            except Exception:
                return password

    try:
        # Verificar se já existem usuários
        user_count = session.query(User).count()

        if user_count == 0:
            # Criar usuários padrão (armazenando senha como hash quando possível)
            default_users_data = [
                {
                    "username": "admin",
                    "password": "root",
                    "role": "gerente",
                    "full_name": "Administrador",
                },
                {
                    "username": "user_caixa",
                    "password": "123",
                    "role": "caixa",
                    "full_name": "Caixa 1",
                },
                {
                    "username": "estoque1",
                    "password": "root",
                    "role": "estoque",
                    "full_name": "Auxiliar de Estoque",
                },
            ]

            for udata in default_users_data:
                pwd = udata.get("password") or ""
                # If password set to special marker, store marker so system
                # requires the user (gerente) to set a new password on first login.
                if pwd == "__REQUIRE_SET__":
                    hashed = "__REQUIRE_SET__"
                else:
                    hashed = _hash_password(pwd) if pwd else ""
                user = User(
                    username=udata.get("username"),
                    password=hashed,
                    role=udata.get("role"),
                    full_name=udata.get("full_name"),
                )
                session.add(user)

            session.commit()
            safe_print(
                "[OK] Usuarios padrao criados automaticamente (senhas armazenadas como hash quando possível)!"
            )

        # Verificar se há produtos e carregar do JSON se necessário
        produto_count = session.query(Produto).count()
        if produto_count == 0:
            safe_print("[INFO] Nenhum produto no banco. Carregando de produtos.json...")
            _importar_produtos_do_json(session)

        # Criar uma configuração padrão de Pix se não existir
        try:
            from sqlalchemy import select

            existe = session.query(PaymentSettings).count()
            if existe == 0:
                default_pix = PaymentSettings(
                    merchant_name="Mercadinho Ponto Certo",
                    chave_pix=None,
                    cpf_cnpj=None,
                    cidade="Recife",
                    tipo_pix="dinamico",
                    active=True,
                )
                session.add(default_pix)
                session.commit()
                safe_print(
                    "[OK] PaymentSettings: registro padrão criado (chave vazia)."
                )
        except Exception:
            try:
                session.rollback()
            except Exception:
                pass

    except Exception as e:
        safe_print(f"[ERROR] Erro durante inicializacao: {e}")
        session.rollback()

    finally:
        session.close()

    return engine


def _importar_produtos_do_json(session):
    """Importa produtos do arquivo JSON para o banco de dados"""
    import json
    from pathlib import Path

    try:
        # Usar path_resolver para encontrar o arquivo
        base_path = Path(__file__).parent.parent
        json_path = base_path / "data" / "produtos.json"

        if not json_path.exists():
            safe_print(f"[WARN] Arquivo {json_path} nao encontrado!")
            return

        with open(json_path, "r", encoding="utf-8") as f:
            produtos_json = json.load(f)

        count_inserted = 0
        for prod in produtos_json:
            codigo_barras = str(
                prod.get("codigo_barras") or prod.get("codigo") or ""
            ).strip()
            if not codigo_barras:
                continue

            # Verificar se já existe
            produto_existente = (
                session.query(Produto).filter_by(codigo_barras=codigo_barras).first()
            )
            if produto_existente:
                continue

            nome = prod.get("nome") or prod.get("descricao") or "Produto"
            preco_custo = float(prod.get("preco_custo", 0.0))
            preco_venda = float(prod.get("preco_venda", prod.get("preco", 0.0)))
            estoque_atual = int(prod.get("quantidade", prod.get("estoque", 0)))
            validade = prod.get("validade")

            novo_prod = Produto(
                codigo_barras=codigo_barras,
                nome=nome,
                preco_custo=preco_custo,
                preco_venda=preco_venda,
                estoque_atual=estoque_atual,
                validade=validade,
            )
            session.add(novo_prod)
            count_inserted += 1

        if count_inserted > 0:
            session.commit()
            safe_print(f"[OK] {count_inserted} produtos carregados do JSON!")
        else:
            safe_print("[INFO] Nenhum novo produto para carregar do JSON")

    except Exception as e:
        safe_print(f"[ERROR] Erro ao importar produtos do JSON: {e}")
        session.rollback()


def get_session(engine):
    """Retorna uma nova sessão do banco de dados"""
    Session = sessionmaker(bind=engine)
    return Session()


def get_active_pix_settings(session: Session):
    """Retorna o registro ativo de PaymentSettings como dict ou None."""
    try:
        setting = session.query(PaymentSettings).filter_by(active=True).first()
        if not setting:
            return None
        return {
            "merchant_name": setting.merchant_name,
            "chave_pix": setting.chave_pix,
            "cpf_cnpj": setting.cpf_cnpj,
            "cidade": setting.cidade,
            "tipo_pix": setting.tipo_pix,
            "qr_image": getattr(setting, "qr_image_base64", None),
        }
    except Exception:
        return None


# ====================================================================
# Funções utilitárias (BÔNUS - úteis para desenvolvimento)
# ====================================================================
def reset_database():
    """
    ⚠️ APAGA E RECRIA TODAS AS TABELAS (USE COM EXTREMO CUIDADO!)
    Útil apenas em desenvolvimento.
    """
    engine = create_engine(DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    safe_print("[OK] Banco de dados resetado com sucesso!")


def seed_sample_data(session):
    """
    Popula o banco com dados de exemplo para desenvolvimento
    """
    # TODO: Implementar conforme necessário
    pass
