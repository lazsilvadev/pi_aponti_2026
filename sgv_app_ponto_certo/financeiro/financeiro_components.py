from datetime import datetime

import flet as ft

from .financeiro_utils import format_currency


def create_kpi_card(title, value, icon, color):
    return ft.Card(
        ft.Container(
            padding=20,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(title, size=16, weight=ft.FontWeight.W_500),
                            ft.Icon(icon, color=color, size=30),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(
                        format_currency(value),
                        size=32,
                        weight=ft.FontWeight.BOLD,
                        color=color,
                    ),
                ],
                spacing=10,
            ),
        ),
        elevation=5,
    )


def create_caixa_control_card(page: ft.Page, pdv_core):
    user_id = page.session.get("user_id")
    if user_id is None:
        user_id = 1
    current_open_session = pdv_core.get_current_open_session(user_id)

    status_text = ft.Text(
        "CAIXA ABERTO" if current_open_session else "CAIXA FECHADO",
        color=ft.Colors.GREEN if current_open_session else ft.Colors.RED,
        weight=ft.FontWeight.BOLD,
        size=18,
    )
    saldo_valor = current_open_session.opening_balance if current_open_session else 0.0
    return ft.Card(
        ft.Container(
            padding=20,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                (
                                    ft.Icons.LOCK_OPEN_ROUNDED
                                    if current_open_session
                                    else ft.Icons.LOCK_OUTLINED
                                ),
                                size=28,
                            ),
                            ft.Text(
                                "Controle Operacional de Caixa",
                                size=20,
                                weight=ft.FontWeight.W_600,
                            ),
                        ]
                    ),
                    ft.Divider(height=10),
                    status_text,
                    ft.Text(
                        f"Saldo Inicial: {format_currency(saldo_valor)}",
                        size=22,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BLUE,
                    ),
                ],
                spacing=10,
            ),
        ),
        elevation=5,
    )


def create_finance_table(page: ft.Page, data, is_receber=False, pdv_core=None):
    """Cria tabela de finanças usando Column com Rows ao invés de DataTable."""
    if data is None:
        data = []

    # Cabeçalho
    header = ft.Container(
        ft.Row(
            [
                ft.Text("Vencimento", size=13, weight="bold", width=80),
                ft.Text("Descrição", size=13, weight="bold", expand=True),
                ft.Text(
                    "Categoria" if not is_receber else "Origem",
                    size=13,
                    weight="bold",
                    width=90,
                ),
                ft.Text("Valor", size=13, weight="bold", width=80, text_align="right"),
                ft.Text("Status", size=13, weight="bold", width=70),
                ft.Text("Ações", size=13, weight="bold", width=80),
            ],
            spacing=5,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.BLUE_50,
        padding=ft.padding.symmetric(horizontal=10, vertical=8),
        border=ft.border.all(1, ft.Colors.BLACK12),
    )

    # Linhas de dados
    rows = [header]
    for item in data:
        item_id = getattr(item, "id", 0)
        vencimento = getattr(item, "vencimento", "-")
        descricao = getattr(item, "descricao", "N/A")
        categoria = getattr(item, "categoria", getattr(item, "origem", "N/A"))
        valor = getattr(item, "valor", 0.0)
        status = getattr(item, "status", "Pendente")

        # Verificar se está atrasado
        is_atrasado = False
        try:
            if isinstance(vencimento, str):
                venc_date = datetime.strptime(vencimento, "%d/%m/%Y").date()
            else:
                venc_date = vencimento if hasattr(vencimento, "date") else vencimento

            is_atrasado = venc_date < datetime.now().date() and status in [
                "Pendente",
                "Pago",
                "Recebido",
            ]
        except Exception:
            pass

        # Status color - destacar com vermelho se atrasado
        if is_atrasado and status not in ["Pago", "Recebido"]:
            status_color = ft.Colors.RED_50
            status_text_color = ft.Colors.RED_700
            row_bgcolor = ft.Colors.RED_50
        else:
            status_color = (
                ft.Colors.GREEN_50
                if status in ["Pago", "Recebido"]
                else ft.Colors.ORANGE_50
            )
            status_text_color = (
                ft.Colors.GREEN_700
                if status in ["Pago", "Recebido"]
                else ft.Colors.ORANGE_700
            )
            row_bgcolor = ft.Colors.WHITE

        # Botão de ação - Marcar como Pago / Desmarcar
        def make_toggle_handler(item_id, is_receber, core, current_status):
            def toggle_status(e):
                try:
                    tipo = "Receita" if is_receber else "Despesa"
                    if is_receber:
                        if current_status in ["Recebido"]:
                            core.mark_receivable_as_unpaid(item_id)
                            status_novo = "Pendente"
                        else:
                            core.mark_receivable_as_paid(item_id)
                            status_novo = "Recebido"
                    else:
                        if current_status in ["Pago"]:
                            core.mark_expense_as_unpaid(item_id)
                            status_novo = "Pendente"
                        else:
                            core.mark_expense_as_paid(item_id)
                            status_novo = "Pago"

                    print(f"[OK] {tipo} ID={item_id} alterado para {status_novo}")
                    # Atualizar cards se houver callback disponível
                    if hasattr(page, "atualizar_dashboard_cards") and callable(
                        page.atualizar_dashboard_cards
                    ):
                        try:
                            page.atualizar_dashboard_cards()
                        except Exception as ex:
                            print(f"[ERRO] atualizar_dashboard_cards: {ex}")
                    # Atualizar tabela se houver callback disponível
                    if hasattr(page, "atualizar_finance_tables") and callable(
                        page.atualizar_finance_tables
                    ):
                        try:
                            page.atualizar_finance_tables()
                        except Exception:
                            pass
                    # Atualizar badge de alertas (contas alteradas)
                    try:
                        from alertas.alertas_init import (
                            atualizar_badge_alertas_no_gerente,
                        )

                        pdv_core_ref = page.app_data.get("pdv_core")
                        if pdv_core_ref:
                            try:
                                atualizar_badge_alertas_no_gerente(page, pdv_core_ref)
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception as ex:
                    print(f"[ERRO] Ao alternar status: {ex}")

            return toggle_status

        # Botão de ação - Excluir
        def make_delete_handler(item_id, is_receber, core):
            def delete_item(e):
                try:
                    if is_receber:
                        core.delete_receivable(item_id)
                        tipo = "Receita"
                    else:
                        core.delete_expense(item_id)
                        tipo = "Despesa"

                    print(f"[OK] {tipo} ID={item_id} excluída")
                    # Atualizar cards se houver callback disponível
                    if hasattr(page, "atualizar_dashboard_cards") and callable(
                        page.atualizar_dashboard_cards
                    ):
                        try:
                            page.atualizar_dashboard_cards()
                        except Exception:
                            pass
                    # Atualizar tabela se houver callback disponível
                    if hasattr(page, "atualizar_finance_tables") and callable(
                        page.atualizar_finance_tables
                    ):
                        try:
                            page.atualizar_finance_tables()
                        except Exception:
                            pass
                    # Atualizar badge de alertas (conta excluída)
                    try:
                        from alertas.alertas_init import (
                            atualizar_badge_alertas_no_gerente,
                        )

                        pdv_core_ref = page.app_data.get("pdv_core")
                        if pdv_core_ref:
                            try:
                                atualizar_badge_alertas_no_gerente(page, pdv_core_ref)
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception as ex:
                    print(f"[ERRO] Ao excluir: {ex}")

            return delete_item

        # Buttons de ação
        mark_btn = ft.IconButton(
            icon=(
                ft.Icons.CHECK_CIRCLE
                if status not in ["Pago", "Recebido"]
                else ft.Icons.CANCEL
            ),
            icon_color=(
                ft.Colors.GREEN if status not in ["Pago", "Recebido"] else ft.Colors.RED
            ),
            tooltip=(
                "Marcar como " + ("Recebido" if is_receber else "Pago")
                if status not in ["Pago", "Recebido"]
                else "Desmarcar como " + ("Recebido" if is_receber else "Pago")
            ),
            on_click=make_toggle_handler(item_id, is_receber, pdv_core, status),
            width=30,
        )

        delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE,
            icon_color=ft.Colors.RED,
            tooltip="Excluir",
            on_click=make_delete_handler(item_id, is_receber, pdv_core),
            width=30,
        )

        action_row = ft.Row(
            [mark_btn, delete_btn],
            spacing=0,
            width=80,
        )

        row = ft.Container(
            ft.Row(
                [
                    ft.Text(str(vencimento), size=12, width=80),
                    ft.Text(
                        str(descricao),
                        size=13,
                        expand=True,
                        max_lines=1,
                        overflow="ellipsis",
                    ),
                    ft.Text(str(categoria), size=12, width=90),
                    ft.Text(
                        format_currency(valor), size=12, width=80, text_align="right"
                    ),
                    ft.Container(
                        ft.Text(
                            status, size=11, color=status_text_color, weight="w500"
                        ),
                        padding=ft.padding.symmetric(horizontal=6, vertical=3),
                        bgcolor=status_color,
                        border_radius=3,
                        width=70,
                    ),
                    action_row,
                ],
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=10, vertical=6),
            border=ft.border.all(
                width=2 if is_atrasado else 1,
                color=ft.Colors.RED if is_atrasado else ft.Colors.BLACK12,
            ),
            bgcolor=row_bgcolor,
        )
        rows.append(row)

    # Se não há dados
    if len(rows) == 1:
        rows.append(
            ft.Container(
                ft.Column(
                    [
                        ft.Text(
                            "Nenhuma conta cadastrada ainda.",
                            size=14,
                            weight="bold",
                            color=ft.Colors.GREY_700,
                        ),
                        ft.Text(
                            "➜ Clique em Nova despesa ou Nova receita para começar.",
                            size=12,
                            color=ft.Colors.GREY_600,
                        ),
                    ],
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=30,
                alignment=ft.alignment.center,
                bgcolor=ft.Colors.WHITE,
                border=ft.border.all(0.5, ft.Colors.BLACK12),
            )
        )

    return ft.Column(
        rows,
        spacing=0,
        scroll=ft.ScrollMode.ADAPTIVE,
    )
