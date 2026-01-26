import flet as ft

from utils.path_resolver import get_asset_path

COLORS = {
    "primary": "#034986",
    "text_primary": "#0D47A1",
    "text_secondary": "#636E72",
    "surface": "#FFFFFF",
    "background": "#F0F4F8",
}


def create_sobre_view(page: ft.Page, handle_back=None):
    """View de Sobre o Sistema com créditos e contexto do projeto."""

    def _voltar(_):
        try:
            if callable(handle_back):
                handle_back(_)
            else:
                page.go("/login")
        except Exception:
            page.route = "/login"
            page.update()

    # Removida faixa superior (AppBar) para manter tela limpa

    # Logo com ref para permitir atualização dinâmica
    logo_ref = ft.Ref[ft.Image]()
    logo = ft.Image(
        ref=logo_ref,
        src=page.app_data.get("site_logo")
        or get_asset_path("Mercadinho_Ponto_Certo.png"),
        width=220,
        height=220,
        fit=ft.ImageFit.CONTAIN,
    )

    def section_title(t: str) -> ft.Text:
        return ft.Text(
            t,
            size=18,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.BLACK,
            text_align=ft.TextAlign.CENTER,
        )

    def section_text(t: str) -> ft.Text:
        return ft.Text(
            t,
            size=13,
            color=COLORS["text_secondary"],
            text_align=ft.TextAlign.CENTER,
        )

    content = ft.Container(
        content=ft.Column(
            [
                ft.Row([logo], alignment=ft.MainAxisAlignment.CENTER),
                section_title("Projeto"),
                section_text("Sistema desenvolvido para a empresa Aponti."),
                ft.Container(height=6),
                section_title("Equipe"),
                section_text("Grupo: Loyola Devs."),
                section_text("Desenvolvimento do sistema: Lays Silva."),
                section_text("Demais integrantes: documentação e suporte."),
                ft.Container(height=6),
                section_title("Versão"),
                section_text("v1.0.0 • 2025"),
                ft.Container(height=12),
                ft.Row(
                    [
                        ft.TextButton(
                            content=ft.Text("❮", size=20, color=COLORS["primary"]),
                            tooltip="Voltar ao Login",
                            on_click=_voltar,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.TRANSPARENT,
                                overlay_color=ft.Colors.GREY_200,
                            ),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.START,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=16,
        # Fundo transparente para que o laranja do login apareça
        bgcolor=ft.Colors.TRANSPARENT,
        # Remover borda/cartão para manter estética do login
        border=None,
        border_radius=None,
    )

    # (refresh moved to login view)

    view = ft.View(
        "/sobre",
        [
            ft.Container(content=content, expand=True, bgcolor=COLORS["background"]),
        ],
        bgcolor=COLORS["background"],
        padding=0,
    )
    # Expor ref para permitir atualização imediata pela Configurações
    try:
        page.app_data["sobre_site_logo_ref"] = logo_ref
    except Exception:
        pass
    return view
