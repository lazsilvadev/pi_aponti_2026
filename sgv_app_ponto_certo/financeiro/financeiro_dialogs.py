import time
from datetime import datetime

import flet as ft

from .financeiro_utils import (
    _close_dialog,
    _show_snack,
    format_currency,
    parse_currency,
    refresh_view,
)


def open_new_caixa_dialog(page: ft.Page, pdv_core, user_id: int):
    balance_field = ft.TextField(
        label="Saldo Inicial (R$)",
        value="0,00",
        prefix="R$ ",
        autofocus=True,
        text_size=12,
    )

    def confirm(e):
        try:
            balance = parse_currency(balance_field.value)
            pdv_core.open_new_caixa(user_id, balance)
            fechar_overlay()
            _show_snack(page, "✅ Caixa aberto!", ft.Colors.GREEN)
            # Atualizar status do caixa na tela Financeiro
            page.update()
            time.sleep(0.2)  # Pequeno delay para garantir que a UI seja processada
            if hasattr(page, "atualizar_caixa_control"):
                try:
                    page.atualizar_caixa_control()
                except Exception as ex:
                    print(f"[ERRO] ao atualizar caixa: {ex}")
        except Exception as ex:
            _show_snack(page, f"❌ Erro: {str(ex)[:50]}", ft.Colors.RED)

    def fechar_overlay():
        overlay.visible = False
        page.update()

    # Criar conteúdo do diálogo
    content = ft.Container(
        content=ft.Column(
            [
                ft.Text("Abrir Novo Caixa", size=18, weight=ft.FontWeight.BOLD),
                balance_field,
                ft.Row(
                    [
                        ft.TextButton("Cancelar", on_click=lambda e: fechar_overlay()),
                        ft.ElevatedButton(
                            "Confirmar",
                            bgcolor=ft.Colors.GREEN,
                            color=ft.Colors.WHITE,
                            on_click=confirm,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=12,
        ),
        padding=20,
        bgcolor="white",
        border_radius=10,
        shadow=ft.BoxShadow(spread_radius=2, blur_radius=5),
    )

    # Criar overlay
    overlay = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(content=content, width=380),
                        ft.Container(expand=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        visible=True,
        bgcolor="rgba(0, 0, 0, 0.5)",
        expand=True,
    )

    if overlay not in page.overlay:
        page.overlay.append(overlay)
    page.update()
    print("[OK] Diálogo Abrir Caixa aberto")


def close_and_audit_caixa_dialog(page: ft.Page, pdv_core, session):
    counted_field = ft.TextField(
        label="Valor Contado (R$)",
        value="0,00",
        prefix="R$ ",
        text_size=12,
    )

    def confirm(e):
        try:
            counted = parse_currency(counted_field.value)
            try:
                current_bal = session.current_balance
            except Exception:
                current_bal = session.opening_balance
            pdv_core.close_caixa_session(session.id, current_bal, counted)

            # 🔄 Fazer backup automático ao fechar caixa
            try:
                backup_manager = page.app_data.get("backup_manager")
                if backup_manager:
                    sucesso, mensagem = backup_manager.criar_backup()
                    if sucesso:
                        backup_manager.limpar_backups_antigos(dias=30)
                        print(f"[CAIXA-BACKUP] ✅ {mensagem}")
                    else:
                        print(f"[CAIXA-BACKUP] ⚠️  {mensagem}")
            except Exception as ex:
                print(f"[CAIXA-BACKUP] ❌ Erro ao fazer backup: {ex}")

            fechar_overlay()
            _show_snack(page, "✅ Caixa fechado!", ft.Colors.BLUE)
            # Atualizar status do caixa na tela Financeiro
            page.update()
            time.sleep(0.2)  # Pequeno delay para garantir que a UI seja processada
            if hasattr(page, "atualizar_caixa_control"):
                try:
                    page.atualizar_caixa_control()
                except Exception as ex:
                    print(f"[ERRO] ao atualizar caixa: {ex}")
        except Exception as ex:
            _show_snack(page, f"❌ Erro: {str(ex)[:50]}", ft.Colors.RED)

    def fechar_overlay():
        overlay.visible = False
        page.update()

    # Criar conteúdo do diálogo
    content = ft.Container(
        content=ft.Column(
            [
                ft.Text("Fechar Caixa e Auditar", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(
                    f"Esperado: {format_currency(getattr(session, 'current_balance', session.opening_balance))}",
                    size=11,
                ),
                counted_field,
                ft.Row(
                    [
                        ft.TextButton("Cancelar", on_click=lambda e: fechar_overlay()),
                        ft.ElevatedButton(
                            "Confirmar",
                            bgcolor=ft.Colors.RED,
                            color=ft.Colors.WHITE,
                            on_click=confirm,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=12,
        ),
        padding=20,
        bgcolor="white",
        border_radius=10,
        shadow=ft.BoxShadow(spread_radius=2, blur_radius=5),
    )

    # Criar overlay
    overlay = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(content=content, width=380),
                        ft.Container(expand=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        visible=True,
        bgcolor="rgba(0, 0, 0, 0.5)",
        expand=True,
    )

    if overlay not in page.overlay:
        page.overlay.append(overlay)
    page.update()
    print("[OK] Diálogo Fechar Caixa aberto")


def nova_despesa_dialog(page: ft.Page, pdv_core, e=None):
    print("[DEBUG] nova_despesa_dialog opened")
    descricao_field = ft.TextField(label="Descrição", autofocus=True, text_size=12)
    valor_field = ft.TextField(
        label="Valor (R$)",
        prefix="R$ ",
        keyboard_type=ft.KeyboardType.NUMBER,
        text_size=12,
    )
    vencimento_field = ft.TextField(
        label="Vencimento", value=datetime.now().strftime("%d/%m/%Y"), text_size=12
    )
    categoria_field = ft.Dropdown(
        label="Categoria",
        options=[
            ft.dropdown.Option("Operacional"),
            ft.dropdown.Option("Mercadorias"),
            ft.dropdown.Option("Funcionários"),
            ft.dropdown.Option("Outros"),
        ],
    )

    def confirm(e):
        if not descricao_field.value or not valor_field.value:
            _show_snack(page, "❌ Preencha todos os campos!", ft.Colors.RED)
            return
        try:
            valor = parse_currency(valor_field.value)
            # tenta converter vencimento para date
            from datetime import datetime as _dt

            venc = vencimento_field.value
            try:
                if isinstance(venc, str):
                    venc_dt = _dt.strptime(venc.strip(), "%d/%m/%Y").date()
                elif hasattr(venc, "date"):
                    venc_dt = venc.date()
                else:
                    venc_dt = venc
            except Exception:
                venc_dt = venc

            ok, msg = pdv_core.create_expense(
                descricao_field.value,
                valor,
                venc_dt,
                categoria_field.value,
            )
            fechar_overlay()
            _show_snack(
                page,
                msg if msg else ("✅ Despesa criada!"),
                ft.Colors.GREEN if ok else ft.Colors.RED,
            )

            # Atualizar badge de alertas (nova conta a pagar)
            try:
                from alertas.alertas_init import atualizar_badge_alertas_no_gerente

                pdv_core_ref = page.app_data.get("pdv_core")
                if pdv_core_ref:
                    atualizar_badge_alertas_no_gerente(page, pdv_core_ref)
            except Exception as ex:
                print(f"[ALERTAS] ⚠️  Erro ao atualizar badge: {ex}")

            # Atualiza as tabelas do financeiro se houver callback
            if hasattr(page, "atualizar_finance_tables") and callable(
                page.atualizar_finance_tables
            ):
                try:
                    page.atualizar_finance_tables(False)  # Atualiza tabela de Pagar
                except Exception as ex:
                    print(f"[ERRO] atualizar_finance_tables: {ex}")
            # Atualiza os cards se houver callback
            if hasattr(page, "atualizar_dashboard_cards") and callable(
                page.atualizar_dashboard_cards
            ):
                try:
                    page.atualizar_dashboard_cards()
                except Exception as ex:
                    print(f"[ERRO] atualizar_dashboard_cards: {ex}")
            try:
                page.update()
            except Exception:
                pass
        except Exception as ex:
            _show_snack(page, f"❌ Erro: {str(ex)[:50]}", ft.Colors.RED)

    def fechar_overlay():
        overlay.visible = False
        page.update()

    # Criar conteúdo do diálogo
    content = ft.Container(
        content=ft.Column(
            [
                ft.Text("Nova Despesa", size=18, weight=ft.FontWeight.BOLD),
                descricao_field,
                valor_field,
                vencimento_field,
                categoria_field,
                ft.Row(
                    [
                        ft.TextButton("Cancelar", on_click=lambda e: fechar_overlay()),
                        ft.ElevatedButton(
                            "Salvar",
                            bgcolor=ft.Colors.RED,
                            color=ft.Colors.WHITE,
                            on_click=confirm,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=12,
        ),
        padding=20,
        bgcolor="white",
        border_radius=10,
        shadow=ft.BoxShadow(spread_radius=2, blur_radius=5),
    )

    # Criar overlay
    overlay = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(content=content, width=420),
                        ft.Container(expand=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        visible=True,
        bgcolor="rgba(0, 0, 0, 0.5)",
        expand=True,
    )

    if overlay not in page.overlay:
        page.overlay.append(overlay)
    page.update()
    print("[OK] Diálogo Nova Despesa aberto")


def nova_receita_dialog(page: ft.Page, pdv_core, e=None):
    print("[DEBUG] nova_receita_dialog opened")
    descricao_field = ft.TextField(label="Descrição", autofocus=True, text_size=12)
    valor_field = ft.TextField(
        label="Valor (R$)",
        prefix="R$ ",
        keyboard_type=ft.KeyboardType.NUMBER,
        text_size=12,
    )
    vencimento_field = ft.TextField(
        label="Vencimento", value=datetime.now().strftime("%d/%m/%Y"), text_size=12
    )
    origem_field = ft.Dropdown(
        label="Origem",
        options=[
            ft.dropdown.Option("Vendas"),
            ft.dropdown.Option("Serviços"),
            ft.dropdown.Option("Outros"),
        ],
    )

    def confirm(e):
        if not descricao_field.value or not valor_field.value:
            _show_snack(page, "❌ Preencha todos os campos!", ft.Colors.RED)
            return
        try:
            valor = parse_currency(valor_field.value)
            from datetime import datetime as _dt

            venc = vencimento_field.value
            try:
                if isinstance(venc, str):
                    venc_dt = _dt.strptime(venc.strip(), "%d/%m/%Y").date()
                elif hasattr(venc, "date"):
                    venc_dt = venc.date()
                else:
                    venc_dt = venc
            except Exception:
                venc_dt = venc

            ok, msg = pdv_core.create_receivable(
                descricao_field.value, valor, venc_dt, origem_field.value
            )
            fechar_overlay()
            _show_snack(
                page,
                msg if msg else ("✅ Receita criada!"),
                ft.Colors.GREEN if ok else ft.Colors.RED,
            )
            # Atualiza as tabelas do financeiro se houver callback
            if hasattr(page, "atualizar_finance_tables") and callable(
                page.atualizar_finance_tables
            ):
                try:
                    print(
                        "[DEBUG] Chamando atualizar_finance_tables from nova_receita_dialog"
                    )
                    page.atualizar_finance_tables(True)  # Atualiza tabela de Receber
                except Exception as ex:
                    print(f"[ERRO] atualizar_finance_tables: {ex}")
            # Atualiza os cards se houver callback
            if hasattr(page, "atualizar_dashboard_cards") and callable(
                page.atualizar_dashboard_cards
            ):
                try:
                    page.atualizar_dashboard_cards()
                except Exception as ex:
                    print(f"[ERRO] atualizar_dashboard_cards: {ex}")
            try:
                page.update()
            except Exception:
                pass
        except Exception as ex:
            _show_snack(page, f"❌ Erro: {str(ex)[:50]}", ft.Colors.RED)

    def fechar_overlay():
        overlay.visible = False
        page.update()

    # Criar conteúdo do diálogo
    content = ft.Container(
        content=ft.Column(
            [
                ft.Text("Nova Receita", size=18, weight=ft.FontWeight.BOLD),
                descricao_field,
                valor_field,
                vencimento_field,
                origem_field,
                ft.Row(
                    [
                        ft.TextButton("Cancelar", on_click=lambda e: fechar_overlay()),
                        ft.ElevatedButton(
                            "Salvar",
                            bgcolor=ft.Colors.GREEN,
                            color=ft.Colors.WHITE,
                            on_click=confirm,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=12,
        ),
        padding=20,
        bgcolor="white",
        border_radius=10,
        shadow=ft.BoxShadow(spread_radius=2, blur_radius=5),
    )

    # Criar overlay
    overlay = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(content=content, width=420),
                        ft.Container(expand=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        visible=True,
        bgcolor="rgba(0, 0, 0, 0.5)",
        expand=True,
    )

    if overlay not in page.overlay:
        page.overlay.append(overlay)
    page.dialog = ft.AlertDialog(
        title=ft.Text("Nova Receita", size=15),
        content=ft.Column(
            [descricao_field, valor_field, vencimento_field, origem_field],
            tight=True,
            spacing=8,
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda e: _close_dialog(page)),
            ft.ElevatedButton(
                "Salvar",
                bgcolor=ft.Colors.GREEN,
                color=ft.Colors.WHITE,
                on_click=confirm,
            ),
        ],
    )
    print("[OK] Diálogo Nova Receita aberto")
    page.dialog.open = True
    page.update()
