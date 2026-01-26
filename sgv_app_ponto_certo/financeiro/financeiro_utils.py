import os
import traceback
import webbrowser
from datetime import datetime
from functools import partial

import flet as ft

from models.db_models import Expense, Receivable
from utils import export_utils


def format_currency(value):
    """Formata valor para moeda brasileira."""
    try:
        return (
            f"R$ {float(value):,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    except Exception:
        return str(value)


def _close_dialog(page: ft.Page):
    try:
        if hasattr(page, "close_dialog"):
            page.close_dialog()
        else:
            if getattr(page, "dialog", None):
                page.dialog.open = False
                page.update()
    except Exception:
        try:
            if getattr(page, "dialog", None):
                page.dialog.open = False
                page.update()
        except Exception:
            pass


def _show_snack(page: ft.Page, message: str, color=ft.Colors.BLUE):
    """Mostra um snack bar na tela."""
    page.snack_bar = ft.SnackBar(
        ft.Text(message, color=color), bgcolor=ft.Colors.WHITE, open=True
    )
    page.update()


def parse_currency(value_str):
    if not value_str or value_str.strip() == "":
        return 0.0
    try:
        cleaned = (
            value_str.replace("R$", "")
            .replace(" ", "")
            .replace(".", "")
            .replace(",", ".")
        )
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0


def view_transaction(page: ft.Page, item_id: int, is_receber: bool, e=None):
    print(f"👁️ Visualizando ID: {item_id}")
    _show_snack(page, f"📋 Detalhes ID: {item_id}", ft.Colors.BLUE)


def robust_handler(page: ft.Page, func, label: str = None):
    """Retorna uma função que envolve `func` com tratamento de exceção e feedback visual.

    `func` deve ser um callable que recebe um evento `e` (pode ser um `functools.partial`).
    """

    def _inner(e=None):
        try:
            control = getattr(e, "control", None) if e is not None else None
            # feedback visual imediato: borda temporária + snack
            orig_border = None
            orig_bg = None
            if control is not None:
                orig_border = getattr(control, "border", None)
                orig_bg = getattr(control, "bgcolor", None)
                try:
                    control.border = ft.border.all(2, ft.Colors.BLUE_700)
                except Exception:
                    pass
                try:
                    control.bgcolor = ft.Colors.BLUE_50
                except Exception:
                    pass
                try:
                    page.update()
                except Exception:
                    pass

            if label:
                print(f"[UI] {label} triggered")
                _show_snack(page, f"{label}...", ft.Colors.BLUE)

            # chama a função original
            try:
                func(e)
            except TypeError:
                # Algumas funções podem não aceitar o evento; chamamos sem argumentos
                func()
        except Exception as ex:
            tb = traceback.format_exc()
            print(tb)
            try:
                _show_snack(page, f"❌ Erro: {str(ex)[:100]}", ft.Colors.RED)
            except Exception:
                pass
        finally:
            # reverte estilo do controle
            try:
                if control is not None:
                    if orig_border is not None:
                        control.border = orig_border
                    else:
                        try:
                            delattr(control, "border")
                        except Exception:
                            pass
                    if orig_bg is not None:
                        control.bgcolor = orig_bg
                    else:
                        try:
                            delattr(control, "bgcolor")
                        except Exception:
                            pass
                    try:
                        page.update()
                    except Exception:
                        pass
            except Exception:
                pass

    return _inner


def mark_as_paid(page: ft.Page, pdv_core, item_id: int, is_receber: bool, e=None):
    try:
        print(f"mark_as_paid called: item_id={item_id}, is_receber={is_receber}")

        # Get the item to check its value
        if is_receber:
            item = pdv_core.session.query(Receivable).get(item_id)
        else:
            item = pdv_core.session.query(Expense).get(item_id)

        if not item:
            _show_snack(page, "❌ Item não encontrado!", ft.Colors.RED)
            return

        # Create dialog for payment type selection
        def confirm_full_payment(e):
            if is_receber:
                pdv_core.mark_receivable_as_paid(item_id)
            else:
                pdv_core.mark_expense_as_paid(item_id)
            _close_dialog(page)
            _show_snack(page, "✅ Pagamento total registrado!", ft.Colors.GREEN)
            # Atualizar badge de alertas (contas pagas/alteradas)
            try:
                from alertas.alertas_init import atualizar_badge_alertas_no_gerente

                pdv_core_ref = page.app_data.get("pdv_core") or pdv_core
                try:
                    atualizar_badge_alertas_no_gerente(page, pdv_core_ref)
                except Exception:
                    pass
            except Exception:
                pass
            _update_tables()

        def open_partial_payment(e):
            _close_dialog(page)
            # Show partial payment dialog
            show_partial_payment_dialog(page, pdv_core, item_id, is_receber, item.valor)

        page.dialog = ft.AlertDialog(
            title=ft.Text("Registrar Pagamento"),
            content=ft.Column(
                [
                    ft.Text(f"Descrição: {item.descricao}"),
                    ft.Text(
                        f"Valor Total: {format_currency(item.valor)}", weight="bold"
                    ),
                    ft.Divider(),
                    ft.Text("Qual tipo de pagamento?", size=14, weight="bold"),
                ],
                tight=True,
                spacing=10,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: _close_dialog(page)),
                ft.ElevatedButton(
                    "Pagamento Parcial",
                    bgcolor=ft.Colors.ORANGE,
                    color=ft.Colors.WHITE,
                    on_click=open_partial_payment,
                ),
                ft.ElevatedButton(
                    "Pagamento Total",
                    bgcolor=ft.Colors.GREEN,
                    color=ft.Colors.WHITE,
                    on_click=confirm_full_payment,
                ),
            ],
        )
        page.dialog.open = True
        page.update()

        def _update_tables():
            # Atualizar cards se houver callback disponível
            if hasattr(page, "atualizar_dashboard_cards") and callable(
                page.atualizar_dashboard_cards
            ):
                try:
                    page.atualizar_dashboard_cards()
                except Exception:
                    pass
            try:
                if hasattr(page, "atualizar_finance_tables") and callable(
                    page.atualizar_finance_tables
                ):
                    page.atualizar_finance_tables()
            except Exception:
                pass
            try:
                page.update()
            except Exception:
                pass

    except Exception as ex:
        _show_snack(page, f"❌ Erro: {str(ex)[:50]}", ft.Colors.RED)


def show_partial_payment_dialog(
    page: ft.Page, pdv_core, item_id: int, is_receber: bool, valor_total: float
):
    """Dialog for partial payment input"""
    valor_pago_field = ft.TextField(
        label="Valor Pago (R$)",
        prefix="R$ ",
        keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True,
    )

    def confirm_partial(e):
        try:
            valor_pago = parse_currency(valor_pago_field.value)
            if valor_pago <= 0:
                _show_snack(page, "❌ Valor deve ser maior que zero!", ft.Colors.RED)
                return
            if valor_pago > valor_total:
                _show_snack(
                    page, "❌ Valor não pode ser maior que o total!", ft.Colors.RED
                )
                return

            _close_dialog(page)

            if is_receber:
                success = pdv_core.receive_receivable_partial(item_id, valor_pago)
            else:
                success = pdv_core.pay_expense_partial(item_id, valor_pago)

            if success:
                _show_snack(page, "✅ Pagamento parcial registrado!", ft.Colors.GREEN)
            else:
                _show_snack(page, "❌ Erro ao registrar pagamento!", ft.Colors.RED)

            # Atualizar badge de alertas após pagamento parcial
            try:
                from alertas.alertas_init import atualizar_badge_alertas_no_gerente

                pdv_core_ref = page.app_data.get("pdv_core") or pdv_core
                try:
                    atualizar_badge_alertas_no_gerente(page, pdv_core_ref)
                except Exception:
                    pass
            except Exception:
                pass

            # Atualizar cards se houver callback disponível
            if hasattr(page, "atualizar_dashboard_cards") and callable(
                page.atualizar_dashboard_cards
            ):
                try:
                    page.atualizar_dashboard_cards()
                except Exception:
                    pass
            # Update tables
            try:
                if hasattr(page, "atualizar_finance_tables") and callable(
                    page.atualizar_finance_tables
                ):
                    page.atualizar_finance_tables()
            except Exception:
                pass
            try:
                page.update()
            except Exception:
                pass
        except Exception as ex:
            _show_snack(page, f"❌ Erro: {str(ex)[:50]}", ft.Colors.RED)

    page.dialog = ft.AlertDialog(
        title=ft.Text("Pagamento Parcial"),
        content=ft.Column(
            [
                ft.Text(f"Valor Total: {format_currency(valor_total)}", weight="bold"),
                valor_pago_field,
                ft.Text(
                    "Obs: O restante será criado como novo registro",
                    size=12,
                    color=ft.Colors.GREY_700,
                ),
            ],
            tight=True,
            spacing=10,
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda e: _close_dialog(page)),
            ft.ElevatedButton(
                "Confirmar",
                bgcolor=ft.Colors.ORANGE,
                color=ft.Colors.WHITE,
                on_click=confirm_partial,
            ),
        ],
    )
    page.dialog.open = True
    page.update()


def refresh_view(page: ft.Page, pdv_core, handle_back, create_appbar, view_func=None):
    try:
        # Se foi passada uma função view_func, substituímos a view atual por ela.
        if view_func:
            if len(page.views) > 0:
                page.views.pop()
            page.views.append(view_func(page, pdv_core, handle_back, create_appbar))
        else:
            # Sem view_func, apenas atualiza a página (não remove a view atual).
            page.update()
    except Exception as ex:
        print(f"❌ Erro ao atualizar view: {ex}")


def export_finance_csv(page: ft.Page, pdv_core, is_receber: bool, e=None):
    print(f"[CSV] Iniciando exportação CSV - is_receber={is_receber}")
    try:
        # Detectar tipo de dados
        tipo = "Contas a Receber" if is_receber else "Contas a Pagar"
        print(f"[CSV] Exportando: {tipo}")

        if is_receber:
            items = pdv_core.get_pending_receivables() or []
            print(f"[CSV] Encontrados {len(items)} itens para receber")
            headers = ["Vencimento", "Descrição", "Origem", "Valor", "Status", "ID"]
            rows = [
                [
                    str(getattr(it, "vencimento", "-")),
                    str(getattr(it, "descricao", "")),
                    str(getattr(it, "origem", getattr(it, "categoria", ""))),
                    float(getattr(it, "valor", 0.0)),
                    str(getattr(it, "status", "")),
                    str(getattr(it, "id", "")),
                ]
                for it in items
            ]
            caminho = export_utils.generate_csv_file(
                headers, rows, nome_base="contas_receber"
            )
        else:
            items = pdv_core.get_pending_expenses() or []
            print(f"[CSV] Encontrados {len(items)} itens a pagar")
            headers = ["Vencimento", "Descrição", "Categoria", "Valor", "Status", "ID"]
            rows = [
                [
                    str(getattr(it, "vencimento", "-")),
                    str(getattr(it, "descricao", "")),
                    str(getattr(it, "categoria", "")),
                    float(getattr(it, "valor", 0.0)),
                    str(getattr(it, "status", "")),
                    str(getattr(it, "id", "")),
                ]
                for it in items
            ]
            caminho = export_utils.generate_csv_file(
                headers, rows, nome_base="contas_pagar"
            )

        print(f"[CSV] [OK] Arquivo gerado: {caminho}")
        _show_snack(page, f"✅ CSV Exportado!\n{caminho}", color=ft.Colors.GREEN)
    except Exception as ex:
        print(f"[ERRO] export_finance_csv COMPLETO: {ex}")
        import traceback

        traceback.print_exc()
        _show_snack(page, f"❌ Erro CSV: {str(ex)}", color=ft.Colors.RED)


def export_finance_pdf(page: ft.Page, pdv_core, is_receber: bool, e=None):
    print(f"[PDF] Iniciando exportação PDF - is_receber={is_receber}")
    try:
        from models.db_models import Expense, Receivable

        # Detectar tipo de dados
        tipo = "Contas a Receber" if is_receber else "Contas a Pagar"
        print(f"[PDF] Exportando: {tipo}")

        if is_receber:
            # Buscar TODAS as receitas (não apenas pendentes)
            items = pdv_core.session.query(Receivable).all() or []
            print(f"[PDF] Encontrados {len(items)} itens para receber")
            headers = ["Vencimento", "Descrição", "Origem", "Valor", "Status", "ID"]
            rows = [
                [
                    str(getattr(it, "vencimento", "-")),
                    str(getattr(it, "descricao", "")),
                    str(getattr(it, "origem", getattr(it, "categoria", ""))),
                    f"R$ {float(getattr(it, 'valor', 0.0)):.2f}",
                    str(getattr(it, "status", "")),
                    str(getattr(it, "id", "")),
                ]
                for it in items
            ]
            caminho = export_utils.generate_pdf_file(
                headers,
                rows,
                nome_base="contas_receber",
                title="Contas a Receber",
                col_widths=[14, 34, 18, 12, 12, 10],
            )
        else:
            # Buscar TODAS as despesas (não apenas pendentes)
            items = pdv_core.session.query(Expense).all() or []
            print(f"[PDF] Encontrados {len(items)} itens a pagar")
            headers = ["Vencimento", "Descrição", "Categoria", "Valor", "Status", "ID"]
            rows = [
                [
                    str(getattr(it, "vencimento", "-")),
                    str(getattr(it, "descricao", "")),
                    str(getattr(it, "categoria", "")),
                    f"R$ {float(getattr(it, 'valor', 0.0)):.2f}",
                    str(getattr(it, "status", "")),
                    str(getattr(it, "id", "")),
                ]
                for it in items
            ]
            caminho = export_utils.generate_pdf_file(
                headers,
                rows,
                nome_base="contas_pagar",
                title="Contas a Pagar",
                col_widths=[14, 34, 18, 12, 12, 10],
            )

        print(f"[PDF] [OK] Arquivo gerado: {caminho}")
        _show_snack(page, "Abrindo PDF no navegador...", color=ft.Colors.BLUE)

        # Abrir PDF no navegador
        pdf_absoluto = os.path.abspath(caminho)
        print(f"[PDF] Abrindo no navegador: {pdf_absoluto}")
        webbrowser.open(f"file:///{pdf_absoluto}")

        _show_snack(page, "PDF aberto no navegador!", color=ft.Colors.GREEN)

    except Exception as ex:
        print(f"[ERRO] export_finance_pdf COMPLETO: {ex}")
        traceback.print_exc()
        _show_snack(page, f"Erro PDF: {str(ex)}", color=ft.Colors.RED)
