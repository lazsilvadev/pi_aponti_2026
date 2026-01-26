import flet as ft

from caixa.caixa_schedule_components import (
    create_schedule_dialog,
    create_schedule_override_dialog,
    create_schedule_status_widget,
)
from models.db_models import Expense, Receivable, Venda

from .financeiro_components import create_finance_table, create_kpi_card
from .financeiro_dialogs import (
    close_and_audit_caixa_dialog,
    nova_despesa_dialog,
    nova_receita_dialog,
    open_new_caixa_dialog,
)
from .financeiro_history import create_caixa_history_table
from .financeiro_utils import _show_snack, export_finance_csv, export_finance_pdf

# Paleta de cores usada na tela de financeiro
COLORS = {
    "primary": "#034986",
    "accent": "#FFB347",
    "background": "#F0F4F8",
    "green": "#8FC74F",
    "text": "#2D3748",
}


def create_financeiro_view(page: ft.Page, pdv_core, handle_back, create_appbar):
    """View simplificada: botões para trocar visualização, sem abas complexas."""

    # Estado: qual visualização está ativa
    is_showing_receber = ft.Ref[bool]()
    is_showing_receber.current = False

    # Estado: filtro de status ativo
    current_status_filter = ft.Ref[str]()
    current_status_filter.current = "Todos"

    # Referência para o Container da tabela (criada ANTES de refresh_table)
    tab_pagar_ref = ft.Ref[ft.Container]()

    # Referência para o dropdown de filtro
    status_filter_ref = ft.Ref[ft.Dropdown]()

    # Referências para os cards de KPI (para atualizar valores)
    card_saldo_ref = ft.Ref[ft.Text]()
    card_receita_ref = ft.Ref[ft.Text]()
    card_despesa_ref = ft.Ref[ft.Text]()

    # Dicionário para armazenar os valores dos cards (fallback se refs não funcionarem)
    card_values = {"saldo": "R$ 0,00", "receita": "R$ 0,00", "despesa": "R$ 0,00"}

    # Função para criar os cards (chamada para inicialização e possível reconstrução)
    def create_kpi_cards_row():
        """Cria os cards KPI da dashboard"""
        return ft.ResponsiveRow(
            [
                ft.Column(
                    col={"sm": 12, "md": 4},
                    controls=[
                        ft.Card(
                            ft.Container(
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Icon(
                                                    ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                                                    color=ft.Colors.BLUE,
                                                    size=32,
                                                ),
                                                ft.Text(
                                                    "Saldo Total",
                                                    size=16,
                                                    weight="bold",
                                                ),
                                            ]
                                        ),
                                        ft.Text(
                                            card_values["saldo"],
                                            size=24,
                                            weight="bold",
                                            ref=card_saldo_ref,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                padding=16,
                            ),
                            elevation=5,
                        )
                    ],
                ),
                ft.Column(
                    col={"sm": 6, "md": 4},
                    controls=[
                        ft.Card(
                            ft.Container(
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Icon(
                                                    ft.Icons.TRENDING_UP_ROUNDED,
                                                    color=ft.Colors.GREEN,
                                                    size=32,
                                                ),
                                                ft.Text(
                                                    "Total Receitas",
                                                    size=16,
                                                    weight="bold",
                                                ),
                                            ]
                                        ),
                                        ft.Text(
                                            card_values["receita"],
                                            size=24,
                                            weight="bold",
                                            ref=card_receita_ref,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                padding=16,
                            ),
                            elevation=5,
                        )
                    ],
                ),
                ft.Column(
                    col={"sm": 6, "md": 4},
                    controls=[
                        ft.Card(
                            ft.Container(
                                ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Icon(
                                                    ft.Icons.TRENDING_DOWN_ROUNDED,
                                                    color=ft.Colors.RED,
                                                    size=32,
                                                ),
                                                ft.Text(
                                                    "Total Despesas",
                                                    size=16,
                                                    weight="bold",
                                                ),
                                            ]
                                        ),
                                        ft.Text(
                                            card_values["despesa"],
                                            size=24,
                                            weight="bold",
                                            ref=card_despesa_ref,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                padding=16,
                            ),
                            elevation=5,
                        )
                    ],
                ),
            ],
            spacing=15,
        )

    # Função para calcular e atualizar os valores dos cards
    def update_dashboard_cards():
        """Atualiza os cards da visão geral com valores reais"""
        try:
            # Limpar cache da sessão para pegar valores atualizados
            pdv_core.session.expunge_all()

            # Saldo total = baseado APENAS nas vendas do caixa
            user_id = page.session.get("user_id") or 1
            sess = pdv_core.get_current_open_session(user_id)

            # Se há sessão aberta, saldo = saldo inicial + total de vendas
            if sess:
                vendas = (
                    pdv_core.session.query(Venda)
                    .filter(Venda.status == "CONCLUIDA")
                    .all()
                    or []
                )
                total_vendas = sum(v.total for v in vendas) if vendas else 0.0
                saldo_total = sess.opening_balance + total_vendas
            else:
                # Sem sessão aberta, apenas vendas concluídas
                vendas = (
                    pdv_core.session.query(Venda)
                    .filter(Venda.status == "CONCLUIDA")
                    .all()
                    or []
                )
                saldo_total = sum(v.total for v in vendas) if vendas else 0.0

            # Total de receitas (apenas as marcadas como "Recebido")
            receitas = (
                pdv_core.session.query(Receivable)
                .filter(Receivable.status == "Recebido")
                .all()
                or []
            )
            total_receitas = sum(r.valor for r in receitas) if receitas else 0.0

            # Total de despesas pendentes (status != "Pago") — mostrado no card
            despesas_pendentes = (
                pdv_core.session.query(Expense).filter(Expense.status != "Pago").all()
                or []
            )
            total_despesas_pendentes = (
                sum(d.valor for d in despesas_pendentes) if despesas_pendentes else 0.0
            )

            # Total de despesas já pagas (status == "Pago") — afeta o saldo (saída de caixa)
            despesas_pagas = (
                pdv_core.session.query(Expense).filter(Expense.status == "Pago").all()
                or []
            )
            total_despesas_pagas = (
                sum(d.valor for d in despesas_pagas) if despesas_pagas else 0.0
            )

            # 🔄 Calcular saldo ajustado: saldo base + receitas - despesas já pagas
            saldo_ajustado = saldo_total + total_receitas - total_despesas_pagas

            # Atualizar os cards se as refs existem
            if card_saldo_ref.current:
                card_saldo_ref.current.value = f"R$ {saldo_ajustado:,.2f}"

            if card_receita_ref.current:
                card_receita_ref.current.value = f"R$ {total_receitas:,.2f}"

            if card_despesa_ref.current:
                # Mostrar apenas despesas pendentes no card
                card_despesa_ref.current.value = f"R$ {total_despesas_pendentes:,.2f}"

            # Forçar atualização da página
            page.update()
        except Exception as ex:
            print(f"[ERRO] update_dashboard_cards: {ex}")
            import traceback

            traceback.print_exc()

    # Função para atualizar tabela
    def refresh_table(
        is_receber=None, status_filter=None, data_inicio=None, data_fim=None
    ):
        """Atualiza a tabela de financeiro. Retorna True se há dados, False se vazia."""
        try:
            # Se is_receber for passado, usa; caso contrário usa o estado atual
            if is_receber is not None:
                is_showing_receber.current = is_receber

            # Se status_filter for passado, usa; caso contrário usa o atual
            if status_filter is not None:
                current_status_filter.current = status_filter
                # Atualizar o dropdown para refletir o novo status
                if status_filter_ref.current:
                    status_filter_ref.current.value = status_filter

            # Buscar dados com ou sem filtro de data
            if data_inicio and data_fim:
                # Com filtro de data
                if is_showing_receber.current:
                    data = (
                        pdv_core.get_receivables_by_date_range(
                            current_status_filter.current, data_inicio, data_fim
                        )
                        or []
                    )
                    is_receber_var = True
                    titulo = "Receitas"
                else:
                    data = (
                        pdv_core.get_expenses_by_date_range(
                            current_status_filter.current, data_inicio, data_fim
                        )
                        or []
                    )
                    is_receber_var = False
                    titulo = "Despesas"
            else:
                # Sem filtro de data (comportamento original)
                if is_showing_receber.current:
                    data = (
                        pdv_core.get_receivables_by_status(
                            current_status_filter.current
                        )
                        or []
                    )
                    is_receber_var = True
                    titulo = "Receitas"
                else:
                    data = (
                        pdv_core.get_expenses_by_status(current_status_filter.current)
                        or []
                    )
                    is_receber_var = False
                    titulo = "Despesas"

            table = create_finance_table(
                page, data, is_receber=is_receber_var, pdv_core=pdv_core
            )
            # Atualiza o container único
            if tab_pagar_ref.current:
                tab_pagar_ref.current.content = table

            # Atualizar os cards da visão geral
            update_dashboard_cards()

            page.update()
            print(
                f"[OK] Tabela atualizada: {titulo} ({len(data)} itens) - Filtro: {current_status_filter.current}"
            )
            return len(data) > 0  # Retornar se há dados
        except Exception as ex:
            print(f"[ERRO] refresh_table: {ex}")
            import traceback

            traceback.print_exc()
            return False

    # Handlers para trocar visualização
    def show_pagar(e):
        print("[OK] Clicado: Contas a Pagar")
        # Se houver resultados de busca em cache, use-os
        try:
            last = (
                page.app_data.get("financeiro_last_search") if page.app_data else None
            )
        except Exception:
            last = None

        if last and last.get("despesas") is not None:
            try:
                table = create_finance_table(
                    page, last.get("despesas", []), is_receber=False, pdv_core=pdv_core
                )
                if tab_pagar_ref.current:
                    tab_pagar_ref.current.content = table
                page.update()
                return
            except Exception:
                pass

        refresh_table(is_receber=False)

    def show_receber(e):
        print("[OK] Clicado: Contas a Receber")
        # Se houver resultados de busca em cache, use-os
        try:
            last = (
                page.app_data.get("financeiro_last_search") if page.app_data else None
            )
        except Exception:
            last = None

        if last and last.get("receitas") is not None:
            try:
                table = create_finance_table(
                    page, last.get("receitas", []), is_receber=True, pdv_core=pdv_core
                )
                if tab_pagar_ref.current:
                    tab_pagar_ref.current.content = table
                page.update()
                return
            except Exception:
                pass

        refresh_table(is_receber=True)

    # Handler para Nova Despesa
    def on_nova_despesa(e):
        print("[DEBUG] Clicado em Nova Despesa")
        nova_despesa_dialog(page, pdv_core)

    # Handler para Nova Receita
    def on_nova_receita(e):
        print("[DEBUG] Clicado em Nova Receita")
        nova_receita_dialog(page, pdv_core)

    # Referência para o widget de status de agendamento (criada depois)
    schedule_status_widget_inner = None

    # Handlers para agendamento de caixa
    def abrir_dialog_agendamento(e=None):
        """Abre diálogo para agendar fechamento/reabertura"""
        print("[DEBUG] Clicado em Agendar Fechamento")
        try:
            current_user = pdv_core.get_user_by_id(user_id)
            overlay = create_schedule_dialog(
                page, pdv_core, current_user, on_complete=atualizar_widget_agendamento
            )
            # O overlay já é adicionado e exibido pela função create_schedule_dialog
            print("[OK] Diálogo Agendar Fechamento aberto")
        except Exception as ex:
            _show_snack(page, f"Erro ao abrir diálogo: {ex}", color=ft.Colors.RED)
            print(f"[ERRO] abrir_dialog_agendamento: {ex}")

    def atualizar_widget_agendamento():
        """Atualiza o widget de status de agendamento"""
        try:
            # Chama update_status do widget para atualizar o conteúdo
            if hasattr(schedule_status_widget_inner, "update_status"):
                schedule_status_widget_inner.update_status()

            # Atualizar a notificação de fechamento instantaneamente
            atualizar_notificacao_fechamento()
        except Exception as ex:
            print(f"[ERRO] atualizar_widget_agendamento: {ex}")

    def abrir_dialog_override(e=None):
        """Abre diálogo para pausar/retomar/cancelar agendamento"""
        print("[DEBUG] Clicado em Controle")
        try:
            # Buscar próximo agendamento ativo (independente da data)
            schedule = pdv_core.get_proxima_fechamento_programado()

            if not schedule or schedule.get("status") == "Cancelado":
                print("[DEBUG] Nenhum agendamento ativo")

                # Mostrar diálogo usando o método correto do Flet
                def fechar_dialogo(e):
                    dlg.open = False
                    page.update()

                dlg = ft.AlertDialog(
                    title=ft.Text("ℹ️ Nenhum Agendamento Ativo"),
                    content=ft.Column(
                        [
                            ft.Text(
                                "Não há fechamento automático programado no momento.",
                                size=13,
                            ),
                            ft.Container(height=10),
                            ft.Text(
                                "Para agendar um fechamento automático, use o botão 'Agendar Fechamento'.",
                                size=12,
                                italic=True,
                            ),
                        ],
                        tight=True,
                    ),
                    actions=[
                        ft.TextButton(
                            "OK",
                            on_click=fechar_dialogo,
                        ),
                    ],
                    modal=True,
                )
                page.dialog = dlg
                dlg.open = True
                page.update()
                print("[OK] Diálogo exibido")
                return

            create_schedule_override_dialog(
                page,
                pdv_core,
                schedule.get("id"),
                on_complete=atualizar_widget_agendamento,
            )
            # O overlay já é adicionado e exibido pela função create_schedule_override_dialog
            print("[OK] Diálogo Controle aberto")
        except Exception as ex:
            _show_snack(page, f"Erro ao abrir diálogo: {ex}", color=ft.Colors.RED)
            print(f"[ERRO] abrir_dialog_override: {ex}")  # Card do Caixa

    # Referências para atualizar status do caixa instantaneamente
    caixa_status_ref = ft.Ref[ft.Text]()
    caixa_saldo_ref = ft.Ref[ft.Text]()
    caixa_color_ref = ft.Ref[str]()

    user_id = page.session.get("user_id") or 1
    sess = pdv_core.get_current_open_session(user_id)
    caixa_status = "ABERTO" if sess else "FECHADO"
    caixa_color = ft.Colors.GREEN if sess else ft.Colors.RED
    saldo = sess.opening_balance if sess else 0.0
    caixa_color_ref.current = caixa_color

    # Função para atualizar status do caixa instantaneamente
    def atualizar_status_caixa():
        """Atualiza o status e saldo do caixa em tempo real"""
        try:
            sess = pdv_core.get_current_open_session(user_id)
            novo_status = "ABERTO" if sess else "FECHADO"
            nova_cor = ft.Colors.GREEN if sess else ft.Colors.RED
            novo_saldo = sess.opening_balance if sess else 0.0

            if caixa_status_ref.current:
                caixa_status_ref.current.value = f"Status: {novo_status}"
                caixa_status_ref.current.color = nova_cor

            if caixa_saldo_ref.current:
                caixa_saldo_ref.current.value = f"Saldo: R$ {novo_saldo:,.2f}"

            caixa_color_ref.current = nova_cor
            page.update()
        except Exception as ex:
            print(f"[ERRO] atualizar_status_caixa: {ex}")

    caixa_card = ft.Card(
        ft.Container(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.LOCK, size=24),
                            ft.Text("Controle Caixa", size=18, weight="bold"),
                        ]
                    ),
                    ft.Divider(height=5),
                    ft.Text(
                        f"Status: {caixa_status}",
                        ref=caixa_status_ref,
                        color=caixa_color,
                        size=14,
                        weight="bold",
                    ),
                    ft.Text(
                        f"Saldo: R$ {saldo:,.2f}",
                        ref=caixa_saldo_ref,
                        size=14,
                    ),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "Abrir (F1)",
                                bgcolor=ft.Colors.GREEN,
                                on_click=lambda e: (
                                    print("[DEBUG] Clicado em Abrir Caixa"),
                                    open_new_caixa_dialog(page, pdv_core, user_id),
                                ),
                            ),
                            ft.ElevatedButton(
                                "Fechar (F2)",
                                bgcolor=ft.Colors.RED,
                                on_click=lambda e: (
                                    print("[DEBUG] Clicado em Fechar Caixa"),
                                    (
                                        close_and_audit_caixa_dialog(
                                            page,
                                            pdv_core,
                                            pdv_core.get_current_open_session(user_id),
                                        )
                                        if pdv_core.get_current_open_session(user_id)
                                        else print("[DEBUG] Sem sessão aberta")
                                    ),
                                ),
                            ),
                            ft.ElevatedButton(
                                "📅 Agendar Fechamento",
                                icon=ft.Icons.SCHEDULE,
                                bgcolor=ft.Colors.BLUE_700,
                                color=ft.Colors.WHITE,
                                on_click=lambda e: abrir_dialog_agendamento(),
                                tooltip="Agendar fechamento/reabertura automática (apenas gerente)",
                            ),
                            ft.ElevatedButton(
                                "⚙️ Controle",
                                icon=ft.Icons.TUNE,
                                bgcolor=ft.Colors.BLUE_700,
                                color=ft.Colors.WHITE,
                                on_click=lambda e: abrir_dialog_override(),
                                tooltip="Pausar/retomar/cancelar agendamento (apenas gerente)",
                            ),
                        ],
                        wrap=True,
                        spacing=5,
                    ),
                ],
                spacing=5,
                expand=True,
            ),
            padding=10,
            bgcolor=ft.Colors.BLUE_50,
            expand=True,
        ),
        elevation=5,
    )

    # Widget de status de agendamento (não usado no novo layout)
    schedule_status_widget_inner = create_schedule_status_widget(page, pdv_core)
    # schedule_status_widget = ft.Card(
    #     ft.Container(
    #         schedule_status_widget_inner,
    #         padding=12,
    #     ),
    #     elevation=3,
    # )

    # KPIs - Cards da Visão Geral (criados dinamicamente)
    dashboard_row = create_kpi_cards_row()

    # Botões para trocar visualização - TABS SEM CONTEÚDO
    def on_tab_change(e):
        selected_tab = e.control.selected_index
        is_receber = selected_tab == 1  # Tab 0 = Pagar, Tab 1 = Receber
        # Resetar filtro ao trocar de aba
        current_status_filter.current = "Todos"
        if status_filter_ref.current:
            status_filter_ref.current.value = "Todos"
        refresh_table(is_receber=is_receber)

    view_buttons = ft.Tabs(
        selected_index=0,
        on_change=on_tab_change,
        tabs=[
            ft.Tab(
                text="Contas a Pagar",
                icon=ft.Icons.ACCOUNT_BALANCE,
            ),
            ft.Tab(
                text="Contas a Receber",
                icon=ft.Icons.TRENDING_UP,
            ),
        ],
    )

    # Dropdown de filtro por status
    def on_status_filter_change(e):
        """Handler para mudança do filtro de status"""
        selected_status = e.control.value
        refresh_table(status_filter=selected_status)

    # Referências para os DatePickers de filtro
    data_inicio_ref = ft.Ref[ft.DatePicker]()
    data_fim_ref = ft.Ref[ft.DatePicker]()
    data_inicio_text_ref = ft.Ref[ft.TextField]()
    data_fim_text_ref = ft.Ref[ft.TextField]()

    def on_date_inicio_change(e):
        """Callback quando a data de início muda"""
        if data_inicio_ref.current and data_inicio_ref.current.value:
            data_inicio_text_ref.current.value = data_inicio_ref.current.value
            page.update()

    def on_date_fim_change(e):
        """Callback quando a data de fim muda"""
        if data_fim_ref.current and data_fim_ref.current.value:
            data_fim_text_ref.current.value = data_fim_ref.current.value
            page.update()

    # DatePickers - Criar sob demanda quando botões são clicados
    date_picker_inicio_ref = None
    date_picker_fim_ref = None

    def abrir_date_picker_inicio():
        """Abre o seletor de data de início"""
        nonlocal date_picker_inicio_ref
        if date_picker_inicio_ref is None:
            date_picker_inicio_ref = ft.DatePicker(
                ref=data_inicio_ref,
                on_change=on_date_inicio_change,
                help_text="Selecione a data de início",
                cancel_text="Cancelar",
                confirm_text="Confirmar",
            )
            page.overlay.append(date_picker_inicio_ref)
            page.update()

        page.open(date_picker_inicio_ref)

    def abrir_date_picker_fim():
        """Abre o seletor de data de fim"""
        nonlocal date_picker_fim_ref
        if date_picker_fim_ref is None:
            date_picker_fim_ref = ft.DatePicker(
                ref=data_fim_ref,
                on_change=on_date_fim_change,
                help_text="Selecione a data de fim",
                cancel_text="Cancelar",
                confirm_text="Confirmar",
            )
            page.overlay.append(date_picker_fim_ref)
            page.update()

        page.open(date_picker_fim_ref)

    # TextFields para exibir as datas (sem on_focus para evitar loop)
    data_inicio_field = ft.TextField(
        ref=data_inicio_text_ref,
        label="Data Início",
        read_only=True,
        width=120,
    )

    data_fim_field = ft.TextField(
        ref=data_fim_text_ref,
        label="Data Fim",
        read_only=True,
        width=120,
    )

    # Buttons para abrir os calendários
    btn_data_inicio = ft.IconButton(
        ft.Icons.CALENDAR_TODAY,
        on_click=lambda e: abrir_date_picker_inicio(),
        tooltip="Selecionar data de início",
    )

    btn_data_fim = ft.IconButton(
        ft.Icons.CALENDAR_TODAY,
        on_click=lambda e: abrir_date_picker_fim(),
        tooltip="Selecionar data de fim",
    )

    def on_buscar_data(e):
        """Handler para buscar por período de datas"""
        print("[DEBUG] Clicado em Buscar Data")
        data_inicio = data_inicio_ref.current.value if data_inicio_ref.current else None
        data_fim = data_fim_ref.current.value if data_fim_ref.current else None

        if not data_inicio or not data_fim:
            print("[DEBUG] Datas não selecionadas")
            _show_snack(
                page, "Selecione as datas de início e fim", color=ft.Colors.ORANGE
            )
            return

        print(f"[DEBUG] Buscando dados entre {data_inicio} e {data_fim}")
        # Buscar dados tanto de receitas quanto de despesas e armazenar em cache
        try:
            receitas = (
                pdv_core.get_receivables_by_date_range(
                    current_status_filter.current, data_inicio, data_fim
                )
                or []
            )
        except Exception:
            receitas = []
        try:
            despesas = (
                pdv_core.get_expenses_by_date_range(
                    current_status_filter.current, data_inicio, data_fim
                )
                or []
            )
        except Exception:
            despesas = []

        # Salvar resultado da busca para reuso ao alternar entre views
        try:
            page.app_data["financeiro_last_search"] = {
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "status_filter": current_status_filter.current,
                "receitas": receitas,
                "despesas": despesas,
            }
        except Exception:
            pass

        # Atualizar a tabela visível conforme a aba atual
        try:
            if is_showing_receber.current:
                table = create_finance_table(
                    page, receitas, is_receber=True, pdv_core=pdv_core
                )
            else:
                table = create_finance_table(
                    page, despesas, is_receber=False, pdv_core=pdv_core
                )

            if tab_pagar_ref.current:
                tab_pagar_ref.current.content = table
        except Exception as ex:
            print(f"[ERRO] on_buscar_data atualizar tabela: {ex}")

        tem_dados = len(receitas) + len(despesas) > 0

        # Mostrar snackbar apropriado
        if tem_dados:
            _show_snack(
                page,
                f"Filtro aplicado: {data_inicio} até {data_fim}",
                color=ft.Colors.GREEN,
            )
        else:
            _show_snack(
                page,
                f"Nenhum registro encontrado entre {data_inicio} e {data_fim}",
                color=ft.Colors.ORANGE,
            )

    btn_buscar = ft.ElevatedButton(
        "Buscar",
        icon=ft.Icons.SEARCH,
        on_click=on_buscar_data,
        bgcolor=ft.Colors.BLUE,
        color=ft.Colors.WHITE,
    )

    status_filter_dropdown = ft.Dropdown(
        ref=status_filter_ref,
        width=200,
        options=[
            ft.dropdown.Option("Todos", text="Todos"),
            ft.dropdown.Option("Pago", text="Pago"),
            ft.dropdown.Option("Pendente", text="Pendente"),
            ft.dropdown.Option("Atrasado", text="Atrasado"),
            ft.dropdown.Option("Recebido", text="Recebido"),
        ],
        value="Todos",
        on_change=on_status_filter_change,
        label="Filtrar por Status",
    )

    # Tabela inicial (container que será atualizado)
    pagar_data = pdv_core.get_pending_expenses() or []
    pagar_table = create_finance_table(
        page, pagar_data, is_receber=False, pdv_core=pdv_core
    )

    table_container = ft.Container(
        ref=tab_pagar_ref,
        content=pagar_table,
        expand=True,
        bgcolor=ft.Colors.WHITE,
        padding=0,
    )

    # Botões de ação
    def on_export_csv(e):
        """Handler para exportar CSV"""
        print(
            f"[HANDLER] Clicado em CSV - is_showing_receber={is_showing_receber.current}"
        )
        try:
            export_finance_csv(page, pdv_core, is_showing_receber.current, e)
        except Exception as ex:
            print(f"[HANDLER ERROR] CSV: {ex}")
            import traceback

            traceback.print_exc()

    def on_export_pdf(e):
        """Handler para exportar PDF"""
        print(
            f"[HANDLER] Clicado em PDF - is_showing_receber={is_showing_receber.current}"
        )
        try:
            export_finance_pdf(page, pdv_core, is_showing_receber.current, e)
        except Exception as ex:
            print(f"[HANDLER ERROR] PDF: {ex}")
            import traceback

            traceback.print_exc()

    action_buttons = ft.Row(
        [
            ft.ElevatedButton(
                "Nova Despesa",
                icon=ft.Icons.ADD,
                bgcolor=ft.Colors.RED,
                color=ft.Colors.WHITE,
                on_click=on_nova_despesa,
            ),
            ft.ElevatedButton(
                "Nova Receita",
                icon=ft.Icons.ADD,
                bgcolor=ft.Colors.GREEN,
                color=ft.Colors.WHITE,
                on_click=on_nova_receita,
            ),
            ft.ElevatedButton(
                "CSV",
                icon=ft.Icons.FILE_DOWNLOAD,
                bgcolor=ft.Colors.BLUE,
                color=ft.Colors.WHITE,
                tooltip="Exportar Contas em CSV",
                on_click=on_export_csv,
            ),
            ft.ElevatedButton(
                "PDF",
                icon=ft.Icons.PICTURE_AS_PDF,
                bgcolor=ft.Colors.RED,
                color=ft.Colors.WHITE,
                tooltip="Exportar Contas em PDF",
                on_click=on_export_pdf,
            ),
        ],
        spacing=8,
    )

    # Content - com Tabs e tabela separada

    # Referência para a notificação de fechamento (permite atualizar instantaneamente)
    closing_notification_ref = ft.Ref[ft.Container]()

    # Criar notificação de status de fechamento
    def create_closing_status_notification():
        """Cria notificação mostrando se há fechamento ativo/programado"""
        try:
            # Verificar se há fechamento programado e ativo (não cancelado)
            schedule = pdv_core.get_proxima_fechamento_programado()

            # Verificar se existe agendamento E se o status não é "Cancelado"
            if schedule and schedule.get("status") != "Cancelado":
                # Há fechamento ativo/programado
                status_text = "📅 FECHAMENTO ATIVO"
                status_color = ft.Colors.ORANGE_100
                text_color = ft.Colors.ORANGE_900
                icon = ft.Icons.SCHEDULE
                desc = "Fechamento programado"
            else:
                # Sem fechamento programado
                status_text = "✅ SEM FECHAMENTO"
                status_color = ft.Colors.GREEN_100
                text_color = ft.Colors.GREEN_900
                icon = ft.Icons.CHECK_CIRCLE
                desc = "Sistema operacional normal"

            notification_content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, color=text_color, size=32),
                            ft.Column(
                                [
                                    ft.Text(
                                        status_text,
                                        size=14,
                                        weight="bold",
                                        color=text_color,
                                    ),
                                    ft.Text(
                                        desc,
                                        size=12,
                                        color=text_color,
                                    ),
                                ],
                                spacing=2,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=15,
                    ),
                ],
                spacing=10,
            )

            return {
                "content": notification_content,
                "bgcolor": status_color,
                "padding": 20,
                "status": "ATIVO" if schedule else "SEM_FECHAMENTO",
            }
        except Exception as ex:
            print(f"[ERRO] create_closing_status_notification: {ex}")
            return {
                "content": ft.Text(
                    "Erro ao carregar status", size=12, color=ft.Colors.RED
                ),
                "bgcolor": ft.Colors.RED_100,
                "padding": 10,
                "status": "ERRO",
            }

    # Criar o Container da notificação uma única vez
    notification_data = create_closing_status_notification()
    closing_notification_container = ft.Container(
        ref=closing_notification_ref,
        content=notification_data["content"],
        padding=notification_data["padding"],
        bgcolor=notification_data["bgcolor"],
        border_radius=8,
        expand=False,
        width=320,
        height=120,
    )

    # Função para atualizar a notificação instantaneamente
    def atualizar_notificacao_fechamento():
        """Atualiza a notificação de fechamento em tempo real"""
        try:
            print(
                f"[DEBUG] atualizar_notificacao_fechamento chamado, ref.current={closing_notification_ref.current}"
            )
            if closing_notification_ref.current:
                nova_notificacao = create_closing_status_notification()
                # Atualizar o Container com os novos valores
                closing_notification_ref.current.content = nova_notificacao["content"]
                closing_notification_ref.current.bgcolor = nova_notificacao["bgcolor"]
                closing_notification_ref.current.padding = nova_notificacao["padding"]
                print("[OK] Notificação de fechamento atualizada")
                page.update()
            else:
                print("[AVISO] closing_notification_ref.current está None")
        except Exception as ex:
            print(f"[ERRO] atualizar_notificacao_fechamento: {ex}")
            import traceback

            traceback.print_exc()

    # Tabela de histórico de fechamentos
    history_table = create_caixa_history_table(page, pdv_core)
    history_column = ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    "📊 Histórico de Fechamento e Abertura",
                    size=18,
                    weight="bold",
                    color=ft.Colors.BLUE_700,
                ),
                ft.Divider(height=10, color=ft.Colors.BLACK12),
                ft.Row(
                    [
                        ft.Container(history_table, expand=True),
                        closing_notification_container,
                    ],
                    spacing=15,
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ],
            spacing=5,
            expand=True,
        ),
        padding=15,
        bgcolor=ft.Colors.GREY_100,
        border_radius=8,
        expand=True,
    )

    # Row com Controle de Caixa expandindo para ocupar espaço disponível
    # (removido - agora usa caixa_card diretamente)

    content = ft.Column(
        [
            # Header com Controle de Caixa (expandido para toda a largura)
            ft.Container(
                caixa_card,
                padding=20,
                bgcolor=ft.Colors.WHITE,
                border_radius=0,
            ),
            # Dashboard Cards
            ft.Container(
                dashboard_row,
                padding=20,
                bgcolor=ft.Colors.BLUE_50,
            ),
            # Abas e Filtros em um Card unificado
            ft.Container(
                ft.Card(
                    ft.Container(
                        ft.Column(
                            [
                                view_buttons,
                                ft.Divider(height=15),
                                ft.Row(
                                    [
                                        status_filter_dropdown,
                                        ft.Row(
                                            [data_inicio_field, btn_data_inicio],
                                            spacing=0,
                                        ),
                                        ft.Row(
                                            [data_fim_field, btn_data_fim], spacing=0
                                        ),
                                        btn_buscar,
                                        ft.Container(expand=True),
                                    ],
                                    spacing=10,
                                    alignment=ft.MainAxisAlignment.START,
                                ),
                                ft.Divider(height=15),
                                action_buttons,
                            ],
                            spacing=10,
                        ),
                        padding=15,
                    ),
                    elevation=3,
                ),
                padding=15,
                bgcolor=ft.Colors.WHITE,
            ),
            # Tabelas em Grid Responsivo
            ft.Container(
                ft.ResponsiveRow(
                    [
                        ft.Column(
                            col={"sm": 12, "md": 5},
                            controls=[
                                ft.Card(
                                    ft.Container(
                                        table_container,
                                        expand=True,
                                        padding=0,
                                    ),
                                    elevation=2,
                                ),
                            ],
                        ),
                        ft.Column(
                            col={"sm": 12, "md": 7},
                            controls=[
                                history_column,
                            ],
                        ),
                    ],
                    spacing=15,
                    expand=True,
                ),
                padding=15,
                bgcolor=ft.Colors.BLUE_50,
                expand=True,
            ),
        ],
        scroll=ft.ScrollMode.ADAPTIVE,
        expand=True,
        spacing=0,
    )

    # AppBar
    appbar = ft.AppBar(
        title=ft.Text("Financeiro", size=24, weight="bold", color=ft.Colors.WHITE),
        center_title=True,
        bgcolor=COLORS["primary"],
    )
    if handle_back:

        def _local_financeiro_back(e):
            try:
                # Fecha overlays adicionados via page.overlay (dialogs customizados)
                try:
                    closed_any = False
                    overlays = list(getattr(page, "overlay", []) or [])
                    for ov in overlays:
                        try:
                            if getattr(ov, "visible", False):
                                # heurística: modais costumam usar semi-transparência
                                bgcolor = getattr(ov, "bgcolor", "") or ""
                                if (
                                    isinstance(bgcolor, str)
                                    and "rgba(0, 0, 0" in bgcolor
                                ):
                                    ov.visible = False
                                    closed_any = True
                        except Exception:
                            pass
                    if closed_any:
                        page.update()
                        try:
                            e.handled = True
                        except Exception:
                            pass
                        return
                except Exception:
                    pass

                # Fecha qualquer AlertDialog padrão (page.dialog)
                try:
                    if getattr(page, "dialog", None) is not None and getattr(
                        page.dialog, "open", False
                    ):
                        page.dialog.open = False
                        page.update()
                        try:
                            e.handled = True
                        except Exception:
                            pass
                        return
                except Exception:
                    pass

                # Se nada fechado, delega para o callback original
                try:
                    handle_back(e)
                except Exception:
                    try:
                        handle_back(None)
                    except Exception:
                        pass
            except Exception:
                pass

        appbar.leading = ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            on_click=_local_financeiro_back,
            icon_color=ft.Colors.WHITE,
        )

    # Expor função para atualizar tabelas (chamada pelos dialogs)
    page.atualizar_finance_tables = refresh_table

    # Expor função para atualizar cards (chamada pelos dialogs)
    page.atualizar_dashboard_cards = update_dashboard_cards

    # Expor função para atualizar status do caixa (chamada pelos dialogs)
    page.atualizar_caixa_control = atualizar_status_caixa

    # Atualizar cards na inicialização
    update_dashboard_cards()

    view = ft.View(route="/financeiro", controls=[appbar, content], padding=0)
    try:

        def _financeiro_on_key(e):
            try:
                key = (str(e.key) or "").upper()
                if key in ("ESCAPE", "ESC"):
                    page.go("/gerente")
            except Exception:
                pass

        view.on_keyboard_event = _financeiro_on_key
    except Exception:
        pass

    return view
