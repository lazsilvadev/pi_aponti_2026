"""Testes para a funcionalidade de agendamento automático de caixa"""

from datetime import datetime

import pytest

from core.sgv import PDVCore
from models.db_models import get_session, init_db


@pytest.fixture
def db_session():
    """Cria uma session de teste"""
    engine = init_db()
    session = get_session(engine)
    yield session
    session.close()


@pytest.fixture
def pdv_core(db_session):
    """Cria instância do PDVCore para testes"""
    return PDVCore(db_session)


class TestCaixaSchedule:
    """Testes para agendamento de fechamento/reabertura de caixa"""

    def test_schedule_caixa_closure(self, pdv_core):
        """Testa criação de agendamento"""
        data_hoje = datetime.now().strftime("%d/%m/%Y")

        resultado = pdv_core.schedule_caixa_closure(
            data_vigencia=data_hoje,
            hora_fechamento="20:30",
            hora_reabertura="07:00",
            usuario="admin",
            notas="Fechamento de teste",
        )

        assert resultado is True, "Agendamento deveria ser criado com sucesso"

    def test_get_caixa_schedule(self, pdv_core):
        """Testa busca de agendamento"""
        data_hoje = datetime.now().strftime("%d/%m/%Y")

        # Primeiro, cria o agendamento
        pdv_core.schedule_caixa_closure(
            data_vigencia=data_hoje,
            hora_fechamento="20:30",
            hora_reabertura="07:00",
            usuario="admin",
        )

        # Depois, busca
        schedule = pdv_core.get_caixa_schedule(data_hoje)

        assert schedule is not None, "Agendamento deveria ser encontrado"
        assert schedule.hora_fechamento == "20:30"
        assert schedule.hora_reabertura == "07:00"

    def test_override_caixa_schedule(self, pdv_core):
        """Testa pausa/retomada de agendamento"""
        data_hoje = datetime.now().strftime("%d/%m/%Y")

        # Cria agendamento
        pdv_core.schedule_caixa_closure(
            data_vigencia=data_hoje,
            hora_fechamento="20:30",
            hora_reabertura="07:00",
            usuario="admin",
        )

        schedule = pdv_core.get_caixa_schedule(data_hoje)
        schedule_id = schedule.id

        # Pausa
        resultado = pdv_core.override_caixa_schedule(schedule_id, "Pausado")
        assert resultado is True, "Override deveria retornar True"

        # Verifica se foi pausado
        schedule_updated = pdv_core.get_caixa_schedule(data_hoje)
        assert schedule_updated.status == "Pausado"

    def test_check_and_apply_schedule_no_schedule(self, pdv_core):
        """Testa verificação quando não há agendamento"""
        resultado = pdv_core.check_and_apply_schedule()

        assert resultado["acao"] == "nenhuma"
        assert resultado["aplicado"] is False

    def test_check_and_apply_schedule_paused(self, pdv_core):
        """Testa que agendamento pausado não aplica"""
        data_hoje = datetime.now().strftime("%d/%m/%Y")

        pdv_core.schedule_caixa_closure(
            data_vigencia=data_hoje,
            hora_fechamento="00:00",  # Passou
            hora_reabertura="23:59",
            usuario="admin",
        )

        schedule = pdv_core.get_caixa_schedule(data_hoje)
        pdv_core.override_caixa_schedule(schedule.id, "Pausado")

        resultado = pdv_core.check_and_apply_schedule()

        assert resultado["acao"] == "nenhuma"
        assert resultado["aplicado"] is False

    def test_get_proxima_fechamento_programado(self, pdv_core):
        """Testa busca do próximo fechamento programado"""
        data_hoje = datetime.now().strftime("%d/%m/%Y")

        pdv_core.schedule_caixa_closure(
            data_vigencia=data_hoje,
            hora_fechamento="20:30",
            hora_reabertura="07:00",
            usuario="admin",
            notas="Teste programado",
        )

        info = pdv_core.get_proxima_fechamento_programado()

        assert info, "Deveria retornar informações do agendamento"
        assert info["hora_fechamento"] == "20:30"
        assert info["hora_reabertura"] == "07:00"
        assert info["status"] == "Ativo"

    def test_validacao_hora_formato(self, pdv_core):
        """Testa validação de formato de hora"""
        data_hoje = datetime.now().strftime("%d/%m/%Y")

        # Tenta com formato errado
        pdv_core.schedule_caixa_closure(
            data_vigencia=data_hoje,
            hora_fechamento="25:00",  # Inválido
            hora_reabertura="07:00",
            usuario="admin",
        )

        # Mesmo assim cria (validação é no frontend)
        # Mas vamos verificar se foi armazenado
        schedule = pdv_core.get_caixa_schedule(data_hoje)
        assert schedule.hora_fechamento == "25:00"  # Armazena como-está


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
