import os
import platform
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path

import flet as ft

from estoque.repository import carregar_produtos as carregar_estoque_local
from utils.export_utils import generate_csv_file, generate_pdf_file

# removido import não utilizado

# Brand Color Palette - Based on Mercadinho Ponto Certo Logo
COLORS = {
    "primary": "#034986",
    "primary_solid": "#034986",
    "accent": "#FFB347",
    "background": "#F0F4F8",
    "surface": "#FFFFFF",
    "text_primary": "#2D3748",
    "text_secondary": "#636E72",
    "success": "#8FC74F",
    "warning": "#FDCB6E",
    "danger": "#FF7675",
    "info": "#034986",
    "border": "#DFE6E9",
    "hover": "#F0F4F8",
}

# Modern Typography
TYPOGRAPHY = {
    "h1": {"size": 28, "weight": ft.FontWeight.BOLD},
    "h2": {"size": 20, "weight": ft.FontWeight.BOLD},
    "h3": {"size": 16, "weight": ft.FontWeight.W_600},
    "body": {"size": 14, "weight": ft.FontWeight.NORMAL},
    "caption": {"size": 12, "weight": ft.FontWeight.W_500},
}


def show_snackbar(page: ft.Page, message: str, color=COLORS["success"]):
    """Modern snackbar with icon and better styling"""
    page.snack_bar = ft.SnackBar(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.WHITE, size=20),
                ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
            ]
        ),
        bgcolor=color,
        behavior=ft.SnackBarBehavior.FLOATING,
        margin=10,
        duration=3000,
    )
    page.snack_bar.open = True
    page.update()


def format_brl(val: float) -> str:
    """Format currency with Brazilian Real"""
    return f"R$ {val:,.2f}".replace(".", "#").replace(",", ".").replace("#", ",")


def create_status_chip(value: float, is_percentage: bool = False) -> ft.Container:
    """Create colored status chip for values"""
    color = COLORS["success"] if value > 0 else COLORS["danger"]
    if is_percentage and value > 30:
        color = COLORS["success"]
    elif is_percentage and value < 10:
        color = COLORS["warning"]

    return ft.Container(
        content=ft.Text(
            f"{value:.2f}%" if is_percentage else format_brl(value),
            size=12,
            weight=ft.FontWeight.W_600,
            color=color,
        ),
        bgcolor=ft.Colors.with_opacity(0.2, color),
        padding=ft.padding.symmetric(horizontal=8, vertical=4),
        border_radius=20,
    )


def create_modern_button(
    text: str,
    icon: str,
    on_click,
    style: str = "primary",
    expand: bool = False,
) -> ft.Container:
    """Create modern styled button"""
    color_map = {
        "primary": COLORS["primary_solid"],
        "secondary": COLORS["text_secondary"],
        "success": COLORS["success"],
    }

    return ft.Container(
        content=ft.ElevatedButton(
            content=ft.Row(
                [ft.Icon(icon, size=18), ft.Text(text, size=14)],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            on_click=on_click,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=color_map[style],
                elevation=2,
                overlay_color=ft.Colors.with_opacity(0.1, ft.Colors.WHITE),
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
            ),
            expand=expand,
        ),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )


def create_relatorio_produtos_view(page: ft.Page, pdv_core, handle_back):
    # Armazenar pdv_core em page.app_data para acessar nas funções internas
    page.app_data["pdv_core"] = pdv_core

    # Modern refs with better naming
    chart_ref = ft.Ref[ft.BarChart]()
    loading_ring = ft.Ref[ft.ProgressRing]()
    data_table = ft.Ref[ft.DataTable]()
    refresh_slot_ref = ft.Ref[ft.Container]()
    # removido ref não utilizado: card_devolucoes_ref

    def create_summary_card(label: str, icon: str, color: str) -> ft.Container:
        """Create modern summary card"""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, size=24, color=color),
                            ft.Text(
                                label,
                                **TYPOGRAPHY["caption"],
                                color=COLORS["text_secondary"],
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Text(
                        "R$ 0,00", **TYPOGRAPHY["h2"], color=COLORS["text_primary"]
                    ),
                ]
            ),
            padding=16,
            border_radius=16,
            bgcolor=COLORS["surface"],
            border=ft.border.all(1, COLORS["border"]),
            shadow=ft.BoxShadow(
                color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                blur_radius=8,
                offset=ft.Offset(0, 2),
            ),
            animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    summary_cards = {
        "custo": create_summary_card("Total Custo", "attach_money", COLORS["warning"]),
        "venda": create_summary_card("Total Venda", "trending_up", COLORS["info"]),
        "lucro": create_summary_card(
            "Total Lucro", "account_balance", COLORS["success"]
        ),
    }

    def get_bar_color(prod, total_lucro):
        """Determine bar color based on profit margin"""
        if total_lucro < 0:
            return COLORS["danger"]
        if prod["venda"] > 0:
            margin = (prod["margem"] / prod["venda"]) * 100
            if margin > 30:
                return COLORS["success"]
            elif margin > 15:
                return COLORS["warning"]
        return COLORS["primary_solid"]

    def create_bar_chart_group(x, value, name, color):
        """Create animated bar chart group"""
        return ft.BarChartGroup(
            x=x,
            bar_rods=[
                ft.BarChartRod(
                    from_y=0,
                    to_y=value,
                    width=20,
                    color=color,
                    gradient=ft.LinearGradient(
                        begin=ft.alignment.bottom_center,
                        end=ft.alignment.top_center,
                        colors=[ft.Colors.with_opacity(0.5, color), color],
                    ),
                    tooltip=f"{name}\nLucro: {format_brl(value)}",
                    border_radius=8,
                )
            ],
        )

    def create_chart_label(value, label):
        """Create rotated chart label"""
        return ft.ChartAxisLabel(
            value=value,
            label=ft.Container(
                content=ft.Text(label[:12], size=11, color=COLORS["text_secondary"]),
                padding=5,
                rotate=ft.Rotate(angle=-0.5),
            ),
        )

    def update_summary_cards(totals):
        """Update summary cards with animation"""
        for key, card in summary_cards.items():
            value_label = card.content.controls[1]
            value_label.value = format_brl(totals[key])
            value_label.update()

    def show_empty_state(message: str):
        """Show empty state illustration"""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(
                        ft.Icons.INVENTORY_2_OUTLINED,
                        size=64,
                        color=COLORS["text_secondary"],
                    ),
                    ft.Text(
                        message, **TYPOGRAPHY["h3"], color=COLORS["text_secondary"]
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            alignment=ft.alignment.center,
            expand=True,
        )

    def close_dlg(dlg):
        """Close dialog"""
        dlg.visible = False
        dlg.parent.update()

    modal_container = ft.Container(
        visible=False,
        bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
        alignment=ft.alignment.center,
        expand=True,
    )

    def open_edit_modal(e, produto):
        """Open modal to edit product pricing"""
        try:
            print(f"[EDIT] Abrindo modal para produto: {produto['nome']}")
            show_snackbar(page, f"Editando: {produto['nome']}", COLORS["info"])

            custo_input = ft.TextField(
                label="Custo Unitário (R$)",
                value=f"{produto['custo']:.2f}",
                keyboard_type=ft.KeyboardType.NUMBER,
                prefix="R$ ",
                width=300,
            )

            venda_input = ft.TextField(
                label="Venda Unitária (R$)",
                value=f"{produto['venda']:.2f}",
                keyboard_type=ft.KeyboardType.NUMBER,
                prefix="R$ ",
                width=300,
            )

            margem_display = ft.Text(
                "Margem: 0.00%",
                size=14,
                weight=ft.FontWeight.W_600,
                color=COLORS["success"],
            )

            def on_value_change(e):
                """Update margem display when values change"""
                try:
                    custo = float(custo_input.value.replace(",", ".") or 0)
                    venda = float(venda_input.value.replace(",", ".") or 0)

                    if venda > 0:
                        margem = ((venda - custo) / venda) * 100
                        margem_display.value = f"Margem: {margem:.2f}%"
                        margem_color = (
                            COLORS["success"] if margem > 0 else COLORS["danger"]
                        )
                        margem_display.color = margem_color
                    else:
                        margem_display.value = "Margem: N/A"
                        margem_display.color = COLORS["text_secondary"]

                    if margem_display.page:
                        margem_display.update()
                except ValueError:
                    margem_display.value = "Margem: Invalido"
                    margem_display.color = COLORS["danger"]
                    if margem_display.page:
                        margem_display.update()

            custo_input.on_change = on_value_change
            venda_input.on_change = on_value_change
            on_value_change(None)

            def on_save(e):
                """Save changes to database"""
                print(f"[SAVE] Tentando salvar: {produto['nome']}")
                try:
                    novo_custo = float(custo_input.value.replace(",", ".") or 0)
                    novo_venda = float(venda_input.value.replace(",", ".") or 0)
                    print(f"[SAVE] Custo: {novo_custo}, Venda: {novo_venda}")

                    if novo_custo < 0 or novo_venda < 0:
                        show_snackbar(
                            page, "Precos nao podem ser negativos!", COLORS["danger"]
                        )
                        return

                    if novo_venda < novo_custo:
                        show_snackbar(
                            page,
                            "Venda nao pode ser menor que custo!",
                            COLORS["warning"],
                        )
                        return

                    pdv_core = page.app_data.get("pdv_core")
                    if pdv_core:
                        pdv_core.atualizar_preco_produto(
                            produto["id"], novo_custo, novo_venda
                        )
                        show_snackbar(
                            page,
                            f"Produto '{produto['nome']}' atualizado!",
                            COLORS["success"],
                        )
                        modal_container.visible = False
                        modal_container.update()
                        load_relatorio_produtos()
                    else:
                        print("[SAVE] pdv_core nao encontrado")
                except ValueError as ex:
                    print(f"[SAVE] Erro: {ex}")
                    show_snackbar(page, "Valores invalidos!", COLORS["danger"])

            def on_close(e):
                modal_container.visible = False
                modal_container.update()

            dialog_card = ft.Card(
                elevation=8,
                content=ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        f"Editar: {produto['nome']}",
                                        **TYPOGRAPHY["h3"],
                                    ),
                                    ft.IconButton(
                                        ft.Icons.CLOSE,
                                        on_click=on_close,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Divider(),
                            custo_input,
                            venda_input,
                            ft.Divider(),
                            margem_display,
                            ft.Text(
                                f"Estoque: {produto['estoque']} un.",
                                size=12,
                                color=COLORS["text_secondary"],
                            ),
                            ft.Divider(),
                            ft.Row(
                                [
                                    ft.TextButton(
                                        "Cancelar",
                                        on_click=on_close,
                                    ),
                                    ft.ElevatedButton(
                                        "Salvar",
                                        on_click=on_save,
                                        style=ft.ButtonStyle(
                                            bgcolor=COLORS["primary_solid"],
                                            color=ft.Colors.WHITE,
                                        ),
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.END,
                                spacing=12,
                            ),
                        ],
                        spacing=12,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    padding=24,
                    width=500,
                ),
            )

            modal_container.content = dialog_card
            modal_container.visible = True
            modal_container.update()
            print(f"[MODAL] Modal exibido para: {produto['nome']}")

        except Exception as ex:
            print(f"[ERROR] Erro ao abrir modal: {ex}")
            import traceback

            traceback.print_exc()

    def atualizar_card_devolucoes():
        """Atualiza o card de devoluções (placeholder)."""
        # Implemente aqui a lógica para atualizar o card de devoluções, se necessário.
        # Atualmente, esta função é um placeholder para evitar erro de nome indefinido.
        pass

    def load_relatorio_produtos():
        """Load products report with modern loading state"""
        # Garante que refs estejam resolvidas antes de carregar
        if not loading_ring.current:
            try:
                import asyncio

                async def _defer_load():
                    try:
                        await asyncio.sleep(0)
                    except Exception:
                        pass
                    load_relatorio_produtos()

                if hasattr(page, "run_task"):
                    page.run_task(_defer_load)
                    return
            except Exception:
                pass
            # Fallback: tenta novamente logo em seguida
            try:
                load_relatorio_produtos()
            except Exception:
                return

        try:
            loading_ring.current.visible = True
            loading_ring.current.update()

            pdv_core = page.app_data.get("pdv_core")
            if not pdv_core:
                raise RuntimeError("Sistema não iniciado")

            # 1) Carregar produtos do banco (dados financeiros)
            todos_produtos = pdv_core.gerar_relatorio_produtos()

            # 2) Carregar produtos da tela de Estoque (fonte de verdade para quantidade e existência)
            def _normalize(s: str) -> str:
                if not s:
                    return ""
                nf = unicodedata.normalize("NFD", str(s))
                return "".join(c for c in nf if unicodedata.category(c) != "Mn").lower()

            produtos = []
            try:
                estoque_local = carregar_estoque_local() or []
                # Índices auxiliares
                db_por_barcode = {
                    str(p.get("codigo_barras") or "").strip(): p for p in todos_produtos
                }
                db_por_nome = {_normalize(p.get("nome")): p for p in todos_produtos}

                # Se o arquivo local estiver vazio, usar fallback direto do banco
                if not estoque_local:
                    for item_db in todos_produtos:
                        try:
                            produtos.append(
                                {
                                    "id": item_db.get("id") or 0,
                                    "codigo_barras": str(
                                        item_db.get("codigo_barras") or ""
                                    ).strip(),
                                    "nome": item_db.get("nome") or "",
                                    "estoque": int(item_db.get("estoque", 0) or 0),
                                    "custo": float(item_db.get("custo", 0.0) or 0.0),
                                    "venda": float(item_db.get("venda", 0.0) or 0.0),
                                    "margem": float(
                                        item_db.get(
                                            "margem",
                                            (
                                                item_db.get("venda", 0.0)
                                                - item_db.get("custo", 0.0)
                                                if item_db.get("venda") is not None
                                                else 0
                                            ),
                                        )
                                        or 0
                                    ),
                                    "lote": item_db.get("lote", ""),
                                }
                            )
                        except Exception:
                            continue
                else:
                    for p in estoque_local:
                        try:
                            codigo_barras = str(
                                p.get("codigo_barras") or p.get("codigo") or ""
                            ).strip()
                            nome_norm = _normalize(p.get("nome"))

                            # Quantidade real vem do JSON (tela de Estoque)
                            quantidade = int(p.get("quantidade", 0) or 0)

                            # Tentar casar com item do banco por código de barras; senão, por nome
                            item_db = None
                            if codigo_barras and codigo_barras in db_por_barcode:
                                item_db = db_por_barcode[codigo_barras]
                            elif nome_norm in db_por_nome:
                                item_db = db_por_nome[nome_norm]

                            # Montar registro unificado
                            custo = None
                            venda = None
                            margem = None
                            if item_db:
                                custo = float(item_db.get("custo", 0.0) or 0.0)
                                venda = float(item_db.get("venda", 0.0) or 0.0)
                                margem = float(
                                    item_db.get("margem", venda - (custo or 0.0))
                                )
                                pid = item_db.get("id") or (p.get("id") or 0)
                            else:
                                custo = float(p.get("preco_custo", 0) or 0)
                                venda = float(
                                    p.get("preco_venda", p.get("preco", 0)) or 0
                                )
                                margem = (venda - custo) if custo >= 0 else 0
                                pid = p.get("id") or 0

                            produtos.append(
                                {
                                    "id": pid,
                                    "codigo_barras": codigo_barras,
                                    "nome": p.get("nome")
                                    or (item_db.get("nome") if item_db else ""),
                                    "estoque": quantidade,
                                    "lote": p.get("lote", ""),
                                    "custo": custo,
                                    "venda": venda,
                                    "margem": margem,
                                }
                            )
                        except Exception:
                            # Ignora registros malformados do JSON
                            continue

            except Exception:
                # Se falhar ao ler o JSON, pelo menos exibir o que veio do banco
                produtos = []

            print(
                f"[DEBUG] Total no banco: {len(todos_produtos)} | Total na tela de Estoque: {len(produtos)}"
            )

            if not produtos:
                show_snackbar(
                    page,
                    "Nenhum produto encontrado na tela de Estoque.",
                    ft.Colors.ORANGE_700,
                )
                # Limpar tabela mesmo sem produtos
                if data_table.current:
                    data_table.current.rows.clear()
                    data_table.current.update()
                return

            if data_table.current:
                data_table.current.rows.clear()

            chart_bars = []
            chart_labels = []
            totals = {"custo": 0.0, "venda": 0.0, "lucro": 0.0}

            produtos_ordenados = sorted(
                produtos, key=lambda p: p["margem"] * p["estoque"], reverse=True
            )

            print(
                f"[DEBUG] Começando a adicionar {len(produtos_ordenados)} linhas à tabela"
            )

            # Debug: mostrar se o flag de lote está ativo
            print(
                f"[DEBUG] relprod_show_lote flag = {page.app_data.get('relprod_show_lote', False)}"
            )

            for idx, prod in enumerate(produtos_ordenados):
                total_custo = prod["custo"] * prod["estoque"]
                total_venda = prod["venda"] * prod["estoque"]
                total_lucro = prod["margem"] * prod["estoque"]

                totals["custo"] += total_custo
                totals["venda"] += total_venda
                totals["lucro"] += total_lucro

                # Build cells with optional Lote column
                cells = []
                cells.append(
                    ft.DataCell(ft.Text(str(prod["id"]), **TYPOGRAPHY["body"]))
                )
                cells.append(
                    ft.DataCell(
                        ft.Row(
                            [
                                ft.Icon(
                                    ft.Icons.INVENTORY_2_OUTLINED,
                                    size=16,
                                    color=COLORS["primary_solid"],
                                ),
                                ft.Text(
                                    prod["nome"],
                                    **TYPOGRAPHY["body"],
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                            spacing=8,
                        )
                    )
                )

                # opcional: Lote
                if page.app_data.get("relprod_show_lote", False):
                    cells.append(
                        ft.DataCell(
                            ft.Text(str(prod.get("lote", "")), **TYPOGRAPHY["body"])
                        )
                    )

                cells.append(
                    ft.DataCell(ft.Text(str(prod["estoque"]), **TYPOGRAPHY["body"]))
                )
                cells.append(ft.DataCell(create_status_chip(total_custo, False)))
                cells.append(ft.DataCell(create_status_chip(total_venda, False)))
                cells.append(
                    ft.DataCell(
                        create_status_chip(
                            (
                                (prod["margem"] / prod["venda"] * 100)
                                if prod["venda"]
                                else 0
                            ),
                            True,
                        )
                    )
                )
                cells.append(ft.DataCell(create_status_chip(total_lucro, False)))
                cells.append(
                    ft.DataCell(
                        ft.TextButton(
                            "Editar",
                            icon=ft.Icons.EDIT,
                            on_click=lambda e, p=prod: open_edit_modal(e, p),
                        )
                    )
                )

                row = ft.DataRow(
                    cells=cells,
                    color=(
                        ft.Colors.with_opacity(0.05, COLORS["primary_solid"])
                        if idx % 2 == 0
                        else None
                    ),
                )

                if data_table.current:
                    data_table.current.rows.append(row)

                # Debug: print lote value for first few rows when flag active
                if page.app_data.get("relprod_show_lote", False) and idx < 5:
                    print(
                        f"[DEBUG] lote for idx={idx} id={prod.get('id')} lote={prod.get('lote')}"
                    )

                bar_color = get_bar_color(prod, total_lucro)
                chart_bars.append(
                    create_bar_chart_group(idx, total_lucro, prod["nome"], bar_color)
                )
                chart_labels.append(create_chart_label(idx, prod["nome"]))

            update_summary_cards(totals)

            if chart_ref.current:
                chart_ref.current.bar_groups = chart_bars
                chart_ref.current.bottom_axis.labels = chart_labels
                chart_ref.current.update()

            if data_table.current:
                print(
                    f"[DEBUG] relatorio_dt.columns count = {len(relatorio_dt.columns)}"
                )
                print(
                    f"[DEBUG] Atualizando tabela com {len(data_table.current.rows)} linhas"
                )
                data_table.current.update()
            else:
                print("[DEBUG] ERRO: data_table.current é None!")

            atualizar_card_devolucoes()

            show_snackbar(
                page, f"✅ {len(produtos)} produtos da tela de Estoque carregados"
            )

        except Exception as ex:
            show_snackbar(page, f"Erro: {str(ex)}", COLORS["danger"])
        finally:
            loading_ring.current.visible = False
            loading_ring.current.update()

    # --- Refresh com animação ---
    def _make_refresh_button():
        return ft.Container(
            content=ft.ElevatedButton(
                content=ft.Row(
                    [ft.Icon(ft.Icons.REFRESH, size=18), ft.Text("Atualizar", size=14)],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                on_click=lambda e: handle_refresh(e),
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=COLORS["primary_solid"],
                    elevation=2,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                ),
            ),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    def handle_refresh(e):
        try:
            import asyncio

            async def _do_refresh():
                try:
                    if refresh_slot_ref.current:
                        refresh_slot_ref.current.content = ft.ProgressRing(
                            width=28, height=28, color=COLORS["primary_solid"]
                        )
                        refresh_slot_ref.current.update()
                    await asyncio.sleep(0)
                    load_relatorio_produtos()
                finally:
                    try:
                        if refresh_slot_ref.current:
                            refresh_slot_ref.current.content = (
                                _make_refresh_button().content
                            )
                            refresh_slot_ref.current.update()
                    except Exception:
                        pass

            try:
                page.run_task(_do_refresh)
            except Exception:
                try:
                    asyncio.run(_do_refresh())
                except Exception:
                    pass
        except Exception:
            try:
                load_relatorio_produtos()
            except Exception:
                pass

    def export_relatorio(export_type: str):
        """Export report with modern feedback"""
        try:
            print(f"[DEBUG] Iniciando exportação tipo: {export_type}")
            pdv_core = page.app_data.get("pdv_core")
            if not pdv_core:
                raise RuntimeError("Sistema não iniciado")

            # Unificar com a tela de Estoque para exportar exatamente o que é exibido
            todos_produtos = pdv_core.gerar_relatorio_produtos()

            def _normalize(s: str) -> str:
                if not s:
                    return ""
                nf = unicodedata.normalize("NFD", str(s))
                return "".join(c for c in nf if unicodedata.category(c) != "Mn").lower()

            produtos = []
            try:
                estoque_local = carregar_estoque_local() or []
                db_por_barcode = {
                    str(p.get("codigo_barras") or "").strip(): p for p in todos_produtos
                }
                db_por_nome = {_normalize(p.get("nome")): p for p in todos_produtos}

                for p in estoque_local:
                    try:
                        codigo_barras = str(
                            p.get("codigo_barras") or p.get("codigo") or ""
                        ).strip()
                        nome_norm = _normalize(p.get("nome"))
                        quantidade = int(p.get("quantidade", 0) or 0)

                        item_db = None
                        if codigo_barras and codigo_barras in db_por_barcode:
                            item_db = db_por_barcode[codigo_barras]
                        elif nome_norm in db_por_nome:
                            item_db = db_por_nome[nome_norm]

                        if item_db:
                            custo = float(item_db.get("custo", 0.0) or 0.0)
                            venda = float(item_db.get("venda", 0.0) or 0.0)
                            margem = float(
                                item_db.get("margem", venda - (custo or 0.0))
                            )
                            pid = item_db.get("id") or (p.get("id") or 0)
                            nome_final = item_db.get("nome") or (p.get("nome") or "")
                        else:
                            custo = float(p.get("preco_custo", 0) or 0)
                            venda = float(p.get("preco_venda", p.get("preco", 0)) or 0)
                            margem = (venda - custo) if custo >= 0 else 0
                            pid = p.get("id") or 0
                            nome_final = p.get("nome") or ""

                        produtos.append(
                            {
                                "id": pid,
                                "codigo_barras": codigo_barras,
                                "nome": nome_final,
                                "estoque": quantidade,
                                "custo": custo,
                                "venda": venda,
                                "margem": margem,
                            }
                        )
                    except Exception:
                        continue
            except Exception:
                produtos = list(todos_produtos)

            if not produtos:
                show_snackbar(
                    page, "Nenhum dado em estoque para exportar", COLORS["warning"]
                )
                return

            headers = [
                "ID",
                "Produto",
                "Estoque",
                "Custo Unitário",
                "Venda Unitária",
                "% Margem",
                "Total Custo",
                "Total Venda",
                "Total Lucro",
            ]

            # Ordena por lucro total desc para relatório mais útil
            produtos_ordenados = sorted(
                produtos, key=lambda p: p["margem"] * p["estoque"], reverse=True
            )

            data = []
            total_custo = 0.0
            total_venda = 0.0
            total_lucro = 0.0

            for prod in produtos_ordenados:
                tc = prod["custo"] * prod["estoque"]
                tv = prod["venda"] * prod["estoque"]
                tl = prod["margem"] * prod["estoque"]

                total_custo += tc
                total_venda += tv
                total_lucro += tl

                perc_margem = (
                    (prod["margem"] / prod["venda"] * 100) if prod["venda"] else 0
                )

                data.append(
                    [
                        prod["id"],
                        prod["nome"],
                        int(prod["estoque"]),
                        format_brl(prod["custo"]),
                        format_brl(prod["venda"]),
                        f"{perc_margem:.2f}%",
                        format_brl(tc),
                        format_brl(tv),
                        format_brl(tl),
                    ]
                )

            # Linha de totais
            data.append(
                [
                    "",
                    "TOTAL",
                    "",
                    "",
                    "",
                    "",
                    format_brl(total_custo),
                    format_brl(total_venda),
                    format_brl(total_lucro),
                ]
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            caminho = (
                generate_csv_file(headers, data, f"relatorio_produtos_{timestamp}")
                if export_type == "csv"
                else generate_pdf_file(
                    headers,
                    data,
                    f"relatorio_produtos_{timestamp}",
                    "Relatório de Produtos em Estoque",
                    col_widths=[1, 4, 1, 1.5, 1.5, 1.2, 1.5, 1.5, 1.5],
                )
            )

            print(f"[DEBUG] Arquivo exportado: {caminho}")
            show_snackbar(page, f"✅ Exportado: {Path(caminho).name}")

            # Abrir o arquivo automaticamente
            try:
                caminho_absoluto = os.path.abspath(caminho)
                print(f"[DEBUG] Abrindo arquivo: {caminho_absoluto}")

                if platform.system() == "Windows":
                    os.startfile(caminho_absoluto)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.Popen(["open", caminho_absoluto])
                else:  # Linux
                    subprocess.Popen(["xdg-open", caminho_absoluto])
            except Exception as open_ex:
                print(f"[DEBUG] Erro ao abrir arquivo: {str(open_ex)}")
                # Não mostrar erro se não conseguir abrir, apenas continuar

        except Exception as ex:
            print(f"[DEBUG] Erro na exportação: {str(ex)}")
            show_snackbar(page, f"Erro ao exportar: {str(ex)}", COLORS["danger"])

    # Importação removida desta tela por decisão de produto

    def create_sortable_header(text: str, sort_key: str) -> ft.Container:
        """Create clickable sortable header"""
        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        text, **TYPOGRAPHY["caption"], color=COLORS["text_primary"]
                    ),
                    ft.Icon(
                        ft.Icons.UNFOLD_MORE,
                        size=16,
                        color=COLORS["text_secondary"],
                    ),
                ],
                spacing=4,
            ),
            padding=ft.padding.only(right=12),
            on_click=lambda e: handle_sort(sort_key),
        )

    def handle_sort(key: str):
        """Handle column sorting"""
        pass

    def toggle_lote(e=None):
        """Toggle Lote column visibility and rebuild columns + refresh data"""
        try:
            val = False
            if e is not None and hasattr(e, "control") and hasattr(e.control, "value"):
                val = bool(e.control.value)
            else:
                val = bool(page.app_data.get("relprod_show_lote", False))
            page.app_data["relprod_show_lote"] = val
            # Rebuild columns if table exists
            try:
                cols = [
                    ft.DataColumn(create_sortable_header("ID", "id")),
                    ft.DataColumn(create_sortable_header("Produto", "nome")),
                ]
                if val:
                    cols.append(ft.DataColumn(create_sortable_header("Lote", "lote")))
                cols.extend(
                    [
                        ft.DataColumn(create_sortable_header("Estoque", "estoque")),
                        ft.DataColumn(create_sortable_header("Custo Unit.", "custo")),
                        ft.DataColumn(create_sortable_header("Venda Unit.", "venda")),
                        ft.DataColumn(create_sortable_header("Margem %", "margem")),
                        ft.DataColumn(
                            create_sortable_header("Total Lucro", "total_lucro")
                        ),
                        ft.DataColumn(ft.Text("Ações", **TYPOGRAPHY["body"])),
                    ]
                )
                relatorio_dt.columns.clear()
                relatorio_dt.columns.extend(cols)
                try:
                    relatorio_dt.update()
                except Exception:
                    pass
            except Exception:
                pass
            # reload table
            try:
                load_relatorio_produtos()
            except Exception:
                pass
        except Exception:
            pass

    app_bar = ft.AppBar(
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            tooltip="Voltar",
            on_click=lambda _: page.go("/gerente"),
            icon_color=ft.Colors.WHITE,
        ),
        title=ft.Text(
            "Relatórios de Produtos",
            size=20,
            weight="bold",
            color=ft.Colors.WHITE,
            text_align=ft.TextAlign.CENTER,
        ),
        center_title=True,
        bgcolor=COLORS["primary"],
        elevation=2,
    )

    relatorio_dt = ft.DataTable(
        ref=data_table,
        columns=[
            ft.DataColumn(create_sortable_header("ID", "id")),
            ft.DataColumn(create_sortable_header("Produto", "nome")),
            ft.DataColumn(create_sortable_header("Estoque", "estoque")),
            ft.DataColumn(create_sortable_header("Custo Unit.", "custo")),
            ft.DataColumn(create_sortable_header("Venda Unit.", "venda")),
            ft.DataColumn(create_sortable_header("Margem %", "margem")),
            ft.DataColumn(create_sortable_header("Total Lucro", "total_lucro")),
            ft.DataColumn(ft.Text("Ações", **TYPOGRAPHY["body"])),
        ],
        rows=[],
        expand=False,
        heading_row_color=ft.Colors.with_opacity(0.05, COLORS["primary_solid"]),
        data_row_color={"hovered": COLORS["hover"]},
        column_spacing=20,
    )

    modal_container = ft.Container(
        visible=False,
        bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
        alignment=ft.alignment.center,
        expand=True,
    )

    content_container = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.ProgressRing(
                        ref=loading_ring,
                        width=40,
                        height=40,
                        color=COLORS["primary_solid"],
                    ),
                    alignment=ft.alignment.center,
                    visible=False,
                ),
                ft.Container(
                    content=ft.ResponsiveRow(
                        [
                            ft.Column(col=4, controls=[card])
                            for card in summary_cards.values()
                        ],
                        spacing=16,
                    ),
                    padding=ft.padding.only(bottom=24),
                ),
                ft.Container(
                    content=ft.ResponsiveRow(
                        [
                            ft.Column(
                                col={"md": 12, "lg": 5},
                                controls=[
                                    ft.Card(
                                        elevation=0,
                                        content=ft.Container(
                                            content=ft.Column(
                                                [
                                                    ft.Text(
                                                        "Lucro por Produto",
                                                        **TYPOGRAPHY["h2"],
                                                    ),
                                                    ft.Container(
                                                        content=ft.BarChart(
                                                            ref=chart_ref,
                                                            bar_groups=[],
                                                            bottom_axis=ft.ChartAxis(
                                                                labels=[],
                                                                labels_size=40,
                                                            ),
                                                            left_axis=ft.ChartAxis(
                                                                title=ft.Text(
                                                                    "Valor (R$)",
                                                                    **TYPOGRAPHY[
                                                                        "caption"
                                                                    ],
                                                                ),
                                                                labels_size=60,
                                                            ),
                                                            tooltip_bgcolor=ft.Colors.with_opacity(
                                                                0.9,
                                                                COLORS["text_primary"],
                                                            ),
                                                            border=ft.border.all(
                                                                0, ft.Colors.TRANSPARENT
                                                            ),
                                                            expand=True,
                                                        ),
                                                        height=400,
                                                        border_radius=16,
                                                        border=ft.border.all(
                                                            1, COLORS["border"]
                                                        ),
                                                        bgcolor=COLORS["surface"],
                                                        padding=10,
                                                    ),
                                                    # ações associadas ao gráfico (compactas, abaixo do gráfico)
                                                    ft.Container(
                                                        content=ft.Row(
                                                            [
                                                                ft.Container(
                                                                    ref=refresh_slot_ref,
                                                                    content=_make_refresh_button(),
                                                                ),
                                                                ft.Container(
                                                                    content=ft.Checkbox(
                                                                        label="Mostrar Lote",
                                                                        value=page.app_data.get(
                                                                            "relprod_show_lote",
                                                                            False,
                                                                        ),
                                                                        on_change=toggle_lote,
                                                                    ),
                                                                    padding=ft.padding.only(
                                                                        left=8, right=8
                                                                    ),
                                                                ),
                                                                create_modern_button(
                                                                    "CSV",
                                                                    ft.Icons.DOWNLOAD,
                                                                    lambda _: export_relatorio(
                                                                        "csv"
                                                                    ),
                                                                    "secondary",
                                                                ),
                                                                create_modern_button(
                                                                    "PDF",
                                                                    ft.Icons.PICTURE_AS_PDF,
                                                                    lambda _: export_relatorio(
                                                                        "pdf"
                                                                    ),
                                                                    "secondary",
                                                                ),
                                                            ],
                                                            spacing=10,
                                                            alignment=ft.MainAxisAlignment.START,
                                                        ),
                                                        padding=ft.padding.only(top=12),
                                                    ),
                                                ],
                                                spacing=16,
                                            ),
                                            padding=16,
                                        ),
                                        surface_tint_color=COLORS["surface"],
                                    ),
                                ],
                            ),
                            ft.Column(
                                col={"md": 12, "lg": 7},
                                controls=[
                                    ft.Container(
                                        content=ft.Column(
                                            [
                                                ft.Row(
                                                    [
                                                        ft.Text(
                                                            "Produtos em Estoque",
                                                            **TYPOGRAPHY["h2"],
                                                        ),
                                                        ft.Container(
                                                            content=ft.Text(
                                                                "Live",
                                                                size=12,
                                                                weight=ft.FontWeight.W_600,
                                                                color=ft.Colors.WHITE,
                                                            ),
                                                            bgcolor=COLORS["success"],
                                                            padding=ft.padding.symmetric(
                                                                horizontal=8,
                                                                vertical=4,
                                                            ),
                                                            border_radius=12,
                                                        ),
                                                    ],
                                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                                ),
                                                ft.Container(
                                                    content=ft.Column(
                                                        [relatorio_dt],
                                                        scroll=ft.ScrollMode.AUTO,
                                                    ),
                                                    border=ft.border.all(
                                                        1, COLORS["border"]
                                                    ),
                                                    border_radius=16,
                                                    bgcolor=COLORS["surface"],
                                                    padding=0,
                                                    expand=True,
                                                    height=520,
                                                    shadow=ft.BoxShadow(
                                                        color=ft.Colors.with_opacity(
                                                            0.05, ft.Colors.BLACK
                                                        ),
                                                        blur_radius=10,
                                                        offset=ft.Offset(0, 4),
                                                    ),
                                                ),
                                            ]
                                        ),
                                        expand=True,
                                    )
                                ],
                            ),
                        ],
                        spacing=24,
                    ),
                    expand=True,
                ),
            ],
            spacing=0,
        ),
        padding=ft.padding.all(12),
        bgcolor=COLORS["background"],
        expand=True,
    )

    view = ft.View(
        "/gerente/relatorio_produtos",
        [
            ft.Stack(
                [
                    content_container,
                    modal_container,
                ],
                expand=True,
            )
        ],
        padding=0,
        bgcolor=COLORS["background"],
        appbar=app_bar,
    )

    def on_view_did_mount(e):
        print("📊 View montada - Iniciando carga")
        load_relatorio_produtos()

    try:

        def _relprod_on_key(e):
            try:
                key = (str(e.key) or "").upper()
                if key in ("ESCAPE", "ESC"):
                    page.go("/gerente")
            except Exception:
                pass

        view.on_keyboard_event = _relprod_on_key
    except Exception:
        pass

    view.on_view_did_mount = on_view_did_mount
    # Atualiza sempre que a view voltar a aparecer (quando suportado pelo Flet)
    try:
        view.on_view_will_appear = lambda e: load_relatorio_produtos()
    except Exception:
        pass

    # Expor método para permitir disparo via roteador (app.py)
    try:
        setattr(view, "load_data", load_relatorio_produtos)
    except Exception:
        pass
    return view
