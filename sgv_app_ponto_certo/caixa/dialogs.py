from typing import Any, Callable, Dict, List, Optional, Tuple

import flet as ft


def create_price_check_overlay(
    COLORS: Dict[str, Any],
    on_lookup: Callable[[str], None],
    on_close: Callable[[], None],
) -> ft.Container:
    """Cria o overlay de Consulta de Preço (F6).

    - COLORS: paleta do app
    - on_lookup: callback chamado com o código digitado
    - on_close: callback para fechar o overlay
    """
    result_text = ft.Text("", size=16)

    code_field = ft.TextField(
        label="Código de barras",
        prefix_icon=ft.Icons.QR_CODE_SCANNER,
        autofocus=True,
        border_radius=8,
        filled=True,
        bgcolor=ft.Colors.WHITE,
        keyboard_type=ft.KeyboardType.NUMBER,
        on_submit=lambda ev: on_lookup(ev.control.value),
    )

    def _close(e=None):
        try:
            on_close(e)
        except TypeError:
            # compatibilidade: se on_close não aceitar parâmetro, chamar sem
            try:
                on_close()
            except Exception:
                pass
        except Exception:
            try:
                on_close()
            except Exception:
                pass

    price_check_overlay = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(
                                                "Consulta de Preço",
                                                size=16,
                                                weight=ft.FontWeight.BOLD,
                                            )
                                        ],
                                        alignment=ft.MainAxisAlignment.CENTER,
                                    ),
                                    ft.Divider(height=10),
                                    code_field,
                                    ft.Divider(height=5),
                                    result_text,
                                    ft.Divider(height=10),
                                    ft.Row(
                                        [ft.TextButton("Fechar", on_click=_close)],
                                        alignment=ft.MainAxisAlignment.END,
                                    ),
                                ],
                                spacing=8,
                                width=400,
                            ),
                            width=450,
                            bgcolor="white",
                            border_radius=8,
                            padding=20,
                        ),
                        ft.Container(expand=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        visible=False,
        bgcolor="rgba(0, 0, 0, 0.5)",
        expand=True,
    )

    # expor refs úteis
    price_check_overlay.__result_text__ = result_text  # type: ignore[attr-defined]
    price_check_overlay.__code_field__ = code_field  # type: ignore[attr-defined]
    return price_check_overlay


def create_cancel_sale_dialog(
    COLORS: Dict[str, Any],
    vendas_dia: List[Dict[str, Any]],
    produtos_por_codigo: Dict[str, Any],
    handle_confirm: Callable[[str, str, int, int], Tuple[bool, str]],
    on_close: Callable[[], None],
) -> ft.Container:
    """Cria o diálogo (F7) para estornar vendas.

    - vendas_dia: lista de vendas (dicts) do dia
    - produtos_por_codigo: mapa auxiliar para detalhar itens
    - handle_confirm: recebe (username, password, venda_id) e retorna (ok, msg)
    - on_close: callback de fechamento
    """

    def make_option(v):
        vid = v.get("id")
        total = float(v.get("total", 0.0))
        data_str = v.get("data", "")
        header = f"#{vid} • {data_str} • Total: R$ {total:.2f}"

        itens = v.get("itens", []) or []
        itens_parts = []
        for idx, it in enumerate(itens[:3], start=1):
            cod = (
                str(it.get("codigo_barras") or "").strip()
                or str(it.get("produto_id") or "").strip()
            )
            qtd = it.get("quantidade", 0)

            pj = produtos_por_codigo.get(cod)
            if pj:
                nome = pj.get("nome") or pj.get("descricao") or "Produto"
                pu = float(
                    pj.get(
                        "preco_venda", pj.get("preco", it.get("preco_unitario", 0.0))
                    )
                    or 0.0
                )
                pid = pj.get("id", "?")
                itens_parts.append(
                    f"{idx}) ID {pid} • {cod} - {nome} x{qtd} R$ {pu:.2f}"
                )
            else:
                nome = it.get("produto", "Produto")
                pu = float(it.get("preco_unitario", 0.0))
                itens_parts.append(f"{idx}) {cod or '?'} - {nome} x{qtd} R$ {pu:.2f}")

        if len(itens) > 3:
            itens_parts.append(f"... (+{len(itens) - 3} itens)")

        itens_str = "\n".join(itens_parts) if itens_parts else "(Sem itens registrados)"
        label = f"{header}\n{itens_str}"
        return ft.Radio(value=str(vid), label=label)

    radios = [make_option(v) for v in vendas_dia]
    default_value = str(vendas_dia[0].get("id")) if vendas_dia else None

    vendas_group = ft.RadioGroup(
        value=default_value, content=ft.Column(radios, scroll="auto", height=200)
    )

    # Grupo de itens da venda selecionada (padrão: lista de checkboxes para seleção múltipla)
    itens_container = ft.Column([], scroll="auto", height=160)

    gerente_user_field = ft.TextField(label="Usuário do gerente", autofocus=True)
    password_field = ft.TextField(
        label="Senha do gerente", password=True, can_reveal_password=True
    )
    status_text = ft.Text("", size=14)

    def _confirm(_=None):
        selected_value = vendas_group.value
        username = (gerente_user_field.value or "").strip()
        password = (password_field.value or "").strip()
        if not selected_value:
            status_text.value = "Selecione uma venda para cancelar."
            status_text.color = COLORS["warning"]
            status_text.update()
            return
        # itens selecionados (opcional) - coletar ids de checkboxes marcadas
        selected_ids = []
        try:
            for c in itens_container.controls:
                # checkboxes têm atributo 'value' True quando marcadas and .data com id
                if getattr(c, "value", False):
                    data = getattr(c, "data", None)
                    if data is not None:
                        selected_ids.append(data)
        except Exception:
            selected_ids = []

        ok, msg = handle_confirm(
            username, password, int(selected_value), selected_ids or None
        )
        status_text.value = msg
        status_text.color = COLORS["primary"] if ok else COLORS["danger"]
        status_text.update()
        if ok:
            on_close()

    def _close(_=None):
        on_close()

    # Cores e estilos
    TEXT_COLOR = "#2D3748"
    CARD_BG = "#F8F9FA"

    # Construir modal como Container (overlay) em vez de AlertDialog, para
    # permitir que eventos de teclado (ESC) cheguem ao handler global.
    inner_card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Text(
                            "Estornar Venda",
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            color=TEXT_COLOR,
                        ),
                        ft.Container(expand=True),
                        ft.IconButton(
                            ft.Icons.CLOSE, icon_color=TEXT_COLOR, on_click=_close
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(height=10, color="#DFE6E9"),
                ft.Text(
                    "Selecione a venda que deseja cancelar:", size=12, color="#636E72"
                ),
                ft.Container(
                    content=vendas_group,
                    height=200,
                    border_radius=8,
                    border=ft.border.all(1, "#DFE6E9"),
                    padding=ft.padding.all(8),
                ),
                ft.Divider(height=10, color="#DFE6E9"),
                ft.Text(
                    "Opcional: estornar item específico da venda:",
                    size=12,
                    color="#636E72",
                ),
                ft.Container(
                    content=itens_container,
                    height=160,
                    border_radius=8,
                    border=ft.border.all(1, "#DFE6E9"),
                    padding=ft.padding.all(8),
                ),
                ft.Divider(height=15, color="#DFE6E9"),
                ft.Text(
                    "Autenticação do Gerente:",
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=TEXT_COLOR,
                ),
                ft.Container(
                    content=ft.Column([gerente_user_field, password_field], spacing=10),
                    padding=ft.padding.all(12),
                    bgcolor=CARD_BG,
                    border_radius=8,
                ),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            text=" Fechar",
                            width=120,
                            height=36,
                            on_click=_close,
                            style=ft.ButtonStyle(
                                bgcolor="#00B894", color=ft.Colors.WHITE
                            ),
                        ),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            text="Confirmar",
                            width=160,
                            height=36,
                            on_click=_confirm,
                            style=ft.ButtonStyle(
                                bgcolor="#00B894", color=ft.Colors.WHITE
                            ),
                        ),
                    ],
                    spacing=8,
                ),
                ft.Divider(height=10, color="#DFE6E9"),
                ft.Container(
                    content=status_text, padding=ft.padding.all(10), border_radius=8
                ),
            ],
            spacing=12,
            width=560,
            scroll=ft.ScrollMode.AUTO,
        ),
        width=620,
        height=600,
        bgcolor=CARD_BG,
        border_radius=8,
        padding=ft.padding.all(16),
    )

    dlg = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        inner_card,
                        ft.Container(expand=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        visible=False,
        bgcolor=None,
        expand=True,
    )

    # expor campos úteis
    # expor os refs para compatibilidade com o restante da aplicação
    dlg.__vendas_group__ = vendas_group  # type: ignore[attr-defined]
    dlg.__status_text__ = status_text  # type: ignore[attr-defined]
    dlg.__user_field__ = gerente_user_field  # type: ignore[attr-defined]
    dlg.__password_field__ = password_field  # type: ignore[attr-defined]
    dlg.__items_container__ = itens_container  # type: ignore[attr-defined]
    # manter atributo "open" por compatibilidade com uso em view.py
    try:
        dlg.open = False  # type: ignore[attr-defined]
    except Exception:
        pass

    # Atualizar lista de itens quando a venda selecionada mudar
    def _on_venda_change(e=None):
        try:
            vid = vendas_group.value
            itens_container.controls.clear()
            if not vid:
                # nothing selected
                itens_container.update()
                return
            # localizar venda no conjunto
            venda_sel = None
            for v in vendas_dia:
                if str(v.get("id")) == str(vid):
                    venda_sel = v
                    break
            if not venda_sel:
                itens_container.update()
                return
            itens = venda_sel.get("itens", []) or []
            checks = []
            for it in itens:
                # identificar item via id do item na venda ou índice
                item_id = it.get("id") or it.get("produto_id")
                nome = (
                    it.get("produto")
                    or produtos_por_codigo.get(
                        str(it.get("codigo_barras") or it.get("produto_id") or ""), {}
                    ).get("nome")
                    or "Produto"
                )
                qtd = it.get("quantidade", 0)
                pu = float(it.get("preco_unitario", 0.0) or 0.0)
                label = f"ID {item_id} • {nome} x{qtd} R$ {pu:.2f}"
                chk = ft.Checkbox(label=label, value=False)
                # armazenar id do item no controle para recuperação posterior
                setattr(chk, "data", int(item_id) if item_id is not None else None)
                checks.append(chk)

            # opção para estornar a venda inteira
            chk_all = ft.Checkbox(label="Estornar venda inteira", value=False)
            setattr(chk_all, "data", "__all__")
            checks.append(chk_all)

            itens_container.controls.extend(checks)
            itens_container.update()
        except Exception:
            pass

    vendas_group.on_change = _on_venda_change
    # inicializar itens para a venda selecionada por padrão
    _on_venda_change()
    return dlg


def create_pix_overlay(
    payload_text: str,
    qr_base64: Optional[str],
    on_confirm: Callable[[], None],
    on_cancel: Callable[[], None],
    merchant_name: str = None,
    chave_pix: str = None,
    cidade: str = "Recife",
    tipo_pix: str = "dinamico",
    remaining_amount: float = None,
) -> ft.Container:
    """Cria o overlay simples para confirmação de pagamento Pix.

    Agora permite ao operador escolher se deseja embutir o valor no QR (auto-fill).
    Se o switch estiver ativo, o QR será regenerado com `tipo='com_valor'` e o
    payload exibido será atualizado.
    """

    qr_control = ft.Image(src_base64=qr_base64) if qr_base64 else ft.Container()
    # switch para embutir valor no QR (auto-fill)
    embed_switch = ft.Checkbox(
        label="Embutir valor no QR (auto-fill)",
        value=True if (remaining_amount and remaining_amount > 0) else False,
    )
    embedded_value_text = ft.Text(
        (
            f"Valor embutido: R$ {float(remaining_amount):.2f}".replace(".", ",")
            if (remaining_amount is not None and remaining_amount > 0)
            else ""
        ),
        size=14,
    )

    pix_column_children = [
        ft.Text(
            "Aproxime o leitor para pagar via Pix",
            size=14,
            weight=ft.FontWeight.BOLD,
        ),
        ft.Row([qr_control], alignment=ft.MainAxisAlignment.CENTER),
        ft.Row([embed_switch, ft.Container(expand=True), embedded_value_text]),
    ]

    # mostrar payload para depuração (opcional)
    try:
        pix_column_children.append(ft.Text(payload_text or "", size=12))
    except Exception:
        pass

    pix_column = ft.Column(pix_column_children, spacing=8)

    # função para (re)gerar payload e imagem de QR conforme switch
    def regenerate_qr(embed: bool):
        try:
            import base64
            import io

            import qrcode

            from caixa.logic import montar_payload_pix

            tipo_for = tipo_pix
            valor_for = 0.0
            if embed and remaining_amount is not None:
                tipo_for = "com_valor"
                try:
                    valor_for = float(remaining_amount)
                except Exception:
                    valor_for = round(float(remaining_amount or 0.0), 2)
            else:
                valor_for = 0.0

            payload = montar_payload_pix(
                merchant_name or "",
                valor_for,
                chave_pix or "",
                None,
                cidade or "Recife",
                tipo_for,
            )
            try:
                qr = qrcode.QRCode(box_size=6, border=2)
                qr.add_data(payload)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            except Exception:
                b64 = None

            # atualizar controles visuais
            try:
                if b64:
                    qr_control.src_base64 = b64
                else:
                    qr_control.src_base64 = None
            except Exception:
                pass
            try:
                embedded_value_text.value = (
                    f"Valor embutido: R$ {valor_for:.2f}".replace(".", ",")
                    if embed and valor_for > 0
                    else ""
                )
            except Exception:
                pass
            try:
                # atualizar payload texto exibido (último controle)
                if len(pix_column.controls) > 0:
                    last_txt = pix_column.controls[-1]
                    try:
                        last_txt.value = payload
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                qr_control.update()
                embedded_value_text.update()
                pix_column.update()
            except Exception:
                pass
        except Exception:
            pass

    def _on_embed_change(e=None):
        try:
            regenerate_qr(embed_switch.value)
        except Exception:
            pass

    embed_switch.on_change = _on_embed_change

    # Gerar QR inicial conforme valor embutido padrão do switch
    try:
        regenerate_qr(embed_switch.value)
    except Exception:
        pass

    def _confirm(_=None):
        on_confirm()

    def _cancel(_=None):
        on_cancel()

    pix_overlay = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Pagamento via Pix",
                                        size=16,
                                        weight=ft.FontWeight.BOLD,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                    ft.Divider(height=10),
                                    ft.Container(content=pix_column, width=500),
                                    ft.Divider(height=10),
                                    ft.Row(
                                        [
                                            ft.TextButton("Cancelar", on_click=_cancel),
                                            ft.ElevatedButton(
                                                "Pagamento recebido", on_click=_confirm
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.END,
                                    ),
                                ],
                                spacing=8,
                            ),
                            width=550,
                            bgcolor="white",
                            border_radius=8,
                            padding=20,
                        ),
                        ft.Container(expand=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        visible=False,
        bgcolor="rgba(0, 0, 0, 0.5)",
        expand=True,
    )

    return pix_overlay
