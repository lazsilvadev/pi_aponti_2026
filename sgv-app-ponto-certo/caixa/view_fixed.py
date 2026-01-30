"""Implementação enxuta e substituta da view do Caixa (arquivo fixo).

Arquivo criado para contornar corrupção no `caixa/view.py`. Fornece
uma versão limpa e testável do Caixa com funcionalidade mínima: adicionar
produto por código, exibir carrinho, selecionar pagamento e modal de
Crédito limitado a 2x com exibição do valor por parcela.
"""

import json
import os
from typing import List, Tuple

import flet as ft

from utils.cupom import show_cupom_dialog


def _load_products():
    base = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(base, "data", "produtos.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return []


def create_caixa_view(
    page: ft.Page,
    pdv_core,
    handle_back,
    handle_logout=None,
    current_user=None,
    appbar: ft.AppBar = None,
):
    cart: List[Tuple[str, int, float]] = []
    produtos = _load_products()

    def _format_currency(v: float) -> str:
        return f"R$ {v:.2f}".replace(".", ",")

    def calc_total() -> float:
        return sum(qtd * preco for (_, qtd, preco) in cart)

    total_text = ft.Text(_format_currency(0.0), size=20, weight=ft.FontWeight.BOLD)
    cart_rows = ft.Column([], spacing=6, expand=True)
    payment_type_ref = ft.Ref()
    installments_ref = ft.Ref()

    def refresh_cart():
        cart_rows.controls.clear()
        for i, (nome, qtd, preco) in enumerate(cart):
            row = ft.Row(
                [
                    ft.Text(nome, expand=True),
                    ft.Text(str(qtd), width=40, text_align=ft.TextAlign.RIGHT),
                    ft.Text(
                        _format_currency(preco), width=90, text_align=ft.TextAlign.RIGHT
                    ),
                    ft.Text(
                        _format_currency(qtd * preco),
                        width=90,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                    ft.IconButton(
                        ft.icons.REMOVE, on_click=lambda e, idx=i: remove_item(idx)
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            cart_rows.controls.append(row)
        total_text.value = _format_currency(calc_total())
        page.update()

    def add_product_by_code(e=None):
        code = code_field.value.strip()
        if not code:
            page.snack_bar = ft.SnackBar(ft.Text("Informe o código do produto"))
            page.snack_bar.open = True
            page.update()
            return
        found = None
        for pj in produtos:
            cod = str(pj.get("codigo_barras") or pj.get("codigo") or "").strip()
            if cod == code:
                found = pj
                break
        if not found:
            page.snack_bar = ft.SnackBar(ft.Text("Produto não encontrado"))
            page.snack_bar.open = True
            page.update()
            return
        nome = found.get("nome", "Produto")
        preco = float(found.get("preco_venda", 0.0))
        cart.append((nome, 1, preco))
        code_field.value = ""
        refresh_cart()

    def remove_item(idx: int):
        try:
            cart.pop(idx)
        except Exception:
            pass
        refresh_cart()

    code_field = ft.TextField(label="Código do produto", width=220, autofocus=False)

    def open_credit_modal(e=None):
        total = calc_total()
        installments = 2
        per_installment = total / installments if installments > 0 else 0.0

        content = ft.Column(
            [
                ft.Text(
                    f"{installments}x de {_format_currency(per_installment)} por mês",
                    size=14,
                ),
                ft.Dropdown(
                    value=str(installments),
                    options=[ft.dropdown.Option("2")],
                    width=160,
                ),
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Crédito"),
            content=content,
            actions=[
                ft.TextButton("Fechar", on_click=lambda e: page.dialog.close()),
                ft.ElevatedButton(
                    "Confirmar",
                    on_click=lambda e: _confirm_credit(installments, per_installment),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.dialog = dlg
        page.dialog.open = True
        page.update()

    def _confirm_credit(installments: int, per_installment: float):
        payment_type_ref.current = "Crédito"
        installments_ref.current = installments
        page.dialog.open = False
        page.update()

    def finalize_sale(e=None):
        total = calc_total()
        if total <= 0:
            page.snack_bar = ft.SnackBar(ft.Text("Carrinho vazio"))
            page.snack_bar.open = True
            page.update()
            return

        p_type = payment_type_ref.current or "Não informado"
        installments = (
            installments_ref.current
            if getattr(installments_ref, "current", None)
            else None
        )
        per_installment = (total / installments) if installments else None

        itens = [
            (
                nome,
                qtd,
                f"R$ {preco:.2f}".replace(".", ","),
                f"R$ {qtd * preco:.2f}".replace(".", ","),
            )
            for (nome, qtd, preco) in cart
        ]

        try:
            show_cupom_dialog(
                page,
                itens,
                "Cupom NÃO Fiscal - Venda",
                total,
                p_type,
                received=None,
                change=None,
                auto_print=False,
                transaction_id=None,
                payment_status=None,
                installments_count=installments,
                per_installment=per_installment,
                is_fiscal=False,
            )
        except Exception:
            page.snack_bar = ft.SnackBar(ft.Text("Erro ao abrir cupom"))
            page.snack_bar.open = True
            page.update()

    def select_payment(pt: str):
        payment_type_ref.current = pt
        if pt == "Crédito":
            open_credit_modal()
        page.update()

    payment_buttons = ft.Row(
        [
            ft.ElevatedButton(
                "Dinheiro", on_click=lambda e: select_payment("Dinheiro")
            ),
            ft.ElevatedButton("Débito", on_click=lambda e: select_payment("Débito")),
            ft.ElevatedButton("Crédito", on_click=lambda e: select_payment("Crédito")),
        ],
        spacing=12,
    )

    main = ft.Column(
        [
            ft.Row(
                [
                    code_field,
                    ft.ElevatedButton("Adicionar", on_click=add_product_by_code),
                ]
            ),
            ft.Divider(),
            cart_rows,
            ft.Divider(),
            ft.Row([ft.Container(expand=True), total_text]),
            payment_buttons,
            ft.Row([ft.ElevatedButton("Finalizar", on_click=finalize_sale)]),
        ],
        expand=True,
        spacing=10,
    )

    view = ft.View("/caixa", [main], bgcolor="white")
    try:
        page.show_bottom_status = lambda msg, bg: None
    except Exception:
        pass

    return view
