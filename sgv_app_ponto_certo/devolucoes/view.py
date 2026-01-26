"""View de Devoluções e Trocas - Tela principal de gerenciamento de devoluções."""

import os
from datetime import datetime, timedelta
from pathlib import Path

import flet as ft

from estoque.devolucoes import (
    add_hidden_id,
    carregar_devol,
    carregar_hidden_ids,
    remover_devolucao,
)
from utils.export_utils import generate_pdf_file

# Color palette
COLORS = {
    "primary": "#034986",
    "primary_solid": "#034986",
    "background": "#F0F4F8",
    "surface": "#FFFFFF",
    "text_primary": "#2D3748",
    "text_secondary": "#636E72",
    "success": "#8FC74F",
    "warning": "#FDCB6E",
    "danger": "#FF7675",
    "info": "#034986",
    "accent": "#FFB347",
    "border": "#DFE6E9",
    "hover": "#F0F4F8",
}

TYPOGRAPHY = {
    "h1": {"size": 28, "weight": ft.FontWeight.BOLD},
    "h2": {"size": 20, "weight": ft.FontWeight.BOLD},
    "h3": {"size": 16, "weight": ft.FontWeight.W_600},
    "body": {"size": 14, "weight": ft.FontWeight.NORMAL},
    "caption": {"size": 12, "weight": ft.FontWeight.W_500},
}


def format_brl(val: float) -> str:
    """Format currency with Brazilian Real"""
    return f"R$ {val:,.2f}".replace(".", "#").replace(",", ".").replace("#", ",")


def show_snackbar(page: ft.Page, message: str, color=None):
    """Modern snackbar notification"""
    if color is None:
        color = COLORS["success"]

    snackbar = ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
        bgcolor=color,
        behavior=ft.SnackBarBehavior.FLOATING,
        margin=10,
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


def show_modal_troca(page: ft.Page, devolucao: dict, pdv_core, on_troca_callback):
    """Modal para registrar troca de produto"""
    print("[TROCA] Iniciando show_modal_troca...")
    try:
        from estoque.devolucoes import adicionar_troca

        print("[TROCA] ✓ Importação OK")
    except ImportError as e:
        print(f"[TROCA] ✗ Erro ao importar: {e}")
        show_snackbar(page, "Erro ao carregar função de troca", COLORS["danger"])
        return

    campo_produto = ft.TextField(
        label="ID ou Código de Barras",
        width=400,
        border_radius=8,
        filled=True,
        hint_text="Digite ID ou código de barras",
    )

    # Criar o dialog primeiro
    dlg = ft.AlertDialog(modal=True)

    def confirmar_troca(e):
        """Confirma a troca"""
        valor = campo_produto.value.strip()

        if not valor:
            show_snackbar(
                page,
                "Digite um ID ou código de barras",
                COLORS["danger"],
            )
            return

        try:
            from estoque.devolucoes import (
                atualizar_estoque_troca,
                validar_produto_existe,
            )

            # Tentar encontrar o produto por ID ou código de barras
            existe, produto = validar_produto_existe(pdv_core, valor)
            if not existe:
                show_snackbar(
                    page,
                    f"Produto '{valor}' não encontrado no estoque",
                    COLORS["danger"],
                )
                return

            novo_id = produto.id
            novo_nome = produto.nome
            estoque_novo = produto.estoque_atual or 0
            quantidade_devolvida = devolucao.get("quantidade", 1)

            if estoque_novo < quantidade_devolvida:
                show_snackbar(
                    page,
                    f"Estoque insuficiente de {novo_nome} (disponível: {estoque_novo})",
                    COLORS["danger"],
                )
                return

            adicionar_troca(
                devolucao_id=devolucao.get("id"),
                novo_produto_id=novo_id,
                novo_produto_nome=novo_nome,
            )
            print("[TROCA] ✓ Troca registrada")

            sucesso_estoque, msg_estoque = atualizar_estoque_troca(
                pdv_core,
                produto_original_id=devolucao.get("produto_id"),
                novo_produto_id=novo_id,
                quantidade=quantidade_devolvida,
            )

            if sucesso_estoque:
                show_snackbar(
                    page,
                    f"✓ Troca realizada!\n{devolucao.get('produto_nome')} → {novo_nome}",
                    COLORS["success"],
                )
                dlg.open = False
                page.update()
                if on_troca_callback:
                    on_troca_callback()
            else:
                show_snackbar(
                    page,
                    f"Troca registrada, mas erro ao atualizar estoque: {msg_estoque}",
                    COLORS["warning"],
                )

        except ValueError as ex:
            show_snackbar(page, f"ID inválido: {str(ex)}", COLORS["danger"])
        except Exception as ex:
            print(f"[TROCA] ✗ Erro: {ex}")
            import traceback

            traceback.print_exc()
            show_snackbar(page, f"Erro: {str(ex)}", COLORS["danger"])

    def fechar_modal(e):
        print("[TROCA] Fechando modal")
        dlg.open = False
        page.update()

    # Construir conteúdo
    conteudo = ft.Column(
        [
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Produto Original:", **TYPOGRAPHY["h3"]),
                            ft.Text(
                                devolucao.get("produto_nome", "?"),
                                **TYPOGRAPHY["caption"],
                            ),
                        ]
                    ),
                    ft.Row(
                        [
                            ft.Text("Valor:", **TYPOGRAPHY["h3"]),
                            ft.Text(
                                format_brl(devolucao.get("valor_total", 0)),
                                **TYPOGRAPHY["caption"],
                            ),
                        ]
                    ),
                ],
                spacing=8,
            ),
            ft.Divider(height=1),
            ft.Text(
                "Digite o ID ou código de barras do novo produto",
                **TYPOGRAPHY["caption"],
                color=COLORS["text_secondary"],
            ),
            campo_produto,
            ft.Text(
                "Exemplo: 5 ou 1234567890123 (código de barras)",
                **TYPOGRAPHY["caption"],
                color=COLORS["text_secondary"],
                italic=True,
            ),
        ],
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
    )

    # Configurar o dialog
    dlg.title = ft.Text("Trocar Devolução")
    dlg.content = ft.Container(
        content=conteudo,
        width=350,
        padding=12,
    )
    dlg.actions = [
        ft.ElevatedButton(
            "Confirmar Troca",
            on_click=confirmar_troca,
            bgcolor=COLORS["success"],
            color=ft.Colors.WHITE,
        ),
        ft.OutlinedButton(
            "Cancelar",
            on_click=fechar_modal,
        ),
    ]

    print("[TROCA] Abrindo Modal...")
    page.overlay.append(dlg)
    dlg.open = True
    page.update()
    print("[TROCA] ✓ Modal aberto")


def create_devolucoes_view(page: ft.Page, pdv_core, handle_back):
    """Cria a view principal de devoluções e trocas."""

    # Refs para atualização dinâmica
    tabela_ref = ft.Ref[ft.DataTable]()
    loading_ref = ft.Ref[ft.ProgressRing]()
    stats_container_ref = ft.Ref[ft.Container]()
    filtro_periodo_ref = ft.Ref[ft.RadioGroup]()
    refresh_slot_ref = ft.Ref[ft.Container]()
    # Cache das devoluções filtradas para exportação
    devol_filtradas_cache = []

    # --- Refresh com animação ---
    def _make_refresh_icon():
        return ft.IconButton(
            ft.Icons.REFRESH, on_click=lambda e: handle_refresh(e), tooltip="Atualizar"
        )

    def handle_delete_all_filtered(e=None):
        print("[DEVOLUCOES] handle_delete_all_filtered called")
        try:
            # confirmar ação (modal)
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Remover devoluções"),
                content=ft.Text(
                    "Deseja realmente remover todas as devoluções atualmente exibidas? Esta ação não pode ser desfeita."
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda ev: _close(ev)),
                    ft.ElevatedButton("Confirmar", on_click=lambda ev: _confirm(ev)),
                ],
            )

            def _close(ev=None):
                try:
                    dlg.open = False
                    page.update()
                except Exception:
                    pass

            def _confirm(ev=None):
                try:
                    # remover cada devolução filtrada (apenas registros do JSON)
                    prev_ids = []
                    for d in list(devol_filtradas_cache):
                        try:
                            prev_ids.append(int(d.get("id")))
                        except Exception:
                            pass

                    count_removed = 0
                    for did in prev_ids:
                        try:
                            remover_devolucao(did)
                            count_removed += 1
                        except Exception:
                            pass

                    # fechar diálogo e recarregar tabela
                    dlg.open = False
                    page.update()
                    carregar_tabela()

                    # verificar quantos dos ids ainda existem no JSON (provavelmente linhas oriundas do DB)
                    try:
                        from estoque.devolucoes import carregar_devol

                        remaining = [
                            d
                            for d in carregar_devol()
                            if int(d.get("id", -1)) in prev_ids
                        ]
                        remaining_count = len(remaining)
                    except Exception:
                        remaining_count = 0

                    # esconder qualquer id que ainda permaneça (vindo do DB)
                    try:
                        for d in prev_ids:
                            add_hidden_id(d)
                        remaining_count = 0
                    except Exception:
                        pass

                    show_snackbar(
                        page,
                        f"Removidas {count_removed} devoluções (visão atualizada).",
                        COLORS["danger"],
                    )
                except Exception as ex:
                    print(f"[DEVOLUÇÕES] Erro ao remover em massa: {ex}")
                    show_snackbar(page, "Erro ao remover devoluções.", COLORS["danger"])

            try:
                page.overlay.append(dlg)
            except Exception:
                pass
            dlg.open = True
            page.update()
        except Exception as ex:
            print(f"[DEVOLUÇÕES] Erro ao abrir diálogo de remoção: {ex}")

    def handle_refresh(e):
        try:
            import asyncio

            async def _do():
                try:
                    if refresh_slot_ref.current:
                        refresh_slot_ref.current.content = ft.ProgressRing(
                            width=28, height=28, color=COLORS["primary"]
                        )
                        refresh_slot_ref.current.update()
                    await asyncio.sleep(0)
                    carregar_tabela()
                finally:
                    try:
                        if refresh_slot_ref.current:
                            refresh_slot_ref.current.content = _make_refresh_icon()
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
                carregar_tabela()
            except Exception:
                pass

    # ========== ESTATÍSTICAS ==========
    def criar_card_stat(titulo: str, valor: str, cor: str, icone: str) -> ft.Container:
        """Cria card de estatística"""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icone, size=28, color=cor),
                            ft.Text(
                                titulo,
                                **TYPOGRAPHY["caption"],
                                color=COLORS["text_secondary"],
                            ),
                        ],
                        spacing=12,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(valor, **TYPOGRAPHY["h2"], color=cor),
                ],
                spacing=8,
            ),
            padding=16,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.05, cor),
            border=ft.border.all(1, ft.Colors.with_opacity(0.2, cor)),
        )

    def calcular_stats(devol_list):
        """Calcula estatísticas das devoluções"""
        if not devol_list:
            return {
                "total": "0",
                "taxa_devolucao": "0%",
                "valor": "R$ 0,00",
                "valor_medio": "R$ 0,00",
            }

        total_valor = sum(d.get("valor_total", 0) for d in devol_list)
        quantidade_itens = sum(d.get("quantidade", 0) for d in devol_list)

        taxa = (len(devol_list) / max(len(devol_list) + 100, 1)) * 100
        valor_medio = total_valor / quantidade_itens if quantidade_itens > 0 else 0

        return {
            "total": str(len(devol_list)),
            "taxa_devolucao": f"{taxa:.1f}%",
            "valor": format_brl(total_valor),
            "valor_medio": format_brl(valor_medio),
        }

    def atualizar_stats(devol_list):
        """Atualiza cards de estatísticas"""
        if not stats_container_ref.current:
            return

        stats = calcular_stats(devol_list)

        # O content é um Row diretamente
        row = stats_container_ref.current.content
        cards = row.controls

        # Atualizar cada card
        if len(cards) > 0:
            cards[0].content.controls[1].value = stats["total"]
        if len(cards) > 1:
            cards[1].content.controls[1].value = stats["taxa_devolucao"]
        if len(cards) > 2:
            cards[2].content.controls[1].value = stats["valor"]
        if len(cards) > 3:
            cards[3].content.controls[1].value = stats["valor_medio"]

        stats_container_ref.current.update()

    # ========== TABELA DE DEVOLUÇÕES ==========
    def carregar_tabela():
        """Carrega e exibe devoluções na tabela"""
        nonlocal devol_filtradas_cache
        try:
            if loading_ref.current:
                loading_ref.current.visible = True
                loading_ref.current.update()
        except Exception:
            pass

        try:
            # Obter período selecionado
            periodo = "7"
            if filtro_periodo_ref.current:
                periodo = filtro_periodo_ref.current.value or "7"

            dias = int(periodo) if periodo != "todos" else 365

            data_inicio = (
                datetime.now() - timedelta(days=dias)
                if dias != 365
                else datetime(2000, 1, 1)
            )
            data_fim = datetime.now()

            devol_list = carregar_devol()

            # Fallback: se não houver registros em JSON, buscar estornos diretamente do banco
            if not devol_list:
                try:
                    from models.db_models import Venda

                    q = (
                        pdv_core.session.query(Venda)
                        .filter(
                            Venda.status == "ESTORNADA",
                            Venda.data_venda >= data_inicio,
                            Venda.data_venda <= data_fim,
                        )
                        .order_by(Venda.data_venda.desc())
                    )
                    vendas_estornadas = q.all()

                    devol_from_db = []
                    hidden_ids = carregar_hidden_ids() or []
                    for v in vendas_estornadas:
                        for it in getattr(v, "itens", []) or []:
                            try:
                                nome = (
                                    it.produto.nome
                                    if getattr(it, "produto", None)
                                    else "Produto"
                                )
                                qtd = int(getattr(it, "quantidade", 0) or 0)
                                preco = float(getattr(it, "preco_unitario", 0.0) or 0.0)
                                item_id = getattr(it, "id", None) or 0
                                # pular itens marcados como escondidos
                                try:
                                    if int(item_id) in hidden_ids:
                                        continue
                                except Exception:
                                    pass

                                devol_from_db.append(
                                    {
                                        # id opcional (pode não existir em ItemVenda)
                                        "id": item_id,
                                        "produto_id": getattr(it, "produto_id", None),
                                        "produto_nome": nome,
                                        "quantidade": qtd,
                                        "valor_total": preco * qtd,
                                        "motivo": f"Estorno da venda #{v.id}",
                                        "data": (
                                            v.data_venda.isoformat()
                                            if hasattr(v.data_venda, "isoformat")
                                            else str(v.data_venda)
                                        ),
                                        "foi_trocado": False,
                                    }
                                )
                            except Exception:
                                pass

                    # Usa os registros do banco diretamente para exibição
                    devol_list = devol_from_db
                except Exception as ex_db:
                    print(f"[DEVOLUÇÕES] Fallback DB falhou: {ex_db}")

            # Filtrar por data
            devol_filtradas = []
            for d in devol_list:
                try:
                    data_devol = datetime.fromisoformat(d.get("data", ""))
                    if data_inicio <= data_devol <= data_fim:
                        devol_filtradas.append(d)
                except Exception:
                    pass

            # Ordenar por data (mais recentes primeiro)
            devol_filtradas.sort(key=lambda x: x.get("data", ""), reverse=True)
            # Atualiza cache para exportação
            devol_filtradas_cache = list(devol_filtradas)

            # Limpar tabela
            if tabela_ref.current:
                tabela_ref.current.rows.clear()

                # Adicionar linhas
                for d in devol_filtradas:
                    data_formatada = datetime.fromisoformat(d.get("data", "")).strftime(
                        "%d/%m/%Y %H:%M"
                    )

                    def criar_botao_remover(dev_id):
                        def remover(e):
                            try:
                                print(f"[DEVOLUCOES] remover called for id={dev_id}")
                                remover_devolucao(dev_id)
                                # verificar se ainda existe no JSON
                                try:
                                    remaining = [
                                        d
                                        for d in carregar_devol()
                                        if int(d.get("id", -1)) == int(dev_id)
                                    ]
                                except Exception:
                                    remaining = []

                                if remaining:
                                    # se ainda existe no JSON, tentou remover e falhou
                                    print(
                                        f"[DEVOLUCOES] remover: id {dev_id} still present in JSON, marking hidden"
                                    )
                                    try:
                                        add_hidden_id(dev_id)
                                    except Exception:
                                        pass
                                    show_snackbar(
                                        page,
                                        "Devolução removida da visualização.",
                                        COLORS["warning"],
                                    )
                                else:
                                    print(f"[DEVOLUCOES] removed id {dev_id}")
                                    show_snackbar(
                                        page,
                                        "Devolução removida com sucesso.",
                                        COLORS["danger"],
                                    )
                                carregar_tabela()
                            except Exception as ex:
                                print(f"[DEVOLUCOES] remover erro: {ex}")
                                show_snackbar(
                                    page, "Erro ao remover devolução.", COLORS["danger"]
                                )

                        return ft.IconButton(
                            ft.Icons.DELETE,
                            icon_color=COLORS["danger"],
                            on_click=remover,
                        )

                    def criar_botao_troca(devolucao_id, devolucao_data):
                        """Cria botão de troca com melhor captura de variáveis"""
                        print(f"[TROCA] Criando botão para devolução {devolucao_id}")

                        def handle_click(e):
                            print(
                                f"[TROCA] ✓✓✓ CLIQUE DISPARADO! {devolucao_id}",
                                flush=True,
                            )
                            try:
                                dev = devolucao_data
                                print(
                                    f"[TROCA] Dados capturados: {dev.get('produto_nome')}",
                                    flush=True,
                                )

                                if dev.get("foi_trocado"):
                                    print("[TROCA] Já foi trocado")
                                    show_snackbar(
                                        page,
                                        "Este produto já foi trocado.",
                                        COLORS["warning"],
                                    )
                                    return

                                print(
                                    "[TROCA] Chamando show_modal_troca...", flush=True
                                )
                                show_modal_troca(page, dev, pdv_core, carregar_tabela)
                                print("[TROCA] show_modal_troca retornou", flush=True)

                            except Exception as ex:
                                print(
                                    f"[TROCA] ✗✗✗ ERRO EM handle_click: {ex}",
                                    flush=True,
                                )
                                import traceback

                                traceback.print_exc()
                                show_snackbar(
                                    page, f"Erro: {str(ex)}", COLORS["danger"]
                                )

                        foi_trocado = devolucao_data.get("foi_trocado", False)
                        cor = (
                            COLORS["warning"]
                            if not foi_trocado
                            else COLORS["text_secondary"]
                        )

                        btn = ft.IconButton(
                            ft.Icons.SWAP_HORIZ,
                            icon_color=cor,
                            on_click=handle_click,
                            tooltip="Trocar" if not foi_trocado else "Trocado",
                        )
                        print(f"[TROCA] Botão criado para {devolucao_id}")
                        return btn

                    row = ft.DataRow(
                        cells=[
                            ft.DataCell(
                                ft.Text(
                                    str(d.get("produto_id", "?")), **TYPOGRAPHY["body"]
                                )
                            ),
                            ft.DataCell(
                                ft.Text(
                                    d.get("produto_nome", "?")[:30],
                                    **TYPOGRAPHY["body"],
                                )
                            ),
                            ft.DataCell(
                                ft.Text(
                                    str(d.get("quantidade", 0)),
                                    **TYPOGRAPHY["body"],
                                    text_align=ft.TextAlign.CENTER,
                                )
                            ),
                            ft.DataCell(
                                ft.Text(
                                    format_brl(d.get("valor_total", 0)),
                                    **TYPOGRAPHY["body"],
                                )
                            ),
                            ft.DataCell(
                                ft.Text(
                                    d.get("motivo", "")[:25],
                                    **TYPOGRAPHY["caption"],
                                    color=COLORS["text_secondary"],
                                )
                            ),
                            ft.DataCell(
                                ft.Text(data_formatada, **TYPOGRAPHY["caption"])
                            ),
                            ft.DataCell(criar_botao_troca(d.get("id"), d)),
                            ft.DataCell(criar_botao_remover(d.get("id"))),
                        ]
                    )
                    tabela_ref.current.rows.append(row)

            # Atualizar estatísticas
            atualizar_stats(devol_filtradas)

            if tabela_ref.current:
                tabela_ref.current.update()

            show_snackbar(
                page, f"Carregadas {len(devol_filtradas)} devoluções", COLORS["info"]
            )

        except Exception as ex:
            print(f"[DEVOLUÇÕES] ✗ Erro ao carregar tabela: {ex}")
            import traceback

            traceback.print_exc()
            show_snackbar(page, f"Erro ao carregar: {str(ex)}", COLORS["danger"])
        finally:
            try:
                if loading_ref.current:
                    loading_ref.current.visible = False
                    loading_ref.current.update()
            except Exception:
                pass

    # Exportar PDF das devoluções/trocas filtradas
    def exportar_pdf_devolucoes(e=None):
        try:
            print("[DEVOLUÇÕES] Exportar PDF acionado")
            if not devol_filtradas_cache:
                print("[DEVOLUÇÕES] Nenhuma devolução filtrada para exportar")
                show_snackbar(
                    page, "Não há devoluções para exportar.", COLORS["warning"]
                )
                return

            # Montar cabeçalhos e dados
            headers = [
                "ID Dev",
                "ID Prod",
                "Produto",
                "Qtd",
                "Valor",
                "Motivo",
                "Data/Hora",
                "Troca",
            ]

            def _fmt_data(v):
                try:
                    return datetime.fromisoformat(str(v)).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    return str(v)

            linhas = []
            for d in devol_filtradas_cache:
                troca_txt = "Não"
                if d.get("foi_trocado"):
                    destino = d.get("troca_para_nome") or d.get("troca_para_id")
                    # FPDF core fonts usam Latin-1; substituir seta unicode por ASCII
                    troca_txt = f"Sim -> {destino}" if destino else "Sim"
                linhas.append(
                    [
                        d.get("id"),
                        d.get("produto_id"),
                        d.get("produto_nome", "") or "",
                        d.get("quantidade", 0),
                        d.get("valor_total", 0.0),
                        d.get("motivo", ""),
                        _fmt_data(d.get("data", "")),
                        troca_txt,
                    ]
                )

            print(f"[DEVOLUÇÕES] Preparando PDF com {len(linhas)} linhas")
            # Pesos: dar mais espaço para Produto e Motivo
            # Ajuste de largura: dar mais espaço para a coluna "Troca"
            pesos = [1, 1, 7, 1, 2, 6, 4, 3]
            caminho = generate_pdf_file(
                headers,
                linhas,
                nome_base="devolucoes_trocas",
                title="Relatório de Devoluções e Trocas",
                col_widths=pesos,
            )

            print(f"[DEVOLUÇÕES] PDF gerado: {caminho}")
            try:
                if os.path.exists(caminho):
                    os.startfile(caminho)
                    print("[DEVOLUÇÕES] Abrindo PDF no visualizador padrão")
                else:
                    print("[DEVOLUÇÕES] Caminho de PDF não existe após geração")
            except Exception as ex_open:
                print(f"[DEVOLUÇÕES] Falha ao abrir PDF: {ex_open}")

            show_snackbar(
                page,
                f"PDF exportado: {Path(caminho).name}",
                COLORS["success"],
            )
        except Exception as ex:
            print(f"[DEVOLUÇÕES] Erro ao exportar PDF: {ex}")
            show_snackbar(page, f"Erro ao exportar: {ex}", COLORS["danger"])

    # ========== LAYOUT PRINCIPAL ==========
    view = ft.View(
        "/gerente/devolucoes",
        [
            ft.AppBar(
                title=ft.Text(
                    "Devoluções e Trocas",
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.BOLD,
                ),
                bgcolor=COLORS["primary"],
                center_title=True,
                leading=ft.IconButton(
                    ft.Icons.ARROW_BACK,
                    icon_color=ft.Colors.WHITE,
                    on_click=handle_back,
                ),
            ),
            ft.Container(
                content=ft.Column(
                    [
                        # ===== CARDS DE ESTATÍSTICAS =====
                        ft.Container(
                            ref=stats_container_ref,
                            content=ft.Row(
                                [
                                    criar_card_stat(
                                        "Total de Devoluções",
                                        "0",
                                        COLORS["info"],
                                        ft.Icons.ASSIGNMENT_RETURN,
                                    ),
                                    criar_card_stat(
                                        "Taxa de Devolução",
                                        "0%",
                                        COLORS["warning"],
                                        ft.Icons.TRENDING_UP,
                                    ),
                                    criar_card_stat(
                                        "Valor Total",
                                        "R$ 0,00",
                                        COLORS["danger"],
                                        ft.Icons.MONEY,
                                    ),
                                    criar_card_stat(
                                        "Valor Médio",
                                        "R$ 0,00",
                                        COLORS["success"],
                                        ft.Icons.TRENDING_UP,
                                    ),
                                ],
                                spacing=12,
                                scroll=ft.ScrollMode.AUTO,
                            ),
                            padding=16,
                        ),
                        # ===== FILTROS E TABELA - LAYOUT RESPONSIVO =====
                        ft.Row(
                            [
                                # Coluna esquerda - Filtros (pequena)
                                ft.Container(
                                    content=ft.Column(
                                        [
                                            ft.Text(
                                                "Período",
                                                **TYPOGRAPHY["h3"],
                                                color=COLORS["text_primary"],
                                            ),
                                            ft.RadioGroup(
                                                ref=filtro_periodo_ref,
                                                value="7",
                                                content=ft.Column(
                                                    [
                                                        ft.Radio(
                                                            "Últimos 7 dias", value="7"
                                                        ),
                                                        ft.Radio(
                                                            "Últimos 30 dias",
                                                            value="30",
                                                        ),
                                                        ft.Radio(
                                                            "Últimos 90 dias",
                                                            value="90",
                                                        ),
                                                        ft.Radio(
                                                            "Todos", value="todos"
                                                        ),
                                                    ],
                                                    spacing=8,
                                                ),
                                                on_change=lambda _: carregar_tabela(),
                                            ),
                                        ],
                                        spacing=12,
                                    ),
                                    padding=16,
                                    border_radius=8,
                                    bgcolor=COLORS["surface"],
                                    border=ft.border.all(1, COLORS["border"]),
                                    width=200,
                                    expand=False,
                                ),
                                # Coluna direita - Tabela (grande, expandida)
                                ft.Container(
                                    content=ft.Column(
                                        [
                                            ft.Row(
                                                [
                                                    ft.Text(
                                                        "Histórico de Devoluções",
                                                        **TYPOGRAPHY["h2"],
                                                    ),
                                                    ft.Row(
                                                        [
                                                            ft.Container(
                                                                ref=refresh_slot_ref,
                                                                content=ft.IconButton(
                                                                    ft.Icons.REFRESH,
                                                                    on_click=lambda e: handle_refresh(
                                                                        e
                                                                    ),
                                                                    tooltip="Atualizar",
                                                                ),
                                                            ),
                                                            ft.IconButton(
                                                                ft.Icons.DELETE_FOREVER,
                                                                icon_color=COLORS[
                                                                    "danger"
                                                                ],
                                                                tooltip="Remover todas as devoluções exibidas",
                                                                on_click=lambda e: handle_delete_all_filtered(
                                                                    e
                                                                ),
                                                            ),
                                                            ft.ElevatedButton(
                                                                text="Exportar PDF",
                                                                icon=ft.Icons.PICTURE_AS_PDF,
                                                                bgcolor=COLORS[
                                                                    "primary"
                                                                ],
                                                                color=ft.Colors.WHITE,
                                                                on_click=exportar_pdf_devolucoes,
                                                            ),
                                                        ]
                                                    ),
                                                ],
                                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                            ),
                                            ft.DataTable(
                                                ref=tabela_ref,
                                                columns=[
                                                    ft.DataColumn(
                                                        ft.Text(
                                                            "ID Prod",
                                                            weight=ft.FontWeight.BOLD,
                                                        )
                                                    ),
                                                    ft.DataColumn(
                                                        ft.Text(
                                                            "Produto",
                                                            weight=ft.FontWeight.BOLD,
                                                        )
                                                    ),
                                                    ft.DataColumn(
                                                        ft.Text(
                                                            "Qtd",
                                                            weight=ft.FontWeight.BOLD,
                                                        )
                                                    ),
                                                    ft.DataColumn(
                                                        ft.Text(
                                                            "Valor",
                                                            weight=ft.FontWeight.BOLD,
                                                        )
                                                    ),
                                                    ft.DataColumn(
                                                        ft.Text(
                                                            "Motivo",
                                                            weight=ft.FontWeight.BOLD,
                                                        )
                                                    ),
                                                    ft.DataColumn(
                                                        ft.Text(
                                                            "Data/Hora",
                                                            weight=ft.FontWeight.BOLD,
                                                        )
                                                    ),
                                                    ft.DataColumn(
                                                        ft.Text(
                                                            "Trocar",
                                                            weight=ft.FontWeight.BOLD,
                                                        )
                                                    ),
                                                    ft.DataColumn(
                                                        ft.Text(
                                                            "Deletar",
                                                            weight=ft.FontWeight.BOLD,
                                                        )
                                                    ),
                                                ],
                                                rows=[],
                                                heading_row_color=ft.Colors.with_opacity(
                                                    0.05, COLORS["primary"]
                                                ),
                                                border=ft.border.all(
                                                    1, COLORS["border"]
                                                ),
                                                vertical_lines=ft.border.BorderSide(
                                                    1, COLORS["border"]
                                                ),
                                                horizontal_lines=ft.border.BorderSide(
                                                    1, COLORS["border"]
                                                ),
                                            ),
                                        ],
                                        spacing=12,
                                        expand=True,
                                    ),
                                    padding=16,
                                    border_radius=8,
                                    bgcolor=COLORS["surface"],
                                    border=ft.border.all(1, COLORS["border"]),
                                    expand=True,
                                ),
                            ],
                            spacing=16,
                            expand=True,
                        ),
                        # ===== LOADING =====
                        ft.Container(
                            content=ft.ProgressRing(
                                ref=loading_ref,
                                visible=False,
                                color=COLORS["primary"],
                            ),
                            alignment=ft.alignment.center,
                            padding=16,
                        ),
                    ],
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                bgcolor=COLORS["background"],
                expand=True,
                padding=16,
            ),
        ],
        bgcolor=COLORS["background"],
    )
    try:

        def _devol_on_key(e):
            try:
                key = (str(e.key) or "").upper()
                if key in ("ESCAPE", "ESC"):
                    page.go("/gerente")
            except Exception:
                pass

        view.on_keyboard_event = _devol_on_key
    except Exception:
        pass

    # Carregar devoluções quando a view for montada
    def on_view_did_mount(e):
        try:

            def carregar_depois():
                try:
                    print("[DEVOLUÇÕES] Iniciando carregar_tabela()...")
                    carregar_tabela()
                    page.update()
                except Exception as err:
                    print(f"[DEVOLUÇÕES] ✗ Erro: {err}")
                    import traceback

                    traceback.print_exc()

            import threading

            thread = threading.Thread(target=carregar_depois, daemon=True)
            thread.start()
        except Exception as ex:
            print(f"[DEVOLUÇÕES] ✗ Erro ao inicializar: {ex}")

    view.on_view_did_mount = on_view_did_mount
    # Expor método para permitir disparo via roteador (app.py)
    try:
        setattr(view, "load_data", carregar_tabela)
    except Exception:
        pass

    return view
