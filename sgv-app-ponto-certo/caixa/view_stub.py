"""Stub `caixa.view_stub` para restaurar execução da aplicação rapidamente.

Este módulo fornece uma `create_caixa_view` mínima permitindo a aplicação iniciar
enquanto o arquivo original `caixa/view.py` é reparado.
"""

import flet as ft


def create_caixa_view(
    page: ft.Page,
    pdv_core,
    handle_back,
    handle_logout=None,
    current_user=None,
    appbar: ft.AppBar = None,
):
    content = ft.Column(
        [
            ft.Text("CAIXA (modo temporário — funcionalidades desativadas)", size=20),
            ft.Text("Restaure o arquivo original para recuperar recursos completos."),
            ft.Row([ft.ElevatedButton("Voltar", on_click=lambda e: page.go("/"))]),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )

    view = ft.View("/caixa", [content], bgcolor="white")
    return view
