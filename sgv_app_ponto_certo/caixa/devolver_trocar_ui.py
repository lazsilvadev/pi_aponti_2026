"""
Componentes de UI para Devolver & Trocar no Caixa
Modal e botões para gerenciar devoluções e trocas direto da tela de vendas
"""

import os
import time

import flet as ft

from models.db_models import Produto
from vendas.vendas_devolucoes_logic import (
    buscar_vendas_do_caixa,
    processar_devolucao_e_trocar,
)

# Cores padrão
PRIMARY_COLOR = "#007BFF"
DANGER_COLOR = "#FF7675"
SUCCESS_COLOR = "#00B894"
TEXT_COLOR = "#2D3748"
CARD_BG = "#F8F9FA"

# Armazenar referências de modais (evita recriação)
_modais_cache = {}


def buscar_produto_por_barras(pdv_core, codigo_barras: str):
    """Busca produto por código de barras ou ID; fallback para JSON se necessário.

    - Tenta via `validar_produto_existe` (ID ou barras) no banco.
    - Se não existir, tenta localizar em data/produtos.json e cria Produto mínimo.
    """
    try:
        valor = str(codigo_barras or "").strip()
        if not valor:
            return None

        # Primeiro: tentar pelo banco (ID ou código de barras)
        try:
            from estoque.devolucoes import validar_produto_existe

            existe, produto = validar_produto_existe(pdv_core, valor)
            if existe and produto:
                return {
                    "id": produto.id,
                    "nome": produto.nome,
                    "preco": produto.preco_venda,
                    "estoque": produto.estoque_atual,
                }
        except Exception as ex_db:
            print(f"[DEVOLVER TROCAR] Falha ao validar produto no banco: {ex_db}")

        # Tentar diretamente pelo core (busca por código de barras)
        try:
            produto_core = getattr(pdv_core, "buscar_produto", None)
            if callable(produto_core):
                p = produto_core(valor)
                if p:
                    return {
                        "id": p.id,
                        "nome": p.nome,
                        "preco": p.preco_venda,
                        "estoque": p.estoque_atual,
                    }
        except Exception as ex_core:
            print(f"[DEVOLVER TROCAR] Falha ao buscar via core: {ex_core}")

        # Fallback: tentar via JSON e criar produto mínimo no banco
        try:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            arquivo = os.path.join(base_dir, "data", "produtos.json")
            if os.path.exists(arquivo):
                import json

                with open(arquivo, "r", encoding="utf-8") as f:
                    dados_json = json.load(f)

                match = None
                # 1) Match exato
                for pj in dados_json:
                    codigo_json = str(
                        pj.get("codigo_barras") or pj.get("codigo") or ""
                    ).strip()
                    if codigo_json and codigo_json == valor:
                        match = pj
                        break

                # 2) Match sem zeros à esquerda
                if not match:
                    valor_sem_zeros = valor.lstrip("0")
                    for pj in dados_json:
                        codigo_json = str(
                            pj.get("codigo_barras") or pj.get("codigo") or ""
                        ).strip()
                        if codigo_json.lstrip("0") == valor_sem_zeros and codigo_json:
                            match = pj
                            break

                # 3) Match por prefixo único (evita ambiguidade)
                if not match:
                    candidatos = []
                    valor_sem_zeros = valor.lstrip("0")
                    for pj in dados_json:
                        codigo_json = str(
                            pj.get("codigo_barras") or pj.get("codigo") or ""
                        ).strip()
                        if not codigo_json:
                            continue
                        if codigo_json.startswith(valor) or codigo_json.lstrip(
                            "0"
                        ).startswith(valor_sem_zeros):
                            candidatos.append(pj)
                    if len(candidatos) == 1:
                        match = candidatos[0]

                if match:
                    try:
                        session = pdv_core.session
                        # Determinar valores mínimos para campos obrigatórios
                        preco_v = float(
                            match.get("preco_venda") or match.get("preco") or 0.0
                        )
                        preco_c = float(
                            match.get("preco_custo") or match.get("custo") or preco_v
                        )
                        estoque_min = int(match.get("estoque_minimo") or 10)

                        novo = Produto(
                            nome=match.get("nome") or match.get("descricao") or valor,
                            codigo_barras=str(
                                match.get("codigo_barras")
                                or match.get("codigo")
                                or valor
                            ),
                            preco_venda=preco_v,
                            estoque_atual=int(
                                match.get("estoque_atual") or match.get("estoque") or 0
                            ),
                            estoque_minimo=estoque_min,
                        )
                        # Alguns campos podem ser NOT NULL no modelo
                        try:
                            setattr(novo, "preco_custo", preco_c)
                        except Exception:
                            pass
                        session.add(novo)
                        try:
                            session.commit()
                        except Exception as ex_commit:
                            # Se falhar por UNIQUE, fazer rollback e retornar o existente
                            try:
                                session.rollback()
                            except Exception:
                                pass
                            msg = str(ex_commit)
                            if (
                                "UNIQUE constraint failed: produtos.codigo_barras"
                                in msg
                            ):
                                try:
                                    # Procurar pelo código realmente utilizado na criação
                                    codigo_alvo = (
                                        getattr(novo, "codigo_barras", None) or valor
                                    )
                                    existente = (
                                        session.query(Produto)
                                        .filter_by(codigo_barras=codigo_alvo)
                                        .first()
                                    )
                                    if existente:
                                        return {
                                            "id": existente.id,
                                            "nome": existente.nome,
                                            "preco": existente.preco_venda,
                                            "estoque": existente.estoque_atual,
                                        }
                                    # Tentar sem zeros à esquerda tanto do valor quanto do código alvo
                                    candidato = (codigo_alvo or "").lstrip("0")
                                    existente2 = (
                                        session.query(Produto)
                                        .filter_by(codigo_barras=candidato)
                                        .first()
                                    )
                                    if existente2:
                                        return {
                                            "id": existente2.id,
                                            "nome": existente2.nome,
                                            "preco": existente2.preco_venda,
                                            "estoque": existente2.estoque_atual,
                                        }
                                except Exception:
                                    pass
                            # Se outro erro, propagar para o bloco externo
                            raise ex_commit
                        return {
                            "id": novo.id,
                            "nome": novo.nome,
                            "preco": novo.preco_venda,
                            "estoque": novo.estoque_atual,
                        }
                    except Exception as ex_create:
                        try:
                            session.rollback()
                        except Exception:
                            pass
                        print(
                            f"[DEVOLVER TROCAR] Erro ao criar Produto mínimo: {ex_create}"
                        )
        except Exception as ex_json:
            print(f"[DEVOLVER TROCAR] Falha no fallback JSON: {ex_json}")

        return None
    except Exception as e:
        print(f"[DEVOLVER TROCAR] Erro ao buscar produto: {e}")
        return None


def criar_modal_confirmacao_troca(
    page, carrinho_original, trocas_selecionadas, callback_confirmar
):
    """
    Cria modal de confirmação para a troca

    Args:
        page: Página Flet
        carrinho_original: Lista de produtos originais devolvidos
        trocas_selecionadas: Dict com produtos selecionados para trocar
        callback_confirmar: Callback quando confirmar a troca
    """

    # Criar coluna com comparação de produtos
    comparacao_column = ft.Column(spacing=12)

    for produto_original in carrinho_original:
        produto_id = produto_original["id"]
        produto_troca = trocas_selecionadas.get(produto_id)

        if produto_troca:
            # Linha com original -> novo
            linha = ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "Devolução → Troca",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color="#636E72",
                        ),
                        ft.Row(
                            [
                                # Original (esquerda)
                                ft.Container(
                                    content=ft.Column(
                                        [
                                            ft.Icon(
                                                ft.Icons.ARROW_BACK,
                                                color=DANGER_COLOR,
                                                size=16,
                                            ),
                                            ft.Text(
                                                produto_original["nome"],
                                                size=11,
                                                weight=ft.FontWeight.BOLD,
                                                color=TEXT_COLOR,
                                            ),
                                            ft.Text(
                                                f"Qtd: {produto_original['quantidade']}",
                                                size=10,
                                                color="#636E72",
                                            ),
                                        ],
                                        spacing=4,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    padding=ft.padding.all(10),
                                    bgcolor=f"{DANGER_COLOR}20",
                                    border_radius=6,
                                    expand=True,
                                ),
                                # Seta
                                ft.Icon(
                                    ft.Icons.ARROW_FORWARD, color=PRIMARY_COLOR, size=20
                                ),
                                # Novo (direita)
                                ft.Container(
                                    content=ft.Column(
                                        [
                                            ft.Icon(
                                                ft.Icons.ARROW_FORWARD,
                                                color=SUCCESS_COLOR,
                                                size=16,
                                            ),
                                            ft.Text(
                                                produto_troca["nome"],
                                                size=11,
                                                weight=ft.FontWeight.BOLD,
                                                color=TEXT_COLOR,
                                            ),
                                            ft.Text(
                                                f"R$ {produto_troca['preco']:.2f}",
                                                size=10,
                                                color=SUCCESS_COLOR,
                                            ),
                                        ],
                                        spacing=4,
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    padding=ft.padding.all(10),
                                    bgcolor=f"{SUCCESS_COLOR}20",
                                    border_radius=6,
                                    expand=True,
                                ),
                            ],
                            spacing=10,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
                padding=ft.padding.all(12),
                border=ft.border.all(1, "#DFE6E9"),
                border_radius=8,
            )
            comparacao_column.controls.append(linha)

    # Calcular totais e diferença entre original e novos (por quantidade)
    try:
        total_original = 0.0
        total_novo = 0.0
        for p in carrinho_original:
            pid = p.get("id")
            qty = int(p.get("quantidade") or 1)
            preco_orig = float(p.get("preco") or 0.0)
            total_original += preco_orig * qty
            novo = trocas_selecionadas.get(pid)
            if novo:
                total_novo += float(novo.get("preco") or 0.0) * qty

        diff = total_novo - total_original
        if diff > 0:
            diff_text = f"Cliente deve pagar R$ {diff:.2f}"
            diff_color = DANGER_COLOR
        elif diff < 0:
            diff_text = f"Trocará R$ {abs(diff):.2f} de volta ao cliente"
            diff_color = SUCCESS_COLOR
        else:
            diff_text = "Sem diferença de valor"
            diff_color = TEXT_COLOR

        resumo_totais = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                f"Total Original: R$ {total_original:.2f}",
                                size=12,
                                color=TEXT_COLOR,
                            ),
                            ft.Container(expand=True),
                            ft.Text(
                                f"Total Troca: R$ {total_novo:.2f}",
                                size=12,
                                color=TEXT_COLOR,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Row(
                        [
                            ft.Text(
                                diff_text,
                                size=13,
                                weight=ft.FontWeight.BOLD,
                                color=diff_color,
                            ),
                        ]
                    ),
                ],
                spacing=8,
            ),
            padding=ft.padding.all(10),
            border=ft.border.all(1, "#DFE6E9"),
            border_radius=6,
            bgcolor="#FFFFFF",
        )
    except Exception:
        resumo_totais = None

    # Modal de confirmação
    def on_confirmar_click(e):
        """Confirma a troca e fecha o modal"""
        print("[DEVOLVER TROCAR] Confirmando troca...")
        callback_confirmar(trocas_selecionadas)

        # Fechar modal
        try:
            if hasattr(page, "_troca_modal_ref") and page._troca_modal_ref:
                try:
                    page._troca_modal_ref.open = False
                except Exception:
                    pass
                try:
                    if getattr(page, "dialog", None) is page._troca_modal_ref:
                        try:
                            page.dialog = None
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    if page._troca_modal_ref in getattr(page, "overlay", []):
                        try:
                            page.overlay.remove(page._troca_modal_ref)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    page.app_data["caixa_last_modal_closed_ts"] = time.time()
                except Exception:
                    pass
                try:
                    page._troca_modal_ref = None
                except Exception:
                    pass
                try:
                    orig = getattr(dialog, "_original_keyboard", None)
                    if callable(orig):
                        try:
                            page.on_keyboard_event = orig
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    page.app_data["caixa_modal_open"] = False
                except Exception:
                    pass
                # limpar overlays fantasmas
                try:
                    for ov in list(getattr(page, "overlay", []) or []):
                        try:
                            if not getattr(ov, "visible", True) and not getattr(
                                ov, "open", True
                            ):
                                try:
                                    try:
                                        setattr(ov, "open", False)
                                    except Exception:
                                        pass
                                    page.overlay.remove(ov)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass
        page.update()

    def on_cancelar_click(e):
        """Cancela a troca"""
        print("[DEVOLVER TROCAR] Cancelando troca...")
        try:
            if hasattr(page, "_troca_modal_ref") and page._troca_modal_ref:
                try:
                    page._troca_modal_ref.open = False
                except Exception:
                    pass
                try:
                    if getattr(page, "dialog", None) is page._troca_modal_ref:
                        try:
                            page.dialog = None
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    if page._troca_modal_ref in getattr(page, "overlay", []):
                        try:
                            page.overlay.remove(page._troca_modal_ref)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    page.app_data["caixa_last_modal_closed_ts"] = time.time()
                except Exception:
                    pass
                try:
                    page._troca_modal_ref = None
                except Exception:
                    pass
                try:
                    orig = getattr(dialog, "_original_keyboard", None)
                    if callable(orig):
                        try:
                            page.on_keyboard_event = orig
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    page.app_data["caixa_modal_open"] = False
                except Exception:
                    pass
        except Exception:
            pass
        page.update()

    modal_content = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(
                        "Confirmar Troca",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=TEXT_COLOR,
                    ),
                    ft.Container(expand=True),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            ft.Divider(height=10, color="#DFE6E9"),
            ft.Text(
                "Revise os produtos devolvidos e os novos produtos selecionados:",
                size=12,
                color="#636E72",
            ),
            ft.Container(
                content=comparacao_column,
                height=300,
                border_radius=8,
                border=ft.border.all(1, "#DFE6E9"),
                padding=ft.padding.all(8),
            ),
            # Resumo de totais e diferença (se calculado)
            (
                resumo_totais
                if "resumo_totais" in locals() and resumo_totais is not None
                else ft.Container(height=0)
            ),
            ft.Divider(height=10, color="#DFE6E9"),
            ft.Row(
                [
                    ft.ElevatedButton(
                        text="❌ Cancelar",
                        width=150,
                        height=45,
                        on_click=on_cancelar_click,
                        style=ft.ButtonStyle(
                            bgcolor=DANGER_COLOR,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                    ft.Container(expand=True),
                    ft.ElevatedButton(
                        text="✅ Confirmar Troca",
                        width=200,
                        height=45,
                        on_click=on_confirmar_click,
                        style=ft.ButtonStyle(
                            bgcolor=SUCCESS_COLOR,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                ],
                spacing=10,
            ),
        ],
        spacing=12,
    )

    # Criar diálogo
    dialog = ft.AlertDialog(
        modal=True,
        title_padding=20,
        content_padding=20,
        inset_padding=20,
        content=ft.Container(
            content=modal_content,
            width=700,
            height=600,
        ),
    )

    # Armazenar referência na página
    page._troca_modal_ref = dialog

    # Abrir como dialog (preferir page.dialog em vez de append ao overlay)
    try:
        try:
            page.dialog = dialog
        except Exception:
            pass
        try:
            dialog.open = True
        except Exception:
            pass
        try:
            page.update()
        except Exception:
            pass
        try:
            page.app_data["caixa_modal_open"] = True
        except Exception:
            pass
    except Exception:
        pass

    # Fallback: algumas versões do Flet exibem melhor quando o AlertDialog
    # também está presente em page.overlay — adicionar somente se necessário.
    try:
        overlays_now = getattr(page, "overlay", []) or []
        has_self = any((ov is dialog for ov in overlays_now))
        if getattr(dialog, "open", False) and not has_self:
            try:
                page.overlay.append(dialog)
                page._troca_modal_ref_appended = True
                page.update()
            except Exception:
                pass
    except Exception:
        pass

    # Registrar handler local de teclado que fecha este diálogo ao pressionar ESC
    original_page_keyboard = getattr(page, "on_keyboard_event", None)

    def _troca_confirm_local_key(e):
        try:
            k = (str(e.key) or "").upper()
        except Exception:
            k = ""
        try:
            if k == "ESCAPE":
                try:
                    on_cancelar_click(e)
                except Exception:
                    pass
                try:
                    e.handled = True
                except Exception:
                    pass
                return
        except Exception:
            pass
        try:
            if callable(original_page_keyboard):
                try:
                    original_page_keyboard(e)
                except Exception:
                    pass
        except Exception:
            pass

    try:
        try:
            dialog._original_keyboard = original_page_keyboard
        except Exception:
            pass
        page.on_keyboard_event = _troca_confirm_local_key
    except Exception:
        try:
            page.on_keyboard_event = dialog
        except Exception:
            pass

    print("[DEVOLVER TROCAR] Modal de confirmação aberto")


def criar_modal_devolver_trocar(
    page: ft.Page, pdv_core, usuario_responsavel: str, callback_nova_venda
):
    """
    Cria modal para devolver e trocar produtos

    Args:
        page: Página Flet
        pdv_core: Core da aplicação
        usuario_responsavel: Username do caixa
        callback_nova_venda: Callback para iniciar nova venda

    Returns:
        Função que abre o modal existente
    """

    # Usar chave única para cada página/usuário
    cache_key = f"{id(page)}_{usuario_responsavel}"

    # Se modal já existe no cache, retornar função que abre ele
    if cache_key in _modais_cache:
        return _modais_cache[cache_key]["show_modal"]

    # Referências reutilizáveis
    dialog_ref = ft.Ref[ft.AlertDialog]()
    vendas_column = ft.Column(spacing=12, scroll="auto")
    produtos_troca_column = ft.Column(spacing=12, scroll="auto")

    # Estado para rastrear a venda selecionada
    estado = {"venda_selecionada": None, "produtos_trocados": {}}

    def criar_campo_troca(produto_original):
        """Cria um campo de troca para um produto devolvido"""
        campo_barras = ft.TextField(
            label=f"Código de barras para trocar por: {produto_original['nome']}",
            hint_text="Digite o código de barras",
            width=400,
            height=50,
            border_radius=8,
        )

        resultado = ft.Container(height=0)  # Inicialmente vazio

        def on_barras_submit(e):
            """Busca o produto quando Enter é pressionado"""
            print(
                f"[DEVOLVER TROCAR] Enter pressionado com valor: '{campo_barras.value}'"
            )

            if len(campo_barras.value) >= 1:
                produto = buscar_produto_por_barras(
                    pdv_core, campo_barras.value.strip()
                )

                if produto:
                    print(f"[DEVOLVER TROCAR] Produto encontrado: {produto['nome']}")
                    estado["produtos_trocados"][produto_original["id"]] = produto

                    # Mostrar resultado
                    # Calcular diferença por quantidade do produto original
                    try:
                        qty = int(produto_original.get("quantidade") or 1)
                        preco_orig = float(produto_original.get("preco") or 0.0)
                        preco_novo = float(produto.get("preco") or 0.0)
                        diff_total = (preco_novo - preco_orig) * qty
                        if diff_total > 0:
                            diff_text = f"Cliente deve pagar R$ {diff_total:.2f}"
                            diff_color = DANGER_COLOR
                        elif diff_total < 0:
                            diff_text = f"Devolver R$ {abs(diff_total):.2f} ao cliente"
                            diff_color = SUCCESS_COLOR
                        else:
                            diff_text = "Sem diferença de valor"
                            diff_color = TEXT_COLOR
                    except Exception:
                        diff_text = ""
                        diff_color = TEXT_COLOR

                    resultado.content = ft.Container(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Icon(
                                            ft.Icons.CHECK_CIRCLE,
                                            color=SUCCESS_COLOR,
                                            size=20,
                                        ),
                                        ft.Column(
                                            [
                                                ft.Text(
                                                    produto["nome"],
                                                    size=12,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=TEXT_COLOR,
                                                ),
                                                ft.Text(
                                                    f"R$ {produto['preco']:.2f} | Estoque: {produto['estoque']}",
                                                    size=11,
                                                    color="#636E72",
                                                ),
                                            ],
                                            spacing=2,
                                        ),
                                    ],
                                    spacing=10,
                                ),
                                ft.Container(height=6),
                                ft.Row(
                                    [
                                        ft.Container(expand=True),
                                        ft.Text(
                                            diff_text,
                                            size=12,
                                            weight=ft.FontWeight.BOLD,
                                            color=diff_color,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.END,
                                ),
                            ],
                            spacing=6,
                        ),
                        padding=ft.padding.all(10),
                        bgcolor=f"{SUCCESS_COLOR}20",
                        border_radius=8,
                    )
                    resultado.height = 80
                    print(
                        "[DEVOLVER TROCAR] Resultado do produto exibido com diferença, altura: 80"
                    )
                else:
                    print(
                        f"[DEVOLVER TROCAR] Produto NÃO encontrado para barras: {campo_barras.value}"
                    )
                    resultado.content = ft.Text(
                        "❌ Produto não encontrado",
                        color=DANGER_COLOR,
                        size=11,
                    )
                    resultado.height = 25
                    estado["produtos_trocados"].pop(produto_original["id"], None)

                page.update()
            else:
                print("[DEVOLVER TROCAR] Campo vazio, ignorando")

        campo_barras.on_submit = on_barras_submit

        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Text(
                            f"🔄 {produto_original['nome']} (Qtd: {produto_original['quantidade']})",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=TEXT_COLOR,
                        ),
                        padding=ft.padding.all(10),
                        bgcolor=CARD_BG,
                        border_radius=8,
                    ),
                    campo_barras,
                    resultado,
                ],
                spacing=8,
            ),
            padding=ft.padding.all(10),
            border=ft.border.all(1, "#DFE6E9"),
            border_radius=8,
            data={
                "id": produto_original.get("id"),
                "nome": produto_original.get("nome"),
                "preco": float(produto_original.get("preco") or 0.0),
                "quantidade": int(produto_original.get("quantidade") or 1),
            },
        )

    def atualizar_lista_vendas():
        """Atualiza a lista de vendas exibidas no modal"""
        vendas_column.controls.clear()
        estado["venda_selecionada"] = None

        # Buscar vendas do caixa
        vendas = buscar_vendas_do_caixa(pdv_core, usuario_responsavel, limite=20)

        if not vendas:
            vendas_column.controls.append(
                ft.Text(
                    "Nenhuma venda encontrada para devolver.",
                    color=DANGER_COLOR,
                    size=14,
                )
            )
            return

        for venda in vendas:

            def on_select_venda(venda_data):
                def handler(e):
                    print(f"[DEVOLVER TROCAR] Selecionada venda #{venda_data['id']}")

                    # Processar devolução
                    sucesso, mensagem, carrinho = processar_devolucao_e_trocar(
                        pdv_core, venda_data["id"], usuario_responsavel
                    )

                    if sucesso:
                        # Registrar devoluções no JSON para aparecerem na tela de Devoluções
                        try:
                            from estoque.devolucoes import (
                                registrar_devolucoes_por_venda,
                            )

                            registrado = registrar_devolucoes_por_venda(
                                pdv_core,
                                venda_data["id"],
                                motivo=f"Devolução/Troca da venda #{venda_data['id']}",
                            )
                            if not registrado:
                                print(
                                    "[DEVOLVER TROCAR] Aviso: venda preparada para troca, mas não foi possível salvar em devolucoes.json"
                                )
                        except Exception as ex_reg:
                            print(
                                f"[DEVOLVER TROCAR] Erro ao registrar devoluções JSON: {ex_reg}"
                            )

                        estado["venda_selecionada"] = venda_data["id"]
                        estado["produtos_trocados"] = {}

                        # Limpar e popular com produtos para trocar
                        produtos_troca_column.controls.clear()

                        for item in carrinho:
                            campo_troca = criar_campo_troca(
                                {
                                    "id": item["produto_id"],
                                    "nome": item["nome"],
                                    "quantidade": item["qtd"],
                                    "preco": item["preco"],
                                }
                            )
                            produtos_troca_column.controls.append(campo_troca)

                        # Mostrar painel de trocas
                        page.update()
                        print(
                            f"[DEVOLVER TROCAR] {len(carrinho)} produtos prontos para trocar"
                        )
                    else:
                        snackbar = ft.SnackBar(
                            content=ft.Text(mensagem, color="white"),
                            bgcolor=DANGER_COLOR,
                        )
                        try:
                            page.snack_bar = snackbar
                            page.snack_bar.open = True
                            page.update()
                        except Exception:
                            page.overlay.append(snackbar)
                            snackbar.open = True
                            page.update()

                return handler

            venda_card = ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            f"Venda #{venda['id']}",
                                            size=14,
                                            weight=ft.FontWeight.BOLD,
                                            color=TEXT_COLOR,
                                        ),
                                        ft.Text(
                                            venda["data"],
                                            size=12,
                                            color="#636E72",
                                        ),
                                    ],
                                    spacing=2,
                                ),
                                ft.Container(expand=True),
                                ft.Column(
                                    [
                                        ft.Text(
                                            f"R$ {venda['total']:.2f}",
                                            size=14,
                                            weight=ft.FontWeight.BOLD,
                                            color=PRIMARY_COLOR,
                                        ),
                                        ft.Text(
                                            venda["pagamento"],
                                            size=11,
                                            color="#636E72",
                                        ),
                                    ],
                                    spacing=2,
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(
                            f"Produtos: {venda['resumo']}",
                            size=11,
                            color="#636E72",
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                    spacing=4,
                ),
                padding=ft.padding.all(12),
                bgcolor=CARD_BG,
                border_radius=8,
                border=ft.border.all(1, "#DFE6E9"),
                data=venda,
            )

            # Envolver em GestureDetector para capturar cliques
            venda_row = ft.GestureDetector(
                content=venda_card,
                on_tap=on_select_venda(venda),
            )
            vendas_column.controls.append(venda_row)

    # Criar conteúdo do modal (UMA ÚNICA VEZ)
    # Painel esquerdo: Lista de vendas
    painel_vendas = ft.Column(
        [
            ft.Text(
                "Selecionar Venda",
                size=14,
                weight=ft.FontWeight.BOLD,
                color=TEXT_COLOR,
            ),
            ft.Container(
                content=vendas_column,
                height=300,
                border_radius=8,
                border=ft.border.all(1, "#DFE6E9"),
                padding=ft.padding.all(8),
                expand=True,
            ),
        ],
        spacing=8,
        expand=False,
        width=350,
    )

    # Painel direito: Produtos para trocar
    def on_confirmar_trocas_click(e):
        """Abre o modal de confirmação"""
        if estado["venda_selecionada"] and len(estado["produtos_trocados"]) > 0:
            print(
                f"[DEVOLVER TROCAR] Abrindo confirmação com {len(estado['produtos_trocados'])} trocas"
            )

            # Buscar carrinho original a partir dos containers (data) para obter preço/quantidade
            carrinho_original = []
            for item in produtos_troca_column.controls:
                try:
                    meta = getattr(item, "data", None) or {}
                    prod_id = meta.get("id")
                    if not prod_id:
                        continue
                    carrinho_original.append(
                        {
                            "id": prod_id,
                            "nome": meta.get("nome") or "",
                            "quantidade": int(meta.get("quantidade") or 1),
                            "preco": float(meta.get("preco") or 0.0),
                        }
                    )
                except Exception:
                    continue

            # Callback para confirmar
            def callback_confirmar(trocas):
                print("[DEVOLVER TROCAR] Troca confirmada!")
                # Fechar primeiro modal
                if dialog_ref.current:
                    dialog_ref.current.open = False
                page.update()

                # Marcar devoluções como trocadas e atualizar estoque
                try:
                    from estoque.devolucoes import (
                        adicionar_troca,
                        atualizar_estoque_troca,
                        carregar_devol,
                    )

                    devs = carregar_devol() or []
                    venda_id_sel = estado.get("venda_selecionada")
                    motivo_match = (
                        f"Devolução/Troca da venda #{venda_id_sel}"
                        if venda_id_sel
                        else None
                    )

                    # Mapa de quantidades por produto original
                    qtd_por_prod = {}
                    for co in carrinho_original:
                        try:
                            qtd_por_prod[int(co["id"])] = int(co["quantidade"]) or 0
                        except Exception:
                            pass

                    for prod_id_str, novo_prod in trocas.items():
                        try:
                            prod_id = int(prod_id_str)
                        except Exception:
                            # Caso a chave já seja int
                            prod_id = (
                                prod_id_str if isinstance(prod_id_str, int) else None
                            )
                        if not prod_id:
                            continue

                        # Encontrar devolução correspondente
                        dev_alvo = None
                        for d in devs:
                            try:
                                if int(d.get("produto_id") or 0) != prod_id:
                                    continue
                                if d.get("foi_trocado"):
                                    continue
                                if motivo_match and d.get("motivo") != motivo_match:
                                    continue
                                dev_alvo = d
                                break
                            except Exception:
                                continue

                        # Fallback: primeira devolução não trocada do mesmo produto
                        if dev_alvo is None:
                            for d in devs:
                                try:
                                    if int(
                                        d.get("produto_id") or 0
                                    ) == prod_id and not d.get("foi_trocado"):
                                        dev_alvo = d
                                        break
                                except Exception:
                                    continue

                        if dev_alvo:
                            try:
                                adicionar_troca(
                                    devolucao_id=int(dev_alvo.get("id")),
                                    novo_produto_id=int(novo_prod.get("id")),
                                    novo_produto_nome=str(novo_prod.get("nome")),
                                )
                            except Exception as ex_add:
                                print(
                                    f"[DEVOLVER TROCAR] Erro ao marcar troca em JSON: {ex_add}"
                                )

                            # Atualizar estoque: original +, novo -
                            try:
                                quantidade = int(qtd_por_prod.get(prod_id) or 1)
                                ok_estoque, msg_estoque = atualizar_estoque_troca(
                                    pdv_core,
                                    produto_original_id=prod_id,
                                    novo_produto_id=int(novo_prod.get("id")),
                                    quantidade=quantidade,
                                )
                                if not ok_estoque:
                                    print(
                                        f"[DEVOLVER TROCAR] Aviso estoque: {msg_estoque}"
                                    )
                            except Exception as ex_stock:
                                print(
                                    f"[DEVOLVER TROCAR] Erro ao atualizar estoque: {ex_stock}"
                                )

                except Exception as ex_all:
                    print(f"[DEVOLVER TROCAR] Erro no pós-confirmação: {ex_all}")

                # Mostrar sucesso
                try:
                    # App bar inferior informando Troca Confirmada
                    if hasattr(page, "show_bottom_status") and callable(
                        page.show_bottom_status
                    ):
                        page.show_bottom_status("Troca Confirmada", "#FFB347")
                except Exception:
                    pass
                try:
                    snackbar = ft.SnackBar(
                        content=ft.Text(
                            "✅ Troca realizada com sucesso!", color="white"
                        ),
                        bgcolor=SUCCESS_COLOR,
                        duration=3000,
                    )
                    page.snack_bar = snackbar
                    page.snack_bar.open = True
                    page.update()
                except Exception:
                    try:
                        page.overlay.append(snackbar)
                        snackbar.open = True
                        page.update()
                    except Exception:
                        pass

            # Abrir modal de confirmação
            criar_modal_confirmacao_troca(
                page, carrinho_original, estado["produtos_trocados"], callback_confirmar
            )
        else:
            # Mostrar erro
            snackbar = ft.SnackBar(
                content=ft.Text(
                    "❌ Selecione todos os produtos para trocar!", color="white"
                ),
                bgcolor=DANGER_COLOR,
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

    painel_trocas = ft.Column(
        [
            ft.Text(
                "Produtos para Trocar",
                size=14,
                weight=ft.FontWeight.BOLD,
                color=TEXT_COLOR,
            ),
            ft.Container(
                content=produtos_troca_column,
                height=300,
                border_radius=8,
                border=ft.border.all(1, "#DFE6E9"),
                padding=ft.padding.all(8),
                expand=True,
            ),
            ft.ElevatedButton(
                text="✅ Confirmar Troca",
                width=250,
                height=45,
                on_click=on_confirmar_trocas_click,
                style=ft.ButtonStyle(
                    bgcolor=SUCCESS_COLOR,
                    color=ft.Colors.WHITE,
                ),
            ),
        ],
        spacing=8,
        expand=True,
    )

    # Layout em duas colunas
    modal_content = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(
                        "Troca de Produtos",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=TEXT_COLOR,
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        ft.Icons.CLOSE,
                        icon_color=TEXT_COLOR,
                        on_click=lambda e: _close_modal(dialog_ref, page),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Divider(height=10, color="#DFE6E9"),
            ft.Row(
                [
                    painel_vendas,
                    ft.VerticalDivider(width=1, color="#DFE6E9"),
                    painel_trocas,
                ],
                spacing=10,
                expand=True,
            ),
        ],
        spacing=12,
    )

    # Criar dialog (UMA ÚNICA VEZ)
    dialog_ref.current = ft.AlertDialog(
        modal=True,
        title_padding=20,
        content_padding=20,
        inset_padding=20,
        content=ft.Container(
            content=modal_content,
            width=900,
            height=500,
        ),
    )

    def show_modal():
        """Abre o modal (reutilizável)"""
        print("[DEVOLVER TROCAR] Abrindo modal de devoluções...")
        try:
            print(
                f"[DEVOLVER TROCAR] created/loaded dialog_ref.current type={type(dialog_ref.current).__name__ if dialog_ref.current else None}"
            )
        except Exception:
            pass

        # Atualizar lista de vendas
        atualizar_lista_vendas()

        # Limpar trocas anteriores
        produtos_troca_column.controls.clear()
        estado["venda_selecionada"] = None

        # sinalizar que um modal do caixa está aberto (para handlers globais)
        try:
            # abrir como dialog (preferir page.dialog em vez de append ao overlay)
            try:
                page.dialog = dialog_ref.current
                print("[DEVOLVER TROCAR] page.dialog assigned")
            except Exception as ex:
                print(f"[DEVOLVER TROCAR] error assigning page.dialog: {ex}")
            try:
                dialog_ref.current.open = True
                print("[DEVOLVER TROCAR] dialog_ref.current.open = True")
            except Exception as ex:
                print(f"[DEVOLVER TROCAR] error setting open=True: {ex}")
            try:
                page.update()
                print("[DEVOLVER TROCAR] page.update() called")
            except Exception as ex:
                print(f"[DEVOLVER TROCAR] page.update error: {ex}")
            try:
                page.app_data["caixa_modal_open"] = True
                print("[DEVOLVER TROCAR] caixa_modal_open set True")
            except Exception as ex:
                print(f"[DEVOLVER TROCAR] error setting caixa_modal_open: {ex}")
        except Exception as ex:
            print(f"[DEVOLVER TROCAR] unexpected error opening dialog: {ex}")

        # Fallback: append ao overlay somente se necessário
        try:
            overlays_now = getattr(page, "overlay", []) or []
            has_self = any((ov is dialog_ref.current for ov in overlays_now))
            if getattr(dialog_ref.current, "open", False) and not has_self:
                try:
                    page.overlay.append(dialog_ref.current)
                    page._troca_modal_ref_appended = True
                    page.update()
                except Exception:
                    pass
        except Exception:
            pass

        # Debug: listar overlays atuais e estado do page.dialog
        try:
            overlays_now = getattr(page, "overlay", []) or []
            for i, ov in enumerate(overlays_now):
                try:
                    print(
                        f"[DEVOLVER TROCAR] overlay[{i}] type={type(ov).__name__} visible={getattr(ov, 'visible', None)} open={getattr(ov, 'open', None)} bgcolor={getattr(ov, 'bgcolor', None)}"
                    )
                except Exception:
                    pass
        except Exception:
            pass
        try:
            dlg = getattr(page, "dialog", None)
            print(
                f"[DEVOLVER TROCAR] page.dialog now: {type(dlg).__name__ if dlg else None} open={getattr(dlg, 'open', None)}"
            )
        except Exception:
            pass

        # Registrar handler local de teclado que fecha este diálogo ao pressionar ESC
        original_page_keyboard = getattr(page, "on_keyboard_event", None)

        def _troca_local_key(e):
            try:
                k = (str(e.key) or "").upper()
            except Exception:
                k = ""
            try:
                if k == "ESCAPE":
                    try:
                        _close_modal_safe()
                    except Exception:
                        pass
                    try:
                        e.handled = True
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            try:
                if callable(original_page_keyboard):
                    try:
                        original_page_keyboard(e)
                    except Exception:
                        pass
            except Exception:
                pass

        try:
            try:
                dialog_ref._original_keyboard = original_page_keyboard
            except Exception:
                pass
            page.on_keyboard_event = _troca_local_key
        except Exception:
            try:
                page.on_keyboard_event = dialog_ref.current
            except Exception:
                pass

        page.update()
        print("[DEVOLVER TROCAR] Modal aberto com sucesso")

    # fechar seguro: remove do overlay, marca closed timestamp e restaura handler
    def _close_modal_safe():
        try:
            dlg = dialog_ref.current

            # fechar o diálogo principal
            if dlg:
                try:
                    dlg.open = False
                except Exception:
                    pass

            # remover do overlay se presente
            try:
                if dlg in getattr(page, "overlay", []):
                    try:
                        page.overlay.remove(dlg)
                    except Exception:
                        pass
            except Exception:
                pass

            # limpar page.dialog se for este
            try:
                if getattr(page, "dialog", None) is dlg:
                    try:
                        page.dialog = None
                    except Exception:
                        pass
            except Exception:
                pass

            # timestamps / flags
            try:
                page.app_data["caixa_last_modal_closed_ts"] = time.time()
            except Exception:
                pass
            try:
                page.app_data["caixa_modal_open"] = False
            except Exception:
                pass

            # limpeza agressiva de overlays fechados ou camadas dim
            try:
                overlays = list(getattr(page, "overlay", []) or [])
                for ov in overlays:
                    try:
                        open_flag = getattr(ov, "open", None)
                        vis = getattr(ov, "visible", None)
                        bgcolor = getattr(ov, "bgcolor", None)
                        if (
                            (open_flag is False)
                            or (vis is False)
                            or (isinstance(bgcolor, str) and "rgba" in bgcolor.lower())
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

            # restaurar handler original caso tenhamos salvo
            try:
                orig = getattr(dialog_ref, "_original_keyboard", None)
                if callable(orig):
                    try:
                        page.on_keyboard_event = orig
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                page.update()
            except Exception:
                pass
            try:
                # garantir que o dialog_ref seja removido da página
                try:
                    if getattr(page, "dialog", None) is dlg:
                        page.dialog = None
                except Exception:
                    pass

                # pausa curta e update extra para forçar redraw e evitar artefatos
                try:
                    try:
                        page.sleep(80)
                    except Exception:
                        import time

                        time.sleep(0.08)
                except Exception:
                    pass
                try:
                    page.update()
                except Exception:
                    pass

            except Exception:
                pass

            print("[DEVOLVER TROCAR] Modal fechado (safe)")
        except Exception:
            pass

    # Armazenar no cache
    _modais_cache[cache_key] = {"show_modal": show_modal, "dialog_ref": dialog_ref}

    return show_modal


def _close_modal(dialog_ref, page):
    """Fecha o modal"""
    if dialog_ref.current:
        dialog_ref.current.open = False
        page.update()
        print("[DEVOLVER TROCAR] Modal fechado")


def criar_botao_devolver_trocar(
    page: ft.Page,
    pdv_core,
    usuario_responsavel: str,
    callback_nova_venda,
    colors: dict = None,
):
    """
    Cria botão "Devolver & Trocar" para a tela do Caixa

    Args:
        page: Página Flet
        pdv_core: Core da aplicação
        usuario_responsavel: Username do caixa
        callback_nova_venda: Callback para iniciar nova venda
        colors: Dicionário customizado de cores

    Returns:
        Botão ft.ElevatedButton
    """
    if colors is None:
        colors = {
            "warning": "#FDCB6E",
            "text": "#2D3748",
            "text_light": "#FFF",
        }

    modal_function = criar_modal_devolver_trocar(
        page, pdv_core, usuario_responsavel, callback_nova_venda
    )

    def on_button_click(e):
        """Handler para clique no botão Devolver & Trocar"""
        try:
            print("[DEVOLVER TROCAR] Botão clicado")
            modal_function()
            print("[DEVOLVER TROCAR] Modal chamado com sucesso")
        except Exception as ex:
            print(f"[DEVOLVER TROCAR] ❌ Erro ao abrir modal: {ex}")
            import traceback

            traceback.print_exc()

    botao = ft.Container(
        ft.ElevatedButton(
            "(F7) TROCA",
            icon=ft.Icons.SWAP_HORIZ,
            bgcolor=colors.get("card_bg", ft.Colors.WHITE),
            on_click=on_button_click,
        ),
        shadow=ft.BoxShadow(
            blur_radius=8,
            spread_radius=2,
            color="#007BFF",
            offset=ft.Offset(2, 2),
        ),
    )

    # Expor atributo on_click no container para compatibilidade com handlers
    try:
        setattr(botao, "on_click", on_button_click)
    except Exception:
        pass

    return botao
