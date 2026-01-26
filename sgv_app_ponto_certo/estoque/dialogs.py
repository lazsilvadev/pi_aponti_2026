from typing import Callable

import flet as ft


def create_dialog_content(
    nome_field: ft.TextField,
    categoria_field: ft.Dropdown,
    data_validade_field: ft.TextField,
    quantidade_field: ft.TextField,
    preco_custo_field: ft.TextField,
    preco_field: ft.TextField,
    codigo_barras_field: ft.TextField,
    codigo_barras_leitor_field: ft.TextField,
    lote_field: ft.TextField,
    accent_color: str,
    on_salvar: Callable[[ft.ControlEvent], None],
    on_cancelar: Callable[[ft.ControlEvent], None],
) -> ft.Container:
    """Cria o conteúdo do diálogo de adicionar/editar produto.

    - `on_salvar`: callback chamado ao clicar em "Salvar".
    - `accent_color`: cor de destaque para o botão salvar.
    """
    return ft.Container(
        content=ft.Column(
            [
                ft.Row([nome_field, categoria_field], spacing=12),
                ft.Row(
                    [
                        data_validade_field,
                        lote_field,
                        quantidade_field,
                        preco_custo_field,
                        preco_field,
                    ],
                    spacing=12,
                ),
                ft.Row([codigo_barras_field, codigo_barras_leitor_field], spacing=12),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Cancelar",
                            bgcolor="#012a4a",
                            color=ft.Colors.WHITE,
                            on_click=on_cancelar,
                        ),
                        ft.ElevatedButton(
                            "Salvar",
                            bgcolor="#012a4a",
                            color=ft.Colors.WHITE,
                            on_click=on_salvar,
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


def create_dialog_overlay(dialog_content: ft.Container) -> ft.Container:
    """Cria overlay semi-transparente centralizando o conteúdo do diálogo."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Container(expand=True),
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(content=dialog_content, width=700),
                        ft.Container(expand=True),
                    ],
                    expand=True,
                ),
                ft.Container(expand=True),
            ],
            expand=True,
        ),
        visible=False,
        bgcolor="rgba(0, 0, 0, 0.5)",
        expand=True,
    )


def create_exclusao_content(
    on_confirmar: Callable[[ft.ControlEvent], None],
    on_cancelar: Callable[[ft.ControlEvent], None],
) -> ft.Container:
    """Cria o conteúdo do diálogo de confirmação de exclusão."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Text("Confirmar Exclusão", size=18, weight=ft.FontWeight.BOLD),
                ft.Text("Tem certeza que deseja excluir este produto?", size=14),
                ft.Row(
                    [
                        ft.TextButton(
                            content=ft.Text("Cancelar", color=ft.Colors.WHITE),
                            on_click=on_cancelar,
                        ),
                        ft.ElevatedButton(
                            "Sim, Excluir",
                            bgcolor="#012a4a",
                            color=ft.Colors.WHITE,
                            on_click=on_confirmar,
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


def create_exclusao_overlay(exclusao_content: ft.Container) -> ft.Container:
    """Cria overlay semi-transparente para confirmação de exclusão."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(content=exclusao_content, width=350),
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
