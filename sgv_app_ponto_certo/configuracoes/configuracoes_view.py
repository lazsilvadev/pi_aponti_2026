import json
import os

import flet as ft

# Import estático do modal PIX para evitar falhas em builds empacotados.
try:
    from configuracoes.pix_settings_view import (
        create_pix_settings_modal_content,
        create_pix_settings_view,
    )
except Exception:
    create_pix_settings_modal_content = None
    create_pix_settings_view = None

COLORS = {
    "primary": "#034986",  # Azul padrão das demais telas
    "grey": "#4A4A4A",
    "white": ft.Colors.WHITE,
    "background": ft.Colors.GREY_100,
}


def show_snackbar(page: ft.Page, message: str, color: str):
    """Mostra uma mensagem de confirmação (snackbar) na tela"""
    snackbar = ft.SnackBar(
        ft.Text(message, color=ft.Colors.BLACK, weight=ft.FontWeight.BOLD),
        bgcolor=color,
        duration=3000,
    )
    try:
        page.snack_bar = snackbar
        page.snack_bar.open = True
        page.update()
    except Exception:
        page.overlay.append(snackbar)
        snackbar.open = True
        page.update()
    print(f"📢 Snackbar exibida: {message}")


def create_configuracoes_view(
    page: ft.Page, user_id_obj_do_gerente_logado, handle_back
):
    print("🔧 Iniciando view de configurações...")

    # CRIAR REFERÊNCIAS
    user_dropdown_ref = ft.Ref[ft.Dropdown]()
    full_name_ref = ft.Ref[ft.TextField]()
    password_ref = ft.Ref[ft.TextField]()
    save_button_ref = ft.Ref[ft.FilledButton]()
    delete_button_ref = ft.Ref[ft.ElevatedButton]()
    printer_name_ref = ft.Ref[ft.TextField]()
    paper_size_ref = ft.Ref[ft.Dropdown]()
    overlay_container_ref = ft.Ref[ft.Container]()
    # Barra inferior para confirmação de salvamento
    bottom_bar_ref = ft.Ref[ft.Container]()
    bottom_bar_text_ref = ft.Ref[ft.Text]()

    def show_bottom_bar(
        message: str, color=ft.Colors.GREEN_600, duration_ms: int = 3000
    ):
        """Exibe uma barra inferior com mensagem por alguns segundos."""
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
            print(f"[CONFIG] Falha ao mostrar barra inferior: {_ex}")

    # FUNÇÃO PARA CARREGAR USUÁRIOS
    def load_users():
        try:
            pdv_core = page.app_data.get("pdv_core")
            if not pdv_core:
                print("❌ pdv_core não encontrado")
                return []

            users = pdv_core.get_all_users()
            editable = [
                u
                for u in users
                if (u.get("role") if isinstance(u, dict) else getattr(u, "role", None))
                in ("gerente", "caixa", "estoque")
            ]
            print(f"✅ {len(editable)} usuários carregados")
            return editable
        except Exception as e:
            print(f"❌ Erro ao carregar usuários: {e}")
            return []

    # FUNÇÃO PARA POPULAR DROPDOWN (COM RETRY)
    def populate_dropdown(users, selected_id=None, attempt=0):
        max_attempts = 5

        if not user_dropdown_ref.current:
            if attempt < max_attempts:
                print(f"⏳ Dropdown não pronto, tentativa {attempt + 1}/{max_attempts}")
                page.run_task(
                    lambda: (
                        page.sleep(200),
                        populate_dropdown(users, selected_id, attempt + 1),
                    )
                )
            else:
                print("❌ Falhou após muitas tentativas")
            return

        try:
            # Limpar opções existentes
            user_dropdown_ref.current.options.clear()

            # Adicionar opções
            for u in users:
                user_id = str(u.get("id") if isinstance(u, dict) else u.id)
                user_name = (
                    u.get("full_name") or u.get("username")
                    if isinstance(u, dict)
                    else (u.full_name or u.username)
                )
                user_role = (u.get("role") if isinstance(u, dict) else u.role).title()

                # ft.dropdown.Option(key, text) -> primeiro argumento é a chave/valor,
                # segundo é o texto visível.
                user_dropdown_ref.current.options.append(
                    ft.dropdown.Option(user_id, f"{user_name} ({user_role})")
                )

            # Set valor selecionado
            user_dropdown_ref.current.value = str(selected_id) if selected_id else None

            # FORÇAR ATUALIZAÇÃO
            user_dropdown_ref.current.update()
            print(f"✅ Dropdown populado com {len(users)} usuários")
        except Exception as e:
            print(f"❌ Erro ao popular: {e}")

    # --- Construir opções iniciais imediatamente para evitar dropdown vazio/inacessível ---
    try:
        _initial_users = load_users()
        initial_options = []
        for u in _initial_users:
            uid = str(u.get("id") if isinstance(u, dict) else u.id)
            uname = (
                u.get("full_name") or u.get("username")
                if isinstance(u, dict)
                else (u.full_name or u.username)
            )
            urole = (u.get("role") if isinstance(u, dict) else u.role).title()
            initial_options.append(ft.dropdown.Option(uid, f"{uname} ({urole})"))
    except Exception:
        initial_options = []

    # FUNÇÃO PARA RESETAR CAMPOS
    def reset_user_fields():
        try:
            if not all(
                [full_name_ref.current, password_ref.current, save_button_ref.current]
            ):
                return

            full_name_ref.current.value = ""
            password_ref.current.value = ""
            full_name_ref.current.disabled = True
            password_ref.current.disabled = True
            save_button_ref.current.disabled = True
            if delete_button_ref.current:
                delete_button_ref.current.disabled = True
                try:
                    delete_button_ref.current.update()
                except Exception:
                    pass

            full_name_ref.current.update()
            password_ref.current.update()
            save_button_ref.current.update()
            print("🔄 Campos resetados")
        except Exception as e:
            print(f"❌ Erro ao resetar: {e}")

    # FUNÇÃO PARA HABILITAR CAMPOS
    def enable_user_fields(user_data):
        try:
            if not all(
                [full_name_ref.current, password_ref.current, save_button_ref.current]
            ):
                print("⏳ Campos não prontos")
                return

            name = (
                user_data.get("full_name", "")
                if isinstance(user_data, dict)
                else (user_data.full_name or "")
            )

            full_name_ref.current.value = name
            full_name_ref.current.disabled = False
            password_ref.current.disabled = False
            save_button_ref.current.disabled = False
            # Habilitar botão deletar (mas proteger último gerente no core)
            if delete_button_ref.current:
                delete_button_ref.current.disabled = False
                try:
                    delete_button_ref.current.update()
                except Exception:
                    pass

            full_name_ref.current.update()
            password_ref.current.update()
            save_button_ref.current.update()
            print(f"✅ Campos habilitados para: {name}")
        except Exception as e:
            print(f"❌ Erro ao habilitar: {e}")

    # HANDLER DE SELEÇÃO (COM DEBUG)
    def on_user_select(e):
        print(f"🎯 EVENTO on_change ACIONADO! Valor: {e.control.value}")
        selected_id = e.control.value

        if not selected_id:
            reset_user_fields()
            return

        pdv_core = page.app_data.get("pdv_core")
        if not pdv_core:
            print("❌ pdv_core não encontrado")
            return

        try:
            user = pdv_core.get_user_by_id(int(selected_id))
            if user:
                enable_user_fields(user)
            else:
                print("❌ Usuário não encontrado")
                reset_user_fields()
        except Exception as e:
            print(f"❌ Erro ao buscar usuário: {e}")

    # SALVAR USUÁRIO
    def save_user(e):
        print("💾 Tentando salvar usuário...")
        if not user_dropdown_ref.current or not user_dropdown_ref.current.value:
            show_snackbar(page, "Selecione um usuário primeiro", ft.Colors.RED)
            return

        pdv_core = page.app_data.get("pdv_core")
        if not pdv_core:
            return

        user_id = int(user_dropdown_ref.current.value)
        full_name = full_name_ref.current.value.strip()
        password = password_ref.current.value.strip()

        if not full_name:
            show_snackbar(page, "Nome não pode estar vazio", ft.Colors.RED)
            return

        sucesso, msg = pdv_core.update_user_settings(
            user_id, full_name, password or None
        )

        if sucesso:
            show_snackbar(
                page, "✅ Dados do usuário salvos com sucesso!", ft.Colors.GREEN
            )
            show_bottom_bar("Alterações do usuário salvas")
            password_ref.current.value = ""
            password_ref.current.update()

            # ✅ ATUALIZAR SESSÃO se o usuário editado for o usuário logado
            current_user_id = page.session.get("user_id")
            if current_user_id == user_id:
                page.session.set("user_display_name", full_name)
                print(f"✅ Nome do usuário atualizado em tempo real: {full_name}")

            # Recarregar dropdown
            users = load_users()
            populate_dropdown(users, selected_id=user_id)
        else:
            show_snackbar(page, f"❌ Erro: {msg}", ft.Colors.RED)

    # REMOVER USUÁRIO SELECIONADO
    def delete_user_handler(e):
        try:
            print("🎯 delete_user_handler chamado")

            if not user_dropdown_ref.current or not user_dropdown_ref.current.value:
                show_snackbar(page, "Selecione um usuário primeiro", ft.Colors.RED)
                return

            user_id = int(user_dropdown_ref.current.value)
            pdv_core = page.app_data.get("pdv_core")
            if not pdv_core:
                show_snackbar(page, "Core não iniciado", ft.Colors.RED)
                return

            print(f"🗑️ Tentando deletar usuário {user_id}...")

            # Confirmação via overlay
            def confirm_delete(_e):
                print(f"✅ Confirmando delete de {user_id}...")
                ok, msg = pdv_core.delete_user(user_id)
                if ok:
                    show_snackbar(page, msg, ft.Colors.GREEN)
                    # Mostrar barra inferior informando exclusão
                    try:
                        show_bottom_bar(msg, color=ft.Colors.GREEN_600)
                    except Exception:
                        pass
                    users = load_users()
                    populate_dropdown(users)
                    close_overlay()
                else:
                    show_snackbar(page, msg, ft.Colors.RED)

            def close_overlay():
                print("✅ Fechando overlay de delete...")
                overlay_container_ref.current.visible = False
                page.update()

            # Criar conteúdo do diálogo de confirmação
            dialog_content = ft.Container(
                bgcolor="white",
                border_radius=10,
                padding=20,
                shadow=ft.BoxShadow(blur_radius=10, spread_radius=2),
                content=ft.Column(
                    [
                        ft.Text(
                            "Confirmar Remoção", size=22, weight=ft.FontWeight.BOLD
                        ),
                        ft.Text("Deseja realmente remover o usuário selecionado?"),
                        ft.Row(
                            [
                                ft.TextButton(
                                    "Cancelar",
                                    on_click=lambda e: close_overlay(),
                                ),
                                ft.ElevatedButton(
                                    "Remover",
                                    bgcolor=ft.Colors.RED_600,
                                    on_click=confirm_delete,
                                ),
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=15,
                    tight=True,
                ),
            )

            # Stack com overlay
            overlay_stack = ft.Stack(
                [
                    ft.Container(
                        bgcolor="rgba(0,0,0,0.5)",
                        on_click=lambda e: close_overlay(),
                    ),
                    ft.Row(
                        [dialog_content],
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                expand=True,
            )

            overlay_container_ref.current.content = overlay_stack
            overlay_container_ref.current.visible = True
            page.update()
            print("🎨 Overlay de confirmação exibido!")

        except Exception as ex:
            print(f"❌ Erro em delete_user_handler: {ex}")
            import traceback

            traceback.print_exc()
            show_snackbar(page, f"Erro: {ex}", ft.Colors.RED)

    # UI SIMPLIFICADA
    user_card = ft.Card(
        content=ft.Container(
            padding=20,
            content=ft.Column(
                [
                    ft.Text(
                        "Gerenciamento de Usuários 👥",
                        style=ft.TextThemeStyle.TITLE_LARGE,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text("Selecione um usuário para editar"),
                    ft.Dropdown(
                        ref=user_dropdown_ref,
                        label="Selecionar Usuário",
                        options=initial_options,
                        on_change=on_user_select,
                        width=400,
                    ),
                    ft.TextField(
                        ref=full_name_ref,
                        label="Nome Completo",
                        disabled=True,
                        prefix_icon=ft.Icons.PERSON,
                    ),
                    ft.TextField(
                        ref=password_ref,
                        label="Nova Senha",
                        disabled=True,
                        password=True,
                        can_reveal_password=True,
                        prefix_icon=ft.Icons.LOCK,
                    ),
                    ft.Row(
                        [
                            ft.FilledButton(
                                "Salvar Alterações",
                                ref=save_button_ref,
                                icon=ft.Icons.SAVE,
                                on_click=save_user,
                                disabled=True,
                            ),
                            ft.ElevatedButton(
                                "Novo Usuário",
                                icon=ft.Icons.PERSON_ADD,
                                on_click=lambda e: nova_usuario_dialog(page),
                            ),
                            ft.ElevatedButton(
                                "Deletar Usuário",
                                ref=delete_button_ref,
                                icon=ft.Icons.DELETE,
                                bgcolor=ft.Colors.RED_600,
                                color=ft.Colors.BLACK,
                                on_click=delete_user_handler,
                                disabled=True,
                            ),
                        ],
                        spacing=12,
                    ),
                ],
                spacing=15,
            ),
        )
    )

    # SALVAR IMPRESSORA
    def save_printer(e):
        printer_name = printer_name_ref.current.value.strip()
        paper_size = paper_size_ref.current.value

        if not printer_name:
            show_snackbar(page, "❌ Informe o nome da impressora", ft.Colors.RED)
            return

        pdv_core = page.app_data.get("pdv_core")
        if pdv_core and hasattr(pdv_core, "save_printer_config"):
            sucesso, msg = pdv_core.save_printer_config(printer_name, paper_size)
            if sucesso:
                # também refletir em sessão para uso imediato em outras telas
                page.session.set("printer_name", printer_name)
                page.session.set("paper_size", paper_size)
                show_snackbar(
                    page,
                    "✅ Configurações da impressora salvas com sucesso!",
                    ft.Colors.GREEN,
                )
                show_bottom_bar("Configurações da impressora salvas")
            else:
                show_snackbar(page, f"❌ Erro: {msg}", ft.Colors.RED)
        else:
            page.session.set("printer_name", printer_name)
            page.session.set("paper_size", paper_size)
            show_snackbar(page, "✅ Configurações salvas com sucesso!", ft.Colors.GREEN)

    # CARREGAR CONFIGURAÇÕES DE IMPRESSORA
    def load_printer_config():
        """Carrega as configurações de impressora salvas"""
        try:
            pdv_core = page.app_data.get("pdv_core")
            loaded = False
            if pdv_core and hasattr(pdv_core, "get_printer_config"):
                config = pdv_core.get_printer_config() or {}
                name = config.get("printer_name") or ""
                psize = config.get("paper_size") or "80mm"
                if printer_name_ref.current:
                    printer_name_ref.current.value = name
                    loaded = loaded or bool(name)
                if paper_size_ref.current:
                    paper_size_ref.current.value = psize
                    loaded = True

            # Fallback: carregar da sessão caso core não exponha método ou não tenha valores
            if not loaded:
                sess_name = page.session.get("printer_name") or ""
                sess_size = page.session.get("paper_size") or "80mm"
                if printer_name_ref.current:
                    printer_name_ref.current.value = sess_name
                if paper_size_ref.current:
                    paper_size_ref.current.value = sess_size
            page.update()
        except Exception as ex:
            print(f"[ERRO] load_printer_config: {ex}")

    printer_card = ft.Card(
        content=ft.Container(
            padding=20,
            content=ft.Column(
                [
                    ft.Text(
                        "Configurações da Impressora 🖨️",
                        style=ft.TextThemeStyle.TITLE_LARGE,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.TextField(
                        ref=printer_name_ref,
                        label="Nome da Impressora",
                        prefix_icon=ft.Icons.PRINT,
                    ),
                    ft.Dropdown(
                        ref=paper_size_ref,
                        label="Tamanho do Papel",
                        options=[
                            ft.dropdown.Option("80mm"),
                            ft.dropdown.Option("58mm"),
                        ],
                        value="80mm",
                    ),
                    ft.FilledButton(
                        "Salvar Config. Impressora",
                        icon=ft.Icons.SAVE,
                        on_click=save_printer,
                    ),
                ],
                spacing=15,
            ),
        )
    )

    # CARD PIX - atalho para a tela dedicada de PIX
    # --- Identidade Visual do Sistema ---
    logo_preview_ref = ft.Ref[ft.Image]()
    file_picker_ref = ft.Ref[ft.FilePicker]()
    slogan_ref = ft.Ref[ft.TextField]()
    pdv_title_ref = ft.Ref[ft.TextField]()
    pdv_upper_ref = ft.Ref[ft.Checkbox]()
    # novos refs para cores personalizáveis
    icon_color_ref = ft.Ref[ft.TextField]()
    login_btn_bg_ref = ft.Ref[ft.TextField]()
    login_btn_text_ref = ft.Ref[ft.TextField]()

    def load_identity_config():
        try:
            # Preferir caminho de config do pdv_core quando disponível (persistente)
            cfg_path = None
            pdv_core = page.app_data.get("pdv_core")
            try:
                cfg_path = getattr(pdv_core, "_config_file", None)
            except Exception:
                cfg_path = None
            if not cfg_path:
                cfg_path = os.path.join(os.getcwd(), "data", "app_config.json")

            cfg = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            logo = cfg.get("site_logo") or page.app_data.get("site_logo") or ""
            slogan = cfg.get("site_slogan") or page.app_data.get("site_slogan") or ""
            pdv_title = (
                cfg.get("site_pdv_title") or page.app_data.get("site_pdv_title") or ""
            )
            pdv_upper = (
                cfg.get("site_pdv_title_upper")
                if cfg.get("site_pdv_title_upper") is not None
                else page.app_data.get("site_pdv_title_upper", False)
            )
            if logo and logo_preview_ref.current:
                try:
                    logo_preview_ref.current.src = logo
                    logo_preview_ref.current.update()
                except Exception:
                    pass
            if slogan_ref.current is not None:
                slogan_ref.current.value = slogan
                slogan_ref.current.update()
            if pdv_title_ref.current is not None:
                pdv_title_ref.current.value = pdv_title
                pdv_title_ref.current.update()
            try:
                if pdv_upper_ref.current is not None:
                    pdv_upper_ref.current.value = bool(pdv_upper)
                    pdv_upper_ref.current.update()
            except Exception:
                pass
            # aplicar cores, se existentes
            try:
                icon_color = (
                    cfg.get("icon_color")
                    or page.app_data.get("icon_color")
                    or "#034986"
                )
                login_btn_bg = (
                    cfg.get("login_button_bg")
                    or page.app_data.get("login_button_bg")
                    or "#034986"
                )
                login_btn_text = (
                    cfg.get("login_button_text_color")
                    or page.app_data.get("login_button_text_color")
                    or "#FFFFFF"
                )
                if icon_color_ref.current is not None:
                    icon_color_ref.current.value = icon_color
                    icon_color_ref.current.update()
                if login_btn_bg_ref.current is not None:
                    login_btn_bg_ref.current.value = login_btn_bg
                    login_btn_bg_ref.current.update()
                if login_btn_text_ref.current is not None:
                    login_btn_text_ref.current.value = login_btn_text
                    login_btn_text_ref.current.update()
            except Exception:
                pass
        except Exception as ex:
            print(f"[IDENT] load_identity_config error: {ex}")

    # helper para setar cores em campos sem exigir digitação manual
    def set_color_field(field_ref: ft.Ref, color: str):
        try:
            if not color:
                return
            if field_ref and getattr(field_ref, "current", None):
                field_ref.current.value = color
                field_ref.current.update()
        except Exception:
            pass

    def normalize_hex(s: str) -> str:
        try:
            if not s:
                return s
            s2 = s.strip()
            if not s2:
                return s2
            if not s2.startswith("#"):
                s2 = "#" + s2
            return s2.upper()
        except Exception:
            return s

    def on_file_picker_result(e: ft.FilePickerResultEvent):
        try:
            if not e.files:
                return
            f0 = e.files[0]
            path = f0.path
            # Atualizar preview em tempo real
            if logo_preview_ref.current:
                logo_preview_ref.current.src = path
                logo_preview_ref.current.update()
            # armazenar temporariamente em app_data
            page.app_data["site_logo_temp"] = path
            page.update()
        except Exception as ex:
            print(f"[IDENT] file pick error: {ex}")

    def pick_logo(e=None):
        try:
            if file_picker_ref.current:
                file_picker_ref.current.pick_files(
                    allow_multiple=False,
                    allowed_extensions=["png", "jpg", "jpeg", "svg"],
                )
        except Exception as ex:
            print(f"[IDENT] pick_logo error: {ex}")

    def save_identity(e=None):
        try:
            # Preferir caminho de config do pdv_core quando disponível (persistente fora do bundle)
            pdv_core = page.app_data.get("pdv_core")
            try:
                cfg_path = getattr(pdv_core, "_config_file", None)
            except Exception:
                cfg_path = None
            if not cfg_path:
                cfg_path = os.path.join(os.getcwd(), "data", "app_config.json")

            cfg = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    try:
                        cfg = json.load(f)
                    except Exception:
                        cfg = {}

            # logo prefer temp, else existing preview src
            logo_path = page.app_data.get("site_logo_temp") or (
                logo_preview_ref.current.src if logo_preview_ref.current else ""
            )
            slogan = slogan_ref.current.value.strip() if slogan_ref.current else ""
            pdv_title = (
                pdv_title_ref.current.value.strip() if pdv_title_ref.current else ""
            )
            pdv_upper = (
                bool(pdv_upper_ref.current.value) if pdv_upper_ref.current else False
            )
            # ler valores das cores opcionais
            icon_color_val = (
                icon_color_ref.current.value.strip()
                if icon_color_ref.current
                else "#034986"
            )
            login_btn_bg_val = (
                login_btn_bg_ref.current.value.strip()
                if login_btn_bg_ref.current
                else "#034986"
            )
            login_btn_text_val = (
                login_btn_text_ref.current.value.strip()
                if login_btn_text_ref.current
                else "#FFFFFF"
            )

            # normalizar hex (adicionar # se necessário e uppercase)
            try:
                icon_color_val = normalize_hex(icon_color_val)
            except Exception:
                pass
            try:
                login_btn_bg_val = normalize_hex(login_btn_bg_val)
            except Exception:
                pass
            try:
                login_btn_text_val = normalize_hex(login_btn_text_val)
            except Exception:
                pass

            cfg["site_logo"] = logo_path
            cfg["site_slogan"] = slogan
            cfg["site_pdv_title"] = pdv_title
            cfg["site_pdv_title_upper"] = pdv_upper
            cfg["icon_color"] = icon_color_val
            cfg["login_button_bg"] = login_btn_bg_val
            cfg["login_button_text_color"] = login_btn_text_val

            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)

            # Refletir imediatamente no app_data e notificar
            page.app_data["site_logo"] = logo_path
            page.app_data["site_slogan"] = slogan
            page.app_data["site_pdv_title"] = pdv_title
            page.app_data["site_pdv_title_upper"] = pdv_upper
            page.app_data["icon_color"] = icon_color_val
            page.app_data["login_button_bg"] = login_btn_bg_val
            page.app_data["login_button_text_color"] = login_btn_text_val
            show_snackbar(page, "Identidade Visual salva", ft.Colors.GREEN)
            show_bottom_bar("Identidade Visual salva")
            # Atualizar views já montadas (ex.: Painel Gerencial) via refs expostos
            try:
                gerente_logo_ref = page.app_data.get("gerente_site_logo_ref")
                if gerente_logo_ref and gerente_logo_ref.current:
                    gerente_logo_ref.current.src = logo_path
                    gerente_logo_ref.current.update()
            except Exception as _ex:
                print(f"[IDENT] não foi possível atualizar logo no gerente: {_ex}")
            try:
                gerente_slogan_ref = page.app_data.get("gerente_site_slogan_ref")
                if gerente_slogan_ref and gerente_slogan_ref.current:
                    gerente_slogan_ref.current.value = slogan
                    gerente_slogan_ref.current.update()
            except Exception as _ex:
                print(f"[IDENT] não foi possível atualizar slogan no gerente: {_ex}")
            # Também atualizar Login e Sobre se estiverem montados
            try:
                login_logo_ref = page.app_data.get("login_site_logo_ref")
                if login_logo_ref and login_logo_ref.current:
                    login_logo_ref.current.src = logo_path
                    login_logo_ref.current.update()
            except Exception as _ex:
                print(f"[IDENT] não foi possível atualizar logo no login: {_ex}")
            # tentar atualizar botao do login (se view montada expôs ref em app_data)
            try:
                login_btn_ref = page.app_data.get("login_button_ref")
                if login_btn_ref and getattr(login_btn_ref, "current", None):
                    try:
                        b = login_btn_ref.current
                        try:
                            b.style = ft.ButtonStyle(
                                color=login_btn_text_val,
                                bgcolor=login_btn_bg_val,
                                shape=ft.RoundedRectangleBorder(radius=6),
                                overlay_color=login_btn_bg_val,
                            )
                        except Exception:
                            pass
                        try:
                            b.update()
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                sobre_logo_ref = page.app_data.get("sobre_site_logo_ref")
                if sobre_logo_ref and sobre_logo_ref.current:
                    sobre_logo_ref.current.src = logo_path
                    sobre_logo_ref.current.update()
            except Exception as _ex:
                print(f"[IDENT] não foi possível atualizar logo no Sobre: {_ex}")
            # Atualizar appbar do Caixa se estiver visível
            try:
                if str(page.route or "").startswith("/caixa"):
                    create_appbar_fn = page.app_data.get("create_appbar")
                    if create_appbar_fn:
                        # aplicar título (usar upper se configurado)
                        title_to_use = pdv_title or "MERCADINHO PONTO CERTO"
                        if pdv_upper:
                            title_to_use = title_to_use.upper()
                        # manter o formato sem usuário (show_user=False)
                        # Atualizar o page.appbar (global)
                        new_appbar = create_appbar_fn(
                            f"{title_to_use}", show_user=False
                        )
                        try:
                            page.appbar = new_appbar
                        except Exception:
                            pass
                        try:
                            page.update()
                        except Exception:
                            pass
                        # Se a view do Caixa está usando um appbar passado (ref), atualize-o também
                        try:
                            caixa_appbar_ref = page.app_data.get("caixa_appbar_ref")
                            if caixa_appbar_ref and caixa_appbar_ref.current:
                                try:
                                    caixa_appbar_ref.current.title = new_appbar.title
                                    caixa_appbar_ref.current.update()
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception as _ex:
                print(f"[IDENT] não foi possível atualizar appbar do Caixa: {_ex}")
            page.update()
        except Exception as ex:
            print(f"[IDENT] save_identity error: {ex}")
            show_snackbar(page, f"Erro ao salvar: {ex}", ft.Colors.RED)

    def reset_identity_defaults(e=None):
        """Resetar cores para valores padrão e salvar imediatamente."""
        try:
            default_icon = "#034986"
            default_btn_bg = "#034986"
            default_btn_text = "#FFFFFF"
            # atualizar campos visuais
            try:
                set_color_field(icon_color_ref, default_icon)
            except Exception:
                pass
            try:
                set_color_field(login_btn_bg_ref, default_btn_bg)
            except Exception:
                pass
            try:
                set_color_field(login_btn_text_ref, default_btn_text)
            except Exception:
                pass
            # forçar salvar
            save_identity(None)
            show_snackbar(page, "Restaurado para padrão", ft.Colors.GREEN)
        except Exception as ex:
            print(f"[IDENT] reset defaults error: {ex}")
            show_snackbar(page, "Erro ao restaurar padrão", ft.Colors.RED)

    # componente de preview e controles
    identity_card = ft.Card(
        content=ft.Container(
            padding=20,
            content=ft.Column(
                [
                    ft.Text(
                        "Identidade Visual do Sistema",
                        style=ft.TextThemeStyle.TITLE_MEDIUM,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Container(
                                        content=ft.Image(
                                            ref=logo_preview_ref,
                                            src=page.app_data.get("site_logo", ""),
                                            width=300,
                                            height=120,
                                            fit=ft.ImageFit.CONTAIN,
                                        ),
                                        border=ft.border.all(1, ft.Colors.BLACK12),
                                        padding=8,
                                    ),
                                    ft.Text("Tamanho sugerido: 300x120 px", size=12),
                                ],
                                spacing=8,
                            ),
                            ft.Column(
                                [
                                    ft.ElevatedButton(
                                        "Alterar Logo",
                                        icon=ft.Icons.UPLOAD_FILE,
                                        on_click=pick_logo,
                                    ),
                                    ft.Row(
                                        [
                                            ft.Text(
                                                "Preview abaixo mostrará a imagem selecionada em tempo real."
                                            )
                                        ]
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.START,
                                spacing=12,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=20,
                    ),
                    ft.TextField(
                        ref=slogan_ref,
                        label="Slogan / Frase",
                        hint_text="Crie um slogan",
                        width=520,
                    ),
                    ft.TextField(
                        ref=pdv_title_ref,
                        label="Título do Caixa",
                        hint_text="Nome do estabelecimento",
                        helper_text="Este texto aparece centralizado no topo da tela do caixa",
                        width=520,
                        max_length=40,
                    ),
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.TextField(
                                        ref=icon_color_ref,
                                        label="Cor dos ícones (HEX)",
                                        hint_text="#034986",
                                        width=260,
                                    ),
                                    ft.Row(
                                        [
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#034986",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=icon_color_ref: set_color_field(
                                                    r, "#034986"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#007BFF",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=icon_color_ref: set_color_field(
                                                    r, "#007BFF"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#28A745",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=icon_color_ref: set_color_field(
                                                    r, "#28A745"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#FFC107",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=icon_color_ref: set_color_field(
                                                    r, "#FFC107"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#DC3545",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=icon_color_ref: set_color_field(
                                                    r, "#DC3545"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#FFFFFF",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=icon_color_ref: set_color_field(
                                                    r, "#FFFFFF"
                                                ),
                                            ),
                                        ],
                                        spacing=6,
                                    ),
                                    ft.Text("Ex.: #034986", size=11),
                                ]
                            ),
                            ft.Column(
                                [
                                    ft.TextField(
                                        ref=login_btn_bg_ref,
                                        label="Cor de fundo do botão Entrar (HEX)",
                                        hint_text="#034986",
                                        width=260,
                                    ),
                                    ft.Row(
                                        [
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#034986",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_bg_ref: set_color_field(
                                                    r, "#034986"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#007BFF",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_bg_ref: set_color_field(
                                                    r, "#007BFF"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#28A745",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_bg_ref: set_color_field(
                                                    r, "#28A745"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#FFC107",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_bg_ref: set_color_field(
                                                    r, "#FFC107"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#DC3545",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_bg_ref: set_color_field(
                                                    r, "#DC3545"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#000000",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_bg_ref: set_color_field(
                                                    r, "#000000"
                                                ),
                                            ),
                                        ],
                                        spacing=6,
                                    ),
                                    ft.TextField(
                                        ref=login_btn_text_ref,
                                        label="Cor do texto do botão Entrar (HEX)",
                                        hint_text="#FFFFFF",
                                        width=260,
                                    ),
                                    ft.Row(
                                        [
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#034986",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_text_ref: set_color_field(
                                                    r, "#034986"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#007BFF",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_text_ref: set_color_field(
                                                    r, "#007BFF"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#28A745",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_text_ref: set_color_field(
                                                    r, "#28A745"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#FFC107",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_text_ref: set_color_field(
                                                    r, "#FFC107"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#DC3545",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_text_ref: set_color_field(
                                                    r, "#DC3545"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#FFFFFF",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_text_ref: set_color_field(
                                                    r, "#FFFFFF"
                                                ),
                                            ),
                                            ft.ElevatedButton(
                                                " ",
                                                bgcolor="#000000",
                                                width=28,
                                                height=28,
                                                on_click=lambda e,
                                                r=login_btn_text_ref: set_color_field(
                                                    r, "#000000"
                                                ),
                                            ),
                                        ],
                                        spacing=6,
                                    ),
                                ]
                            ),
                        ],
                        spacing=12,
                    ),
                    # Checkbox 'Exibir em MAIÚSCULAS' removido per request
                    ft.Row(
                        [
                            ft.OutlinedButton(
                                "Voltar ao padrão",
                                icon=ft.Icons.REFRESH,
                                on_click=reset_identity_defaults,
                            ),
                            ft.FilledButton(
                                "Salvar Identidade Visual",
                                on_click=save_identity,
                                icon=ft.Icons.SAVE,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                        spacing=12,
                    ),
                ],
                spacing=12,
            ),
        )
    )

    def open_pix_settings(e=None):
        print("[CONFIG] open_pix_settings called (overlay)")
        try:
            # função local para fechar somente o overlay do PIX (não navegar para trás)
            def close_overlay(_e=None):
                try:
                    overlay_container_ref.current.visible = False
                    overlay_container_ref.current.content = None
                    page.update()
                except Exception as ex:
                    print(f"[CONFIG] Erro ao fechar overlay PIX: {ex}")

            # Tentar usar import estático (mais compatível com empacotadores).
            try:
                if create_pix_settings_modal_content:
                    content = create_pix_settings_modal_content(page, close_overlay)
                else:
                    raise RuntimeError("static import unavailable")
            except Exception:
                # Fallback: importar dinamicamente como antes
                try:
                    mod = __import__("configuracoes.pix_settings_view", fromlist=["*"])
                    try:
                        content = mod.create_pix_settings_modal_content(
                            page, close_overlay
                        )
                    except Exception:
                        v = mod.create_pix_settings_view(page, close_overlay)
                        content = v.controls[0].content
                except Exception as ex:
                    print(f"[CONFIG] Erro preparando conteúdo PIX: {ex}")
                    content = ft.Column([ft.Text("Erro ao carregar PIX")])

            # close_overlay já definido acima e passado como handle_back

            modal_container = ft.Stack(
                [
                    ft.Container(
                        bgcolor="rgba(0,0,0,0.5)", expand=True, on_click=close_overlay
                    ),
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Column([content], spacing=12),
                                width=760,
                                padding=20,
                                bgcolor="white",
                                border_radius=10,
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                expand=True,
            )

            overlay_container_ref.current.content = modal_container
            overlay_container_ref.current.visible = True
            page.update()
            print("[CONFIG] Overlay PIX exibido")
        except Exception as ex:
            print(f"[CONFIG] Erro abrindo overlay PIX: {ex}")

    pix_card = ft.Card(
        content=ft.Container(
            padding=20,
            content=ft.Column(
                [
                    ft.Text(
                        "PIX",
                        style=ft.TextThemeStyle.TITLE_MEDIUM,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text("Configurar chave, QR e opções do PIX (somente gerente)."),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "Configurar PIX",
                                icon=ft.Icons.PAYMENT,
                                on_click=open_pix_settings,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                ],
                spacing=10,
            ),
        )
    )

    # CARD CALCULADORA DE TAXAS - atalho para a calculadora de taxas
    def open_tax_calculator(e=None):
        print("[CONFIG] open_tax_calculator called (overlay)")
        try:
            # garantir compatibilidade ft.icons importando adaptador cedo
            try:
                __import__("core.flet_compat", fromlist=["*"])
            except Exception:
                pass
            mod = __import__("utils.tax_calculator_view", fromlist=["*"])

            def close_overlay(_e=None):
                try:
                    overlay_container_ref.current.visible = False
                    overlay_container_ref.current.content = None
                    page.update()
                except Exception as ex:
                    print(f"[CONFIG] Erro ao fechar overlay Calculadora: {ex}")

            try:
                v = mod.criar_calculadora_view(page)
                content = (
                    v.controls[0].content
                    if hasattr(v.controls[0], "content")
                    else v.controls[0]
                )
            except Exception as ex:
                print(f"[CONFIG] Erro preparando conteúdo Calculadora: {ex}")
                content = ft.Column([ft.Text("Erro ao carregar Calculadora")])

            modal_container = ft.Stack(
                [
                    ft.Container(
                        bgcolor="rgba(0,0,0,0.5)", expand=True, on_click=close_overlay
                    ),
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Column([content], spacing=12),
                                width=760,
                                padding=20,
                                bgcolor="white",
                                border_radius=10,
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                expand=True,
            )

            overlay_container_ref.current.content = modal_container
            overlay_container_ref.current.visible = True
            page.update()
            print("[CONFIG] Overlay Calculadora exibido")
        except Exception as ex:
            print(f"[CONFIG] Erro abrindo overlay Calculadora: {ex}")

    tax_card = ft.Card(
        content=ft.Container(
            padding=20,
            content=ft.Column(
                [
                    ft.Text(
                        "Calculadora de Taxas",
                        style=ft.TextThemeStyle.TITLE_MEDIUM,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text("Simule taxas e repasses da maquininha."),
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "Abrir Calculadora",
                                on_click=open_tax_calculator,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.START,
                    ),
                ],
                spacing=10,
            ),
        )
    )

    # Container para overlays de diálogos
    overlay_container_ref = ft.Ref[ft.Container]()

    # Referência para o container principal de scroll
    main_scroll_ref = ft.Ref[ft.Container]()

    # Tabs: Gerenciamento de Usuários + Identidade Visual
    # Mantém os cards na mesma coluna (restaurando layout original)
    # A aba de Identidade Visual foi substituída por um card abaixo

    # FilePicker (necessário estar na árvore de controles)
    file_picker = ft.FilePicker(
        ref=file_picker_ref,
        on_result=on_file_picker_result,
    )

    view = ft.View(
        "/gerente/configuracoes",
        [
            ft.AppBar(
                title=ft.Text(
                    "Configurações",
                    style=ft.TextThemeStyle.TITLE_LARGE,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
                center_title=True,
                bgcolor=COLORS["primary"],
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    on_click=handle_back,
                    icon_color=ft.Colors.WHITE,
                ),
            ),
            file_picker,
            ft.Stack(
                [
                    ft.Container(
                        ref=main_scroll_ref,
                        content=ft.Column(
                            [
                                user_card,
                                printer_card,
                                pix_card,
                                tax_card,
                                identity_card,
                            ],
                            spacing=20,
                            expand=True,
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        padding=ft.padding.only(top=20, left=20, right=20),
                        expand=True,
                    ),
                    ft.Container(
                        ref=overlay_container_ref,
                        visible=False,
                        expand=True,
                        bgcolor="transparent",
                    ),
                ],
                expand=True,
            ),
            # Barra inferior fixa como controle abaixo do Stack
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
                            "Alterações salvas",
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
    )

    # LIFECYCLE - GARANTIR TUDO ESTEJA PRONTO
    def on_view_did_mount(e):
        page.bgcolor = COLORS["background"]
        print("🎨 View montada, iniciando carregamento...")

        # Usar run_task para garantir que a view está completamente montada
        def delayed_setup():
            page.sleep(300)  # Aguardar 300ms
            users = load_users()
            populate_dropdown(users)
            reset_user_fields()
            # carregar identidade visual (logo e slogan)
            try:
                load_identity_config()
            except Exception:
                pass
            # ajustar altura do container de scroll para ficar até o botão da calculadora
            try:
                if main_scroll_ref.current:
                    win_h = None
                    try:
                        win_h = page.window_height
                    except Exception:
                        pass
                    if not win_h:
                        try:
                            win_h = page.client_size.height
                        except Exception:
                            win_h = None
                    if not win_h:
                        win_h = 800

                    # reservar espaço para AppBar + margens
                    h = int(win_h) - 200
                    if h > 220:
                        main_scroll_ref.current.height = h
                        main_scroll_ref.current.update()
            except Exception as _ex:
                print(f"[IDENT] não foi possível ajustar altura do scroll: {_ex}")
            # Ajustar cursor de mouse do botão "Deletar Usuário" (se suportado)
            try:
                if delete_button_ref.current and hasattr(
                    delete_button_ref.current, "mouse_cursor"
                ):
                    delete_button_ref.current.mouse_cursor = ft.MouseCursor.CLICK
                    delete_button_ref.current.update()
            except Exception as _ex:
                print(f"[CONFIG] Não foi possível definir mouse_cursor: {_ex}")
            print("✅ Setup completo!")

        page.run_task(delayed_setup)

    view.on_view_did_mount = on_view_did_mount

    def nova_usuario_dialog(page: ft.Page):
        print("🎯 Abrindo diálogo de novo usuário...")

        pdv_core = page.app_data.get("pdv_core")
        if not pdv_core:
            show_snackbar(page, "Core não iniciado", ft.Colors.RED)
            return

        username_field = ft.TextField(label="Username", width=300)
        fullname_field = ft.TextField(label="Nome Completo", width=300)
        password_field = ft.TextField(
            label="Senha", password=True, can_reveal_password=True, width=300
        )
        role_dropdown = ft.Dropdown(
            label="Funções",
            value="caixa",
            width=300,
            options=[
                ft.dropdown.Option("gerente", "Gerente"),
                ft.dropdown.Option("caixa", "Caixa"),
                ft.dropdown.Option("estoque", "Estoque"),
            ],
        )

        def close_overlay():
            print("✅ Fechando overlay de novo usuário...")
            overlay_container_ref.current.visible = False
            page.update()

        def submit(e):
            print("💾 Tentando criar usuário...")
            uname = username_field.value.strip()
            fname = fullname_field.value.strip()
            pwd = password_field.value.strip()
            role = role_dropdown.value

            if not uname or not pwd or not role:
                show_snackbar(
                    page, "Informe username, senha e função", ft.Colors.ORANGE
                )
                return

            ok, result = pdv_core.create_user(uname, pwd, role, fname or None)
            if ok:
                new_user = result
                print("✅ Usuário criado com sucesso!")
                show_snackbar(page, "Usuário criado com sucesso", ft.Colors.GREEN)
                # Recarregar dropdown e selecionar o novo usuário
                users = load_users()
                populate_dropdown(users, selected_id=getattr(new_user, "id", None))
                close_overlay()
            else:
                print(f"❌ Erro ao criar: {result}")
                show_snackbar(page, f"Erro: {result}", ft.Colors.RED)

        # Criar conteúdo do diálogo
        dialog_content = ft.Container(
            bgcolor="white",
            border_radius=10,
            padding=20,
            shadow=ft.BoxShadow(blur_radius=10, spread_radius=2),
            content=ft.Column(
                [
                    ft.Text("Novo Usuário", size=22, weight=ft.FontWeight.BOLD),
                    username_field,
                    fullname_field,
                    password_field,
                    role_dropdown,
                    ft.Row(
                        [
                            ft.TextButton(
                                "Cancelar", on_click=lambda e: close_overlay()
                            ),
                            ft.ElevatedButton("Criar", on_click=submit),
                        ],
                        spacing=10,
                    ),
                ],
                spacing=15,
                tight=True,
            ),
        )

        # Stack com overlay
        overlay_stack = ft.Stack(
            [
                ft.Container(
                    bgcolor="rgba(0,0,0,0.5)",
                    on_click=lambda e: close_overlay(),
                ),
                ft.Row(
                    [dialog_content],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
        )

        overlay_container_ref.current.content = overlay_stack
        overlay_container_ref.current.visible = True
        page.update()
        print("🎨 Overlay exibido!")

    # Carregar configurações de impressora ao abrir a view
    load_printer_config()

    return view
