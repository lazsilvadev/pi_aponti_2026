import os
from datetime import date, datetime
from typing import List, Optional, Tuple

from logging_config import logger
from messages import (
    MSG_CAIXA_ABERTO,
    MSG_CAIXA_FECHADO,
    MSG_DESPESA_CRIADA,
    MSG_DESPESA_PAGA,
    MSG_ERRO_ABRIR_CAIXA,
    MSG_ERRO_FECHAR_CAIXA,
    MSG_ERRO_INESPERADO,
    MSG_RECEBIMENTO_CONFIRMADO,
    MSG_RECEITA_CRIADA,
)
from passlib.hash import bcrypt
from routes import PAINEL
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.db_models import (
    CaixaSession,
    Expense,
    MovimentoFinanceiro,
    Receivable,
    User,
    Venda,
    get_session,
    init_db,
)


class PDVCore:
    """Centraliza operações de negócio e acesso a dados com qualidade profissional."""

    def __init__(self, session: Session):
        self.session = session
        init_db()
        self._initialize_dummy_data()

    # ---------- INICIALIZAÇÃO ----------
    def _initialize_dummy_data(self) -> None:
        """Cria dados de demonstração apenas se o banco estiver vazio.

        OBS: A semeadura de dados de demonstração só ocorrerá se a variável
        de ambiente `SEED_DEMO_DATA` estiver definida como '1'. Isso evita
        inserir valores fictícios em ambientes reais.
        """
        try:
            seed_demo = os.getenv("SEED_DEMO_DATA", "0") == "1"
            if (
                seed_demo
                and not self.session.query(User).filter(User.role == "gerente").first()
            ):
                dummy_user = User(
                    username="admin",
                    password=bcrypt.hash("123"),
                    full_name="Gerente Financeiro",
                    role="gerente",
                )
                self.session.add(dummy_user)
                self.session.commit()
                self._create_demo_sessions(dummy_user.id)
                self._create_demo_finances()
                self.session.commit()
                logger.info("Dados de demonstração criados com sucesso.")
        except Exception as e:
            self.session.rollback()
            logger.exception("Erro ao inicializar dados de demonstração.")

    def _create_demo_sessions(self, user_id: int) -> None:
        """Cria sessões de caixa fechadas e uma aberta para demo."""
        sessions = [
            CaixaSession(
                user_id=user_id,
                opening_balance=100.00,
                closing_balance_system=650.00,
                closing_balance_actual=645.50,
                closing_time=datetime(2025, 11, 5, 20, 0),
                status="Closed",
                notes="Faltou R$ 4,50. Conferido.",
            ),
            CaixaSession(
                user_id=user_id,
                opening_balance=150.00,
                closing_balance_system=800.00,
                closing_balance_actual=801.10,
                closing_time=datetime(2025, 11, 4, 20, 0),
                status="Closed",
                notes="Sobrou R$ 1,10. Verificado.",
            ),
            CaixaSession(
                user_id=user_id,
                opening_balance=50.00,
                closing_balance_system=450.00,
                closing_balance_actual=450.00,
                closing_time=datetime(2025, 11, 3, 20, 0),
                status="Closed",
                notes="Caixa perfeito.",
            ),
            CaixaSession(
                user_id=user_id,
                opening_balance=200.00,
                opening_time=datetime.now(),
                status="Open",
            ),
        ]
        self.session.add_all(sessions)

    def _create_demo_finances(self) -> None:
        """Cria despesas e recebíveis de exemplo."""
        if not self.session.query(Expense).first():
            expenses = [
                Expense(
                    descricao="Aluguel Loja",
                    valor=3500.00,
                    vencimento=date(2025, 11, 10),
                    categoria="Operacional",
                    status="Pendente",
                    data_cadastro=datetime.now(),
                ),
                Expense(
                    descricao="Conta de Luz",
                    valor=850.25,
                    vencimento=date(2025, 11, 5),
                    categoria="Operacional",
                    status="Pago",
                    data_cadastro=datetime.now(),
                    data_pagamento=datetime(2025, 11, 5),
                ),
            ]
            self.session.add_all(expenses)

        if not self.session.query(Receivable).first():
            receivables = [
                Receivable(
                    descricao="Venda Parcelada (Cliente A)",
                    valor=450.00,
                    vencimento=date(2025, 11, 12),
                    origem="Vendas",
                    status="Pendente",
                    data_cadastro=datetime.now(),
                ),
                Receivable(
                    descricao="Reembolso Fiscal",
                    valor=150.00,
                    vencimento=date(2025, 11, 2),
                    origem="Outros",
                    status="Recebido",
                    data_cadastro=datetime.now(),
                    data_recebimento=datetime(2025, 11, 2),
                ),
            ]
            self.session.add_all(receivables)

    def get_all_vendas(self) -> List[Venda]:
        return self.session.query(Venda).order_by(Venda.data_venda.desc()).all()

    def get_all_closed_sessions(self) -> List[CaixaSession]:
        return (
            self.session.query(CaixaSession)
            .filter(CaixaSession.status == "Closed")
            .order_by(CaixaSession.closing_time.desc())
            .all()
        )

    def get_current_open_session(
        self, user_id: Optional[int] = None
    ) -> Optional[CaixaSession]:
        query = self.session.query(CaixaSession).filter(CaixaSession.status == "Open")
        if user_id:
            query = query.filter(CaixaSession.user_id == user_id)
        return query.first()

    def open_new_caixa(self, user_id: int, opening_balance: float) -> CaixaSession:
        try:
            new_session = CaixaSession(
                user_id=user_id,
                opening_balance=opening_balance,
                opening_time=datetime.now(),
                status="Open",
            )
            self.session.add(new_session)
            self.session.commit()
            logger.info(MSG_CAIXA_ABERTO)
            return new_session
        except Exception as e:
            self.session.rollback()
            logger.exception(MSG_ERRO_ABRIR_CAIXA)
            raise RuntimeError(MSG_ERRO_ABRIR_CAIXA) from e

    def close_caixa_session(
        self,
        session_id: int,
        closing_balance_system: float,
        closing_balance_actual: float,
        notes: Optional[str] = None,
    ) -> Optional[CaixaSession]:
        try:
            session_to_close = self.session.get(CaixaSession, session_id)
            if not session_to_close or session_to_close.status == "Closed":
                return None

            session_to_close.closing_time = datetime.now()
            session_to_close.closing_balance_system = closing_balance_system
            session_to_close.closing_balance_actual = closing_balance_actual
            session_to_close.status = "Closed"
            session_to_close.notes = notes

            self.session.commit()
            logger.info(MSG_CAIXA_FECHADO)
            return session_to_close
        except Exception as e:
            self.session.rollback()
            logger.exception(MSG_ERRO_FECHAR_CAIXA)
            raise RuntimeError(MSG_ERRO_FECHAR_CAIXA) from e

    def create_expense(
        self, descricao: str, valor: float, vencimento: date, categoria: str
    ) -> Tuple[bool, str]:
        try:
            expense = Expense(
                descricao=descricao,
                valor=valor,
                vencimento=vencimento,
                categoria=categoria,
                status="Pendente",
                data_cadastro=datetime.now(),
            )
            self.session.add(expense)
            self.session.commit()
            logger.info("Despesa criada: %s", descricao)
            return True, MSG_DESPESA_CRIADA
        except Exception as e:
            self.session.rollback()
            logger.exception("Erro ao criar despesa")
            return False, MSG_ERRO_INESPERADO

    def create_receivable(
        self, descricao: str, valor: float, vencimento: date, origem: str
    ) -> Tuple[bool, str]:
        try:
            receivable = Receivable(
                descricao=descricao,
                valor=valor,
                vencimento=vencimento,
                origem=origem,
                status="Pendente",
                data_cadastro=datetime.now(),
            )
            self.session.add(receivable)
            self.session.commit()
            logger.info("Recebível criado: %s", descricao)
            return True, MSG_RECEITA_CRIADA
        except Exception as e:
            self.session.rollback()
            logger.exception("Erro ao criar recebível")
            return False, MSG_ERRO_INESPERADO

    def mark_expense_as_paid(self, expense_id: int) -> bool:
        try:
            expense = self.session.get(Expense, expense_id)
            if not expense or expense.status == "Pago":
                return False

            expense.status = "Pago"
            expense.data_pagamento = datetime.now()

            movimento = MovimentoFinanceiro(
                descricao=f"Pagamento despesa: {expense.descricao}",
                valor=expense.valor,
                tipo="DESPESA",
                usuario_responsavel="sistema",
                data=datetime.now(),
            )
            self.session.add(movimento)
            self.session.commit()
            logger.info("Despesa paga: ID=%s", expense_id)
            return True
        except Exception as e:
            self.session.rollback()
            logger.exception("Erro ao pagar despesa")
            return False

    def mark_expense_as_unpaid(self, expense_id: int) -> bool:
        try:
            expense = self.session.get(Expense, expense_id)
            if not expense or expense.status == "Pendente":
                return False

            expense.status = "Pendente"
            expense.data_pagamento = None

            self.session.commit()
            logger.info("Despesa desmarcada como pago: ID=%s", expense_id)
            return True
        except Exception as e:
            self.session.rollback()
            logger.exception("Erro ao desmarcar despesa como pago")
            return False

    def mark_receivable_as_paid(self, receivable_id: int) -> bool:
        try:
            receivable = self.session.get(Receivable, receivable_id)
            if not receivable or receivable.status == "Recebido":
                return False

            receivable.status = "Recebido"
            receivable.data_recebimento = datetime.now()

            movimento = MovimentoFinanceiro(
                descricao=f"Recebimento: {receivable.descricao}",
                valor=receivable.valor,
                tipo="RECEITA",
                usuario_responsavel="sistema",
                data=datetime.now(),
            )
            self.session.add(movimento)
            self.session.commit()
            logger.info("Recebível recebido: ID=%s", receivable_id)
            return True
        except Exception as e:
            self.session.rollback()
            logger.exception("Erro ao receber recebível")
            return False

    def mark_receivable_as_unpaid(self, receivable_id: int) -> bool:
        try:
            receivable = self.session.get(Receivable, receivable_id)
            if not receivable or receivable.status == "Pendente":
                return False

            receivable.status = "Pendente"
            receivable.data_recebimento = None

            self.session.commit()
            logger.info("Recebível desmarcado como recebido: ID=%s", receivable_id)
            return True
        except Exception as e:
            self.session.rollback()
            logger.exception("Erro ao desmarcar recebível como recebido")
            return False

    def delete_expense(self, expense_id: int) -> bool:
        try:
            expense = self.session.get(Expense, expense_id)
            if not expense:
                return False

            self.session.delete(expense)
            self.session.commit()
            logger.info("Despesa deletada: ID=%s", expense_id)
            return True
        except Exception as e:
            self.session.rollback()
            logger.exception("Erro ao deletar despesa")
            return False

    def delete_receivable(self, receivable_id: int) -> bool:
        try:
            receivable = self.session.get(Receivable, receivable_id)
            if not receivable:
                return False

            self.session.delete(receivable)
            self.session.commit()
            logger.info("Receita deletada: ID=%s", receivable_id)
            return True
        except Exception as e:
            self.session.rollback()
            logger.exception("Erro ao deletar receita")
            return False

    def get_pending_expenses(self) -> List[Expense]:
        try:
            return (
                self.session.query(Expense)
                .filter(Expense.status == "Pendente")
                .order_by(Expense.vencimento)
                .all()
            )
        except Exception as e:
            logger.exception("Erro ao buscar despesas pendentes")
            return []

    def get_pending_receivables(self) -> List[Receivable]:
        try:
            return (
                self.session.query(Receivable)
                .filter(Receivable.status == "Pendente")
                .order_by(Receivable.vencimento)
                .all()
            )
        except Exception as e:
            logger.exception("Erro ao buscar recebíveis pendentes")
            return []

    def get_dashboard_data(self) -> dict:
        try:
            total_receitas = (
                self.session.query(
                    func.coalesce(func.sum(MovimentoFinanceiro.valor), 0)
                )
                .filter(MovimentoFinanceiro.tipo == "RECEITA")
                .scalar()
                or 0
            )
            total_despesas = (
                self.session.query(
                    func.coalesce(func.sum(MovimentoFinanceiro.valor), 0)
                )
                .filter(MovimentoFinanceiro.tipo == "DESPESA")
                .scalar()
                or 0
            )
            mes_atual = datetime.now().month
            ano_atual = datetime.now().year

            receitas_mes = (
                self.session.query(
                    func.coalesce(func.sum(MovimentoFinanceiro.valor), 0)
                )
                .filter(
                    MovimentoFinanceiro.tipo == "RECEITA",
                    func.extract("month", MovimentoFinanceiro.data) == mes_atual,
                    func.extract("year", MovimentoFinanceiro.data) == ano_atual,
                )
                .scalar()
                or 0
            )

            despesas_mes = (
                self.session.query(
                    func.coalesce(func.sum(MovimentoFinanceiro.valor), 0)
                )
                .filter(
                    MovimentoFinanceiro.tipo == "DESPESA",
                    func.extract("month", MovimentoFinanceiro.data) == mes_atual,
                    func.extract("year", MovimentoFinanceiro.data) == ano_atual,
                )
                .scalar()
                or 0
            )

            return {
                "saldo_atual": float(total_receitas - total_despesas),
                "receitas_mes": float(receitas_mes),
                "despesas_mes": float(despesas_mes),
                "lucro_mes": float(receitas_mes - despesas_mes),
            }
        except Exception as e:
            logger.exception("Erro ao buscar dados do dashboard")
            return {
                "saldo_atual": 0.0,
                "receitas_mes": 0.0,
                "despesas_mes": 0.0,
                "lucro_mes": 0.0,
            }
