import flet as ft


def criar_card_layout(titulo, texto_valor, icone=None, cor_icone=None, cor_fundo=None):
    """Cria um card minimalista/flat com título e valor reativo.

    - `titulo`: rótulo do card
    - `texto_valor`: instância de ft.Text já criada (reativa)
    - `icone`, `cor_icone`, `cor_fundo`: não usados na versão minimalista atual,
      mas mantidos por compatibilidade com futuras variações.
    """
    return ft.Container(
        content=ft.Column(
            [
                texto_valor,
                ft.Text(
                    titulo,
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.GREY_600,
                ),
            ],
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(vertical=6, horizontal=8),
        width=160,
        height=64,
        alignment=ft.alignment.center,
    )


def criar_linha_tabela(p: dict, on_editar, on_excluir):
    """Monta uma linha (DataRow) da tabela de produtos.

    - `p`: dict do produto.
    - `on_editar`: callback (e, produto_id)
    - `on_excluir`: callback (e, produto_id)
    """
    cor_qtd = ft.Colors.RED_600 if p.get("quantidade", 0) < 10 else ft.Colors.GREEN_600

    btn_editar = ft.IconButton(
        icon=ft.Icons.EDIT_OUTLINED,
        tooltip="Editar",
        icon_color=ft.Colors.BLUE_600,
        on_click=lambda e: on_editar(e, p["id"]),
    )
    btn_excluir = ft.IconButton(
        icon=ft.Icons.DELETE_OUTLINE,
        tooltip="Excluir",
        icon_color=ft.Colors.RED_600,
        on_click=lambda e: on_excluir(e, p["id"]),
    )

    return ft.DataRow(
        cells=[
            ft.DataCell(ft.Text(str(p.get("id", "")), size=14)),
            ft.DataCell(
                ft.Container(
                    content=ft.Text(
                        p.get("nome", ""), size=14, max_lines=2, overflow="visible"
                    ),
                    width=180,
                    padding=ft.padding.only(right=4),
                )
            ),
            ft.DataCell(ft.Text(p.get("categoria", ""), size=14)),
            ft.DataCell(ft.Text(p.get("validade").strftime("%d/%m/%Y"), size=14)),
            ft.DataCell(
                ft.Container(
                    content=ft.Text(p.get("lote", ""), size=14),
                    width=90,
                    padding=ft.padding.only(right=6),
                )
            ),
            ft.DataCell(
                ft.Text(
                    str(p.get("quantidade", 0)),
                    size=14,
                    color=cor_qtd,
                    weight=ft.FontWeight.BOLD,
                )
            ),
            ft.DataCell(
                ft.Text(
                    f"R$ {float(p.get('preco_custo', 0.0)):.2f}".replace(
                        ".",
                        ",",
                    ),
                    size=14,
                    color=ft.Colors.GREY_800,
                )
            ),
            ft.DataCell(
                ft.Text(
                    f"R$ {float(p.get('preco_venda', p.get('preco', 0.0))):.2f}".replace(
                        ".",
                        ",",
                    ),
                    size=14,
                    color=ft.Colors.GREY_800,
                )
            ),
            ft.DataCell(
                ft.Text(
                    p.get("codigo_barras", "-"),
                    size=12,
                    color=ft.Colors.GREY_700,
                )
            ),
            ft.DataCell(ft.Row([btn_editar, btn_excluir], spacing=5)),
        ]
    )
