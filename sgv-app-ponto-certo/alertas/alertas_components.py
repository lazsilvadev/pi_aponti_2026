"""
Componente Visual de Alertas de Estoque
Exibe alertas em cards visuais no dashboard gerencial
"""

import flet as ft


def criar_card_alerta(
    alerta: dict, on_resolver=None, on_descartar=None
) -> ft.Container:
    """Cria um card visual para um alerta de estoque"""

    # Determinar cores baseado na severidade
    # Considera estoque zerado como crítico independente do mínimo
    if (
        alerta["estoque_atual"] == 0
        or alerta["falta"] >= alerta["estoque_minimo"] * 0.5
    ):
        # Crítico (falta > 50% do mínimo)
        cor_borda = "#DC3545"
        cor_fundo = "#FFE5E5"
        cor_icone = "#DC3545"
        severidade = "🔴 CRÍTICO"
    else:
        # Moderado
        cor_borda = "#FFC107"
        cor_fundo = "#FFFACD"
        cor_icone = "#FF9800"
        severidade = "🟡 MODERADO"

    # Barra de progresso visual (evitar divisão por zero)
    if (alerta.get("estoque_minimo") or 0) <= 0:
        percentual_falta = 100 if alerta.get("estoque_atual", 0) == 0 else 0
    else:
        percentual_falta = min((alerta["falta"] / alerta["estoque_minimo"]) * 100, 100)

    return ft.Container(
        content=ft.Column(
            [
                # Cabeçalho com severidade
                ft.Row(
                    [
                        ft.Icon(ft.Icons.WARNING, color=cor_icone, size=24),
                        ft.Text(
                            severidade,
                            weight=ft.FontWeight.BOLD,
                            size=14,
                            color=cor_icone,
                        ),
                    ],
                    spacing=10,
                ),
                # Nome do produto
                ft.Text(
                    alerta["nome"], weight=ft.FontWeight.W_600, size=16, color="#131111"
                ),
                # Código de barras
                ft.Text(
                    f"Código: {alerta['codigo']}",
                    size=11,
                    color="#666",
                ),
                # Estoque
                ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("Estoque Atual", size=10, color="#666"),
                                ft.Text(
                                    str(alerta["estoque_atual"]),
                                    weight=ft.FontWeight.BOLD,
                                    size=18,
                                    color="#007BFF",
                                ),
                            ],
                            spacing=2,
                        ),
                        ft.Container(width=20),
                        ft.Column(
                            [
                                ft.Text("Estoque Mínimo", size=10, color="#666"),
                                ft.Text(
                                    str(alerta["estoque_minimo"]),
                                    weight=ft.FontWeight.BOLD,
                                    size=18,
                                    color="#007BFF",
                                ),
                            ],
                            spacing=2,
                        ),
                        ft.Container(width=20),
                        ft.Column(
                            [
                                ft.Text("Falta", size=10, color="#666"),
                                ft.Text(
                                    str(alerta["falta"]),
                                    weight=ft.FontWeight.BOLD,
                                    size=18,
                                    color=cor_icone,
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=10,
                ),
                # Barra de progresso
                ft.Container(
                    content=ft.ProgressBar(
                        value=min(percentual_falta / 100, 1.0),
                        color=cor_icone,
                        height=6,
                    ),
                    margin=ft.margin.only(top=10, bottom=10),
                ),
                # Data de detecção
                ft.Text(
                    f"Detectado em: {alerta['data_deteccao'].split('T')[0]}",
                    size=10,
                    color="#999",
                ),
                # Botões de ação
                ft.Row(
                    [
                        (
                            ft.ElevatedButton(
                                "Resolver",
                                icon=ft.Icons.CHECK_CIRCLE,
                                on_click=lambda e: (
                                    on_resolver(alerta["alerta_id"])
                                    if on_resolver
                                    else None
                                ),
                                color=ft.Colors.WHITE,
                                bgcolor="#28A745",
                                icon_color=ft.Colors.WHITE,
                            )
                            if on_resolver
                            else ft.Container()
                        ),
                        (
                            ft.ElevatedButton(
                                "N/A",
                                icon=ft.Icons.CANCEL,
                                on_click=lambda e: (
                                    on_descartar(alerta["alerta_id"])
                                    if on_descartar
                                    else None
                                ),
                                color=ft.Colors.WHITE,
                                bgcolor="#6C757D",
                                icon_color=ft.Colors.WHITE,
                            )
                            if on_descartar
                            else ft.Container()
                        ),
                    ],
                    spacing=10,
                ),
            ],
            spacing=10,
        ),
        padding=15,
        border=ft.border.all(2, cor_borda),
        border_radius=8,
        bgcolor=cor_fundo,
        margin=ft.margin.only(bottom=10),
    )


def criar_resumo_alertas(resumo: dict) -> ft.Container:
    """Cria um resumo visual dos alertas"""

    total = resumo.get("total", 0)
    critico = resumo.get("critico", 0)
    moderado = resumo.get("moderado", 0)

    if total == 0:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE, size=48, color="#28A745"),
                    ft.Text(
                        "✅ Estoque OK!",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color="#28A745",
                    ),
                    ft.Text("Nenhum alerta ativo", size=12, color="#666"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            padding=20,
            border_radius=8,
            bgcolor="#E8F5E9",
            border=ft.border.all(2, "#28A745"),
            margin=ft.margin.only(bottom=15),
        )

    return ft.Container(
        content=ft.Row(
            [
                # Card Total
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "TOTAL",
                                size=11,
                                color="#666",
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Text(
                                str(total),
                                size=32,
                                weight=ft.FontWeight.BOLD,
                                color="#131111",
                            ),
                            ft.Text("produtos com alerta", size=9, color="#999"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=3,
                    ),
                    padding=15,
                    expand=True,
                    bgcolor="#F5F5F5",
                    border_radius=8,
                    border=ft.border.all(1, "#DDD"),
                ),
                # Card Crítico
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "🔴 CRÍTICO",
                                size=11,
                                color="#DC3545",
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Text(
                                str(critico),
                                size=32,
                                weight=ft.FontWeight.BOLD,
                                color="#DC3545",
                            ),
                            ft.Text("acima de 50% falta", size=9, color="#999"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=3,
                    ),
                    padding=15,
                    expand=True,
                    bgcolor="#FFE5E5",
                    border_radius=8,
                    border=ft.border.all(2, "#DC3545"),
                ),
                # Card Moderado
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "🟡 MODERADO",
                                size=11,
                                color="#FF9800",
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Text(
                                str(moderado),
                                size=32,
                                weight=ft.FontWeight.BOLD,
                                color="#FF9800",
                            ),
                            ft.Text("até 50% falta", size=9, color="#999"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=3,
                    ),
                    padding=15,
                    expand=True,
                    bgcolor="#FFFACD",
                    border_radius=8,
                    border=ft.border.all(2, "#FF9800"),
                ),
            ],
            spacing=10,
        ),
        padding=0,
        margin=ft.margin.only(bottom=15),
    )


def criar_panel_alertas(page, pdv_core) -> ft.Container:
    """Cria o painel completo de alertas para o dashboard gerencial"""

    alertas_manager = page.app_data.get("alertas_manager")
    if not alertas_manager:
        return ft.Container(
            content=ft.Text("Sistema de alertas não inicializado", color="#999"),
            padding=20,
        )

    # Obter resumo
    resumo = alertas_manager.obter_resumo_alertas(pdv_core)

    # Referências para atualização
    alertas_list_ref = ft.Ref[ft.Column]()
    resumo_container_ref = ft.Ref[ft.Container]()

    def _atualizar_alertas():
        """Atualiza a exibição de alertas"""
        try:
            resumo = alertas_manager.obter_resumo_alertas(pdv_core)

            # Atualizar resumo
            if resumo_container_ref.current:
                resumo_container_ref.current.content = criar_resumo_alertas(resumo)
                resumo_container_ref.current.update()

            # Atualizar lista de alertas
            if alertas_list_ref.current:
                alertas_controls = []
                for alerta in resumo.get("produtos_criticos", []) + resumo.get(
                    "produtos_moderados", []
                ):
                    card = criar_card_alerta(
                        alerta,
                        on_resolver=_resolver_alerta,
                        on_descartar=_descartar_alerta,
                    )
                    alertas_controls.append(card)

                alertas_list_ref.current.controls = alertas_controls
                alertas_list_ref.current.update()
        except Exception as e:
            print(f"[ALERTAS-UI] ❌ Erro ao atualizar: {e}")

    def _resolver_alerta(alerta_id: str):
        """Marca alerta como resolvido"""
        if alertas_manager.marcar_como_resolvido(alerta_id):
            _atualizar_alertas()
            print(f"[ALERTAS-UI] ✅ Alerta {alerta_id} resolvido")

    def _descartar_alerta(alerta_id: str):
        """Marca alerta como não aplicável"""
        if alertas_manager.marcar_como_nao_aplicavel(alerta_id):
            _atualizar_alertas()
            print(f"[ALERTAS-UI] ℹ️  Alerta {alerta_id} descartado")

    # Criar conteúdo inicial
    alertas_controls = []
    for alerta in resumo.get("produtos_criticos", []) + resumo.get(
        "produtos_moderados", []
    ):
        card = criar_card_alerta(
            alerta, on_resolver=_resolver_alerta, on_descartar=_descartar_alerta
        )
        alertas_controls.append(card)

    return ft.Container(
        content=ft.Column(
            [
                ft.Text("⚠️  ALERTAS DE ESTOQUE", size=18, weight=ft.FontWeight.BOLD),
                # Resumo dos alertas
                ft.Container(
                    content=criar_resumo_alertas(resumo), ref=resumo_container_ref
                ),
                # Lista de alertas
                ft.Column(
                    alertas_controls,
                    spacing=5,
                    ref=alertas_list_ref,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
            ],
            spacing=10,
            expand=True,
        ),
        padding=20,
        expand=True,
    )
