import asyncio
from datetime import datetime

import flet as ft

from utils.path_resolver import get_asset_path


def create_splash_screen(page: ft.Page) -> ft.View:
    """Cria uma tela de apresentação elegante ao iniciar a aplicação"""

    # Forçar apresentação em modo claro (padrão de exibição)
    try:
        page.theme_mode = ft.ThemeMode.LIGHT
    except Exception:
        pass

    # Cores para modo claro
    PRIMARY_COLOR = "#007BFF"
    BACKGROUND = "#F0F4F8"
    TEXT_COLOR = "#2D3748"

    # Criar componentes com referências para animação
    title_ref = ft.Ref[ft.Text]()
    subtitle_ref = ft.Ref[ft.Text]()
    logo_ref = ft.Ref[ft.Container]()
    progress_ref = ft.Ref[ft.ProgressRing]()
    status_ref = ft.Ref[ft.Text]()

    def create_animated_logo():
        """Cria o logo com imagem da marca (formato original)"""
        return ft.Container(
            ref=logo_ref,
            width=200,
            height=200,
            content=ft.Image(
                src=get_asset_path("Mercadinho_Ponto_Certo.png"),
                width=200,
                height=200,
                fit=ft.ImageFit.CONTAIN,
            ),
            scale=ft.Scale(0.3),
            opacity=0,
            animate_scale=ft.Animation(1500, ft.AnimationCurve.EASE_OUT),
            animate_opacity=ft.Animation(1500, ft.AnimationCurve.EASE_OUT),
        )

    try:
        page.bgcolor = BACKGROUND
    except Exception:
        pass

    splash_view = ft.View(
        route="/splash",
        bgcolor=BACKGROUND,
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(
                expand=True,
                content=ft.Column(
                    [
                        ft.Container(height=20),
                        # Logo animado
                        create_animated_logo(),
                        ft.Container(height=30),
                        # Título principal - REMOVIDO
                        # ft.Text(
                        #     ref=title_ref,
                        #     value="Mercadinho Ponto Certo",
                        #     size=42,
                        #     weight=ft.FontWeight.BOLD,
                        #     color=TEXT_COLOR,
                        #     text_align=ft.TextAlign.CENTER,
                        #     opacity=0,
                        # ),
                        ft.Container(height=10),
                        # Subtítulo
                        ft.Text(
                            ref=subtitle_ref,
                            value="Sistema de Gestão Integrado",
                            size=16,
                            color="#000000",
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                            opacity=0,
                        ),
                        ft.Container(height=40),
                        # Indicador de progresso
                        ft.Container(
                            content=ft.ProgressRing(
                                ref=progress_ref,
                                color="#28A745",
                                stroke_width=4,
                                width=50,
                                height=50,
                            ),
                            alignment=ft.alignment.center,
                        ),
                        ft.Container(height=20),
                        # Status text
                        ft.Text(
                            ref=status_ref,
                            value="Carregando...",
                            size=12,
                            color="#000000",
                            text_align=ft.TextAlign.CENTER,
                            opacity=1.0,
                        ),
                        ft.Container(height=20),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                ),
                alignment=ft.alignment.center,
                padding=40,
            ),
            # Rodapé com versão
            ft.Container(
                content=ft.Text(
                    "v1.0.0 • 2025",
                    size=10,
                    color="#000000",
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.alignment.bottom_center,
                padding=20,
            ),
        ],
    )

    async def animate_splash():
        """Anima os elementos da tela de apresentação e navega para login"""
        messages = [
            "Inicializando...",
            "Carregando banco de dados...",
            "Verificando permissões...",
            "Preparando interface...",
            "Quase pronto...",
        ]

        # Aguardar um pouco para os controles serem renderizados
        await asyncio.sleep(0.5)

        # Animar logo com entrada suave
        if logo_ref.current:
            logo_ref.current.scale = ft.Scale(1.0)
            logo_ref.current.opacity = 1
            page.update()

        await asyncio.sleep(0.5)

        # Animar título
        if title_ref.current:
            title_ref.current.opacity = 1
            page.update()

        # Animar subtítulo
        await asyncio.sleep(0.3)
        if subtitle_ref.current:
            subtitle_ref.current.opacity = 1
            page.update()

        # Atualizar mensagens de status
        for i, msg in enumerate(messages):
            if status_ref.current:
                status_ref.current.value = msg
                page.update()
            await asyncio.sleep(0.6)

        # Determinar rota de retorno: permite reproduzir a apresentação
        # e voltar para uma rota específica (ex.: /sobre). Padrão: /login
        return_route = None
        try:
            return_route = page.app_data.get("presentation_return_route")
        except Exception:
            return_route = None
        if not return_route:
            return_route = "/login"
        # limpar chave para usos futuros
        try:
            page.app_data.pop("presentation_return_route", None)
        except Exception:
            pass
        # Navegar para a rota de retorno após animação
        if hasattr(page, "push_route"):
            try:
                await page.push_route(return_route)
            except TypeError:
                page.push_route(return_route)
        else:
            try:
                page.go(return_route)
            except Exception:
                pass

    # Executar animação em background (compatibilidade com versões do Flet)
    try:
        if hasattr(page, "run_task") and callable(page.run_task):
            page.run_task(animate_splash)
        else:
            # Fallback: tentar agendar com asyncio (usar import global)
            try:
                asyncio.create_task(animate_splash())
            except Exception:
                # Último fallback: executar de forma síncrona com pequenos sleeps
                # (pode não animar suavemente, mas garante navegação para login)
                async def _sync_wrapper():
                    await animate_splash()

                try:
                    asyncio.run(_sync_wrapper())
                except Exception:
                    pass
    except Exception:
        pass

    return splash_view


# Compatibilidade com app.py: função esperada `create_presentation_view`
def create_presentation_view(page: ft.Page, on_continue=None, COLORS=None) -> ft.View:
    """
    Wrapper de compatibilidade que retorna a tela de splash.
    O parâmetro on_continue é ignorado pois a tela já avança automaticamente
    para o login após a animação.
    """
    return create_splash_screen(page)
