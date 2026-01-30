import flet as ft

from utils.path_resolver import get_asset_path


def create_login_view(page, username_entry, password_entry, handle_login, COLORS):
    # Logo central (ref para atualização dinâmica)
    logo_ref = ft.Ref[ft.Image]()
    logo = ft.Image(
        ref=logo_ref,
        src=page.app_data.get("site_logo")
        or get_asset_path("Mercadinho_Ponto_Certo.png"),
        width=250,
        height=250,
        fit=ft.ImageFit.CONTAIN,
    )

    # (Removido) Slogan abaixo do logo

    # Forçar modo claro no login
    is_dark = False

    # cores vindas de app_data (configurações) -> fallback para valores antigos
    ICON_COLOR = page.app_data.get("icon_color") or (
        "#90CAF9" if is_dark else "#034986"
    )
    PRIMARY_COLOR = ICON_COLOR
    TEXT_COLOR = "#E6EEF8" if is_dark else "#0D47A1"
    BG_COLOR = "#0B1220" if is_dark else "#F0F4F8"
    LOGIN_BTN_BG = page.app_data.get("login_button_bg") or PRIMARY_COLOR
    LOGIN_BTN_TEXT = page.app_data.get("login_button_text_color") or "#FFFFFF"

    # Botão Entrar
    btn_ref = ft.Ref[ft.TextButton]()
    btn_entrar = ft.Container(
        content=ft.TextButton(
            "ENTRAR",
            ref=btn_ref,
            width=220,
            height=42,
            on_click=handle_login,
            style=ft.ButtonStyle(
                color=LOGIN_BTN_TEXT,
                bgcolor=LOGIN_BTN_BG,
                shape=ft.RoundedRectangleBorder(radius=6),
                overlay_color=LOGIN_BTN_BG,
            ),
        ),
        alignment=ft.alignment.center,
    )
    # expor ref para que outras views (ex.: Configurações) possam atualizá-lo em runtime
    try:
        page.app_data["login_button_ref"] = btn_ref
    except Exception:
        pass

    # Lista de usuários (caixa / estoque)
    user_dropdown = None
    # Lista ordenada acessível para atalhos e ícones
    ordered_users = []
    # (Removido) suporte a barras de boas-vindas na tela de login
    # (Removido) contêiner do dropdown "Mais opções"

    try:
        pdv_core = page.app_data.get("pdv_core")
        if pdv_core:
            # Filtra apenas Gerente, Caixa (qualquer) e Auxiliar de Estoque
            users = []
            caixa_counter = 0
            for u in pdv_core.get_all_users():
                # Determine flags and attributes once
                show_in_login = getattr(u, "show_in_login", False)
                username = getattr(u, "username", "")
                role = getattr(u, "role", "")

                # Always include admin
                if username == "admin":
                    users.append((u, "Gerente"))
                    continue

                # Always include any Auxiliar de Estoque
                if role == "estoque":
                    users.append((u, "Auxiliar de Estoque"))
                    continue

                # Include Caixa 1 by default; additional caixas only if
                # explicitly marked with `show_in_login=True`.
                if role == "caixa":
                    caixa_counter += 1
                    label = f"Caixa {caixa_counter}"
                    if caixa_counter == 1 or show_in_login:
                        users.append((u, label))
                    continue

                # For any other user/role, include only if explicitly allowed
                if show_in_login:
                    users.append((u, getattr(u, "display_label", username)))

            # Ordenar priorizando Gerente (admin), depois Caixa e Auxiliar de Estoque
            preferred_order = ["admin", "caixa", "estoque"]
            ordered = []
            remaining = users[:]
            for uname in preferred_order:
                for item in users:
                    u_obj, _label = item
                    if (
                        getattr(u_obj, "username", "") == uname
                        or getattr(u_obj, "role", "") == uname
                    ):
                        if item in remaining:
                            ordered.append(item)
                            remaining.remove(item)
            ordered.extend(remaining)

            ordered_users = ordered[:]
            options = [ft.dropdown.Option(str(u.id), label) for u, label in ordered]

            def apply_user(user):
                """Aplica seleção do usuário aos campos e sessão."""
                if not user:
                    return
                # Preencher username sempre
                username_entry.value = user.username
                # Guardar usuário selecionado na sessão
                try:
                    page.session.set("login_selected_username", user.username)
                    # marcar se a seleção permite auto-login (apenas caixas)
                    try:
                        page.session.set(
                            "login_selected_autologin",
                            True if getattr(user, "role", "") == "caixa" else False,
                        )
                    except Exception:
                        pass
                except Exception:
                    pass
                # Também manter flags no app_data (memória local) para maior confiabilidade
                try:
                    page.app_data["login_selected_username"] = user.username
                    page.app_data["login_selected_autologin"] = (
                        True if getattr(user, "role", "") == "caixa" else False
                    )
                except Exception:
                    pass
                # Gerente e Auxiliar de Estoque: campo usuário desabilitado, só digita senha
                if (
                    getattr(user, "username", "") == "admin"
                    or getattr(user, "role", "") == "estoque"
                ):
                    username_entry.disabled = True
                    password_entry.disabled = False
                    try:
                        password_entry.can_reveal_password = True
                    except Exception:
                        pass
                    password_entry.value = ""
                    # mover foco para o campo de senha para digitação imediata
                    try:
                        password_entry.update()
                        password_entry.focus()
                        page.update()
                    except Exception:
                        pass
                # Caixa: não exige senha — desabilitar campos e tentar login automático
                elif getattr(user, "role", "") == "caixa":
                    username_entry.disabled = True
                    password_entry.disabled = True
                    # Não pré-preenche a senha por segurança
                    password_entry.value = ""
                    # Tentar login automático para caixas
                    try:
                        handle_login(None)
                    except Exception:
                        pass
                else:
                    username_entry.disabled = False
                    password_entry.disabled = False
                    try:
                        password_entry.can_reveal_password = True
                    except Exception:
                        pass
                    password_entry.value = ""

                try:
                    username_entry.update()
                    password_entry.update()
                except Exception:
                    pass

            def on_user_select(e):
                try:
                    uid = e.control.value
                    if not uid:
                        try:
                            page.session.set("login_selected_username", None)
                        except Exception:
                            pass
                        # clear selection: allow manual username entry
                        try:
                            username_entry.value = ""
                            password_entry.value = ""
                            username_entry.disabled = False
                            password_entry.disabled = False
                            username_entry.update()
                            password_entry.update()
                        except Exception:
                            pass
                        return
                    user = pdv_core.get_user_by_id(int(uid))
                    if not user:
                        return
                    apply_user(user)
                except Exception:
                    pass

            user_dropdown = ft.Dropdown(
                label="Entrar como",
                options=options,
                width=350,
                on_change=on_user_select,
            )
            # Pré-selecionar Gerente (admin) primeiro; se não existir, selecionar Caixa
            try:
                gerente = next(
                    (u for u, _l in ordered if getattr(u, "username", "") == "admin"),
                    None,
                )
                if gerente:
                    user_dropdown.value = str(gerente.id)
                    on_user_select(ft.ControlEvent(user_dropdown))
                else:
                    caixa = next(
                        (u for u, _l in ordered if getattr(u, "role", "") == "caixa"),
                        None,
                    )
                    if caixa:
                        user_dropdown.value = str(caixa.id)
                        on_user_select(ft.ControlEvent(user_dropdown))
            except Exception:
                pass
    except Exception:
        user_dropdown = None

    # (Removido) handler de "Mais opções"

    # Submeter ao pressionar Enter (on_submit) nos campos
    try:
        username_entry.on_submit = handle_login
        password_entry.on_submit = handle_login
    except Exception:
        pass

    # Coluna central
    # Texto de versão imediatamente abaixo do botão
    version_text = ft.Text(
        "v1.0.0 • 2025",
        size=10,
        color=TEXT_COLOR,
        text_align=ft.TextAlign.CENTER,
    )
    # Login sempre em modo claro — sem alternador
    sobre_button = ft.TextButton(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.INFO, color=PRIMARY_COLOR),
                ft.Text(
                    "Sobre o Sistema",
                    color=PRIMARY_COLOR,
                    weight=ft.FontWeight.W_500,
                ),
            ],
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        on_click=lambda _: page.go("/sobre"),
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.TRANSPARENT,
            overlay_color=ft.Colors.GREY_300,
            shape=ft.RoundedRectangleBorder(radius=6),
        ),
    )

    # Seleção rápida por ícones (se houver usuários disponíveis)
    quick_select_row = ft.Row(
        [],
        spacing=8,
        alignment=ft.MainAxisAlignment.CENTER,
    )
    try:
        if ordered_users:
            buttons = []
            # Mostrar apenas até 3 botões rápidos para evitar lotar a tela
            for idx, (user, label) in enumerate(ordered_users[:3]):
                icon = ft.Icons.ADMIN_PANEL_SETTINGS
                if label.lower().startswith("caixa"):
                    icon = ft.Icons.POINT_OF_SALE
                elif label.lower().startswith("auxiliar") or label.lower().startswith(
                    "estoque"
                ):
                    icon = ft.Icons.INVENTORY

                def make_handler(u):
                    def _h(_):
                        # sincroniza dropdown se existir
                        try:
                            if user_dropdown is not None:
                                user_dropdown.value = str(u.id)
                        except Exception:
                            pass
                        apply_user(u)

                    return _h

                # Ícone padrão conforme papel (Caixa → POINT_OF_SALE)
                icon_control = ft.Icon(icon, size=42, color=PRIMARY_COLOR)

                # Normaliza label para exibir 'Estoque' quando for Auxiliar de Estoque
                display_label = label
                try:
                    if isinstance(label, str) and label.lower().startswith("auxiliar"):
                        display_label = "Estoque"
                    elif isinstance(label, str) and label.lower().startswith("estoque"):
                        display_label = "Estoque"
                except Exception:
                    display_label = label

                buttons.append(
                    ft.TextButton(
                        content=ft.Column(
                            [
                                icon_control,
                                ft.Text(
                                    f"{display_label} (F{idx + 1})",
                                    size=13,
                                    color=PRIMARY_COLOR,
                                    weight=ft.FontWeight.W_500,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=4,
                        ),
                        on_click=make_handler(user),
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.TRANSPARENT,
                            overlay_color=ft.Colors.GREY_300,
                            shape=ft.RoundedRectangleBorder(radius=6),
                        ),
                        height=80,
                        width=160,
                    )
                )
            quick_select_row.controls.extend(buttons)
    except Exception:
        pass

    def permitir_outro_usuario(e):
        try:
            if user_dropdown is not None:
                user_dropdown.value = None
            try:
                page.session.set("login_selected_username", None)
                page.session.set("login_selected_autologin", False)
            except Exception:
                pass
            # limpar também do app_data
            try:
                page.app_data["login_selected_username"] = None
                page.app_data["login_selected_autologin"] = False
            except Exception:
                pass
            username_entry.value = ""
            password_entry.value = ""
            username_entry.disabled = False
            password_entry.disabled = False
            try:
                username_entry.update()
                password_entry.update()
            except Exception:
                pass
        except Exception:
            pass

    outro_usuario_btn = ft.TextButton(
        "Acessar com usuário e senha", on_click=permitir_outro_usuario
    )

    # (Removido) Texto de dica de atalhos F1/F2/F3

    login_column = ft.Column(
        [
            # topo: logo
            ft.Row([ft.Container(expand=True)]),
            logo,
            ft.Container(height=12),
            quick_select_row,
            outro_usuario_btn,
            username_entry,
            password_entry,
            ft.Container(height=20),
            btn_entrar,
            ft.Container(height=8),
            version_text,
            ft.Container(height=6),
            # Sobre button and presentation refresh icon below it
            sobre_button,
            ft.Row(
                [
                    ft.IconButton(
                        icon=ft.Icons.REFRESH,
                        tooltip="Atualizar Sistema",
                        on_click=lambda e: _replay_presentation(e, page),
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # Fundo com rolagem apenas na coluna central
    login_container = ft.Container(
        content=ft.Column(
            [
                ft.Container(height=40),  # margem superior
                login_column,
                ft.Container(height=40),  # margem inferior
            ],
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.START,
        ),
        expand=True,
        bgcolor=BG_COLOR,
        padding=ft.padding.all(16),
    )

    # Teclado: Enter dispara login apenas com o usuário atualmente selecionado
    def login_keyboard_handler(e: ft.KeyboardEvent):
        key = (e.key or "").upper()
        # Seleção rápida somente por F1/F2/F3
        try:
            # Mapear apenas teclas de função (F1-F3) para seleção rápida.
            # Removemos os atalhos por números (1/2/3) para evitar
            # conflito quando o usuário digita a senha.
            index_map = {"F1": 0, "F2": 1, "F3": 2}
            if key in index_map and ordered_users:
                idx = index_map[key]
                if 0 <= idx < len(ordered_users):
                    u, _lbl = ordered_users[idx]
                    try:
                        if user_dropdown is not None:
                            user_dropdown.value = str(u.id)
                    except Exception:
                        pass
                    apply_user(u)
                    return
        except Exception:
            pass
        if key == "ENTER":
            try:
                handle_login(None)
            except Exception:
                pass

    # Registrar handler no objeto View retornado para que o mecanismo
    # de combinação de handlers em `app.py` execute o handler da view
    # Barra inferior para mensagens rápidas (ex.: Senha inválida)
    bottom_bar_ref = ft.Ref[ft.Container]()
    bottom_bar_text_ref = ft.Ref[ft.Text]()

    def show_bottom_bar(
        message: str, color=ft.Colors.GREEN_600, duration_ms: int = 3000
    ):
        try:
            if bottom_bar_text_ref.current:
                bottom_bar_text_ref.current.value = message
                bottom_bar_text_ref.current.update()
            if bottom_bar_ref.current:
                bottom_bar_ref.current.bgcolor = color
                bottom_bar_ref.current.visible = True
                bottom_bar_ref.current.update()

            def _hide():
                page.sleep(duration_ms)
                if bottom_bar_ref.current:
                    bottom_bar_ref.current.visible = False
                    bottom_bar_ref.current.update()

            page.run_task(_hide)
        except Exception as _ex:
            try:
                # Store pending welcome message so it can be shown once the
                # view is mounted and refs are available.
                page.app_data["login_pending_bottom_bar"] = (
                    message,
                    color,
                    duration_ms,
                )
            except Exception:
                pass
            print(f"[LOGIN] Falha ao mostrar barra inferior: {_ex}")

    # Expor função para ser usada por `handle_login` em app.py
    try:
        page.app_data["login_show_bottom_bar"] = show_bottom_bar
    except Exception:
        pass
    # Expor função para ser usada por `handle_login` em app.py
    # (Removido) não expor helper de barra inferior para evitar mensagens de boas-vindas

    def _replay_presentation(e=None, page_local=None):
        try:
            # preparar retorno para tela Sobre após apresentação
            try:
                page.app_data["presentation_return_route"] = "/login"
            except Exception:
                pass
            # navegar para raiz (splash) para reproduzir abertura
            try:
                page.go("/")
            except Exception:
                try:
                    if hasattr(page, "push_route"):
                        page.push_route("/")
                except Exception:
                    pass
        except Exception:
            pass

    view = ft.View(
        "/login",
        [
            login_container,
            ft.Container(
                ref=bottom_bar_ref,
                visible=False,
                height=44,
                bgcolor=ft.Colors.GREEN_600,
                padding=10,
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.BLACK),
                        ft.Text(
                            "",
                            ref=bottom_bar_text_ref,
                            color=ft.Colors.BLACK,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
        ],
        padding=0,
        bgcolor=BG_COLOR,
    )
    # If a pending bottom-bar message was stored (e.g., show_bottom_bar called
    # before the view refs were attached), display it now.
    try:
        pending = page.app_data.get("login_pending_bottom_bar")
        if pending:
            try:
                msg, col, dur = pending
                # Try to set refs directly without forcing immediate control.update()
                try:
                    if bottom_bar_text_ref.current:
                        bottom_bar_text_ref.current.value = msg
                    if bottom_bar_ref.current:
                        bottom_bar_ref.current.bgcolor = col
                        bottom_bar_ref.current.visible = True
                except Exception:
                    # fallback to snackbar if refs still can't be updated
                    try:
                        page.snack_bar = ft.SnackBar(
                            ft.Text(msg), bgcolor=col, duration=2000
                        )
                        page.snack_bar.open = True
                    except Exception:
                        pass
                try:
                    page.update()
                except Exception:
                    pass
            except Exception:
                pass
            try:
                page.app_data["login_pending_bottom_bar"] = None
            except Exception:
                pass
    except Exception:
        pass
    try:
        view.on_keyboard_event = login_keyboard_handler
    except Exception:
        # compatibilidade alternativa
        try:
            setattr(view, "on_keyboard_event", login_keyboard_handler)
        except Exception:
            pass

        # Expor ref da logo para permitir atualização imediata pela Configurações
        try:
            page.app_data["login_site_logo_ref"] = logo_ref
        except Exception:
            pass

    # Garantir que o campo de senha não retenha nenhum valor ao construir a view
    try:
        password_entry.value = ""
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

    return view
