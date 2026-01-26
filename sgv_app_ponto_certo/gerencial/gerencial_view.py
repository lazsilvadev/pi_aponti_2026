import flet as ft

from utils.path_resolver import get_asset_path


def create_gerente_view(user_display_name: str, page: ft.Page, handle_logout):
    # Aplicar preferência de tema escolhida na tela de login (apenas para gerente)
    pref = "light"
    try:
        pref = page.session.get("gerente_theme_choice") or "light"
    except Exception:
        pref = "light"

    if pref == "dark":
        page.theme_mode = ft.ThemeMode.DARK
        COLORS = {
            "text": "#E6EEF8",
            "white": "#0B1220",
            "primary": "#90CAF9",
            "green": "#81C784",
            "red": "#EF9A9A",
            "orange": "#FFB74D",
            "teal": "#4DB6AC",
            "purple": "#CE93D8",
            "background": "#0B1220",
        }
        try:
            page.bgcolor = "#0B1220"
        except Exception:
            pass
    else:
        page.theme_mode = ft.ThemeMode.LIGHT
        COLORS = {
            "text": "#0D47A1",
            "white": "#FFFFFF",
            "primary": "#007BFF",
            "green": "#28A745",
            "red": "#DC3545",
            # substituir laranja por fundo claro (mesma cor do login)
            "orange": "#F0F4F8",
            "teal": "#66119E",
            "purple": "#9C27B0",
            "background": "#F0F4F8",
        }

    def create_toolbar_button(icon_name, text, on_click_handler, color=COLORS["text"]):
        return ft.TextButton(
            content=ft.Column(
                [
                    ft.Icon(icon_name, size=50, color=color),
                    ft.Text(text, size=15, color=color, weight=ft.FontWeight.W_500),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            on_click=on_click_handler,
            height=100,
            width=130,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.TRANSPARENT,
                overlay_color=ft.Colors.GREY_300,
                shape=ft.RoundedRectangleBorder(radius=6),
            ),
        )

    # Refs para logo e slogan para permitir atualização dinâmica
    logo_ref = ft.Ref[ft.Image]()
    slogan_ref = ft.Ref[ft.Text]()

    def _nav(route: str):
        try:
            print(f"[GERENCIAL] Navegando para: {route}")
        except Exception:
            pass
        # Preferir push_route quando disponível, com fallback seguro
        try:
            if hasattr(page, "push_route"):

                async def _go():
                    try:
                        await page.push_route(route)
                    except Exception as ex:
                        print(f"[GERENCIAL] push_route falhou: {ex} → fallback go()")
                        try:
                            page.go(route)
                        except Exception:
                            page.route = route
                            page.update()

                if hasattr(page, "run_task"):
                    page.run_task(_go)
                else:
                    # Ambiente sem run_task: usar go() direto
                    try:
                        page.go(route)
                    except Exception:
                        page.route = route
                        page.update()
            else:
                # Sem push_route: usar go() ou set route
                try:
                    page.go(route)
                except Exception:
                    page.route = route
                    page.update()
        except Exception as ex:
            print(f"[GERENCIAL] Erro na navegação: {ex}")
            try:
                page.go(route)
            except Exception:
                page.route = route
                page.update()

    toolbar = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        create_toolbar_button(
                            ft.Icons.INVENTORY,
                            "Estoque",
                            lambda _: _nav("/estoque"),
                            color="#FFC107",
                        ),
                        create_toolbar_button(
                            ft.Icons.RECEIPT,
                            "Vendas",
                            lambda _: _nav("/gerente/relatorio_vendas"),
                            color=COLORS["primary"],
                        ),
                        create_toolbar_button(
                            ft.Icons.ACCOUNT_BALANCE_WALLET,
                            "Financeiro",
                            lambda _: _nav("/financeiro"),
                            color=COLORS["green"],
                        ),
                        create_toolbar_button(
                            ft.Icons.POINT_OF_SALE,
                            "Caixa",
                            lambda _: _nav("/caixa"),
                            color=COLORS["red"],
                        ),
                        create_toolbar_button(
                            ft.Icons.ASSIGNMENT,
                            "Rel. Produtos",
                            lambda _: _nav("/gerente/relatorio_produtos"),
                            color=COLORS["teal"],
                        ),
                        create_toolbar_button(
                            ft.Icons.LOCAL_SHIPPING,
                            "Fornecedores",
                            lambda _: _nav("/gerente/fornecedores"),
                            color="#000000",
                        ),
                        create_toolbar_button(
                            ft.Icons.ASSIGNMENT_RETURN,
                            "Devoluções",
                            lambda _: _nav("/gerente/devolucoes"),
                            color=COLORS["purple"],
                        ),
                    ],
                    wrap=True,
                    spacing=10,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.GREY_200,
        padding=ft.padding.symmetric(horizontal=15, vertical=10),
        border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_300)),
    )

    main_content = ft.Container(
        content=ft.Column(
            [
                # Logo e slogan dinamicamente carregáveis via page.app_data
                ft.Image(
                    ref=logo_ref,
                    src=page.app_data.get("site_logo")
                    or get_asset_path("Mercadinho_Ponto_Certo.png"),
                    width=400,
                    height=400,
                    fit=ft.ImageFit.CONTAIN,
                ),
                ft.Text(
                    page.app_data.get("site_slogan", ""),
                    ref=slogan_ref,
                    size=20,
                    color=(
                        ft.Colors.BLUE_900
                        if hasattr(ft, "colors")
                        else ft.Colors.BLUE_900
                    ),
                    weight=ft.FontWeight.W_500,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
        ),
        expand=True,
        alignment=ft.alignment.center,
        padding=20,
    )

    alerta_numero_ref = ft.Ref[ft.Text]()
    alerta_container_ref = ft.Ref[ft.Container]()

    # Bottom status bar (mensagens rápidas, ex.: boas-vindas)
    bottom_bar_ref = ft.Ref[ft.Container]()
    bottom_bar_text_ref = ft.Ref[ft.Text]()

    def show_bottom_status(
        message: str, bgcolor: str = ft.Colors.GREEN_600, duration_ms: int = 3000
    ):
        try:
            if not bottom_bar_text_ref.current or not bottom_bar_ref.current:
                # refs ainda não anexados à página — armazenar mensagem pendente
                try:
                    page.app_data["gerente_pending_bottom_bar"] = (
                        message,
                        bgcolor,
                        duration_ms,
                    )
                except Exception:
                    pass
                return

            bottom_bar_text_ref.current.value = message
            bottom_bar_text_ref.current.update()
            bottom_bar_ref.current.bgcolor = bgcolor
            bottom_bar_ref.current.visible = True
            bottom_bar_ref.current.update()

            async def _hide():
                try:
                    await page.sleep(duration_ms / 1000.0)
                except Exception:
                    pass
                try:
                    if bottom_bar_ref.current:
                        bottom_bar_ref.current.visible = False
                        bottom_bar_ref.current.update()
                except Exception:
                    pass

            try:
                page.run_task(_hide)
            except Exception:
                try:
                    import threading
                    import time

                    def _f():
                        try:
                            time.sleep(duration_ms / 1000.0)
                            if bottom_bar_ref.current:
                                bottom_bar_ref.current.visible = False
                                bottom_bar_ref.current.update()
                        except Exception:
                            pass

                    threading.Thread(target=_f, daemon=True).start()
                except Exception:
                    pass
        except Exception as ex:
            print(f"[GERENCIAL] Falha ao mostrar bottom status: {ex}")

    try:
        page.show_bottom_status = show_bottom_status
    except Exception:
        pass

    # Ícones na AppBar (Notificações com badge e Configurações separado)
    def _refresh_badge(_):
        try:
            from alertas.alertas_init import atualizar_badge_alertas_no_gerente

            pdv_core = page.app_data.get("pdv_core")
            atualizar_badge_alertas_no_gerente(page, pdv_core)
        except Exception as e:
            print(f"[ALERTAS-BADGE] [WARN] Refresh manual falhou: {e}")

    # Dialog de notificações (popup)
    notificacoes_column = ft.Column([], scroll=ft.ScrollMode.AUTO, spacing=0)

    def _titulo_secao(texto):
        return ft.Container(
            content=ft.Text(
                texto, size=13, weight=ft.FontWeight.W_700, color=ft.Colors.GREY_800
            ),
            padding=ft.padding.only(left=10, right=10, top=8, bottom=4),
        )

    def _criar_item(icone, cor, titulo, subtitulo):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icone, color=cor, size=18),
                    ft.Column(
                        [
                            ft.Text(
                                titulo,
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=COLORS["text"],
                            ),
                            ft.Text(subtitulo, size=12, color=ft.Colors.GREY_700),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            padding=10,
        )

    def _preencher_notificacoes():
        try:
            print("[NOTIFICACOES-POPUP] Iniciando preenchimento...")
            alertas_manager = page.app_data.get("alertas_manager")
            pdv_core_local = page.app_data.get("pdv_core")
            print(
                f"[NOTIFICACOES-POPUP] alertas_manager: {alertas_manager is not None}"
            )
            print(f"[NOTIFICACOES-POPUP] pdv_core_local: {pdv_core_local is not None}")
            itens = []
            if alertas_manager and pdv_core_local:
                print("[NOTIFICACOES-POPUP] Obtendo resumo de alertas...")
                resumo = alertas_manager.obter_resumo_alertas(pdv_core_local)
                print(
                    f"[NOTIFICACOES-POPUP] Resumo obtido: {resumo.keys() if resumo else 'None'}"
                )
                print(
                    f"[NOTIFICACOES-POPUP] Total de alertas: {resumo.get('total', 0)}"
                )
                print(
                    f"[NOTIFICACOES-POPUP] Produtos críticos: {len(resumo.get('produtos_criticos', []))}"
                )
                print(
                    f"[NOTIFICACOES-POPUP] Produtos moderados: {len(resumo.get('produtos_moderados', []))}"
                )
                print(
                    f"[NOTIFICACOES-POPUP] Contas vencidas: {len(resumo.get('detalhes_vencidas', []))}"
                )
                print(
                    f"[NOTIFICACOES-POPUP] Contas próximas: {len(resumo.get('detalhes_proximas', []))}"
                )
                # Salvaguarda: se por algum motivo os detalhes de contas não vierem no resumo,
                # busca diretamente o resumo de contas.
                if not resumo.get("detalhes_vencidas") and not resumo.get(
                    "detalhes_proximas"
                ):
                    print(
                        "[NOTIFICACOES-POPUP] Detalhes de contas ausentes no resumo; consultando obter_resumo_contas()..."
                    )
                    contas_fallback = alertas_manager.obter_resumo_contas(
                        pdv_core_local
                    )
                    resumo["detalhes_vencidas"] = contas_fallback.get(
                        "detalhes_vencidas", []
                    )
                    resumo["detalhes_proximas"] = contas_fallback.get(
                        "detalhes_proximas", []
                    )
                    print(
                        f"[NOTIFICACOES-POPUP] Fallback - Vencidas: {len(resumo['detalhes_vencidas'])}, Próximas: {len(resumo['detalhes_proximas'])}"
                    )
                # Construir seções separadas: Estoque e Financeiro
                estoque_items = []
                for a in resumo.get("produtos_criticos", []):
                    estoque_items.append(
                        _criar_item(
                            ft.Icons.WARNING,
                            COLORS["red"],
                            f"Estoque crítico: {a['nome']}",
                            f"{a['estoque_atual']}/{a['estoque_minimo']} (falta {a['falta']})",
                        )
                    )
                for a in resumo.get("produtos_moderados", []):
                    estoque_items.append(
                        _criar_item(
                            ft.Icons.WARNING_AMBER,
                            COLORS["orange"],
                            f"Estoque baixo: {a['nome']}",
                            f"{a['estoque_atual']}/{a['estoque_minimo']} (falta {a['falta']})",
                        )
                    )

                financeiro_items = []
                for c in resumo.get("detalhes_vencidas", []):
                    financeiro_items.append(
                        _criar_item(
                            ft.Icons.PAYMENTS,
                            COLORS["red"],
                            f"Conta vencida: {c['descricao']}",
                            f"R$ {float(c['valor']):.2f} (há {c['dias_atraso']} dias)",
                        )
                    )
                for c in resumo.get("detalhes_proximas", []):
                    financeiro_items.append(
                        _criar_item(
                            ft.Icons.PAYMENTS,
                            COLORS["orange"],
                            f"Conta próxima: {c['descricao']}",
                            f"R$ {float(c['valor']):.2f} (em {c['dias_para_vencer']} dias)",
                        )
                    )

                # Montar lista final com seções
                if estoque_items:
                    itens.append(_titulo_secao("Estoque"))
                    itens.extend(estoque_items)
                    if financeiro_items:
                        itens.append(ft.Divider(height=1))

                if financeiro_items:
                    itens.append(_titulo_secao("Financeiro"))
                    itens.extend(financeiro_items)

                print(
                    f"[NOTIFICACOES-POPUP] Total de itens criados: {len(estoque_items) + len(financeiro_items)}"
                )

                # Marcar como lidas: armazenar total visto e atualizar badge para 0
                try:
                    page.app_data["alerts_last_seen_total"] = int(
                        resumo.get("total", 0) or 0
                    )
                    import time as _t

                    page.app_data["alerts_last_seen_ts"] = _t.time()
                    from alertas.alertas_init import atualizar_badge_alertas_no_gerente

                    atualizar_badge_alertas_no_gerente(page, pdv_core_local)
                    print(
                        "[NOTIFICACOES-POPUP] Alertas marcados como lidos; badge atualizado."
                    )
                except Exception as _ex:
                    print(f"[NOTIFICACOES-POPUP] Aviso ao marcar como lidos: {_ex}")
            else:
                print(
                    "[NOTIFICACOES-POPUP] alertas_manager ou pdv_core_local não disponível"
                )

            if not itens:
                print("[NOTIFICACOES-POPUP] Nenhum item - exibindo mensagem padrão")
                itens.append(
                    ft.Container(
                        content=ft.Text(
                            "Sem notificações", size=12, color=ft.Colors.GREY_700
                        ),
                        padding=10,
                    )
                )

            notificacoes_column.controls = itens
            print("[NOTIFICACOES-POPUP] Controles atualizados, tentando update...")
            notificacoes_column.update()
            print("[NOTIFICACOES-POPUP] Update concluído!")
        except Exception as ex:
            print(f"[NOTIFICACOES-POPUP] ERRO ao preencher popup de notificações: {ex}")
            import traceback

            traceback.print_exc()

    def _fechar_notificacoes(_):
        try:
            print("[NOTIFICACOES-POPUP] Fechando popup...")
            nonlocal popup_open
            if hasattr(page, "overlay") and isinstance(page.overlay, list):
                if popup_stack in page.overlay:
                    page.overlay.remove(popup_stack)
                    print("[NOTIFICACOES-POPUP] Removido overlay popup_stack")
            popup_open = False
            page.update()
        except Exception:
            pass

    def _cleanup_dialog():
        try:
            print("[NOTIFICACOES-POPUP] Limpando estado do dialog...")
            # Fechar popup_stack (dialog de notificações)
            try:
                if hasattr(page, "overlay") and isinstance(page.overlay, list):
                    if popup_stack in page.overlay:
                        page.overlay.remove(popup_stack)
                        print("[NOTIFICACOES-POPUP] Removido de page.overlay")
            except Exception as _ex:
                print(f"[NOTIFICACOES-POPUP] Aviso ao limpar overlay: {_ex}")
            page.update()
        except Exception as ex:
            print(f"[NOTIFICACOES-POPUP] ERRO no cleanup: {ex}")

    popup_open = False
    scrim = ft.Container(
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.45, ft.Colors.BLACK),
        on_click=lambda e: _fechar_notificacoes(e),
    )
    # Área de refresh (ícone ↺ que vira carregando brevemente)
    refresh_slot_ref = ft.Ref[ft.Container]()

    def _handle_refresh(e):
        try:
            import asyncio

            async def _do():
                try:
                    if refresh_slot_ref.current is not None:
                        refresh_slot_ref.current.content = ft.ProgressRing(
                            width=18, height=18, stroke_width=2
                        )
                        refresh_slot_ref.current.update()
                    await asyncio.sleep(0.4)
                    _refresh_badge(e)
                    _preencher_notificacoes()
                finally:
                    if refresh_slot_ref.current is not None:
                        refresh_slot_ref.current.content = ft.IconButton(
                            icon=ft.Icons.REFRESH,
                            tooltip="Atualizar",
                            on_click=_handle_refresh,
                        )
                        refresh_slot_ref.current.update()

            if hasattr(page, "run_task"):
                page.run_task(_do)
            else:
                _refresh_badge(e)
                _preencher_notificacoes()
        except Exception as ex:
            print(f"[NOTIFICACOES-POPUP] Erro ao animar refresh: {ex}")

    popup_panel = ft.Container(
        width=380,
        height=460,
        bgcolor=ft.Colors.WHITE,
        border_radius=8,
        padding=12,
        content=ft.Column(
            [
                # Cabeçalho centralizado com refresh à direita
                ft.Stack(
                    [
                        ft.Container(
                            content=ft.Text("Notificações", weight=ft.FontWeight.BOLD),
                            alignment=ft.alignment.center,
                        ),
                        ft.Container(
                            ref=refresh_slot_ref,
                            content=ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip="Atualizar",
                                on_click=_handle_refresh,
                            ),
                            alignment=ft.alignment.center_right,
                        ),
                    ]
                ),
                ft.Divider(height=1),
                ft.Container(expand=True, content=notificacoes_column),
                ft.Row(
                    [
                        ft.TextButton(
                            "Fechar", on_click=lambda e: _fechar_notificacoes(e)
                        )
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=8,
        ),
    )
    popup_stack = ft.Stack(
        [
            scrim,
            ft.Container(
                expand=True, alignment=ft.alignment.center, content=popup_panel
            ),
        ]
    )

    def _abrir_notificacoes(_):
        try:
            print("\n[NOTIFICACOES-POPUP] ========== ABRINDO POPUP ==========")
            nonlocal popup_open
            # Evitar abrir duas vezes
            if popup_open:
                print(
                    "[NOTIFICACOES-POPUP] Já está aberto: apenas atualizando conteúdo"
                )
                _preencher_notificacoes()
                page.update()
                return
            # Anexar overlay
            if hasattr(page, "overlay") and isinstance(page.overlay, list):
                page.overlay.append(popup_stack)
            popup_open = True
            page.update()

            # Após o popup estar visível, atualizar badge e conteúdo
            print("[NOTIFICACOES-POPUP] Atualizando badge...")
            _refresh_badge(_)
            print("[NOTIFICACOES-POPUP] Badge atualizado, preenchendo notificações...")
            _preencher_notificacoes()
            print("[NOTIFICACOES-POPUP] Fazendo page.update() final...")
            page.update()
            print(
                "[NOTIFICACOES-POPUP] ========== POPUP ABERTO COM SUCESSO =========\n"
            )
        except Exception as ex:
            print(f"[NOTIFICACOES-POPUP] ERRO ao abrir notificações: {ex}")
            import traceback

            traceback.print_exc()

    notifications_button = ft.IconButton(
        icon=ft.Icons.NOTIFICATIONS,
        tooltip="Notificações",
        on_click=_abrir_notificacoes,
        icon_color=COLORS["text"],
    )
    settings_button = ft.IconButton(
        icon=ft.Icons.SETTINGS,
        tooltip="Configurações",
        on_click=lambda _: _nav("/gerente/configuracoes"),
        icon_color=COLORS["text"],
    )

    badge_container = ft.Container(
        ref=alerta_container_ref,
        visible=False,
        bgcolor="#DC3545",
        width=18,
        height=18,
        border_radius=9,
        padding=0,
        margin=ft.margin.only(left=-10, top=-8),
        content=ft.Container(
            content=ft.Text(
                "",
                size=10,
                weight=ft.FontWeight.BOLD,
                ref=alerta_numero_ref,
                color=ft.Colors.WHITE,
            ),
            alignment=ft.alignment.center,
        ),
        on_click=_abrir_notificacoes,
    )

    # Notificações (sino) com badge ao lado, e depois o ícone de configurações
    notifications_with_badge = ft.Row(
        [
            notifications_button,
            badge_container,
        ],
        spacing=0,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    app_bar_gerente = ft.AppBar(
        title=ft.Text(
            "PAINEL GERENCIAL", weight=ft.FontWeight.BOLD, color=COLORS["text"]
        ),
        bgcolor=ft.Colors.GREY_100,
        actions=[
            ft.Row(
                [
                    ft.Icon(ft.Icons.ACCOUNT_CIRCLE, color=COLORS["text"]),
                    ft.Text(
                        user_display_name,
                        style=ft.TextThemeStyle.TITLE_MEDIUM,
                        color=COLORS["text"],
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            notifications_with_badge,
            settings_button,
            ft.FilledButton(
                "Sair", on_click=lambda e: handle_logout(e), icon=ft.Icons.LOGOUT
            ),
        ],
    )

    view = ft.View(
        "/gerente",
        [
            app_bar_gerente,
            toolbar,
            main_content,
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
        bgcolor=COLORS["background"],
    )
    # Se havia mensagem pendente (armazenada por handle_login antes do mount), exibi‑la agora
    try:
        pending = page.app_data.pop("gerente_pending_bottom_bar", None)
        if not pending:
            # fallback para chave genérica criada pelo handle_login
            pending = page.app_data.pop("pending_welcome_message", None)
        if pending:
            try:
                if isinstance(pending, tuple):
                    msg, col, dur = pending
                else:
                    msg = pending
                    col = ft.Colors.GREEN_600
                    dur = 3000
                try:
                    show_bottom_status(msg, col, dur)
                except Exception:
                    # última alternativa: snack
                    try:
                        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=col)
                        page.snack_bar.open = True
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass

    def _on_key(e: ft.KeyboardEvent):
        try:
            key_alert = (str(e.key) or "").upper()
            if key_alert == "ESCAPE" and popup_open:
                print("[NOTIFICACOES-POPUP] ESC pressionado: fechando popup...")
                _fechar_notificacoes(e)
        except Exception as ex:
            print(f"[NOTIFICACOES-POPUP] Erro no on_key: {ex}")

    view.on_keyboard_event = _on_key

    def on_view_did_mount():
        page.bgcolor = COLORS["background"]
        try:
            from alertas.alertas_init import atualizar_badge_alertas_no_gerente

            pdv_core = page.app_data.get("pdv_core")
            atualizar_badge_alertas_no_gerente(page, pdv_core)
        except Exception as e:
            print(f"[ALERTAS] Erro ao atualizar badge no mount: {e}")
        # Atualizar logo e slogan caso tenham sido alterados nas configurações
        try:
            logo = page.app_data.get("site_logo")
            slogan = page.app_data.get("site_slogan")
            try:
                if logo and logo_ref.current:
                    logo_ref.current.src = logo
                    logo_ref.current.update()
            except Exception:
                pass
            try:
                # aplicar mesmo quando a string for vazia (para permitir remoção persistente)
                if slogan_ref.current is not None and (slogan is not None):
                    slogan_ref.current.value = slogan or ""
                    slogan_ref.current.update()
            except Exception:
                pass
        except Exception as _ex:
            print(f"[GERENCIAL] Falha ao aplicar identidade visual no mount: {_ex}")

    view.on_view_did_mount = on_view_did_mount

    page.app_data["alerta_numero_ref"] = alerta_numero_ref
    page.app_data["alerta_container_ref"] = alerta_container_ref
    # Tornar os refs de logo/slogan acessíveis globalmente para atualização instantânea
    try:
        page.app_data["gerente_site_logo_ref"] = logo_ref
        page.app_data["gerente_site_slogan_ref"] = slogan_ref
    except Exception:
        pass

    # Atualização automática do badge (a cada 60s) via tarefa assíncrona
    async def _badge_auto_loop():
        while True:
            try:
                # Atualiza somente quando estiver no painel do gerente
                if str(page.route).startswith("/gerente"):
                    from alertas.alertas_init import atualizar_badge_alertas_no_gerente

                    pdv_core_local = page.app_data.get("pdv_core")
                    atualizar_badge_alertas_no_gerente(page, pdv_core_local)
            except Exception as ex:
                print(f"[ALERTAS-BADGE] [WARN] Auto-loop falhou: {ex}")
            # Aguarda 60 segundos
            try:
                await page.sleep(60000)
            except Exception:
                # Em ambientes sem page.sleep, tentar asyncio.sleep
                try:
                    import asyncio

                    await asyncio.sleep(60)
                except Exception:
                    pass

    # Cancela tarefa anterior, se existir
    old_task = page.app_data.get("badge_task")
    try:
        if old_task:
            old_task.cancel()
    except Exception:
        pass
    try:
        task = page.run_task(_badge_auto_loop)
        page.app_data["badge_task"] = task
    except Exception as ex:
        print(f"[ALERTAS-BADGE] [WARN] Falha ao iniciar auto-loop: {ex}")
    return view
