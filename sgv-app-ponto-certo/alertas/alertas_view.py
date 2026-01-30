"""
View Dedicada para Alertas de Estoque
Exibe todos os alertas com opções de gerenciamento
"""

import flet as ft

from alertas.alertas_components import criar_panel_alertas


def create_alertas_view(page, pdv_core, handle_back):
    """Cria a view de alertas de estoque"""

    COLORS = {
        "text": "#131111",
        "white": "#FFFFFF",
        "primary": "#007BFF",
        "orange": "#FF9800",
        "background": "#FFFFFF",
    }

    # AppBar
    app_bar = ft.AppBar(
        title=ft.Text("ALERTAS DE ESTOQUE", weight=ft.FontWeight.BOLD),
        bgcolor=ft.Colors.ORANGE,
        leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: handle_back()),
    )

    # Criar painel de alertas
    alertas_panel = criar_panel_alertas(page, pdv_core)

    # View
    view = ft.View(
        "/alertas",
        [
            app_bar,
            alertas_panel,
        ],
        padding=0,
        bgcolor=COLORS["background"],
    )

    # Handler para ESC voltar ao painel gerencial
    def on_keyboard(e: ft.KeyboardEvent):
        key_alert = str(e.key).upper() if e.key else ""
        if e.key == "Escape" or key_alert == "ESCAPE":
            handle_back()

    view.on_keyboard_event = on_keyboard

    return view
