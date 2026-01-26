"""Componentes para agendamento automático de fechamento/reabertura do caixa."""

from datetime import datetime

import flet as ft


def create_schedule_dialog(page: ft.Page, pdv_core, current_user, on_complete=None):
    """Cria um diálogo para agendar fechamento/reabertura do caixa usando overlay customizado.

    Args:
        page: página Flet
        pdv_core: objeto do núcleo de negócio
        current_user: usuário logado (deve ser gerente)
        on_complete: callback chamado ao sucesso

    Returns:
        Container (overlay customizado)
    """
    from .state import COLORS

    # Referência para o campo de data
    data_field = ft.TextField(
        label="Data de Vigência (dd/mm/aaaa)",
        value=datetime.now().strftime("%d/%m/%Y"),
        read_only=True,
        bgcolor=ft.Colors.GREY_200,
        text_size=12,
    )

    # Variável para armazenar a referência do date_picker
    date_picker_ref = None

    def atualizar_data_selecionada(data_obj):
        """Atualiza o campo de data quando uma data é selecionada"""
        if data_obj:
            data_field.value = data_obj.strftime("%d/%m/%Y")
            page.update()

    def abrir_date_picker():
        """Abre o seletor de data"""
        nonlocal date_picker_ref
        if date_picker_ref is None:
            date_picker_ref = ft.DatePicker(
                first_date=datetime.now(),
                last_date=datetime(2099, 12, 31),
                on_change=lambda e: atualizar_data_selecionada(date_picker_ref.value),
                help_text="Selecione uma data",
                cancel_text="Cancelar",
                confirm_text="OK",
                error_format_text="Formato inválido",
                error_invalid_text="Data fora do intervalo",
                field_label_text="Data",
                field_hint_text="dd/mm/aaaa",
            )
            page.overlay.append(date_picker_ref)
            page.update()

        page.open(date_picker_ref)

    hora_fechamento_field = ft.TextField(
        label="Hora de Fechamento (HH:MM)",
        hint_text="Ex: 20:30",
        value="20:30",
        text_size=12,
    )

    hora_reabertura_field = ft.TextField(
        label="Hora de Reabertura (HH:MM)",
        hint_text="Ex: 07:00",
        value="07:00",
        text_size=12,
    )

    notas_field = ft.TextField(
        label="Notas (opcional)",
        multiline=True,
        min_lines=2,
        max_lines=3,
        text_size=12,
    )

    status_text = ft.Text("", size=14, color=COLORS.get("success", ft.Colors.GREEN))

    def validar_hora(hora_str: str) -> bool:
        """Valida formato HH:MM"""
        try:
            partes = hora_str.split(":")
            if len(partes) != 2:
                return False
            hh = int(partes[0])
            mm = int(partes[1])
            return 0 <= hh <= 23 and 0 <= mm <= 59
        except Exception:
            return False

    def fechar_overlay():
        try:
            try:
                overlay.visible = False
            except Exception:
                pass
            try:
                setattr(overlay, "open", False)
            except Exception:
                pass
            try:
                if overlay in getattr(page, "overlay", []):
                    page.overlay.remove(overlay)
            except Exception:
                pass
        except Exception:
            pass
        try:
            page.update()
        except Exception:
            pass

    def salvar_agendamento(e):
        """Salva o agendamento no banco"""
        # Validações
        data = data_field.value.strip()
        hora_fecho = hora_fechamento_field.value.strip()
        hora_abert = hora_reabertura_field.value.strip()
        notas = notas_field.value.strip()

        if not validar_hora(hora_fecho):
            status_text.value = "❌ Hora de fechamento inválida (use HH:MM)"
            status_text.color = COLORS.get("danger", ft.Colors.RED)
            page.update()
            return

        if not validar_hora(hora_abert):
            status_text.value = "❌ Hora de reabertura inválida (use HH:MM)"
            status_text.color = COLORS.get("danger", ft.Colors.RED)
            page.update()
            return

        # Salva no banco
        sucesso = pdv_core.schedule_caixa_closure(
            data_vigencia=data,
            hora_fechamento=hora_fecho,
            hora_reabertura=hora_abert,
            usuario=(
                current_user.username
                if hasattr(current_user, "username")
                else str(current_user)
            ),
            notas=notas,
        )

        if sucesso:
            status_text.value = f"✅ Agendamento salvo! Caixa fechará às {hora_fecho} e reabrirá às {hora_abert}"
            status_text.color = COLORS.get("success", ft.Colors.GREEN)
            page.update()

            # Callback de sucesso (sem delay)
            if on_complete:
                on_complete()
        else:
            status_text.value = "❌ Erro ao salvar agendamento"
            status_text.color = COLORS.get("danger", ft.Colors.RED)
            page.update()

    # Criar conteúdo do overlay
    content = ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    "Agendar Fechamento/Reabertura do Caixa",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    "Configure os horários para fechamento e reabertura automática:",
                    size=12,
                ),
                ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
                ft.Row(
                    [
                        data_field,
                        ft.IconButton(
                            icon=ft.Icons.CALENDAR_TODAY,
                            on_click=lambda e: abrir_date_picker(),
                            tooltip="Selecionar data",
                            icon_size=18,
                        ),
                    ],
                    spacing=5,
                ),
                hora_fechamento_field,
                hora_reabertura_field,
                notas_field,
                ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
                status_text,
                ft.Row(
                    [
                        ft.TextButton(
                            "Cancelar",
                            on_click=lambda e: fechar_overlay(),
                        ),
                        ft.ElevatedButton(
                            "Salvar",
                            on_click=salvar_agendamento,
                            bgcolor=COLORS.get("primary", ft.Colors.BLUE),
                            color=ft.Colors.WHITE,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=8,
        ),
        padding=20,
        bgcolor="white",
        border_radius=10,
        shadow=ft.BoxShadow(spread_radius=2, blur_radius=5),
    )

    # Criar overlay
    overlay = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(content=content, width=450),
                        ft.Container(expand=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        visible=True,
        bgcolor="rgba(0, 0, 0, 0.5)",
        expand=True,
    )

    def fechar_dialog():
        overlay.visible = False
        page.update()

    if overlay not in page.overlay:
        try:
            try:
                setattr(overlay, "open", True)
            except Exception:
                pass
            page.overlay.append(overlay)
        except Exception:
            try:
                page.overlay.append(overlay)
            except Exception:
                pass
    page.update()

    return overlay


def create_schedule_status_widget(page: ft.Page, pdv_core):
    """Cria um widget exibindo status do agendamento atual."""
    from .state import COLORS

    container = ft.Container(
        bgcolor=ft.Colors.BLUE_50,
        border=ft.border.all(1, ft.Colors.BLUE_300),
        border_radius=8,
        padding=10,
    )

    def atualizar_status():
        """Atualiza o status em tempo real"""
        schedule = pdv_core.get_proxima_fechamento_programado()

        if not schedule:
            container.content = ft.Text(
                "Nenhum agendamento ativo",
                size=12,
                color=COLORS.get("text_muted", ft.Colors.GREY_700),
            )
        else:
            status = schedule.get("status", "Ativo")
            foi_fechado = schedule.get("caixa_foi_fechado", False)
            foi_reaberto = schedule.get("caixa_foi_reaberto", False)

            icon_fecho = "✓" if foi_fechado else "○"
            icon_abert = "✓" if foi_reaberto else "○"

            container.content = ft.Column(
                [
                    ft.Text(
                        f"📋 Agendamento ({status})",
                        size=12,
                        weight="bold",
                        color=COLORS.get("primary", ft.Colors.BLUE),
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                f"{icon_fecho} Fechamento: {schedule.get('hora_fechamento')}",
                                size=11,
                            ),
                            ft.Text(
                                f"{icon_abert} Reabertura: {schedule.get('hora_reabertura')}",
                                size=11,
                            ),
                        ]
                    ),
                ],
                spacing=5,
            )

        page.update()

    # Atualiza inicialmente
    atualizar_status()

    # Retorna container e função de atualização
    container.update_status = atualizar_status
    return container


def create_schedule_override_dialog(
    page: ft.Page, pdv_core, schedule_id: int, on_complete=None
):
    """Cria um diálogo para o gerente pausar/retomar/cancelar um agendamento.

    Args:
        page: página Flet
        pdv_core: objeto do núcleo de negócio
        schedule_id: ID do agendamento
        on_complete: callback após ação

    Returns:
        ft.AlertDialog
    """
    from .state import COLORS

    status_text = ft.Text("", size=13, color=COLORS.get("info", ft.Colors.BLUE))

    # Referências para os campos que serão atualizados
    data_text_ref = ft.Ref()
    fechamento_text_ref = ft.Ref()
    reabertura_text_ref = ft.Ref()
    status_display_ref = ft.Ref()

    def atualizar_exibicao():
        """Atualiza a exibição do agendamento"""
        schedule = pdv_core.get_caixa_schedule_by_id(schedule_id)

        if schedule and data_text_ref.current:
            data_text_ref.current.value = schedule.data_vigencia
            fechamento_text_ref.current.value = schedule.hora_fechamento
            reabertura_text_ref.current.value = schedule.hora_reabertura
            status_display_ref.current.value = schedule.status
            page.update()

    # Buscar informações do agendamento pelo ID
    schedule = pdv_core.get_caixa_schedule_by_id(schedule_id)

    # Construir conteúdo com as informações do agendamento
    content_controls = [
        ft.Text("Agendamento Ativo:", size=14, weight="bold"),
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
    ]

    if schedule:
        content_controls.extend(
            [
                ft.Row(
                    [
                        ft.Text("Data:", width=80, weight="bold"),
                        ft.Text(schedule.data_vigencia, size=12, ref=data_text_ref),
                    ]
                ),
                ft.Row(
                    [
                        ft.Text("Fechamento:", width=80, weight="bold"),
                        ft.Text(
                            schedule.hora_fechamento, size=12, ref=fechamento_text_ref
                        ),
                    ]
                ),
                ft.Row(
                    [
                        ft.Text("Reabertura:", width=80, weight="bold"),
                        ft.Text(
                            schedule.hora_reabertura, size=12, ref=reabertura_text_ref
                        ),
                    ]
                ),
                ft.Row(
                    [
                        ft.Text("Status:", width=80, weight="bold"),
                        ft.Text(
                            schedule.status,
                            size=12,
                            color=ft.Colors.BLUE,
                            ref=status_display_ref,
                        ),
                    ]
                ),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.Text("Escolha uma ação:", size=13, weight="bold"),
                ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                status_text,
            ]
        )
    else:
        content_controls.append(
            ft.Text(
                "Nenhum agendamento ativo encontrado.",
                size=12,
                color=ft.Colors.GREY_700,
            )
        )

    def fazer_override(novo_status: str):
        """Aplica o override e atualiza instantaneamente"""
        sucesso = pdv_core.override_caixa_schedule(schedule_id, novo_status)

        if sucesso:
            status_text.value = f"✅ Agendamento {novo_status.lower()}!"
            status_text.color = COLORS.get("success", ft.Colors.GREEN)

            # Atualizar exibição instantaneamente SEM fechar o diálogo
            atualizar_exibicao()

            # Chamar callback se houver
            if on_complete:
                print(f"[DEBUG] Chamando callback on_complete após {novo_status}")
                on_complete()
            else:
                print("[AVISO] Nenhum callback on_complete foi passado")
        else:
            status_text.value = "❌ Erro ao aplicar ação"
            status_text.color = COLORS.get("danger", ft.Colors.RED)

        page.update()

    # Create overlay container
    overlay = ft.Container(expand=True)  # placeholder

    def fechar_overlay():
        overlay.visible = False
        page.update()

    content = ft.Column(
        spacing=12,
        controls=[
            ft.Text("Controle de Agendamento", size=18, weight="bold"),
            ft.Divider(),
            ft.Column(
                content_controls,
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
            ft.Row(
                [
                    ft.TextButton(
                        "Fechar",
                        on_click=lambda e: fechar_overlay(),
                    ),
                    ft.ElevatedButton(
                        "Pausar",
                        on_click=lambda e: fazer_override("Pausado"),
                        bgcolor=ft.Colors.ORANGE,
                        color=ft.Colors.WHITE,
                    ),
                    ft.ElevatedButton(
                        "Retomar",
                        on_click=lambda e: fazer_override("Ativo"),
                        bgcolor=COLORS.get("success", ft.Colors.GREEN),
                        color=ft.Colors.WHITE,
                    ),
                    ft.ElevatedButton(
                        "Cancelar",
                        on_click=lambda e: fazer_override("Cancelado"),
                        bgcolor=COLORS.get("danger", ft.Colors.RED),
                        color=ft.Colors.WHITE,
                    ),
                ],
                wrap=True,
                spacing=8,
            ),
        ],
    )

    overlay = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(
                            content=content,
                            width=450,
                            bgcolor="white",
                            border_radius=8,
                            padding=20,
                        ),
                        ft.Container(expand=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        visible=True,
        bgcolor="rgba(0, 0, 0, 0.5)",
        expand=True,
    )

    if overlay not in page.overlay:
        page.overlay.append(overlay)
    page.update()

    return overlay
