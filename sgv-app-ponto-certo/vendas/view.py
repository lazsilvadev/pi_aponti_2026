import os
import webbrowser
from datetime import datetime, time, timedelta
from pathlib import Path

import flet as ft

from utils.export_utils import generate_csv_file, generate_pdf_file

# Paleta de cores usada na tela de vendas (cores da logo Mercadinho Ponto Certo)
COLORS = {
    "primary": "#034986",  # Azul da logo
    "accent": "#FFB347",  # Laranja suave da logo
    "background": "#F0F4F8",  # Cinza suave
    "text": "#2D3748",  # Texto escuro
    "green": "#8FC74F",  # Verde da logo
}


def create_relatorio_vendas_view(page, pdv_core, handle_back):
    today_date = datetime.today().date()
    # =========================================================================
    # ESTILOS E VARIÁVEIS
    # =========================================================================
    bg_color = ft.Colors.WHITE

    # Estado inicial e controles mínimos necessários para a view
    vendas_filtradas = []
    caixa_session = None

    # Limite de itens que o fallback pode carregar para popular a tabela
    FALLBACK_LIMIT = 200
    # Estado do fallback paginado
    fallback_list = []
    fallback_loaded = 0
    fallback_total_found = 0

    vendas_hoje_valor = ft.Text("R$ 0,00", size=18, weight=ft.FontWeight.BOLD)
    lucro_hoje_valor = ft.Text("R$ 0,00", size=18, weight=ft.FontWeight.BOLD)

    # Variáveis para o resumo de estatísticas
    total_itens_text = ft.Text(
        "0", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700
    )
    ticket_medio_text = ft.Text(
        "R$ 0,00", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700
    )
    pagamento_text = ft.Text(
        "-", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_800
    )

    percentuais_produtos_column = ft.ListView(expand=True, spacing=6)

    def atualizar_percentuais_produtos():
        """Calcula a participação percentual por produto (por quantidade) e atualiza
        o `percentuais_produtos_column` com um cartão moderno com scroll.
        """
        try:
            # acumula quantidades por produto
            totals = {}
            for v in vendas_filtradas:
                itens = v.get("itens", [])
                for it in itens:
                    nome = it.get("produto", "?")
                    cod = it.get("codigo_barras", "")
                    display = f"{cod} - {nome}" if cod else nome
                    qtd = it.get("quantidade", 0) or 0
                    totals[display] = totals.get(display, 0) + qtd

            total_all = sum(totals.values())

            percentuais_produtos_column.controls.clear()

            if total_all == 0:
                percentuais_produtos_column.controls.append(
                    ft.Container(
                        ft.Text("Sem dados para mostrar.", color=ft.Colors.GREY_600),
                        alignment=ft.alignment.center,
                        height=60,
                    )
                )
                page.update()
                return

            # ordena por quantidade decrescente
            items = sorted(totals.items(), key=lambda x: x[1], reverse=True)

            # principal (top 1)
            top_name, top_qtd = items[0]
            top_pct = (top_qtd / total_all) * 100

            def make_bar_item(label, qtd, pct, index):
                # Cores gradientes para os itens
                colors = [
                    ft.Colors.BLUE_600,
                    ft.Colors.INDIGO_600,
                    ft.Colors.PURPLE_600,
                    ft.Colors.PINK_600,
                    ft.Colors.AMBER_600,
                ]
                color = colors[index % len(colors)]

                return ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        content=ft.Text(
                                            f"{pct:.1f}%",
                                            size=16,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.WHITE,
                                        ),
                                        width=50,
                                        height=40,
                                        bgcolor=color,
                                        border_radius=8,
                                        alignment=ft.alignment.center,
                                    ),
                                    ft.Container(
                                        content=ft.Column(
                                            [
                                                ft.Text(
                                                    label,
                                                    size=12,
                                                    weight=ft.FontWeight.W_600,
                                                    color=ft.Colors.GREY_900,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                                ft.Text(
                                                    f"{int(qtd)} unid.",
                                                    size=11,
                                                    color=ft.Colors.GREY_600,
                                                ),
                                            ],
                                            spacing=2,
                                        ),
                                        expand=True,
                                        padding=ft.padding.only(left=10),
                                    ),
                                ],
                                spacing=8,
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.ProgressBar(
                                value=max(0.0, min(pct / 100.0, 1.0)),
                                color=color,
                                height=6,
                                bgcolor=ft.Colors.GREY_200,
                            ),
                        ],
                        spacing=6,
                    ),
                    padding=12,
                    bgcolor=ft.Colors.WHITE,
                    border_radius=10,
                    border=ft.border.all(1, ft.Colors.GREY_100),
                )

            # Lista de todos os produtos com scroll
            produtos_list = ft.ListView(
                controls=[
                    make_bar_item(name, qtd, (qtd / total_all) * 100, idx)
                    for idx, (name, qtd) in enumerate(items)
                ],
                spacing=10,
                padding=12,
                auto_scroll=False,
            )

            # Cartão moderno com gradient e design premium
            card = ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        [
                            # Cabeçalho com título e ícone
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.TRENDING_UP,
                                        size=28,
                                        color=ft.Colors.BLUE_600,
                                    ),
                                    ft.Text(
                                        "Participação por Produto",
                                        size=16,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.GREY_900,
                                    ),
                                    ft.Text(
                                        f"({len(items)} produtos)",
                                        size=12,
                                        color=ft.Colors.GREY_600,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.START,
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Divider(height=1, color=ft.Colors.GREY_200),
                            # Destaque do top 1
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Container(
                                            content=ft.Column(
                                                [
                                                    ft.Text(
                                                        "🏆 Top Produto",
                                                        size=11,
                                                        weight=ft.FontWeight.W_600,
                                                        color=ft.Colors.AMBER_700,
                                                    ),
                                                    ft.Text(
                                                        f"{top_pct:.0f}%",
                                                        size=28,
                                                        weight=ft.FontWeight.BOLD,
                                                        color=ft.Colors.BLUE_700,
                                                    ),
                                                    ft.Text(
                                                        top_name[:30],
                                                        size=11,
                                                        color=ft.Colors.GREY_700,
                                                        overflow=ft.TextOverflow.ELLIPSIS,
                                                    ),
                                                ],
                                                alignment=ft.MainAxisAlignment.CENTER,
                                                spacing=2,
                                            ),
                                            padding=15,
                                            bgcolor=ft.Colors.AMBER_50,
                                            border_radius=10,
                                            border=ft.border.all(
                                                2, ft.Colors.AMBER_200
                                            ),
                                            expand=True,
                                        ),
                                    ],
                                ),
                                margin=ft.margin.only(bottom=10),
                            ),
                            # Container com scroll para os produtos
                            ft.Container(
                                content=produtos_list,
                                height=300,
                                expand=False,
                                border_radius=10,
                                bgcolor=ft.Colors.GREY_50,
                                border=ft.border.all(1, ft.Colors.GREY_200),
                            ),
                        ],
                        spacing=12,
                    ),
                    padding=16,
                    bgcolor=ft.Colors.WHITE,
                    border_radius=14,
                ),
                elevation=4,
            )

            percentuais_produtos_column.controls.append(card)
            page.update()
        except Exception as ex:
            print(f"Erro ao atualizar percentuais: {ex}")
            percentuais_produtos_column.controls.clear()
            percentuais_produtos_column.controls.append(
                ft.Text("Erro ao calcular percentuais")
            )
            page.update()

    def atualizar_resumo_estatisticas():
        """Atualiza as estatísticas rápidas: total de itens, ticket médio, forma de pagamento mais usada"""
        try:
            if not vendas_filtradas:
                total_itens_text.value = "0"
                ticket_medio_text.value = "R$ 0,00"
                pagamento_text.value = "-"
                page.update()
                return

            # Total de itens
            total_itens = sum(len(v.get("itens", [])) for v in vendas_filtradas)
            total_itens_text.value = str(total_itens)

            # Ticket médio
            total_valor = sum(v.get("total", 0.0) for v in vendas_filtradas)
            ticket_medio = (
                total_valor / len(vendas_filtradas) if vendas_filtradas else 0
            )
            ticket_medio_text.value = f"R$ {ticket_medio:.2f}"

            # Forma de pagamento mais usada
            pagamentos_count = {}
            for v in vendas_filtradas:
                pag = v.get("pagamento", "Desconhecido")
                pagamentos_count[pag] = pagamentos_count.get(pag, 0) + 1

            if pagamentos_count:
                pagamento_top = max(pagamentos_count.items(), key=lambda x: x[1])
                pagamento_text.value = pagamento_top[0]
            else:
                pagamento_text.value = "-"

            page.update()
        except Exception as ex:
            print(f"Erro ao atualizar resumo: {ex}")

    # Controles de data e filtros mínimos para evitar NameError durante import
    start_date_picker = ft.DatePicker(
        value=datetime.now(),
        first_date=datetime(2020, 1, 1),
        last_date=datetime(2050, 12, 31),
    )
    end_date_picker = ft.DatePicker(
        value=datetime.now(),
        first_date=datetime(2020, 1, 1),
        last_date=datetime(2050, 12, 31),
    )

    # Atualiza os labels quando o usuário escolhe uma data
    def _start_date_changed(e):
        try:
            val = e.control.value
            if isinstance(val, datetime):
                inicio_label.value = val.strftime("%d/%m/%Y")
            else:
                inicio_label.value = val.strftime("%d/%m/%Y") if val else ""
        except Exception:
            inicio_label.value = str(e.control.value)
        page.update()

    def _end_date_changed(e):
        try:
            val = e.control.value
            if isinstance(val, datetime):
                fim_label.value = val.strftime("%d/%m/%Y")
            else:
                fim_label.value = val.strftime("%d/%m/%Y") if val else ""
        except Exception:
            fim_label.value = str(e.control.value)
        page.update()

    # vincula os handlers aos pickers
    try:
        start_date_picker.on_change = _start_date_changed
    except Exception:
        pass
    try:
        end_date_picker.on_change = _end_date_changed
    except Exception:
        pass
    # Adiciona os DatePickers ao overlay da página para que o seletor funcione
    try:
        print(
            f"[OVERLAY] vendas: adding start_date_picker bgcolor={getattr(start_date_picker, 'bgcolor', None)}"
        )
        page.overlay.append(start_date_picker)
        print(f"[OVERLAY] vendas: overlays_count={len(getattr(page, 'overlay', []))}")
    except Exception:
        pass
    try:
        print(
            f"[OVERLAY] vendas: adding end_date_picker bgcolor={getattr(end_date_picker, 'bgcolor', None)}"
        )
        page.overlay.append(end_date_picker)
        print(f"[OVERLAY] vendas: overlays_count={len(getattr(page, 'overlay', []))}")
    except Exception:
        pass
    inicio_label = ft.Text("", size=12)
    fim_label = ft.Text("", size=12)
    metodo_pagamento = ft.Dropdown(
        options=[
            ft.dropdown.Option("Todos"),
            ft.dropdown.Option("Dinheiro"),
            ft.dropdown.Option("PIX"),
            ft.dropdown.Option("Crédito"),
            ft.dropdown.Option("Débito"),
        ],
        value="Todos",
        dense=True,
    )

    # Define os estados diretamente, compatível com versões mais antigas
    # Função para criar botão de seleção de data
    def criar_botao_data(texto, picker):
        # Abre o DatePicker associado ao botão
        def _on_click(e):
            try:
                picker.open = True  # ✅ Usar .open = True em vez de pick_date()
                page.update()
            except Exception as ex:
                print(f"❌ Erro ao abrir date picker: {ex}")
                # fallback: definir valor para hoje se picker não estiver disponível
                try:
                    picker.value = datetime.now()
                    page.update()
                except Exception:
                    pass

        return ft.ElevatedButton(texto, on_click=_on_click)

    def create_metric_card(title, value_ref, icon, icon_bg_color, icon_color):
        return ft.Card(
            elevation=2,
            content=ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(icon, color=icon_color, size=30),
                            bgcolor=icon_bg_color,
                            padding=15,
                            border_radius=12,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    title,
                                    size=14,
                                    color=ft.Colors.GREY_600,
                                    weight=ft.FontWeight.W_500,
                                ),
                                value_ref,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=2,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=15,
                ),
                padding=16,
                width=260,
                height=100,
                bgcolor=ft.Colors.WHITE,
                border_radius=12,
            ),
        )

    refresh_slot_ref = ft.Ref[ft.Container]()

    def _make_refresh_icon():
        return ft.Container(
            content=ft.IconButton(
                ft.Icons.REFRESH,
                tooltip="Atualizar Dados",
                on_click=lambda e: handle_refresh(e),
                icon_size=24,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.BLUE_50, shape=ft.CircleBorder(), padding=10
                ),
                icon_color=ft.Colors.BLUE_700,
            ),
            alignment=ft.alignment.center,
        )

    def handle_refresh(e):
        try:
            import asyncio

            async def _do():
                try:
                    if refresh_slot_ref.current:
                        refresh_slot_ref.current.content = ft.ProgressRing(
                            width=28, height=28, color=ft.Colors.BLUE_700
                        )
                        refresh_slot_ref.current.update()
                    await asyncio.sleep(0)
                    carregar_vendas(force=True)
                finally:
                    try:
                        if refresh_slot_ref.current:
                            refresh_slot_ref.current.content = (
                                _make_refresh_icon().content
                            )
                            refresh_slot_ref.current.update()
                    except Exception:
                        pass

            try:
                page.run_task(_do)
            except Exception:
                try:
                    import asyncio

                    asyncio.run(_do())
                except Exception:
                    pass
        except Exception:
            try:
                carregar_vendas(force=True)
            except Exception:
                pass

    # Dashboard agora vazio (cards e botão foram movidos para filtros)
    dashboard = ft.Container(
        content=ft.Row(
            [],
            wrap=True,
            spacing=20,
            alignment=ft.MainAxisAlignment.CENTER,  # <--- Centraliza os cards
        ),
        padding=ft.padding.only(bottom=10),
    )

    # =========================================================================
    # TABELA DETALHADA E LAYOUT DE VISIBILIDADE
    # =========================================================================
    # Tabela de vendas

    tabela_vendas = ft.DataTable(
        columns=[
            ft.DataColumn(
                ft.Text("PRODUTO", size=14, weight=ft.FontWeight.BOLD, expand=True)
            ),
            ft.DataColumn(
                ft.Text("DATA PAGAMENTO", size=14, weight=ft.FontWeight.BOLD, width=200)
            ),
            ft.DataColumn(
                ft.Text("PAGAMENTO", size=14, weight=ft.FontWeight.BOLD, width=140)
            ),
            ft.DataColumn(
                ft.Text("QTD", size=14, weight=ft.FontWeight.BOLD, width=100),
                numeric=True,
            ),
            ft.DataColumn(
                ft.Text("VALOR TOTAL", size=14, weight=ft.FontWeight.BOLD, width=180),
                numeric=True,
            ),
            ft.DataColumn(
                ft.Text("ID VENDA", size=14, weight=ft.FontWeight.BOLD, width=140)
            ),
        ],
        rows=[],
        column_spacing=40,
        bgcolor=None,  # transparente, para não mostrar cinza
        border=ft.border.all(1, ft.Colors.GREY_300),
        border_radius=5,
        heading_row_color=ft.Colors.GREY_50,
        heading_row_height=56,
        data_row_min_height=64,
        visible=False,  # começa invisível
        expand=True,
        width=float("inf"),
    )

    # Mensagem quando não houver vendas
    no_data_message = ft.Container(
        content=ft.Text(
            "Nenhuma venda encontrada para o período e filtro selecionados.",
            color=ft.Colors.GREY_500,
            size=16,
            italic=True,
        ),
        alignment=ft.alignment.center,
        expand=True,
        visible=True,
        bgcolor=ft.Colors.WHITE,  # garante fundo branco
    )

    # Contêiner que envolve tabela e placeholder
    tabela_container = ft.Container(
        content=ft.Column(
            [tabela_vendas],
            expand=True,
            scroll="auto",
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        expand=True,
        width=float("inf"),
        border=ft.border.all(1, ft.Colors.GREY_300),
        border_radius=8,
        bgcolor=ft.Colors.WHITE,
        padding=0,
        margin=ft.margin.only(top=15),
    )

    def carregar_vendas(e=None, force=False, initial=False):
        try:
            nonlocal \
                vendas_filtradas, \
                caixa_session, \
                fallback_list, \
                fallback_loaded, \
                fallback_total_found

            # Evita recarregar se já houver linhas na tabela, a menos que
            # seja solicitado explicitamente via `force=True`.
            if not force and tabela_vendas.rows:
                return

            start_dt = start_date_picker.value
            end_dt = end_date_picker.value

            if not start_dt or not end_dt:
                snackbar = ft.SnackBar(
                    ft.Text(
                        "Selecione as datas.",
                        color=ft.Colors.BLACK,
                        weight=ft.FontWeight.BOLD,
                    ),
                    bgcolor=ft.Colors.ORANGE,
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
                return

            start_dt_obj = (
                start_dt.date() if isinstance(start_dt, datetime) else start_dt
            )
            end_dt_obj = end_dt.date() if isinstance(end_dt, datetime) else end_dt

            vendas = []
            if caixa_session:
                start_s = caixa_session.opening_time
                end_s = caixa_session.closing_time or datetime.now()
                vendas = pdv_core.buscar_vendas_por_intervalo(start_s, end_s)
            else:
                dt_ini = datetime.combine(start_dt_obj, time(0, 0))
                dt_fim = datetime.combine(end_dt_obj, time(23, 59, 59))
                vendas = pdv_core.buscar_vendas_por_intervalo(dt_ini, dt_fim)

            filtered = []
            total_periodo = 0.0
            lucro_periodo = 0.0

            for v in vendas:
                if v.get("status") == "ESTORNADA":
                    continue

                pagamento_venda = v.get("pagamento", "Desconhecido")
                filtro_pag = metodo_pagamento.value

                if filtro_pag != "Todos" and pagamento_venda != filtro_pag:
                    continue

                filtered.append(v)
                total_periodo += v.get("total", 0.0)
                lucro_periodo += v.get("total", 0.0) * 0.3

            vendas_filtradas = filtered

            tabela_vendas.rows.clear()

            for v in filtered:
                data_formatada = v["data"]
                pagamento = v["pagamento"]
                venda_id = str(v["id"])

                itens = v.get("itens", [])
                for item in itens:
                    nome_prod = item.get("produto", "?")
                    cod_barras = item.get("codigo_barras", "")
                    qtd = item.get("quantidade", 0)
                    preco_un = item.get("preco_unitario", 0.0)
                    valor_total_item = qtd * preco_un

                    produto_display = (
                        f"{nome_prod} ({cod_barras})" if cod_barras else nome_prod
                    )

                    cor_pag = ft.Colors.BLUE_GREY_500
                    if pagamento == "Dinheiro":
                        cor_pag = ft.Colors.GREEN_600
                    elif pagamento == "PIX":
                        cor_pag = ft.Colors.TEAL_500
                    elif pagamento in ("Débito", "Crédito"):
                        cor_pag = ft.Colors.BLUE_600

                    tabela_vendas.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(
                                    ft.Text(
                                        produto_display,
                                        size=13,
                                        weight=ft.FontWeight.W_500,
                                    )
                                ),
                                ft.DataCell(ft.Text(data_formatada, size=13)),
                                ft.DataCell(
                                    ft.Container(
                                        content=ft.Text(
                                            pagamento,
                                            size=11,
                                            color="white",
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        bgcolor=cor_pag,
                                        padding=ft.padding.symmetric(
                                            horizontal=10, vertical=4
                                        ),
                                        border_radius=20,
                                    )
                                ),
                                ft.DataCell(ft.Text(str(qtd), size=13)),
                                ft.DataCell(
                                    ft.Text(
                                        f"R$ {valor_total_item:.2f}",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                    )
                                ),
                                ft.DataCell(
                                    ft.Text(venda_id, size=13, color=ft.Colors.GREY_500)
                                ),
                            ]
                        )
                    )

            vendas_hoje_valor.value = f"R$ {total_periodo:.2f}"
            lucro_hoje_valor.value = f"R$ {lucro_periodo:.2f}"

            atualizar_percentuais_produtos()
            atualizar_resumo_estatisticas()

            # Se não encontrou vendas no intervalo filtrado:
            if not filtered:
                if initial:
                    now = datetime.now()
                    found_fb = False
                    # tentar fallback: últimos 30 dias, 365 dias, todo o histórico
                    for days in (30, 365, None):
                        if days is not None:
                            start_fb = now - timedelta(days=days)
                        else:
                            start_fb = datetime(1970, 1, 1)
                        fb_vendas = pdv_core.buscar_vendas_por_intervalo(start_fb, now)
                        fb_filtered = []
                        for v in fb_vendas:
                            if v.get("status") == "ESTORNADA":
                                continue
                            pagamento_venda = v.get("pagamento", "Desconhecido")
                            filtro_pag = metodo_pagamento.value
                            if filtro_pag != "Todos" and pagamento_venda != filtro_pag:
                                continue
                            fb_filtered.append(v)
                        if fb_filtered:
                            found_fb = True
                            # armazena lista completa do fallback para paginação
                            fallback_list = fb_filtered
                            total_found = len(fallback_list)
                            fallback_total_found = total_found
                            # trunca a lista para não carregar milhares de linhas
                            if total_found > FALLBACK_LIMIT:
                                filtered = fallback_list[:FALLBACK_LIMIT]
                                fallback_loaded = len(filtered)
                            else:
                                filtered = fallback_list
                                fallback_loaded = len(filtered)
                            vendas_filtradas = filtered
                            tabela_vendas.rows.clear()
                            total_periodo = 0.0
                            lucro_periodo = 0.0
                            for v in filtered:
                                total_periodo += v.get("total", 0.0)
                                lucro_periodo += v.get("total", 0.0) * 0.3
                                itens = v.get("itens", [])
                                for item in itens:
                                    nome_prod = item.get("produto", "?")
                                    cod_barras = item.get("codigo_barras", "")
                                    qtd = item.get("quantidade", 0)
                                    preco_un = item.get("preco_unitario", 0.0)
                                    valor_total_item = qtd * preco_un
                                    produto_display = (
                                        f"{nome_prod} ({cod_barras})"
                                        if cod_barras
                                        else nome_prod
                                    )
                                    cor_pag = ft.Colors.BLUE_GREY_500
                                    pagamento = v.get("pagamento")
                                    if pagamento == "Dinheiro":
                                        cor_pag = ft.Colors.GREEN_600
                                    elif pagamento == "PIX":
                                        cor_pag = ft.Colors.TEAL_500
                                    elif pagamento in ("Débito", "Crédito"):
                                        cor_pag = ft.Colors.BLUE_600

                                    tabela_vendas.rows.append(
                                        ft.DataRow(
                                            cells=[
                                                ft.DataCell(
                                                    ft.Text(
                                                        produto_display,
                                                        size=13,
                                                        weight=ft.FontWeight.W_500,
                                                    )
                                                ),
                                                ft.DataCell(
                                                    ft.Text(v.get("data"), size=13)
                                                ),
                                                ft.DataCell(
                                                    ft.Container(
                                                        content=ft.Text(
                                                            pagamento,
                                                            size=11,
                                                            color="white",
                                                            weight=ft.FontWeight.BOLD,
                                                        ),
                                                        bgcolor=cor_pag,
                                                        padding=ft.padding.symmetric(
                                                            horizontal=10, vertical=4
                                                        ),
                                                        border_radius=20,
                                                    )
                                                ),
                                                ft.DataCell(ft.Text(str(qtd), size=13)),
                                                ft.DataCell(
                                                    ft.Text(
                                                        f"R$ {valor_total_item:.2f}",
                                                        size=13,
                                                        weight=ft.FontWeight.BOLD,
                                                    )
                                                ),
                                                ft.DataCell(
                                                    ft.Text(
                                                        str(v.get("id")),
                                                        size=13,
                                                        color=ft.Colors.GREY_500,
                                                    )
                                                ),
                                            ]
                                        )
                                    )
                            vendas_hoje_valor.value = f"R$ {total_periodo:.2f}"
                            lucro_hoje_valor.value = f"R$ {lucro_periodo:.2f}"
                            atualizar_percentuais_produtos()
                            tabela_vendas.visible = True
                            no_data_message.visible = False
                            page.update()
                            # informa se truncamos o resultado e ativa botão de carregar mais
                            try:
                                if total_found > FALLBACK_LIMIT:
                                    page.snack_bar = ft.SnackBar(
                                        ft.Text(
                                            f"Mostrando {FALLBACK_LIMIT} de {total_found} vendas (limitado)."
                                        ),
                                        bgcolor=ft.Colors.BLUE_200,
                                    )
                                    page.snack_bar.open = True
                                    # marcar botão para aparecer (se existir)
                                    try:
                                        carregar_mais_btn.visible = True
                                    except Exception:
                                        pass
                                    page.update()
                            except Exception:
                                pass
                            break
                    if not found_fb:
                        tabela_vendas.visible = False
                        no_data_message.visible = True
                        page.snack_bar = ft.SnackBar(
                            ft.Text(
                                "Nenhuma venda encontrada para o período selecionado."
                            ),
                            bgcolor=ft.Colors.ORANGE,
                        )
                        page.snack_bar.open = True
                        page.update()
                        return
                else:
                    # ação do usuário (aplicar filtro/refresh) — mostrar mensagem
                    tabela_vendas.visible = False
                    no_data_message.visible = True
                    page.snack_bar = ft.SnackBar(
                        ft.Text("Nenhuma venda encontrada para o período selecionado."),
                        bgcolor=ft.Colors.ORANGE,
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

            is_empty = not filtered

            # Alterna visibilidade da tabela e da mensagem
            tabela_vendas.visible = not is_empty
            no_data_message.visible = is_empty

            # Atualiza a página
            page.update()

        except Exception as e:
            snackbar = ft.SnackBar(
                ft.Text(
                    f"Erro ao carregar vendas: {e}",
                    color=ft.Colors.BLACK,
                    weight=ft.FontWeight.BOLD,
                ),
                bgcolor=ft.Colors.RED_400,
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

    def carregar_mais(e):
        try:
            nonlocal \
                vendas_filtradas, \
                fallback_list, \
                fallback_loaded, \
                fallback_total_found

            if not fallback_list or fallback_loaded >= fallback_total_found:
                snackbar = ft.SnackBar(
                    ft.Text(
                        "Não há mais vendas para carregar.",
                        color=ft.Colors.BLACK,
                        weight=ft.FontWeight.BOLD,
                    ),
                    bgcolor=ft.Colors.ORANGE,
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
                return

            next_slice = fallback_list[
                fallback_loaded : fallback_loaded + FALLBACK_LIMIT
            ]
            if not next_slice:
                page.snack_bar = ft.SnackBar(
                    ft.Text("Não há mais vendas para carregar."),
                    bgcolor=ft.Colors.ORANGE,
                )
                page.snack_bar.open = True
                page.update()
                return

            # append novos itens à tabela
            for v in next_slice:
                vendas_filtradas.append(v)
                pagamento = v.get("pagamento")
                itens = v.get("itens", [])
                for item in itens:
                    nome_prod = item.get("produto", "?")
                    cod_barras = item.get("codigo_barras", "")
                    qtd = item.get("quantidade", 0)
                    preco_un = item.get("preco_unitario", 0.0)
                    valor_total_item = qtd * preco_un
                    produto_display = (
                        f"{cod_barras} - {nome_prod}" if cod_barras else nome_prod
                    )
                    cor_pag = ft.Colors.BLUE_GREY_500
                    if pagamento == "Dinheiro":
                        cor_pag = ft.Colors.GREEN_600
                    elif pagamento == "PIX":
                        cor_pag = ft.Colors.TEAL_500
                    elif pagamento in ("Débito", "Crédito"):
                        cor_pag = ft.Colors.BLUE_600

                    tabela_vendas.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(
                                    ft.Text(
                                        produto_display,
                                        size=13,
                                        weight=ft.FontWeight.W_500,
                                    )
                                ),
                                ft.DataCell(ft.Text(v.get("data"), size=13)),
                                ft.DataCell(
                                    ft.Container(
                                        content=ft.Text(
                                            pagamento,
                                            size=11,
                                            color="white",
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        bgcolor=cor_pag,
                                        padding=ft.padding.symmetric(
                                            horizontal=10, vertical=4
                                        ),
                                        border_radius=20,
                                    )
                                ),
                                ft.DataCell(ft.Text(str(qtd), size=13)),
                                ft.DataCell(
                                    ft.Text(
                                        f"R$ {valor_total_item:.2f}",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                    )
                                ),
                                ft.DataCell(
                                    ft.Text(
                                        str(v.get("id")),
                                        size=13,
                                        color=ft.Colors.GREY_500,
                                    )
                                ),
                            ]
                        )
                    )

            fallback_loaded += len(next_slice)

            # recalcula métricas
            total_periodo = sum([v.get("total", 0.0) for v in vendas_filtradas])
            lucro_periodo = total_periodo * 0.3
            vendas_hoje_valor.value = f"R$ {total_periodo:.2f}"
            lucro_hoje_valor.value = f"R$ {lucro_periodo:.2f}"

            # controla visibilidade do botão
            try:
                carregar_mais_btn.visible = fallback_loaded < fallback_total_found
            except Exception:
                pass

            page.update()

        except Exception as ex:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Erro: {ex}"), bgcolor=ft.Colors.RED_400
            )
            page.snack_bar.open = True
            page.update()

    def exportar_vendas(formato: str):
        try:
            if not vendas_filtradas:
                snackbar = ft.SnackBar(
                    ft.Text("Não há vendas para exportar."),
                    bgcolor=ft.Colors.ORANGE,
                )
                try:
                    page.snack_bar = snackbar
                    page.snack_bar.open = True
                    page.update()
                except Exception:
                    page.overlay.append(snackbar)
                    snackbar.open = True
                    page.update()
                return

            # Monta linhas detalhadas por item da venda, com valores formatados em R$
            def format_currency(v):
                try:
                    v = float(v or 0.0)
                except Exception:
                    return str(v)
                s = f"R$ {v:,.2f}"
                # converte para formato brasileiro 1.234,56
                s = s.replace(",", "X").replace(".", ",").replace("X", ".")
                return s

            # Cabeçalhos mais curtos para evitar wrap no PDF
            headers = [
                "id",
                "data",
                "pagamento",
                "produto",
                "qtd",
                "preço",
                "total",
                "status",
            ]

            data = []
            for v in vendas_filtradas:
                vid = v.get("id")
                data_venda = v.get("data")
                pagamento_venda = v.get("pagamento")
                status_venda = v.get("status")
                itens = v.get("itens", [])
                if not itens:
                    data.append(
                        [
                            vid,
                            data_venda,
                            pagamento_venda,
                            "-",
                            "0",
                            format_currency(0),
                            format_currency(0),
                            status_venda,
                        ]
                    )
                else:
                    for item in itens:
                        nome_prod = item.get("produto", "?")
                        cod_barras = item.get("codigo_barras", "")
                        produto_display = (
                            f"{cod_barras} - {nome_prod}" if cod_barras else nome_prod
                        )
                        qtd = item.get("quantidade", 0)
                        preco_un = item.get("preco_unitario", 0.0)
                        valor_total_item = qtd * preco_un
                        data.append(
                            [
                                vid,
                                data_venda,
                                pagamento_venda,
                                produto_display,
                                qtd,
                                format_currency(preco_un),
                                format_currency(valor_total_item),
                                status_venda,
                            ]
                        )
            if formato == "csv":
                file_path = generate_csv_file(
                    headers, data, nome_base="relatorio_vendas"
                )
            elif formato == "pdf":
                # Passa pesos fixos para as colunas para melhorar a proporção no PDF
                # Ordem dos headers: id, data, pagamento, produto, qtd, preço, total, status
                # Aumentamos espaço do 'status' para evitar overflow de textos como "Concluindo"
                # Mantemos 'produto' amplo e distribuímos levemente o restante
                pesos = [1, 2, 2, 10, 1, 2, 2, 2]
                file_path = generate_pdf_file(
                    headers,
                    data,
                    nome_base="relatorio_vendas",
                    title="Relatório de Vendas",
                    col_widths=pesos,
                )
            else:
                file_path = None
            if file_path:
                snackbar = ft.SnackBar(
                    ft.Text(f"Relatório exportado para {file_path}"),
                    bgcolor=ft.Colors.GREEN_400,
                )
                page.overlay.append(snackbar)
                snackbar.open = True
                page.update()

                # Abrir PDF no navegador se for PDF
                if formato == "pdf":
                    try:
                        caminho_absoluto = os.path.abspath(file_path)
                        # Converter para URL file:// para abrir no navegador
                        url_arquivo = Path(caminho_absoluto).as_uri()
                        webbrowser.open(url_arquivo)
                    except Exception as open_ex:
                        print(f"[DEBUG] Erro ao abrir PDF no navegador: {str(open_ex)}")

        except Exception as e:
            snackbar = ft.SnackBar(
                ft.Text(f"Erro ao exportar relatório: {e}"),
                bgcolor=ft.Colors.RED_400,
            )
            page.overlay.append(snackbar)
            snackbar.open = True
            page.update()

    # Botão de filtro, posicionado junto ao filtro de data final
    aplicar_filtro_btn = ft.ElevatedButton(
        "Aplicar Filtro",
        icon=ft.Icons.SEARCH,
        on_click=lambda e: carregar_vendas(force=True),
    )

    # Agora que carregar_vendas existe, podemos montar o bloco de filtros com os cards
    filtros_content = ft.Container(
        content=ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("Início", size=12, color=ft.Colors.GREY_700),
                        criar_botao_data("Selecionar Início", start_date_picker),
                        inicio_label,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Column(
                    [
                        ft.Text("Fim", size=12, color=ft.Colors.GREY_700),
                        ft.Row(
                            [
                                criar_botao_data("Selecionar Fim", end_date_picker),
                                aplicar_filtro_btn,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=10,
                        ),
                        fim_label,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Column(
                    [
                        ft.Text("Pagamento", size=12, color=ft.Colors.GREY_700),
                        metodo_pagamento,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                # Cards de Total e Lucro empilhados (evita corte em 1920x1080)
                ft.Column(
                    [
                        create_metric_card(
                            "Total de Vendas",
                            vendas_hoje_valor,
                            ft.Icons.ATTACH_MONEY,
                            ft.Colors.BLUE_50,
                            ft.Colors.BLUE_700,
                        ),
                        ft.Container(height=8),
                        create_metric_card(
                            "Lucro Estimado (30%)",
                            lucro_hoje_valor,
                            ft.Icons.TRENDING_UP,
                            ft.Colors.GREEN_50,
                            ft.Colors.GREEN_700,
                        ),
                        ft.Container(
                            content=ft.Container(
                                ref=refresh_slot_ref, content=_make_refresh_icon()
                            ),
                            alignment=ft.alignment.center,
                            padding=ft.padding.only(top=8),
                        ),
                    ],
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
            wrap=True,
        ),
        padding=20,
        bgcolor=ft.Colors.GREY_50,
        border_radius=12,
    )

    # botão "Carregar mais" será mostrado quando o fallback for truncado
    carregar_mais_btn = ft.ElevatedButton(
        "Carregar mais", on_click=lambda e: carregar_mais(e), visible=False
    )

    export_buttons = ft.Row(
        [
            ft.ElevatedButton(
                "Exportar CSV",
                icon=ft.Icons.TABLE_VIEW,
                on_click=lambda e: exportar_vendas("csv"),
            ),
            ft.ElevatedButton(
                "Exportar PDF",
                icon=ft.Icons.PICTURE_AS_PDF,
                on_click=lambda e: exportar_vendas("pdf"),
            ),
            carregar_mais_btn,
        ],
        spacing=10,
    )

    # Função utilitária para renderizar linhas da tabela a partir de uma lista de vendas
    def render_table_rows(sales, search=None):
        try:
            tabela_vendas.rows.clear()
            total_periodo_local = 0.0
            lucro_periodo_local = 0.0

            s = (search or "").strip().lower()

            for v in sales:
                itens = v.get("itens", [])
                for item in itens:
                    nome_prod = item.get("produto", "?")
                    cod_barras = str(item.get("codigo_barras", "") or "")
                    produto_display = (
                        f"{nome_prod} ({cod_barras})" if cod_barras else nome_prod
                    )

                    # aplicar filtro de busca se fornecido
                    if s:
                        if s not in nome_prod.lower() and s not in cod_barras.lower():
                            continue

                    qtd = item.get("quantidade", 0) or 0
                    preco_un = item.get("preco_unitario", 0.0) or 0.0
                    valor_total_item = qtd * preco_un

                    cor_pag = ft.Colors.BLUE_GREY_500
                    pagamento = v.get("pagamento")
                    if pagamento == "Dinheiro":
                        cor_pag = ft.Colors.GREEN_600
                    elif pagamento == "PIX":
                        cor_pag = ft.Colors.TEAL_500
                    elif pagamento in ("Débito", "Crédito"):
                        cor_pag = ft.Colors.BLUE_600

                    tabela_vendas.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(
                                    ft.Text(
                                        produto_display,
                                        size=13,
                                        weight=ft.FontWeight.W_500,
                                    )
                                ),
                                ft.DataCell(ft.Text(v.get("data"), size=13)),
                                ft.DataCell(
                                    ft.Container(
                                        content=ft.Text(
                                            pagamento,
                                            size=11,
                                            color="white",
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        bgcolor=cor_pag,
                                        padding=ft.padding.symmetric(
                                            horizontal=10, vertical=4
                                        ),
                                        border_radius=20,
                                    )
                                ),
                                ft.DataCell(ft.Text(str(qtd), size=13)),
                                ft.DataCell(
                                    ft.Text(
                                        f"R$ {valor_total_item:.2f}",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                    )
                                ),
                                ft.DataCell(
                                    ft.Text(
                                        str(v.get("id")),
                                        size=13,
                                        color=ft.Colors.GREY_500,
                                    )
                                ),
                            ]
                        )
                    )

                    total_periodo_local += valor_total_item
                    lucro_periodo_local += valor_total_item * 0.3

            vendas_hoje_valor.value = f"R$ {total_periodo_local:.2f}"
            lucro_hoje_valor.value = f"R$ {lucro_periodo_local:.2f}"

            tabela_vendas.visible = len(tabela_vendas.rows) > 0
            no_data_message.visible = not tabela_vendas.visible
            page.update()
        except Exception as ex:
            print(f"[ERRO] render_table_rows: {ex}")

    # (campo de busca simples removido - tabela ocupa espaço abaixo dos cards)

    # summary_bar removed: KPIs already present elsewhere on the screen

    # Coloca filtros, depois uma linha com dashboard (esquerda) e percentuais (direita expandido),
    # e em seguida a tabela de vendas ocupando largura completa.
    percentuais_container = ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    "Percentual de participação dos produtos vendidos:",
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.GREY_700,
                ),
                percentuais_produtos_column,
            ],
            spacing=8,
            expand=True,
        ),
        padding=ft.padding.all(12),
        bgcolor=ft.Colors.GREY_50,
        border_radius=8,
        expand=True,
        # height removed to allow the panel to size naturally
    )

    # Card de Resumo de Estatísticas
    resumo_estatisticas = ft.Card(
        content=ft.Container(
            content=ft.Row(
                [
                    # Total de itens
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "Total de Itens",
                                    size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.GREY_700,
                                ),
                                total_itens_text,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=4,
                        ),
                        padding=15,
                        bgcolor=ft.Colors.BLUE_50,
                        border_radius=10,
                        expand=True,
                    ),
                    # Ticket médio
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "Ticket Médio",
                                    size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.GREY_700,
                                ),
                                ticket_medio_text,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=4,
                        ),
                        padding=15,
                        bgcolor=ft.Colors.GREEN_50,
                        border_radius=10,
                        expand=True,
                    ),
                    # Forma de pagamento mais usada
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text(
                                    "Pagamento Mais Usado",
                                    size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.GREY_700,
                                ),
                                pagamento_text,
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=4,
                        ),
                        padding=15,
                        bgcolor=ft.Colors.PURPLE_50,
                        border_radius=10,
                        expand=True,
                    ),
                ],
                spacing=10,
            ),
            padding=12,
        ),
        elevation=2,
    )

    # Layout atualizado:
    # - Filtros/metric cards à esquerda
    # - Painel de percentuais à direita com o resumo de estatísticas empilhado abaixo dele
    # - Tabela ocupando toda a largura abaixo desses blocos
    main_content = ft.Column(
        [
            ft.Row(
                [
                    # Coluna esquerda: filtros em cima e cards logo abaixo (mantém filtros_content)
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(content=filtros_content),
                                ft.Container(width=20),
                                ft.Container(
                                    content=dashboard, alignment=ft.alignment.center
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.START,
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        expand=True,
                    ),
                    # Coluna direita: percentuais + resumo empilhados
                    ft.Container(
                        content=ft.Column(
                            [
                                percentuais_container,
                            ],
                            spacing=8,
                            expand=True,
                        ),
                        expand=True,
                        alignment=ft.alignment.top_right,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=12,
                expand=True,
            ),
            # Mover o card de resumo para abaixo dos filtros e dos metric cards
            ft.Container(content=resumo_estatisticas),
            ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
            # Tabela agora abaixo dos filtros e dos cards de Total/Lucro
            tabela_container,
            # mostra a mensagem quando não há dados (fora do ListView)
            no_data_message,
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            export_buttons,
        ],
        spacing=12,
    )

    # OBS: não carregar vendas aqui (bloqueia montagem e causa flash branco)
    # Carregaremos em background após a View ser exibida.

    view = ft.View(
        route="/gerente/relatorio_vendas",
        controls=[
            ft.AppBar(
                title=ft.Text(
                    "Histórico de Itens Vendidos",
                    text_align=ft.TextAlign.CENTER,
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
                center_title=True,
                bgcolor=COLORS["primary"],
                leading=ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    on_click=handle_back,
                    icon_color=ft.Colors.WHITE,
                ),
            ),
            ft.Container(
                content=main_content,
                padding=ft.padding.all(12),
                bgcolor=bg_color,
                expand=True,
            ),
        ],
        bgcolor=bg_color,
    )
    try:

        async def _load_initial():
            try:
                carregar_vendas(force=True, initial=True)
            except Exception:
                pass

        def _on_view_mount(e):
            try:
                page.run_task(_load_initial)
            except Exception:
                try:
                    _load_initial()
                except Exception:
                    pass

        view.on_view_did_mount = _on_view_mount
    except Exception:
        pass
    try:

        def _vendas_on_key(e):
            try:
                key = (str(e.key) or "").upper()
                if key in ("ESCAPE", "ESC"):
                    page.go("/gerente")
            except Exception:
                pass

        view.on_keyboard_event = _vendas_on_key
    except Exception:
        pass

    # Expor método para permitir disparo via roteador (app.py)
    try:
        setattr(view, "load_data", lambda: carregar_vendas(force=True, initial=True))
    except Exception:
        pass

    return view
