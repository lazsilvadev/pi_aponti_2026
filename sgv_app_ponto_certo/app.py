# app.py: ponto de entrada principal do sistema Mercadinho Ponto Certo
#
# Este arquivo inicializa o Flet, configura o banco, gerencia rotas e views.
#
# Principais responsabilidades:
# - Inicializar o banco de dados e regras de negócio (PDVCore)
# - Gerenciar autenticação e sessão do usuário
# - Controlar navegação entre telas (views) usando rotas
# - Montar as views conforme o perfil/rota usando funções fábrica
# - Proteger rotas por perfil (gerente, caixa, estoque, etc.)

import importlib
import sys
import time

import flet as ft

# Garantir stdout em UTF-8 no Windows para evitar UnicodeEncodeError ao imprimir emojis
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from caixa import create_caixa_view
from configuracoes.configuracoes_view import create_configuracoes_view
from core.sgv import PDVCore
from devolucoes.view import create_devolucoes_view
from estoque.view import create_estoque_view
from financeiro.financeiro_view import create_financeiro_view
from fornecedores.view import create_fornecedores_view
from gerencial.gerencial_view import create_gerente_view
from intro.presentation_view import create_presentation_view
from intro.sobre_view import create_sobre_view
from login.login_view import create_login_view
from models.db_models import get_active_pix_settings, get_session, init_db
from produtos.relatorio_produtos import create_relatorio_produtos_view
from vendas.view import create_relatorio_vendas_view

COLORS = {
    "background": "#FFFFFF",
    "primary": "#007BFF",
    "green": "#28A745",
    "red": "#DC3545",
    "orange": "#FFC107",
    "purple": "#6F42C1",
    "text": "#212121",
    "white": "#FFFFFF",
    "button_dark_hover": "#D32F2F",
    "button_dark_pressed": "#B71C1C",
    "teal": "#008080",
    "light_orange": "#FFA726",
}


def main(page: ft.Page):
    page.title = "Mercadinho Ponto Certo"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = COLORS["background"]

    engine = init_db()
    session = get_session(engine)
    pdv_core = PDVCore(session)

    # Carregar configurações do Pix do banco e expor em page.app_data
    try:
        pix_settings = get_active_pix_settings(session)
    except Exception:
        pix_settings = None

    # Expor engine e sessão para permitir views administrativas acessarem o DB
    page.app_data = {
        "pdv_core": pdv_core,
        "pix_settings": pix_settings,
        "engine": engine,
        "db_session": session,
    }

    # Helpers locais para operações seguras com overlays/app_data (reduz repetição)
    def _rm_overlay(ov):
        try:
            if ov and ov in getattr(page, "overlay", []):
                page.overlay.remove(ov)
        except Exception:
            pass

    def _pop_app(key):
        try:
            page.app_data.pop(key, None)
        except Exception:
            pass

    def _append_overlay(ov, key=None):
        try:
            page.overlay.append(ov)
            if key:
                page.app_data[key] = ov
            page.update()
        except Exception:
            pass

    # Carregar configurações persistentes (identidade visual) do arquivo JSON
    try:
        import json
        import os

        # Preferir o caminho de config provido pelo PDVCore (persistente na pasta data do projeto)
        cfg_path = None
        try:
            cfg_path = getattr(pdv_core, "_config_file", None)
        except Exception:
            cfg_path = None
        if not cfg_path:
            cfg_path = os.path.join(os.getcwd(), "data", "app_config.json")

        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                # Popular chaves relevantes em page.app_data para uso pelas views
                page.app_data["site_logo"] = cfg.get("site_logo", "")
                page.app_data["site_slogan"] = cfg.get("site_slogan", "")
                page.app_data["site_pdv_title"] = cfg.get("site_pdv_title", "")
                page.app_data["site_pdv_title_upper"] = cfg.get(
                    "site_pdv_title_upper", False
                )
                # carregar cores personalizáveis se existirem
                try:
                    page.app_data["icon_color"] = (
                        cfg.get("icon_color")
                        or page.app_data.get("icon_color")
                        or "#034986"
                    )
                    page.app_data["login_button_bg"] = (
                        cfg.get("login_button_bg")
                        or page.app_data.get("login_button_bg")
                        or "#034986"
                    )
                    page.app_data["login_button_text_color"] = (
                        cfg.get("login_button_text_color")
                        or page.app_data.get("login_button_text_color")
                        or "#FFFFFF"
                    )
                except Exception:
                    pass
            except Exception:
                # proteger contra json inválido
                pass
    except Exception:
        pass

    # Inicializar sistema de alertas (AlertasManager) para que badges e verificações
    # possam ser atualizados durante a execução da aplicação.
    try:
        from alertas.alertas_init import inicializar_alertas

        try:
            inicializar_alertas(page, pdv_core)
        except Exception:
            # proteger contra falhas na inicialização de alertas
            pass
    except Exception:
        pass

    username_entry = ft.TextField(
        label="Usuário", value="", width=300, prefix_icon=ft.Icons.PERSON
    )
    password_entry = ft.TextField(
        label="Senha",
        value="",
        password=True,
        can_reveal_password=True,
        width=300,
        prefix_icon=ft.Icons.LOCK,
    )

    def show_snackbar(message, color=COLORS["green"]):
        page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=color)
        page.snack_bar.open = True
        page.update()

    def schedule_show_welcome_appbar(display_name, delay=3):
        """Mostra imediatamente a appbar de boas-vindas e restaura após `delay` segundos.

        - Define `page.appbar` com o texto "Bem-vindo(a) - {display_name}" imediatamente.
        - Depois de `delay` segundos, restaura a appbar padrão se o usuário logado ainda
          for o mesmo `display_name`.
        """
        try:
            try:
                # Não exibir se houver pedido de cancelamento (logout ocorreu)
                if not page.app_data.get("welcome_cancelled"):
                    page.appbar = create_appbar(
                        f"Bem-vindo(a) - {display_name}", show_user=True
                    )
                    page.update()
            except Exception:
                pass

            async def _task():
                try:
                    await page.sleep(delay)
                except Exception:
                    pass
                try:
                    # só restaurar se o mesmo usuário continuar logado
                    current = None
                    try:
                        current = page.session.get("user_display_name")
                    except Exception:
                        current = None
                    if current != display_name:
                        return
                except Exception:
                    pass
                try:
                    # só restaurar se não houver pedido de cancelamento
                    if not page.app_data.get("welcome_cancelled"):
                        page.appbar = create_appbar(
                            "MERCADINHO PONTO CERTO", show_user=False
                        )
                        page.update()
                    else:
                        # limpar flag de cancelamento para usos futuros
                        try:
                            page.app_data["welcome_cancelled"] = False
                        except Exception:
                            pass
                except Exception:
                    pass

            try:
                page.run_task(_task)
            except Exception:
                # fallback com threading.Timer
                try:
                    import threading

                    def _f():
                        try:
                            # Restaurar appbar padrão
                            page.appbar = create_appbar(
                                "MERCADINHO PONTO CERTO", show_user=False
                            )
                            page.update()
                        except Exception:
                            pass

                    threading.Timer(delay, _f).start()
                except Exception:
                    pass
        except Exception:
            pass

    def _get_pdv_title(default: str = "MERCADINHO PONTO CERTO") -> str:
        try:
            t = page.app_data.get("site_pdv_title") or default
            if page.app_data.get("site_pdv_title_upper"):
                try:
                    t = t.upper()
                except Exception:
                    pass
            return t
        except Exception:
            return default

    def show_admin_bottom_bar(display_name: str, duration: int = 6):
        """Mostra uma barra flutuante no canto inferior direito com mensagem de boas-vindas.

        - `display_name`: nome do usuário para exibir.
        - `duration`: tempo em segundos para manter a barra visível (None para persistir).
        """
        try:
            # debug: registrar que tentamos exibir a barra de admin
            try:
                print(f"[ADMIN_BAR] show_admin_bottom_bar called for: {display_name}")
                page.app_data["admin_welcome_requested"] = True
            except Exception:
                pass
            # remover barra anterior se existir
            try:
                prev = page.app_data.get("admin_welcome_bar")
                _rm_overlay(prev)
                _pop_app("admin_welcome_bar")
            except Exception:
                pass

            content = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(f"Bem-vindo(a) {display_name}", color=ft.Colors.WHITE),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=16, vertical=10),
                bgcolor=COLORS.get("primary", "#007BFF"),
                border_radius=8,
            )

            overlay = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Column([content], alignment=ft.MainAxisAlignment.END),
                    ],
                    expand=True,
                ),
                expand=True,
                visible=True,
                bgcolor="transparent",
                padding=ft.padding.only(bottom=20, right=20),
            )

            _append_overlay(overlay, "admin_welcome_bar")

            if duration and duration > 0:
                try:

                    async def _hide_after():
                        try:
                            await page.sleep(duration)
                        except Exception:
                            pass
                        try:
                            stored = page.app_data.get("admin_welcome_bar")
                            _rm_overlay(stored)
                            _pop_app("admin_welcome_bar")
                            try:
                                page.update()
                            except Exception:
                                pass
                        except Exception:
                            pass

                    try:
                        page.run_task(_hide_after())
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

    def remove_admin_bottom_bar():
        try:
            stored = page.app_data.get("admin_welcome_bar")
            _rm_overlay(stored)
            _pop_app("admin_welcome_bar")
            try:
                page.update()
            except Exception:
                pass
        except Exception:
            pass

    def handle_login(e):
        user = username_entry.value
        pwd = password_entry.value
        # Check if user exists and requires initial password setup
        try:
            existing_user = pdv_core.get_user_by_username(user)
        except Exception:
            existing_user = None

        if (
            existing_user
            and getattr(existing_user, "password", "") == "__REQUIRE_SET__"
        ):
            # Show dialog to let gerente define password for first time
            new_pwd_field = ft.TextField(label="Nova senha", password=True, width=300)
            confirm_pwd_field = ft.TextField(
                label="Confirmar senha", password=True, width=300
            )

            def do_set_password(evt):
                npwd = new_pwd_field.value or ""
                cpwd = confirm_pwd_field.value or ""
                if not npwd:
                    show_snackbar("Senha não pode ser vazia", COLORS["red"])
                    return
                if npwd != cpwd:
                    show_snackbar("Senhas não conferem", COLORS["red"])
                    return
                ok, msg = pdv_core.update_user_settings(
                    existing_user.id, existing_user.full_name or "", npwd
                )
                if ok:
                    show_snackbar(
                        "Senha definida com sucesso. Faça login.", COLORS["green"]
                    )
                    dialog.open = False
                    page.update()
                else:
                    show_snackbar(f"Erro ao definir senha: {msg}", COLORS["red"])

            dialog = ft.AlertDialog(
                title=ft.Text("Definir senha do gerente"),
                content=ft.Column([new_pwd_field, confirm_pwd_field]),
                actions=[
                    ft.ElevatedButton("OK", on_click=do_set_password),
                    ft.TextButton(
                        "Cancelar",
                        on_click=lambda e: setattr(dialog, "open", False)
                        or page.update(),
                    ),
                ],
                modal=True,
            )
            page.dialog = dialog
            dialog.open = True
            page.update()
            return
        # Primeiro: se o username corresponde a um usuário com role 'caixa', entrar automaticamente
        caixa_user = None
        try:
            caixa_user = next(
                (
                    u
                    for u in pdv_core.get_all_users()
                    if getattr(u, "username", "") == user
                    and getattr(u, "role", "") == "caixa"
                ),
                None,
            )
        except Exception as ex:
            print(f"[LOGIN] erro ao buscar usuários para login automático: {ex}")
            caixa_user = None

        # Só aceitar login automático como 'caixa' se o usuário foi
        # explicitamente selecionado via atalho (marcado em sessão).
        # Preferir flags rápidas em app_data quando disponíveis
        selected_username = None
        selected_autologin = False
        try:
            selected_username = page.app_data.get("login_selected_username")
            selected_autologin = bool(page.app_data.get("login_selected_autologin"))
        except Exception:
            try:
                selected_username = page.session.get("login_selected_username")
                selected_autologin = bool(page.session.get("login_selected_autologin"))
            except Exception:
                selected_username = None
                selected_autologin = False

        # auto-login somente quando a seleção foi explicitamente marcada
        # para auto-login (isto é, seleção de um ícone de 'caixa')
        # Além disso, não disparar auto-login se o usuário digitou alguma senha
        # (pressupõe tentativa de autenticação manual).
        if caixa_user and selected_username == user and selected_autologin and not pwd:
            try:
                page.session.set("user_id", caixa_user.id)
                page.session.set("user_username", caixa_user.username)
                page.session.set("role", "caixa")
                page.session.set(
                    "user_display_name",
                    caixa_user.full_name or caixa_user.username,
                )
                show_snackbar(
                    f"Bem-vindo, {caixa_user.full_name or caixa_user.username}!",
                    COLORS["green"],
                )
                # definir appbar de boas-vindas para o usuário (com atraso)
                try:
                    display_name = caixa_user.full_name or caixa_user.username
                    schedule_show_welcome_appbar(display_name, delay=3)
                    try:
                        # store pending welcome and timestamp so it only appears
                        # shortly after login (avoids showing after logout)
                        page.app_data["pending_welcome_message"] = (
                            f"Bem-vindo(a) - {display_name}"
                        )
                        try:
                            page.app_data["pending_welcome_ts"] = time.time()
                        except Exception:
                            pass
                        # If the login view exposes a bottom-bar helper, call it
                        try:
                            # Só tentar acionar a barra inferior do login se estivermos
                            # na rota de login; caso contrário evitar armazenar
                            # uma mensagem pendente que apareceria ao visitar /login
                            # posteriormente (por exemplo, após logout).
                            if str(page.route or "") == "/login":
                                login_show = page.app_data.get("login_show_bottom_bar")
                                if callable(login_show):
                                    try:
                                        login_show(
                                            f"Bem-vindo(a) - {display_name}",
                                            color=ft.Colors.GREEN_600,
                                        )
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        try:
                            page.snack_bar = ft.SnackBar(
                                ft.Text(f"Bem-vindo(a) - {display_name}"),
                                bgcolor=COLORS.get("green", ft.Colors.GREEN_600),
                                duration=2000,
                            )
                            page.snack_bar.open = True
                        except Exception:
                            pass
                    except Exception:
                        pass
                except Exception:
                    pass
                page.go("/caixa")
                return
            except Exception:
                pass

        # Senão, proceder com autenticação normal
        authenticated_user = pdv_core.authenticate_user(user, pwd)
        if authenticated_user:
            page.session.set("user_id", authenticated_user.id)
            page.session.set("user_username", authenticated_user.username)
            page.session.set("role", authenticated_user.role)
            page.session.set(
                "user_display_name",
                authenticated_user.full_name or authenticated_user.username,
            )
            try:
                print(
                    f"[LOGIN] authenticated_user.role={getattr(authenticated_user, 'role', None)} display_name={getattr(authenticated_user, 'full_name', None)} username={getattr(authenticated_user, 'username', None)}"
                )
            except Exception:
                pass
            show_snackbar(
                f"Bem-vindo, {authenticated_user.full_name}!", COLORS["green"]
            )
            # Garantir que administradores/gerentes recebam a barra de boas-vindas
            try:
                uname = getattr(authenticated_user, "username", "") or ""
                roleval = getattr(authenticated_user, "role", "") or ""
                if uname == "admin" or roleval in ("gerente", "admin"):
                    try:
                        display_name = (
                            authenticated_user.full_name or authenticated_user.username
                        )
                        show_admin_bottom_bar(display_name, duration=6)
                        pass
                    except Exception:
                        pass
            except Exception:
                pass
            # definir appbar de boas-vindas personalizada
            try:
                # NÃO mostrar mensagem de boas-vindas para gerentes/admin
                if getattr(authenticated_user, "role", "") != "gerente":
                    display_name = (
                        authenticated_user.full_name or authenticated_user.username
                    )
                    schedule_show_welcome_appbar(display_name, delay=3)
                    # manter apenas a appbar local da página; não armazenar
                    # versão personalizada para reutilização em outras views
                    try:
                        # armazenar mensagem pendente para ser exibida na próxima view
                        page.app_data["pending_welcome_message"] = (
                            f"Bem-vindo(a) - {display_name}"
                        )
                        try:
                            page.app_data["pending_welcome_ts"] = time.time()
                        except Exception:
                            pass
                        # tentar acionar a barra inferior do login (se disponível)
                        try:
                            if str(page.route or "") == "/login":
                                login_show = page.app_data.get("login_show_bottom_bar")
                                if callable(login_show):
                                    try:
                                        login_show(
                                            f"Bem-vindo(a) - {display_name}",
                                            color=ft.Colors.GREEN_600,
                                        )
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        try:
                            page.snack_bar = ft.SnackBar(
                                ft.Text(f"Bem-vindo(a) - {display_name}"),
                                bgcolor=COLORS.get("green", ft.Colors.GREEN_600),
                                duration=2000,
                            )
                            page.snack_bar.open = True
                        except Exception:
                            pass
                    except Exception:
                        pass
                    else:
                        # para gerentes, mostrar barra no canto inferior direito
                        try:
                            display_name = (
                                authenticated_user.full_name
                                or authenticated_user.username
                            )
                            try:
                                print(
                                    f"[LOGIN] calling show_admin_bottom_bar for {display_name}"
                                )
                            except Exception:
                                pass
                            # também preparar a mensagem pendente e snack para o gerente/admin
                            try:
                                welcome_tuple = (
                                    f"Bem-vindo(a) - {display_name}",
                                    ft.Colors.GREEN_600,
                                    3000,
                                )
                                page.app_data["pending_welcome_message"] = welcome_tuple
                                # garantir que a view do gerente tenha prioridade para exibir
                                try:
                                    page.app_data["gerente_pending_bottom_bar"] = (
                                        welcome_tuple
                                    )
                                except Exception:
                                    pass
                                try:
                                    page.app_data["pending_welcome_ts"] = time.time()
                                except Exception:
                                    pass
                                # se a view de login expõe a barra inferior, acionar
                                try:
                                    if str(page.route or "") == "/login":
                                        login_show = page.app_data.get(
                                            "login_show_bottom_bar"
                                        )
                                        if callable(login_show):
                                            try:
                                                login_show(
                                                    f"Bem-vindo(a) - {display_name}",
                                                    color=ft.Colors.GREEN_600,
                                                )
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                                try:
                                    page.snack_bar = ft.SnackBar(
                                        ft.Text(f"Bem-vindo(a) - {display_name}"),
                                        bgcolor=COLORS.get(
                                            "green", ft.Colors.GREEN_600
                                        ),
                                        duration=2000,
                                    )
                                    page.snack_bar.open = True
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            show_admin_bottom_bar(display_name, duration=6)
                        except Exception as ex:
                            try:
                                print(f"[LOGIN] show_admin_bottom_bar failed: {ex}")
                            except Exception:
                                pass
            except Exception:
                pass
            page.go(f"/{authenticated_user.role}")
        else:
            # Se for Gerente ou Auxiliar de Estoque, exibir a barra inferior de erro
            try:
                attempted_user = None
                try:
                    attempted_user = pdv_core.get_user_by_username(user)
                except Exception:
                    attempted_user = None

                role = getattr(attempted_user, "role", None) if attempted_user else None
                if role in ("gerente", "estoque"):
                    try:
                        login_show = page.app_data.get("login_show_bottom_bar")
                        if callable(login_show):
                            login_show("Senha inválida", color=ft.Colors.RED_600)
                        else:
                            show_snackbar("Usuário ou senha inválidos!", COLORS["red"])
                    except Exception:
                        show_snackbar("Usuário ou senha inválidos!", COLORS["red"])
                else:
                    show_snackbar("Usuário ou senha inválidos!", COLORS["red"])
            except Exception:
                show_snackbar("Usuário ou senha inválidos!", COLORS["red"])

    def handle_logout(e=None):
        # Se o usuário é gerente e está na rota /caixa, navegar para o painel
        # gerencial em vez de efetuar logout (clique no ícone Sair pelo admin).
        try:
            role = None
            try:
                role = page.session.get("role")
            except Exception:
                role = None
            if str(role or "").lower() == "gerente" and str(
                page.route or ""
            ).startswith("/caixa"):
                try:
                    page.go("/gerente")
                except Exception:
                    try:
                        page.push_route("/gerente")
                    except Exception:
                        pass
                return
        except Exception:
            pass

        # Limpar sessão e também limpar qualquer seleção/flag de auto-login
        try:
            page.session.clear()
        except Exception:
            try:
                page.session = {}
            except Exception:
                pass

        # Garantir que não fique nenhum usuário pré-selecionado para auto-login
        try:
            page.session.set("login_selected_username", None)
            page.session.set("login_selected_autologin", False)
        except Exception:
            pass
        try:
            page.app_data["login_selected_username"] = None
            page.app_data["login_selected_autologin"] = False
        except Exception:
            pass

        # Limpar campos do formulário de login para forçar digitação de senha
        try:
            username_entry.value = ""
            username_entry.disabled = False
            password_entry.value = ""
            password_entry.disabled = False
            try:
                username_entry.update()
                password_entry.update()
            except Exception:
                pass
        except Exception:
            pass

        # limpar mensagens pendentes de boas-vindas para evitar aparecimento após logout
        try:
            page.app_data["pending_welcome_message"] = None
        except Exception:
            pass
        try:
            page.app_data["pending_welcome_ts"] = None
        except Exception:
            pass
        try:
            page.app_data["login_pending_bottom_bar"] = None
        except Exception:
            pass
        try:
            page.app_data["login_show_bottom_bar"] = None
        except Exception:
            pass
        try:
            # remover barra de admin se existir
            remove_admin_bottom_bar()
        except Exception:
            pass
        try:
            page.app_data["welcome_cancelled"] = True
        except Exception:
            pass
        # garantir que os campos de login não mantenham valor de senha
        try:
            password_entry.value = ""
            password_entry.password = True
            try:
                password_entry.can_reveal_password = False
            except Exception:
                pass
            try:
                password_entry.update()
            except Exception:
                pass
        except Exception:
            pass

        # restaurar appbar padrão (Mercadinho) ao sair
        try:
            page.appbar = create_appbar(_get_pdv_title(), show_user=False)
            page.update()
        except Exception:
            pass

        # Remover quaisquer overlays/dialogs abertos antes de navegar para login
        try:
            overlays = list(getattr(page, "overlay", []) or [])
            for ov in reversed(overlays):
                try:
                    try:
                        # tentar fechar modal se expõe 'open' ou 'visible'
                        if getattr(ov, "open", False):
                            try:
                                ov.open = False
                            except Exception:
                                pass
                        if getattr(ov, "visible", False):
                            try:
                                ov.visible = False
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        if ov in getattr(page, "overlay", []):
                            page.overlay.remove(ov)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

        page.go("/login")

    # ✅ FUNÇÃO SEPARADA para evitar lambda dentro do route_change
    def voltar_para_gerente(e):
        try:
            # Fechar dialog padrão se estiver aberto
            try:
                dlg = getattr(page, "dialog", None)
                if dlg is not None and getattr(dlg, "open", False):
                    try:
                        dlg.open = False
                    except Exception:
                        pass
                    try:
                        page.dialog = None
                    except Exception:
                        pass
            except Exception:
                pass

            # Remover overlays pendentes (fechar visíveis/open)
            try:
                overlays = list(getattr(page, "overlay", []) or [])
                for ov in reversed(overlays):
                    try:
                        if getattr(ov, "open", False) or getattr(ov, "visible", False):
                            try:
                                ov.open = False
                            except Exception:
                                pass
                            try:
                                ov.visible = False
                            except Exception:
                                pass
                            try:
                                if ov in getattr(page, "overlay", []):
                                    page.overlay.remove(ov)
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass
        page.go("/gerente")

    def create_appbar(title_text, show_user=True):
        # title_text esperado: "Mercadinho Ponto Certo - Nome do Usuário"
        try:
            if "-" in title_text:
                loja, usuario = [p.strip() for p in title_text.split("-", 1)]
            else:
                loja, usuario = title_text, ""

            # Mostrar o nome da loja com espaçamento normal e tamanho maior
            # para ocupar melhor o espaço do AppBar de forma profissional.
            if show_user and usuario:
                title_column = ft.Column(
                    [
                        ft.Container(
                            content=ft.Text(
                                loja,
                                size=34,
                                weight="bold",
                                text_align="center",
                                color="#0D47A1",
                                max_lines=1,
                            ),
                            expand=True,
                            padding=ft.padding.symmetric(horizontal=40),
                        ),
                        ft.Text(
                            usuario,
                            size=14,
                            text_align="center",
                        ),
                    ],
                    alignment="center",
                    horizontal_alignment="center",
                )
            else:
                title_column = ft.Container(
                    content=ft.Text(
                        loja,
                        size=34,
                        weight="bold",
                        text_align="center",
                        color="#0D47A1",
                        max_lines=1,
                    ),
                    expand=True,
                    padding=ft.padding.symmetric(horizontal=40),
                )

            return ft.AppBar(
                title=title_column,
                center_title=True,
                bgcolor=ft.Colors.GREY_100,
                actions=[
                    ft.IconButton(
                        icon=ft.Icons.LOGOUT,
                        tooltip="Sair [ESC]",
                        on_click=handle_logout,
                    )
                ],
            )
        except Exception as e:
            print(f"❌ ERRO CRÍTICO em create_appbar: {e}")
            return ft.AppBar(title=ft.Text("ERRO"))

    # Expor fábrica de appbar para uso dinâmico por outras views
    try:
        page.app_data["create_appbar"] = create_appbar
    except Exception:
        pass

    def route_change(route):
        print(f"🔄 Rota alterada para: {page.route}")
        page.views.clear()

        if page.route == "/":
            try:
                page.views.append(create_presentation_view(page))
            except Exception:
                page.views.append(
                    create_login_view(
                        page, username_entry, password_entry, handle_login, COLORS
                    )
                )
        elif page.route == "/login":
            page.views.append(
                create_login_view(
                    page, username_entry, password_entry, handle_login, COLORS
                )
            )
        elif page.route == "/sobre":
            # Tela Sobre é pública e acessível sem autenticação
            try:
                page.views.append(
                    create_sobre_view(page, handle_back=lambda e: page.go("/login"))
                )
            except Exception as ex:
                print(f"❌ Erro ao criar view /sobre: {ex}")
                page.views.append(
                    create_login_view(
                        page, username_entry, password_entry, handle_login, COLORS
                    )
                )
        else:
            user = page.session.get("user_username")
            role = page.session.get("role")

            if not user:
                page.go("/login")
                return

            # ✅ PROTEÇÃO DE ROTA
            if page.route.startswith("/gerente") and role != "gerente":
                show_snackbar("Acesso negado! Apenas gerente.", COLORS["red"])
                page.go(f"/{role}")
                return

            # =============================
            # FÁBRICA DE VIEWS (funções fábrica)
            # =============================
            # Cada rota tem uma função que monta a tela correspondente.
            # Isso facilita a organização e evita duplicação de código.
            # Se o usuário logado for o atalho 'estoque1', o botão de voltar da
            # view de Estoque deve levar ao login. Caso contrário, volta para gerente.
            try:
                _username_for_estoque_back = (
                    (page.session.get("user_username") or "").strip().lower()
                )
            except Exception:
                _username_for_estoque_back = ""

            estoque_voltar_cb = (
                (lambda e: page.go("/login"))
                if _username_for_estoque_back == "estoque1"
                else voltar_para_gerente
            )

            fabrica_de_views = {
                "/gerente": lambda: create_gerente_view(
                    page.session.get("user_display_name"), page, handle_logout
                ),
                "/estoque": lambda: create_estoque_view(
                    page=page, voltar_callback=estoque_voltar_cb
                ),
                "/gerente/relatorio_produtos": lambda: create_relatorio_produtos_view(
                    page=page, pdv_core=pdv_core, handle_back=voltar_para_gerente
                ),
                "/gerente/relatorio_vendas": lambda: create_relatorio_vendas_view(
                    page=page, pdv_core=pdv_core, handle_back=voltar_para_gerente
                ),
                "/gerente/configuracoes": lambda: create_configuracoes_view(
                    page=page,
                    user_id_obj_do_gerente_logado=page.session.get("user_id"),
                    handle_back=voltar_para_gerente,
                ),
                "/gerente/pix_settings": lambda: importlib.import_module(
                    "configuracoes.pix_settings_view"
                ).create_pix_settings_view(page=page, handle_back=voltar_para_gerente),
                "/gerente/fornecedores": lambda: create_fornecedores_view(
                    page=page, pdv_core=pdv_core, handle_back=voltar_para_gerente
                ),
                "/gerente/devolucoes": lambda: create_devolucoes_view(
                    page=page, pdv_core=pdv_core, handle_back=voltar_para_gerente
                ),
                "/caixa": lambda: create_caixa_view(
                    page=page,
                    pdv_core=pdv_core,
                    handle_back=voltar_para_gerente,
                    current_user=page.session.get("user_display_name"),
                    appbar=create_appbar(
                        f"{_get_pdv_title()} - {page.session.get('user_display_name') or ''}",
                        show_user=False,
                    ),
                ),
                "/financeiro": lambda: create_financeiro_view(
                    page=page,
                    pdv_core=pdv_core,
                    handle_back=voltar_para_gerente,
                    create_appbar=create_appbar,
                ),
            }

            # ✅ RESTRIÇÕES EXPLÍCITAS POR ROTA
            if page.route == "/caixa" and role not in ("caixa", "gerente"):
                show_snackbar(
                    "Acesso negado! Apenas caixas podem acessar o Caixa.", COLORS["red"]
                )
                page.go(f"/{role}")
                return

            if page.route == "/estoque" and role not in ("estoque", "gerente"):
                show_snackbar(
                    "Acesso negado! Apenas estoque pode acessar.", COLORS["red"]
                )
                page.go(f"/{role}")
                return

            # ✅ RESTRIÇÃO DE ACESSO PARA FINANCEIRO
            if page.route == "/financeiro" and role not in ["gerente", "estoque"]:
                show_snackbar("Acesso negado a Financeiro.", COLORS["red"])
                page.go(f"/{role}")
                return

            # =============================
            # Fim da fábrica de views
            # =============================

            # Carrega a view da rota usando a função fábrica
            if page.route in fabrica_de_views:
                try:
                    # Garantir que quaisquer dialogs/overlays ativos sejam fechados
                    try:
                        dlg = getattr(page, "dialog", None)
                        if dlg is not None and getattr(dlg, "open", False):
                            try:
                                dlg.open = False
                            except Exception:
                                pass
                            try:
                                page.dialog = None
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        overlays = list(getattr(page, "overlay", []) or [])
                        for ov in reversed(overlays):
                            try:
                                if getattr(ov, "open", False) or getattr(
                                    ov, "visible", False
                                ):
                                    try:
                                        ov.open = False
                                    except Exception:
                                        pass
                                    try:
                                        ov.visible = False
                                    except Exception:
                                        pass
                                    try:
                                        if ov in getattr(page, "overlay", []):
                                            page.overlay.remove(ov)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                    except Exception:
                        pass

                    view = fabrica_de_views[page.route]()
                    if view is None:
                        print(f"❌ Função fábrica retornou None para {page.route}")
                        view = ft.View(
                            page.route,
                            [ft.Text(f"Erro: View {page.route} é None")],
                            appbar=create_appbar(
                                f"{_get_pdv_title()} - {page.session.get('user_display_name')}"
                            ),
                        )
                        try:
                            # também ligar o handler global de teclado à view de erro
                            view.on_keyboard_event = handle_keyboard
                        except Exception:
                            pass
                    page.views.append(view)
                    # Se houver mensagem de boas-vindas pendente do login,
                    # exibir na nova view (barra inferior ou snackbar)
                    try:
                        pending = page.app_data.pop("pending_welcome_message", None)
                        pending_ts = page.app_data.pop("pending_welcome_ts", None)
                        # Mostrar apenas se a mensagem for recente (5s) para evitar
                        # reaparecer após logout ou em visitas posteriores.
                        show_pending = False
                        try:
                            if pending and pending_ts:
                                import time as _time

                                if float(pending_ts) + 5 >= _time.time():
                                    show_pending = True
                        except Exception:
                            show_pending = False

                        if pending and show_pending:
                            try:
                                # Preferir helper da view se disponível
                                if hasattr(page, "show_bottom_status") and callable(
                                    page.show_bottom_status
                                ):
                                    try:
                                        page.show_bottom_status(
                                            pending,
                                            COLORS.get("green", ft.Colors.GREEN_600),
                                        )
                                    except Exception:
                                        pass
                                else:
                                    # fallback para snackbar global
                                    try:
                                        page.snack_bar = ft.SnackBar(
                                            ft.Text(pending),
                                            bgcolor=COLORS.get(
                                                "green", ft.Colors.GREEN_600
                                            ),
                                            duration=3000,
                                        )
                                        page.snack_bar.open = True
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # Se a view expõe função de recarregar dados, disparar após montagem
                    try:
                        # Fornecedores (recebe argumento de busca)
                        if page.route == "/gerente/fornecedores" and hasattr(
                            view, "load_fornecedores_table"
                        ):
                            print(
                                "[APP] Agendando load_fornecedores_table na view de fornecedores"
                            )

                            async def _call_load_f():
                                try:
                                    await page.sleep(0.12)
                                except Exception:
                                    pass
                                try:
                                    getattr(view, "load_fornecedores_table")("")
                                except Exception:
                                    pass

                            try:
                                page.run_task(_call_load_f)
                            except Exception:
                                try:
                                    getattr(view, "load_fornecedores_table")("")
                                except Exception:
                                    pass

                        # Relatório de Produtos
                        if page.route == "/gerente/relatorio_produtos" and hasattr(
                            view, "load_data"
                        ):
                            print(
                                "[APP] Agendando load_data na view Relatório de Produtos"
                            )

                            async def _call_relprod():
                                try:
                                    await page.sleep(0.12)
                                except Exception:
                                    pass
                                try:
                                    getattr(view, "load_data")()
                                except Exception:
                                    pass

                            try:
                                page.run_task(_call_relprod)
                            except Exception:
                                try:
                                    getattr(view, "load_data")()
                                except Exception:
                                    pass

                        # Relatório de Vendas
                        if page.route == "/gerente/relatorio_vendas" and hasattr(
                            view, "load_data"
                        ):
                            print(
                                "[APP] Agendando load_data na view Relatório de Vendas"
                            )

                            async def _call_vendas():
                                try:
                                    await page.sleep(0.12)
                                except Exception:
                                    pass
                                try:
                                    getattr(view, "load_data")()
                                except Exception:
                                    pass

                            try:
                                page.run_task(_call_vendas)
                            except Exception:
                                try:
                                    getattr(view, "load_data")()
                                except Exception:
                                    pass

                        # Devoluções
                        if page.route == "/gerente/devolucoes" and hasattr(
                            view, "load_data"
                        ):
                            print("[APP] Agendando load_data na view Devoluções")

                            async def _call_devol():
                                try:
                                    await page.sleep(0.12)
                                except Exception:
                                    pass
                                try:
                                    getattr(view, "load_data")()
                                except Exception:
                                    pass

                            try:
                                page.run_task(_call_devol)
                            except Exception:
                                try:
                                    getattr(view, "load_data")()
                                except Exception:
                                    pass
                    except Exception:
                        pass
                except Exception as ex:
                    import traceback

                    print(f"❌ Exceção ao criar view {page.route}: {ex}")
                    print(traceback.format_exc())
                    page.views.append(
                        ft.View(
                            page.route,
                            [
                                ft.Text(
                                    "Erro ao carregar view:",
                                    color=ft.Colors.RED,
                                    weight="bold",
                                ),
                                ft.Text(f"{ex}", color=ft.Colors.RED),
                            ],
                            appbar=create_appbar(
                                f"{_get_pdv_title()} - {page.session.get('user_display_name')}"
                            ),
                        )
                    )

            else:
                # Rota não encontrada
                page.views.append(
                    ft.View(
                        page.route,
                        [
                            ft.Text(
                                f"Rota '{page.route}' não encontrada",
                                color=ft.Colors.RED,
                            )
                        ],
                        appbar=create_appbar(
                            f"{_get_pdv_title()} - {page.session.get('user_display_name')}"
                        ),
                    )
                )

        # ✅ VERIFICAÇÃO FINAL antes de update
        if not page.views or page.views[-1] is None:
            print("❌ ERRO CRÍTICO: Nenhuma view válida para exibir!")
            page.views.clear()
            page.views.append(
                ft.View(
                    "/",
                    [ft.Text("Erro crítico: Nenhuma view válida", color=ft.Colors.RED)],
                )
            )

        page.update()
        # Garantir que os eventos de teclado passem pelo handler da view e pelo handler global
        try:

            def _page_combined_key(e: ft.KeyboardEvent):
                try:
                    # Se a tecla ESC foi pressionada, primeiro tentar fechar qualquer
                    # modal/dialog/overlay global (comportamento universal).
                    key_upper = (str(getattr(e, "key", "") or "") or "").upper()
                    if key_upper in ("ESCAPE", "ESC"):
                        try:
                            # Fechar page.dialog se aberto
                            if getattr(page, "dialog", None) is not None and getattr(
                                page.dialog, "open", False
                            ):
                                try:
                                    # preferencialmente sinalizar como fechado
                                    page.dialog.open = False
                                except Exception:
                                    pass
                                try:
                                    # esconder visualmente e remover do overlay se necessário
                                    if (
                                        getattr(page.dialog, "visible", None)
                                        is not None
                                    ):
                                        try:
                                            page.dialog.visible = False
                                        except Exception:
                                            pass
                                    try:
                                        if page.dialog in getattr(page, "overlay", []):
                                            page.overlay.remove(page.dialog)
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                                try:
                                    e.handled = True
                                except Exception:
                                    pass
                                # tentar limpar overlays appended/dim para evitar tela cinza
                                try:
                                    overlays = getattr(page, "overlay", None) or []
                                    for ov in list(overlays):
                                        try:
                                            if (not getattr(ov, "visible", True)) or (
                                                not getattr(ov, "open", True)
                                            ):
                                                try:
                                                    if ov in getattr(
                                                        page, "overlay", []
                                                    ):
                                                        page.overlay.remove(ov)
                                                except Exception:
                                                    pass
                                                continue
                                            bg = getattr(ov, "bgcolor", None)
                                            if (
                                                isinstance(bg, str)
                                                and "rgba" in bg.lower()
                                            ):
                                                try:
                                                    if ov in getattr(
                                                        page, "overlay", []
                                                    ):
                                                        page.overlay.remove(ov)
                                                except Exception:
                                                    pass
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                page.update()
                                return
                        except Exception:
                            pass

                        try:
                            # Fechar qualquer overlay visível (DatePickers, custom overlays, etc.)
                            overlays = getattr(page, "overlay", None)
                            if overlays:
                                # iterar em cópia para evitar mutação durante iteração
                                for ov in list(overlays):
                                    try:
                                        if getattr(ov, "visible", False):
                                            ov.visible = False
                                            try:
                                                e.handled = True
                                            except Exception:
                                                pass
                                            page.update()
                                            return
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                    # chama handler específico da view se existir
                    if page.views:
                        current_view = page.views[-1]
                        vh = getattr(current_view, "on_keyboard_event", None)
                        if callable(vh):
                            vh(e)
                        # compatibilidade com nome alternativo
                        alt = getattr(current_view, "handle_keyboard_shortcuts", None)
                        if callable(alt):
                            alt(e)
                except Exception:
                    pass
                try:
                    # Log do estado do evento após handler da view
                    try:
                        print(
                            f"[COMBINED] after view handler e.handled={getattr(e, 'handled', False)} route={page.route}"
                        )
                    except Exception:
                        pass
                    # Se o evento já foi marcado como consumido pela view, não chamar o handler global
                    if not getattr(e, "handled", False):
                        handle_keyboard(e)
                    else:
                        try:
                            print(
                                "[COMBINED] evento consumido pela view; pulando handle_keyboard"
                            )
                        except Exception:
                            pass
                except Exception:
                    pass

            page.on_keyboard_event = _page_combined_key
        except Exception:
            pass

    def handle_keyboard(e: ft.KeyboardEvent):
        # Atalhos globais de ESC para navegação/logout
        # Se a view do Caixa fechou recentemente um modal, ignorar este ESC global
        try:
            last = page.app_data.get("caixa_last_modal_closed_ts", 0)
            if last and (time.time() - float(last) < 0.6):
                return
        except Exception:
            pass
        # Se a view de Estoque fechou recentemente um modal, ignorar este ESC global
        try:
            last_est = page.app_data.get("estoque_last_modal_closed_ts", 0)
            if last_est and (time.time() - float(last_est) < 0.6):
                return
        except Exception:
            pass
        # Se a view de Estoque setou a flag preventiva (fechou modal agora), ignorar ESC
        try:
            if page.app_data.get("estoque_prevent_esc_nav"):
                return
        except Exception:
            pass
        # Nunca deixar o ESC global tirar a aplicação da tela do Caixa;
        # a própria view do Caixa deve controlar ESC para fechar modais.
        try:
            if str(page.route or "").startswith("/caixa"):
                return
        except Exception:
            pass
        try:
            print(
                f"[GLOBAL-KEY] Received key='{e.key}' on route='{page.route}' views={len(page.views)}"
            )
        except Exception:
            pass
        key_upper = (str(e.key) or "").upper()
        if key_upper in ("ESCAPE", "ESC"):
            role = page.session.get("role")
            username = page.session.get("user_username")

            # Forçar retorno ao Painel Gerencial para rotas principais desejadas
            try:
                route = str(page.route or "")
                special_routes = [
                    "/caixa",
                    "/estoque",
                    "/financeiro",
                    "/gerente/relatorio_produtos",
                    "/gerente/relatorio_vendas",
                    "/gerente/fornecedores",
                    "/gerente/devolucoes",
                    "vendas",
                    "fornecedores",
                    "devolucoes",
                ]
                if route != "/gerente" and (
                    route.startswith("/gerente")
                    or any(r in route for r in special_routes)
                ):
                    voltar_para_gerente(None)
                    return
            except Exception:
                pass

            # Mostrar feedback visual rápido para depuração (o usuário verá na tela)
            try:
                page.snack_bar = ft.SnackBar(
                    ft.Text(
                        f"Tecla ESC detectada (rota: {page.route})",
                        color=ft.Colors.WHITE,
                    ),
                    bgcolor=ft.Colors.BLUE_600,
                )
                page.snack_bar.open = True
                page.update()
            except Exception:
                pass

            # Gerente: sempre volta para o painel gerencial, nunca para login
            if role == "gerente":
                if page.route != "/gerente":
                    voltar_para_gerente(None)

            # Caixa1, Auxiliar de Estoque e usuário específico 'estoque1': ESC faz logout e volta para login
            elif str(username) in ("Caixa1", "Auxiliar de Estoque", "estoque1"):
                if page.route not in ["/login", "/"]:
                    # Especial: para o usuário 'estoque1' garantir que qualquer
                    # mensagem de boas-vindas seja cancelada imediatamente
                    try:
                        if str(username) == "estoque1":
                            try:
                                page.app_data["pending_welcome_message"] = None
                            except Exception:
                                pass
                            try:
                                page.app_data["pending_welcome_ts"] = None
                            except Exception:
                                pass
                            try:
                                page.app_data["login_pending_bottom_bar"] = None
                            except Exception:
                                pass
                            try:
                                page.app_data["login_show_bottom_bar"] = None
                            except Exception:
                                pass
                            try:
                                page.app_data["welcome_cancelled"] = True
                            except Exception:
                                pass
                            try:
                                page.appbar = create_appbar(
                                    _get_pdv_title(), show_user=False
                                )
                                page.update()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    handle_logout()

            # Demais perfis: mantém comportamento padrão anterior
            else:
                if (
                    page.route.startswith("/gerente/")
                    or page.route == "/caixa"
                    or page.route == "/estoque"
                ):
                    voltar_para_gerente(None)
                elif page.route not in ["/login", "/"]:
                    handle_logout()

            return

        # Atalhos específicos da tela do caixa (F1–F12, etc.)
        if page.route == "/caixa" and page.views:
            current_view = page.views[-1]
            # A view do caixa expõe um handler interno chamado handle_keyboard_shortcuts
            handler = getattr(current_view, "handle_keyboard_shortcuts", None)
            if callable(handler):
                handler(e)
                return

    page.on_keyboard_event = handle_keyboard
    page.on_route_change = route_change
    page.go(page.route if page.route else "/")

    # Botão de depuração: simula pressionar ESC (visível enquanto app em desenvolvimento)
    def _simulate_esc_click(e=None):
        try:
            print("[DEBUG] simulate ESC button clicked")

            class _Evt:
                def __init__(self, key):
                    self.key = key

            evt = _Evt("Escape")
            # Preferir chamar o handler combinado se disponível (passa pela view primeiro)
            try:
                if callable(getattr(page, "on_keyboard_event", None)):
                    page.on_keyboard_event(evt)
                else:
                    handle_keyboard(evt)
            except Exception:
                try:
                    handle_keyboard(evt)
                except Exception:
                    pass
        except Exception as ex:
            print(f"[DEBUG] simulate ESC failed: {ex}")

    try:
        page.floating_action_button = ft.FloatingActionButton(
            icon=ft.icons.BUG_REPORT,
            on_click=_simulate_esc_click,
            tooltip="Simular ESC",
        )
    except Exception:
        pass
    # (debug) não iniciar simulação automática aqui em produção


ft.app(
    target=main, assets_dir="assets"
)  # , view=ft.AppView.WEB_BROWSER) ---run in browser
