from typing import Callable

import flet as ft


def create_cart_item_row(
    item_data: dict,
    product_id: str,
    COLORS: dict,
    update_cart_item: Callable[[str, int], None],
    index: int = 0,
) -> ft.Container:
    """Cria a linha visual de um item do carrinho.

    - item_data: dict contendo nome, preco, qtd e refs a serem preenchidas
    - product_id: identificador/código do produto
    - COLORS: paleta de cores utilizada
    - update_cart_item: callback que recebe (product_id, quantity_change)
    """
    qtd_ref = ft.Ref[ft.Text]()
    total_row_ref = ft.Ref[ft.Text]()

    row = ft.Row(
        [
            ft.Text(
                item_data["nome"],
                expand=True,
                size=14,
                weight="bold",
                color=COLORS["text_dark"],
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Container(
                ft.Row(
                    [
                        ft.IconButton(
                            ft.Icons.REMOVE,
                            icon_color=COLORS["danger"],
                            tooltip="Remover item",
                            icon_size=18,
                            on_click=lambda e: update_cart_item(product_id, -1),
                            style=ft.ButtonStyle(
                                padding=5,
                                shape=ft.RoundedRectangleBorder(radius=4),
                            ),
                        ),
                        ft.Text(
                            f"x{item_data['qtd']}",
                            ref=qtd_ref,
                            size=18,
                            weight="bold",
                            width=34,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.IconButton(
                            ft.Icons.ADD,
                            icon_color=COLORS["secondary"],
                            tooltip="Adicionar item",
                            icon_size=18,
                            on_click=lambda e: update_cart_item(product_id, 1),
                            style=ft.ButtonStyle(
                                padding=5,
                                shape=ft.RoundedRectangleBorder(radius=4),
                            ),
                        ),
                    ],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                width=150,
                alignment=ft.alignment.center_right,
            ),
            ft.Text(
                f"R$ {item_data['preco']:.2f}".replace(".", ","),
                size=14,
                color=COLORS["text_muted"],
                width=100,
                text_align=ft.TextAlign.RIGHT,
            ),
            ft.Text(
                f"R$ {item_data['preco'] * item_data['qtd']:.2f}".replace(".", ","),
                ref=total_row_ref,
                size=16,
                weight="bold",
                color=COLORS["primary"],
                width=120,
                text_align=ft.TextAlign.RIGHT,
            ),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
    )

    item_data["qtd_ref"] = qtd_ref
    item_data["total_row_ref"] = total_row_ref

    # Zebra: linhas alternadas para melhor legibilidade
    try:
        if index is None:
            index = 0
        bg = (
            COLORS.get("card_bg", ft.Colors.WHITE)
            if (int(index) % 2 == 0)
            else "#F7FBFF"
        )
    except Exception:
        bg = COLORS.get("card_bg", ft.Colors.WHITE)

    return ft.Container(
        row,
        border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.BLACK12)),
        padding=ft.padding.symmetric(vertical=8, horizontal=10),
        bgcolor=bg,
    )


def create_payment_panel(
    COLORS: dict,
    payment_methods: list,
    on_select_payment: Callable[[str, ft.Ref], None],
    money_received_field_ref: ft.Ref[ft.TextField],
    change_text_ref: ft.Ref[ft.Text],
    calculate_change_cb: Callable[[object], None],
    on_method_value_submit: Callable[[str, int, object], None] = None,
    on_parcel_select: Callable[[int, int], None] = None,
):
    """Cria o painel de opções de pagamento.

    Retorna uma tupla: (payment_options_panel, payment_buttons_refs, money_received_input, change_display)
    """

    payment_buttons_refs: list[ft.Ref] = []
    payment_amount_text_refs: list[ft.Ref] = []
    # refs para mini-botões de parcelamento (alinhados pelo índice dos métodos)
    payment_parcel_button_refs: list = []
    # um TextField por método (refs separados)
    payment_value_field_refs: list[ft.Ref] = []
    # status refs: total, paid, remaining
    total_ref = ft.Ref[ft.Text]()
    paid_ref = ft.Ref[ft.Text]()
    remaining_ref = ft.Ref[ft.Text]()

    # Estado para saber qual método está selecionado
    from flet import Ref

    selected_method_ref = Ref[str]()
    selected_method_ref.current = None

    def _make_btn(item, idx):
        btn_ref = ft.Ref[ft.ElevatedButton]()
        payment_buttons_refs.append(btn_ref)
        # manter slot na lista de parcel buttons para este índice
        payment_parcel_button_refs.append(None)
        amt_ref = ft.Ref[ft.Text]()
        payment_amount_text_refs.append(amt_ref)

        # ref do campo de valor para este método
        if item["name"] == "Dinheiro":
            value_ref = money_received_field_ref
        else:
            value_ref = ft.Ref[ft.TextField]()
        payment_value_field_refs.append(value_ref)

        def on_btn_click(e, name=item["name"], ref=btn_ref):
            selected_method_ref.current = name
            on_select_payment(name, ref)

        controls = [
            ft.ElevatedButton(
                ref=btn_ref,
                content=ft.Row(
                    [
                        ft.Icon(item["icon"], size=20, color=ft.Colors.BLACK),
                        ft.Text(
                            f"({item['key']}) {item['name']}",
                            size=14,
                            weight="bold",
                            color=ft.Colors.BLACK,
                        ),
                        ft.Container(expand=True),
                        ft.Text(
                            "",
                            ref=amt_ref,
                            size=14,
                            weight="bold",
                            color=ft.Colors.BLACK,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                data=item["name"],
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.WHITE,
                    color=ft.Colors.BLACK,
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.padding.symmetric(horizontal=15, vertical=10),
                    side=ft.border.BorderSide(1, "#007BFF"),
                    elevation=1,
                    overlay_color="#81C784",
                ),
                on_click=on_btn_click,
                height=50,
                expand=True,
            )
        ]
        # sempre criar o campo (inicialmente invisível) — tornamos visível quando selecionado
        tf = ft.TextField(
            ref=value_ref,
            label=f"Valor para {item['name']}",
            prefix="R$",
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=calculate_change_cb,
            on_submit=(
                (
                    lambda e, name=item["name"], idx=idx: on_method_value_submit(
                        name, idx, e
                    )
                )
                if on_method_value_submit
                else None
            ),
            visible=False,
            border_radius=8,
            filled=True,
            bgcolor=COLORS["background"],
            height=50,
            text_size=16,
        )
        controls.append(
            ft.Container(tf, padding=ft.padding.only(top=8, left=10, right=10))
        )
        # se for Crédito, adicionar mini-botão 2x abaixo do campo de valor
        try:
            if item["name"] == "Crédito":
                parcel_ref = ft.Ref[ft.ElevatedButton]()

                def _on_parcel_click(e=None, _idx=idx):
                    try:
                        if callable(on_parcel_select):
                            on_parcel_select(_idx, 2)
                    except Exception:
                        pass

                mini = ft.ElevatedButton(
                    "2x",
                    ref=parcel_ref,
                    on_click=_on_parcel_click,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.WHITE,
                        color=ft.Colors.BLACK,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        shape=ft.RoundedRectangleBorder(radius=6),
                    ),
                    height=28,
                    visible=False,
                )
                controls.append(
                    ft.Container(mini, padding=ft.padding.only(top=6, left=10))
                )
                payment_parcel_button_refs[idx] = parcel_ref
        except Exception:
            pass
        return ft.Container(
            ft.Column(controls, spacing=2),
            padding=ft.padding.only(bottom=5),
        )

    payment_buttons = [_make_btn(item, idx) for idx, item in enumerate(payment_methods)]

    # O campo money_received_input agora é renderizado por método; manter referência ao ref passado
    money_received_input = money_received_field_ref

    change_display = ft.Text(
        ref=change_text_ref,
        value="Troco: R$ 0,00",
        size=24,
        weight="bold",
        color=COLORS["secondary"],
        visible=False,
        text_align=ft.TextAlign.RIGHT,
    )

    payment_options_panel = ft.Container(
        ft.Column(
            [
                ft.Text(
                    "OPÇÕES DE PAGAMENTO",
                    size=18,
                    weight="bold",
                    color=COLORS["text_dark"],
                ),
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("Pago:", size=12, color=COLORS["text_muted"]),
                                ft.Text(
                                    "R$ 0,00", ref=paid_ref, size=14, weight="bold"
                                ),
                            ]
                        ),
                        ft.Container(width=12),
                        ft.Column(
                            [
                                ft.Text(
                                    "Restante:", size=12, color=COLORS["text_muted"]
                                ),
                                ft.Text(
                                    "R$ 0,00", ref=remaining_ref, size=14, weight="bold"
                                ),
                            ]
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Divider(height=10, color=ft.Colors.BLACK12),
                ft.Column(payment_buttons, spacing=5),
                ft.Divider(height=10, color=ft.Colors.BLACK12),
                # O campo de valor recebido agora aparece logo abaixo do botão selecionado
                ft.Row(
                    [
                        change_display,
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
                ft.Container(expand=True),
            ],
            spacing=10,
            expand=True,
        ),
        padding=ft.padding.all(20),
        bgcolor=COLORS["card_bg"],
        border_radius=ft.border_radius.all(12),
        width=350,
        border=ft.border.all(1, ft.Colors.BLACK12),
    )

    return (
        payment_options_panel,
        payment_buttons_refs,
        money_received_input,
        change_display,
        payment_amount_text_refs,
        payment_value_field_refs,
        (total_ref, paid_ref, remaining_ref),
        payment_parcel_button_refs,
    )
