"""View do Caixa: registra vendas, controla carrinho e pagamentos.

- Faz leitura de produtos via código de barras (cache em memória).

"""

import io
import json
import os
import re
import threading
import time

import flet as ft

from utils.cupom import show_cupom_dialog

from .components import create_cart_item_row as create_cart_item_row_ext
from .components import create_payment_panel as create_payment_panel_ext
from .devolver_trocar_ui import criar_botao_devolver_trocar
from .dialogs import (
    create_cancel_sale_dialog,
    create_pix_overlay,
    create_price_check_overlay,
)
from .finalize import finalize_transaction as finalize_transaction_impl
from .helpers import log_overlay_event as log_overlay_event_helper
from .helpers import make_monitor_dark_masks, run_clock_task
from .helpers import show_snackbar as show_snackbar_helper
from .logic import (
    calcular_troco,
    montar_itens_cupom,
    montar_payload_pix,
    persistir_estoque_json,
    validar_estoque_disponivel,
)
from .manipuladores import build_caixa_keyboard_handler
from .repository import carregar_produtos_cache as carregar_produtos_cache_repo
from .state import COLORS, FKEY_MAP, PAYMENT_METHODS


def create_caixa_view(
    page: ft.Page,
    pdv_core,
    handle_back,
    handle_logout=None,
    current_user=None,
    appbar: ft.AppBar = None,
):
    """Monta e retorna a View do Caixa.

    - `page`: instância principal do Flet.
    - `pdv_core`: objeto de regra de negócio (vendas, estoque em banco).
    - `handle_back`: callback para voltar à tela anterior.
    - `handle_logout`: função para fazer logout (ESC).
    - `current_user`: usuário logado (pode ser usado para permissões).
    - `appbar`: barra de topo compartilhada entre views.
    """
    # ✅ Handlers de teclado serão registrados após a View ser criada

    # Cache em memória de produtos; índice por id e código de barras
    produtos_cache = {}
    # Detectar se o usuário atual é o operador "user_caixa"
    is_user_caixa = False
    try:
        uname = None
        # current_user pode ser um objeto ou apenas o nome para exibição
        if current_user:
            uname = getattr(current_user, "username", None) or getattr(
                current_user, "user", None
            )
            # Se for string de exibição, usar sessão para obter o username real
            if uname is None and isinstance(current_user, str):
                uname = page.session.get("user_username")
        else:
            uname = page.session.get("user_username")

        is_user_caixa = bool(str(uname or "").lower() in ("user_caixa", "caixa"))
    except Exception:
        is_user_caixa = False

    # Usar um sentinel object em vez de bool, pois ft.Ref não aceita tipos primitivos
    class _CacheMarker:
        pass

    cache_marker = _CacheMarker()
    cache_loaded = ft.Ref[object]()
    cache_loaded.current = None
    # Coluna que renderiza visualmente os itens do carrinho
    cart_items_column = ft.Column(spacing=1, expand=True, scroll="auto")

    # Helper: limpar overlays fantasmas ou de fundo (dim) deixados por dialogs
    def _cleanup_overlays():
        try:
            try:
                cancel_sale_overlay = getattr(page, "_cancel_sale_overlay", None)
                print(
                    f"[F6-OPEN] open_cancel_sale_dialog called: has_overlay={bool(cancel_sale_overlay)} open={getattr(cancel_sale_overlay, 'open', None)} dialog={type(getattr(page, 'dialog', None)).__name__ if getattr(page, 'dialog', None) else None} overlays_count={len(getattr(page, 'overlay', []) or [])}"
                )
            except Exception:
                pass
        except Exception:
            pass
            overlays = list(getattr(page, "overlay", []) or [])
            for ov in overlays:
                try:
                    # remover overlays explicitamente fechados
                    if (not getattr(ov, "visible", True)) or (
                        not getattr(ov, "open", True)
                    ):
                        try:
                            setattr(ov, "open", False)
                        except Exception:
                            pass
                        try:
                            if ov in getattr(page, "overlay", []):
                                page.overlay.remove(ov)
                                _log_overlay_event("cleanup", ov)
                        except Exception:
                            pass
                        continue
                    # heurística: containers com bgcolor 'rgba' são camadas de dim — remover se presentes
                    try:
                        bg = getattr(ov, "bgcolor", None)
                        if isinstance(bg, str) and "rgba" in bg.lower():
                            try:
                                if ov in getattr(page, "overlay", []):
                                    page.overlay.remove(ov)
                                    _log_overlay_event("cleanup_rgba", ov)
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

    # Helper central para fechar e remover um overlay/backdrop
    def _close_and_remove_overlay(ov, page_attr_name: str = None):
        try:
            if ov is None:
                return
            try:
                # esconder visualmente
                if getattr(ov, "visible", None) is not None:
                    try:
                        ov.visible = False
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                # garantir atributo 'open' para compatibilidade com handlers
                try:
                    setattr(ov, "open", False)
                except Exception:
                    pass
            except Exception:
                pass
            try:
                if ov in getattr(page, "overlay", []):
                    try:
                        page.overlay.remove(ov)
                        _log_overlay_event("removed", ov)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                # limpar referência guardada na página, se solicitado
                if page_attr_name and hasattr(page, page_attr_name):
                    try:
                        setattr(page, page_attr_name, None)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                page.app_data["caixa_last_modal_closed_ts"] = time.time()
            except Exception:
                pass
            try:
                page.app_data["caixa_modal_open"] = False
            except Exception:
                pass
        except Exception:
            pass
        try:
            page.update()

            # Pequena pausa e atualização extra para garantir redraw completo
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

    # Placeholder para funções que serão reexportadas por _actions
    reset_cart = lambda: None

    # Total acumulado da venda atual — usar wrapper numérico para compatibilidade
    class NumberBox:
        def __init__(self, v=0.0):
            self.v = float(v)

        def set(self, v):
            self.v = float(v)

        def get(self):
            return self.v

        def __iadd__(self, other):
            self.v += float(other)
            return self

        def __isub__(self, other):
            self.v -= float(other)
            return self

        def __add__(self, other):
            return self.v + other

        def __radd__(self, other):
            return other + self.v

        def __sub__(self, other):
            return self.v - other

        def __float__(self):
            return float(self.v)

        def __int__(self):
            return int(self.v)

        def __repr__(self):
            return repr(self.v)

        def __str__(self):
            return str(self.v)

        def __lt__(self, other):
            return self.v < other

        def __le__(self, other):
            return self.v <= other

        def __gt__(self, other):
            return self.v > other

        def __ge__(self, other):
            return self.v >= other

        def __eq__(self, other):
            return self.v == other

    total_value = ft.Ref[object]()
    total_value.current = NumberBox(0.0)

    class ValueBox:
        def __init__(self, value=None):
            self.value = value

    # Textos exibidos na barra inferior (subtotal, acréscimo e total)
    subtotal_text = ft.Text(
        "R$ 0,00", size=20, weight="bold", color=COLORS["text_dark"], visible=False
    )
    # refs para os labels (para poder ocultar a label inteira)
    subtotal_label_ref = ft.Ref[ft.Text]()
    # acrescimo_text left for compatibility but not shown separately
    acrescimo_text = ft.Text(
        "R$ 0,00", size=20, weight="bold", color=COLORS["text_dark"], visible=False
    )
    acrescimo_label_ref = ft.Ref[ft.Text]()
    total_final_text = ft.Text(
        "R$ 0,00", size=36, weight="bold", color=COLORS["secondary"]
    )
    # Campo de busca por código de barras e texto com nome/estoque do último produto
    search_field_ref = ft.Ref[ft.TextField]()
    product_name_text = ft.Text("", size=16, color=COLORS["primary"])

    # leitura por câmera removida — operação mantida apenas por código de barras

    # Carrega produtos para o cache a partir do JSON e/ou banco (pdv_core)
    def carregar_produtos_cache(force_reload: bool = False) -> bool:
        return carregar_produtos_cache_repo(
            page=page,
            pdv_core=pdv_core,
            produtos_cache=produtos_cache,
            cache_loaded_ref=cache_loaded,
            cache_marker=cache_marker,
            force_reload=force_reload,
        )

    # Estado de pagamento e referências a campos de valor recebido/troco
    selected_payment_type = ft.Ref[object]()
    selected_payment_type.current = ValueBox(None)
    money_received_field = ft.Ref[ft.TextField]()
    change_text = ft.Ref[ft.Text]()
    # seleção de parcelas (1 por padrão, 2 quando mini-botão ativo)
    parcel_selected_ref = ft.Ref[int]()
    parcel_selected_ref.current = 1
    # Aviso na appbar se tentar finalizar sem selecionar pagamento
    appbar_notice_active = ValueBox(False)
    appbar_orig = {"title": None, "bg": None}

    # Se um `appbar` compartilhado foi passado, sobrescrever o botão de voltar
    # para fechar modais/overlays desta view antes de delegar a navegação.
    if appbar is not None:

        def _local_caixa_back(e: ft.ControlEvent):
            try:
                # Fecha overlays específicos desta view, do mais recente para o mais antigo
                try:
                    overlays = list(getattr(page, "overlay", []) or [])
                    for ov in reversed(overlays):
                        try:
                            if getattr(ov, "open", False) or getattr(
                                ov, "visible", False
                            ):
                                _close_and_remove_overlay(ov)
                                try:
                                    e.handled = True
                                except Exception:
                                    pass
                                return
                        except Exception:
                            pass
                except Exception:
                    pass

                # Fechar AlertDialog padrão se aberto
                try:
                    if getattr(page, "dialog", None) is not None and getattr(
                        page.dialog, "open", False
                    ):
                        try:
                            page.dialog.open = False
                        except Exception:
                            pass
                        try:
                            e.handled = True
                        except Exception:
                            pass
                        page.update()
                        return
                except Exception:
                    pass

                # Nada fechado: delega para callback original
                try:
                    if callable(handle_back):
                        handle_back(e)
                    else:
                        try:
                            handle_back(None)
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception:
                pass

        try:
            # Remover seta de voltar no AppBar para a tela do Caixa
            appbar.leading = None
        except Exception:
            pass

    # Expor ref do appbar para permitir atualizações dinâmicas (ex.: título do PDV)
    try:
        caixa_appbar_ref = ft.Ref()
        caixa_appbar_ref.current = appbar
        page.app_data["caixa_appbar_ref"] = caixa_appbar_ref
    except Exception:
        pass

    def notify_missing_payment():
        try:
            # Não alterar o appbar; apenas mostrar feedback via snackbar
            show_snackbar(
                "Escolha uma forma de pagamento antes de finalizar.", COLORS["warning"]
            )
        except Exception:
            pass

    # Estrutura em memória do carrinho (key = código do produto)
    cart_data = {}
    # último produto adicionado (usar ValueBox simples em vez de ft.Ref para evitar weakref em primitives)
    last_added_product_id_box = ValueBox(None)
    payment_buttons_refs: list[ft.Ref] = []
    # Lista de pagamentos já efetuados nesta venda (cada item: {method, amount})
    payments: list = []
    # Flag para evitar finalização múltipla em sequência
    is_finalizing_box = ValueBox(False)

    # Diálogos auxiliares para F6 (consulta) e F7 (cancelamento)
    price_check_dialog_ref = ft.Ref[ft.AlertDialog]()
    cancel_sale_dialog_ref = ft.Ref[ft.AlertDialog]()
    # Debounce para evitar múltiplos ESC gerando muitos dialogs
    # Usar um wrapper (NumberBox) porque ft.Ref não aceita tipos primitivos
    last_esc_ts = ft.Ref[object]()
    last_esc_ts.current = NumberBox(0.0)

    # Helper para exibir mensagens rápidas na parte inferior da tela
    def show_snackbar(message, color):
        try:
            show_snackbar_helper(page, message, color)
        except Exception:
            # Fallback local caso helpers falhe por algum motivo
            page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=color, duration=2000)
            page.snack_bar.open = True
            page.update()

    # Barra de status inferior (mensagem temporária)
    status_bar_ref = ft.Ref[ft.Container]()

    def _hide_status_bar():
        try:
            if status_bar_ref.current:
                status_bar_ref.current.height = 0
                status_bar_ref.current.content = None
                status_bar_ref.current.bgcolor = None
                page.update()
        except Exception:
            pass

    def show_bottom_status(message: str, bgcolor: str):
        try:
            if not status_bar_ref.current:
                status_bar_ref.current = ft.Container(height=0)
            status_bar_ref.current.content = ft.Row(
                [
                    ft.Text(
                        message,
                        size=14,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            )
            status_bar_ref.current.bgcolor = bgcolor
            status_bar_ref.current.padding = ft.padding.symmetric(
                horizontal=20, vertical=8
            )
            status_bar_ref.current.height = 40
            page.update()
            # Ocultar automaticamente após 3 segundos
            try:
                threading.Timer(3.0, _hide_status_bar).start()
            except Exception:
                pass
        except Exception:
            pass

    # Expor helper para outras partes (ex.: troca)
    try:
        page.show_bottom_status = show_bottom_status
    except Exception:
        pass

    def show_welcome_bar(message: str, duration: int = 6):
        """Exibe uma appbar inferior verde com a mensagem de boas‑vindas."""
        try:
            if not status_bar_ref.current:
                status_bar_ref.current = ft.Container(height=0)
            status_bar_ref.current.content = ft.Row(
                [
                    ft.Text(
                        message,
                        size=14,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.WHITE,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            )
            # usar cor verde consistente e preencher largura
            status_bar_ref.current.bgcolor = COLORS.get("green", "#28A745")
            status_bar_ref.current.padding = ft.padding.symmetric(
                horizontal=8, vertical=10
            )
            status_bar_ref.current.height = 48
            try:
                page.update()
            except Exception:
                pass

            # esconder após duration segundos
            try:
                threading.Timer(duration, _hide_status_bar).start()
            except Exception:
                pass
        except Exception:
            pass

    try:
        page.show_welcome_bar = show_welcome_bar
    except Exception:
        pass

    # Se existe uma mensagem pendente vinda da tela de login, exibi-la agora
    try:
        pending = None
        try:
            pending = page.app_data.pop("caixa_pending_welcome", None)
            page.app_data.pop("caixa_pending_welcome_ts", None)
        except Exception:
            pending = None
        # Debug: log do processamento da pending
        try:
            print(f"[CAIXA-WELCOME] pending -> {repr(pending)}")
        except Exception:
            pass
        if pending:
            # Agendar exibição com retries até o ref estar disponível
            async def _delayed_show():
                try:
                    for _ in range(10):
                        try:
                            if status_bar_ref.current:
                                try:
                                    # preferir método estilizado se disponível
                                    try:
                                        if hasattr(
                                            page, "show_welcome_bar"
                                        ) and callable(page.show_welcome_bar):
                                            page.show_welcome_bar(
                                                f"Bem-vindo(a) - {pending}", duration=6
                                            )
                                        else:
                                            show_bottom_status(
                                                f"Bem-vindo(a) - {pending}",
                                                COLORS["green"],
                                            )
                                        return
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        try:
                            await page.sleep(0.05)
                        except Exception:
                            break
                    # fallback: usar snack_bar
                    try:
                        page.snack_bar = ft.SnackBar(
                            ft.Text(f"Bem-vindo, {pending}"), bgcolor=COLORS["green"]
                        )
                        page.snack_bar.open = True
                        page.update()
                    except Exception:
                        pass
                except Exception:
                    pass

            try:
                page.run_task(_delayed_show)
            except Exception:
                try:
                    # immediate fallback
                    show_bottom_status(f"Bem-vindo, {pending}", COLORS["green"])
                except Exception:
                    try:
                        page.snack_bar = ft.SnackBar(
                            ft.Text(f"Bem-vindo, {pending}"), bgcolor=COLORS["green"]
                        )
                        page.snack_bar.open = True
                        page.update()
                    except Exception:
                        pass
    except Exception:
        pass

    # Helper de tracing para overlays (imprime timestamp + stack reduzida)
    def _log_overlay_event(action, overlay):
        try:
            log_overlay_event_helper(action, overlay)
        except Exception:
            # Fallback simples em caso de erro
            print(f"[OVERLAY-TRACE] {action} overlay={type(overlay).__name__}")

    # ==========================
    # F6 - CONSULTA DE PREÇO
    # ==========================

    # Abre diálogo de "Consulta de Preço" (atalho F6)
    def open_price_check_dialog(e=None):
        if not cache_loaded.current:
            if not carregar_produtos_cache(force_reload=True):
                show_snackbar(
                    "Nenhum produto cadastrado para consulta.", COLORS["danger"]
                )
                return

        # Faz a busca de preço/estoque a partir de um código de barras
        def do_price_lookup(code: str):
            codigo = (code or "").strip()
            if not codigo:
                show_snackbar("Informe um código.", COLORS["warning"])
                return

            produto = produtos_cache.get(codigo)
            if not produto:
                # Bip de erro: dois tons graves curtos consecutivos
                try:
                    from utils.beep import error_beep

                    try:
                        print("[BEEP] Chamando error_beep() (price check)")
                        error_beep()
                        print("[BEEP] error_beep() retornou (price check)")
                    except Exception as _be:
                        print(f"[BEEP] error_beep() gerou exceção: {_be}")
                except Exception:
                    try:
                        print("\a\a", end="")
                    except Exception:
                        pass
                ov_res = getattr(price_check_overlay, "__result_text__", None)
                if ov_res:
                    ov_res.value = "Produto não encontrado."
                    ov_res.color = COLORS["danger"]
                page.update()
                return

            if isinstance(produto, dict):
                nome = produto.get("nome", "")
                preco = float(produto.get("preco_venda", 0.0))
                estoque = int(produto.get("quantidade", 0))
            else:
                nome = getattr(produto, "nome", "")
                preco = float(getattr(produto, "preco_venda", 0.0))
                estoque = int(getattr(produto, "estoque_atual", 0))

            # Fallback: se estoque vier 0 (ex.: objeto do banco sem sincronizar),
            # tentar obter a quantidade real do JSON que alimenta a tela de Estoque.
            try:
                if estoque <= 0:
                    base_dir = os.path.dirname(os.path.dirname(__file__))
                    arquivo = os.path.join(base_dir, "data", "produtos.json")
                    if os.path.exists(arquivo):
                        with open(arquivo, "r", encoding="utf-8") as f:
                            dados_json = json.load(f)
                        for pj in dados_json:
                            cod_json = str(
                                pj.get("codigo_barras") or pj.get("codigo") or ""
                            ).strip()
                            if cod_json == codigo:
                                estoque_json = int(pj.get("quantidade", 0))
                                if estoque_json > 0:
                                    estoque = estoque_json
                                break
            except Exception:
                pass

            ov_res = getattr(price_check_overlay, "__result_text__", None)
            if ov_res:
                ov_res.value = f"{nome} — R$ {preco:.2f} — Estoque: {estoque}"
                ov_res.color = COLORS["primary"] if estoque > 0 else COLORS["danger"]
            page.update()

        def close_price_check_dialog(e=None):
            try:
                try:
                    if e is not None:
                        try:
                            e.handled = True
                        except Exception:
                            pass
                except Exception:
                    pass
                pc = getattr(page, "_price_check_overlay", None)
                if pc and pc in getattr(page, "overlay", []):
                    try:
                        try:
                            pc.visible = False
                        except Exception:
                            pass
                        try:
                            setattr(pc, "open", False)
                        except Exception:
                            pass
                        try:
                            page.overlay.remove(pc)
                        except Exception:
                            pass
                    except Exception:
                        pass
                # limpar overlays fantasmas (visíveis False / open False)
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
            try:
                page.app_data["caixa_last_modal_closed_ts"] = time.time()
            except Exception:
                pass
            # limpar referência para permitir recriação futura
            try:
                if hasattr(page, "_price_check_overlay"):
                    page._price_check_overlay = None
            except Exception:
                pass
            try:
                page.app_data["caixa_modal_open"] = False
            except Exception:
                pass
            page.update()

        # Reuse a single price_check_overlay instance to avoid acúmulo de overlays
        if (
            not hasattr(page, "_price_check_overlay")
            or page._price_check_overlay is None
        ):
            try:
                page._price_check_overlay = create_price_check_overlay(
                    COLORS,
                    on_lookup=do_price_lookup,
                    on_close=lambda: close_price_check_dialog(),
                )
            except Exception:
                # fallback: tentar criar novamente diretamente
                page._price_check_overlay = create_price_check_overlay(
                    COLORS,
                    on_lookup=do_price_lookup,
                    on_close=lambda: close_price_check_dialog(),
                )
        price_check_overlay = page._price_check_overlay

        if price_check_overlay not in page.overlay:
            _log_overlay_event("append", price_check_overlay)
            print(
                f"[OVERLAY] Adding price_check_overlay type={type(price_check_overlay).__name__} bgcolor={getattr(price_check_overlay, 'bgcolor', None)} expand={getattr(price_check_overlay, 'expand', None)} visible={getattr(price_check_overlay, 'visible', None)}"
            )
            # Tornar visível ao adicionar para exibir imediatamente
            try:
                price_check_overlay.visible = True
            except Exception:
                pass
            try:
                # Alguns overlays (Container) não expõem 'open'; marcar para
                # que o manipulador de ESC os reconheça como abertos.
                try:
                    setattr(price_check_overlay, "open", True)
                except Exception:
                    pass
            except Exception:
                pass
            try:
                page.app_data["caixa_modal_open"] = True
            except Exception:
                pass
            page.overlay.append(price_check_overlay)
            print(
                f"[OVERLAY] Added price_check_overlay overlays_count={len(getattr(page, 'overlay', []))}"
            )
        page.update()

    # =====================================
    # F7 - CANCELAR VENDA FINALIZADA (GERENTE)
    # =====================================

    # Abre diálogo de "Cancelar venda finalizada" (atalho F7, só gerente)
    def open_cancel_sale_dialog(e=None):
        """Abre o diálogo de cancelamento (F7) com lista de vendas do dia.

        O gerente apenas informa a senha; o usuário logado já vem preenchido
        e desabilitado, e a venda é escolhida em uma lista em vez de digitar ID.
        """

        from datetime import datetime, time

        hoje = datetime.now().date()
        inicio = datetime.combine(hoje, time.min)
        fim = datetime.combine(hoje, time.max)

        # Busca vendas do dia pelo core; se não houver método, cai para lista vazia
        vendas_dia = []
        if hasattr(pdv_core, "buscar_vendas_por_intervalo"):
            try:
                vendas_dia = pdv_core.buscar_vendas_por_intervalo(inicio, fim)
            except Exception as ex:
                print(f"Erro ao buscar vendas do dia para F7: {ex}")

        if not vendas_dia:
            show_snackbar("Nenhuma venda encontrada para hoje.", COLORS["warning"])
            return

        # Carrega produtos do JSON para detalhar itens (nome, preço, id)
        produtos_por_codigo = {}
        try:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            arquivo = os.path.join(base_dir, "data", "produtos.json")
            if os.path.exists(arquivo):
                with open(arquivo, "r", encoding="utf-8") as f:
                    dados_json = json.load(f)
                for pj in dados_json:
                    cod = str(pj.get("codigo_barras") or pj.get("codigo") or "").strip()
                    if not cod:
                        continue
                    produtos_por_codigo[cod] = pj
        except Exception as ex:
            print(f"[F7] Erro ao carregar produtos.json para detalhes da venda: {ex}")

        def close_cancel_sale_dialog(e=None):
            try:
                pass
                try:
                    if e is not None:
                        try:
                            e.handled = True
                        except Exception:
                            pass
                except Exception:
                    pass
                # Fechar o diálogo preferencialmente via o objeto atualmente
                # atribuído em page.dialog. Garantir que qualquer fallback
                # appended em page.overlay seja removido para evitar tela cinza.
                try:
                    dlg = getattr(page, "dialog", None)
                    if dlg is cancel_sale_overlay:
                        try:
                            dlg.open = False
                        except Exception:
                            pass
                        try:
                            page.dialog = None
                        except Exception:
                            pass
                        try:
                            # garantir que também desligamos a visibilidade e removemos de overlays
                            try:
                                cancel_sale_overlay.visible = False
                            except Exception:
                                pass
                            if cancel_sale_overlay in getattr(page, "overlay", []):
                                try:
                                    page.overlay.remove(cancel_sale_overlay)
                                except Exception:
                                    pass
                                pass
                        except Exception:
                            pass
                    else:
                        try:
                            if cancel_sale_overlay:
                                try:
                                    cancel_sale_overlay.open = False
                                except Exception:
                                    pass
                                try:
                                    cancel_sale_overlay.visible = False
                                except Exception:
                                    pass
                                pass
                                try:
                                    if cancel_sale_overlay in getattr(
                                        page, "overlay", []
                                    ):
                                        page.overlay.remove(cancel_sale_overlay)
                                        pass
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
                # restaurar handler de teclado anterior se tivermos salvo um
                try:
                    if callable(original_page_keyboard):
                        try:
                            page.on_keyboard_event = original_page_keyboard
                        except Exception:
                            pass
                except Exception:
                    pass
                # limpar flag preventiva
                try:
                    page.app_data["caixa_prevent_handle_back"] = False
                except Exception:
                    pass
                # limpeza adicional: remover overlays fantasmas/dim
                try:
                    _cleanup_overlays()
                except Exception:
                    pass
                try:
                    cancel_sale_dialog_ref.current = None
                except Exception:
                    pass
                try:
                    page.app_data["caixa_modal_open"] = False
                except Exception:
                    pass
                try:
                    page.app_data["caixa_last_modal_closed_ts"] = time.time()
                except Exception:
                    pass
                # Remoção extra: garantir que não restem overlays semi-transparente (artefatos)
                try:
                    overlays_now = list(getattr(page, "overlay", []) or [])
                    for ov in overlays_now:
                        try:
                            bg = getattr(ov, "bgcolor", None)
                            if isinstance(bg, str) and "rgba" in bg.lower():
                                try:
                                    if ov in getattr(page, "overlay", []):
                                        page.overlay.remove(ov)
                                        _log_overlay_event("cleanup_rgba_postclose", ov)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
                # Forçar remoção de overlays residuais (mais agressivo) para evitar artefatos
                try:
                    overlays_now = list(getattr(page, "overlay", []) or [])
                    for ov in overlays_now:
                        try:
                            # pular o overlay que estamos fechando (já tratado acima)
                            if ov is cancel_sale_overlay:
                                continue
                            try:
                                if getattr(ov, "visible", None) is not None:
                                    ov.visible = False
                            except Exception:
                                pass
                            try:
                                setattr(ov, "open", False)
                            except Exception:
                                pass
                            try:
                                if ov in getattr(page, "overlay", []):
                                    page.overlay.remove(ov)
                                    _log_overlay_event("force_remove_overlay", ov)
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    # garantir page.dialog limpo
                    try:
                        page.dialog = None
                    except Exception:
                        pass
                except Exception:
                    pass
                pass
            except Exception:
                pass
            page.update()

        def handle_confirm(
            username: str, password: str, venda_id: int, selected_ids=None
        ):
            if not username or not password:
                return False, "Informe usuário e senha do gerente."
            gerente = pdv_core.authenticate_user(username, password)
            if not gerente or getattr(gerente, "role", "") != "gerente":
                return False, "Apenas GERENTE pode cancelar venda."

            # Se foram passados ids específicos, estornar itens; se houver '__all__' estornar a venda inteira
            try:
                if selected_ids:
                    # se foi marcada a opção estornar venda inteira
                    if any((str(x) == "__all__" for x in selected_ids)):
                        ok, msg = pdv_core.estornar_venda(
                            venda_id, usuario=gerente.username
                        )
                    else:
                        ok = True
                        msgs = []
                        for it in selected_ids:
                            try:
                                iid = int(it)
                            except Exception:
                                try:
                                    iid = int(getattr(it, "data", it))
                                except Exception:
                                    iid = None
                            if iid is None:
                                continue
                            r_ok, r_msg = pdv_core.estornar_item(
                                venda_id, iid, usuario=gerente.username
                            )
                            if not r_ok:
                                ok = False
                                msgs.append(r_msg)
                        msg = (
                            "; ".join(msgs) if msgs else "Itens estornados com sucesso."
                        )
                else:
                    ok, msg = pdv_core.estornar_venda(
                        venda_id, usuario=gerente.username
                    )
            except Exception as ex:
                print(f"[F7] Erro em handle_confirm estorno parcial: {ex}")
                return False, str(ex)

            if ok:
                show_snackbar(
                    f"Venda #{venda_id} estornada com sucesso.", COLORS["secondary"]
                )
                try:
                    show_bottom_status(
                        "Venda Estornada", COLORS.get("orange", "#FFB347")
                    )
                except Exception:
                    pass
                # Registrar devoluções (estorno) no arquivo consumido pela tela de Devoluções
                try:
                    from estoque.devolucoes import registrar_devolucoes_por_venda

                    registrado = registrar_devolucoes_por_venda(
                        pdv_core, venda_id, motivo=f"Estorno da venda #{venda_id}"
                    )
                    if not registrado:
                        print(
                            "[F7] Aviso: estorno registrado no banco, mas não foi possível salvar em devolucoes.json"
                        )
                except Exception as ex_reg:
                    print(f"[F7] Erro ao registrar devoluções JSON: {ex_reg}")
            return ok, msg

        cancel_sale_dialog_ref = ft.Ref[ft.AlertDialog]()

        # Reutilizar overlay de estorno se já existir para evitar acúmulo
        try:
            if (
                not hasattr(page, "_cancel_sale_overlay")
                or page._cancel_sale_overlay is None
            ):
                page._cancel_sale_overlay = create_cancel_sale_dialog(
                    COLORS,
                    vendas_dia,
                    produtos_por_codigo,
                    handle_confirm=handle_confirm,
                    on_close=close_cancel_sale_dialog,
                )
            try:
                print(
                    f"[F6-OPEN] created/loaded cancel_sale_overlay type={type(page._cancel_sale_overlay).__name__}"
                )
            except Exception:
                pass
        except Exception:
            page._cancel_sale_overlay = create_cancel_sale_dialog(
                COLORS,
                vendas_dia,
                produtos_por_codigo,
                handle_confirm=handle_confirm,
                on_close=close_cancel_sale_dialog,
            )

        cancel_sale_overlay = page._cancel_sale_overlay

        # Referência e registro do overlay
        cancel_sale_dialog_ref.current = cancel_sale_overlay

        # Proteção anti-duplicação: se já está aberto, não reabrir
        try:
            is_open = bool(getattr(cancel_sale_overlay, "open", False))
            current_dialog = getattr(page, "dialog", None)
            # Se já está aberto e é o dialog atual, não reabrir
            if is_open and current_dialog is cancel_sale_overlay:
                return
            # Se está marcado como aberto mas não é o dialog atual, limpar flag stale
            if is_open and current_dialog is not cancel_sale_overlay:
                try:
                    setattr(cancel_sale_overlay, "open", False)
                except Exception:
                    pass
        except Exception:
            pass

        # Abrir usando o mesmo fluxo do F6 (adicionar na `page.overlay` sem escurecer)
        try:
            try:
                # garantir que o overlay do cancelamento não tenha bgcolor escuro
                try:
                    cancel_sale_overlay.bgcolor = None
                except Exception:
                    pass

                # remover overlays residuais que possam causar escurecimento
                try:
                    _cleanup_overlays()
                except Exception:
                    pass

                # marcar visível/aberto e anexar em page.overlay (mesma abordagem do F6)
                try:
                    cancel_sale_overlay.visible = True
                except Exception:
                    pass
                try:
                    setattr(cancel_sale_overlay, "open", True)
                except Exception:
                    pass

                try:
                    overlays_now = getattr(page, "overlay", []) or []
                    if cancel_sale_overlay not in overlays_now:
                        page.overlay.append(cancel_sale_overlay)
                        page._cancel_sale_overlay_appended = True
                except Exception:
                    pass

                try:
                    page.app_data["caixa_modal_open"] = True
                except Exception:
                    pass
            except Exception as ex:
                print(f"[F7-OPEN] error opening cancel_sale_overlay: {ex}")
        except Exception:
            pass
        try:
            page.update()
        except Exception:
            pass

        # Registrar um handler local de teclado que fecha este diálogo ao pressionar ESC
        original_page_keyboard = getattr(page, "on_keyboard_event", None)

        def _cancel_sale_local_key(e):
            try:
                k = (str(e.key) or "").upper()
            except Exception:
                k = ""
            try:
                if k == "ESCAPE":
                    try:
                        # fechar via callback centralizado, passando o evento
                        close_cancel_sale_dialog(e)
                    except Exception:
                        pass
                    try:
                        e.handled = True
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            # delegar ao handler original se houver
            try:
                if callable(original_page_keyboard):
                    try:
                        original_page_keyboard(e)
                    except Exception:
                        pass
            except Exception:
                pass

        try:
            page.on_keyboard_event = _cancel_sale_local_key
        except Exception:
            try:
                page.on_keyboard_event = cancel_sale_overlay
            except Exception:
                pass

        page.update()

    # Delegar ações centrais para CaixaActions (extraído em caixa/actions.py)
    try:
        from .actions import CaixaActions

        _actions = CaixaActions(
            page=page,
            pdv_core=pdv_core,
            produtos_cache=produtos_cache,
            cart_data=cart_data,
            cart_items_column=cart_items_column,
            total_value_ref=total_value,
            subtotal_text=subtotal_text,
            acrescimo_text=acrescimo_text,
            subtotal_label_ref=subtotal_label_ref,
            acrescimo_label_ref=acrescimo_label_ref,
            total_final_text=total_final_text,
            selected_payment_type=selected_payment_type,
            search_field_ref=search_field_ref,
            product_name_text=product_name_text,
            last_added_product_id_box=last_added_product_id_box,
            payment_buttons_refs=payment_buttons_refs,
            money_received_field=money_received_field,
            change_text=change_text,
            is_finalizing_box=is_finalizing_box,
            COLORS=COLORS,
        )

        # Reexportar funções locais para compatibilidade de testes
        reset_cart = _actions.reset_cart
        add_to_cart = lambda product, quantity=1: _actions.add_to_cart(
            product, quantity, create_cart_item_row_ext
        )
        update_cart_item = _actions.update_cart_item
        calculate_total = _actions.calculate_total
        persistir_estoque_apos_venda = _actions.persistir_estoque_apos_venda
        get_product_from_cache = _actions.get_product_from_cache
        get_stock_for_product_obj = _actions.get_stock_for_product_obj
        iniciar_venda_com_sugestao_troca = _actions.iniciar_venda_com_sugestao_troca
        try:
            print(
                f"[ACTIONS] _actions instantiated, reset_cart is {_actions.reset_cart}"
            )
        except Exception:
            pass
    except Exception as ex:
        # Fallback: manter implementações inline caso a import falhe
        try:
            print(f"[ACTIONS] failed to instantiate CaixaActions: {ex}")
        except Exception:
            pass

    def iniciar_venda_com_sugestao_troca(produtos_sugestao: list = None):
        """
        Limpa o carrinho e opcionalmente adiciona produtos sugeridos para troca

        Args:
            produtos_sugestao: Lista de produtos para sugerir na troca
        """
        reset_cart()

        if produtos_sugestao:
            show_snackbar(
                f"✓ Venda devolvida! Adicione os novos produtos para trocar ({len(produtos_sugestao)} itens sugeridos)",
                COLORS["secondary"],
            )

    # Recalcula o total do carrinho e atualiza textos de subtotal/total
    def calculate_total():
        current_total = sum(item["preco"] * item["qtd"] for item in cart_data.values())
        total_value.current.set(current_total)

        # Lógica para exibir/ocultar Subtotal/Acréscimo
        show_subtotal = False
        show_acrescimo = False
        acrescimo_valor = 0.0
        total_valor = current_total
        try:
            selected_method = selected_payment_type.current.value
            if selected_method:
                from utils.tax_calculator_view import carregar_taxas

                taxas = carregar_taxas()
                # Aplicar repasse de taxa quando habilitado para Crédito ou Débito
                if taxas.get("repassar", False):
                    # Mapear nome do método para chave de taxa no arquivo de config (Crédito ou Débito)
                    method_tax_map = {"Débito": "debito", "Crédito": "credito_avista"}
                    tax_key = method_tax_map.get(selected_method)
                    if tax_key:
                        pct = float(taxas.get(tax_key, 0.0))
                        if pct > 0:
                            # considerar pagamentos já efetuados: acrescimo deve incidir apenas
                            # sobre o valor que será cobrado no método selecionado (remaining)
                            try:
                                paid_amt = get_paid_total()
                            except Exception:
                                paid_amt = 0.0
                            try:
                                remaining_amt = max(0.0, current_total - paid_amt)
                            except Exception:
                                remaining_amt = current_total
                            acrescimo_valor = remaining_amt * (pct / 100.0)
                            total_valor = current_total + acrescimo_valor
                            show_subtotal = True
                            show_acrescimo = True
        except Exception:
            pass

        # quando exibimos subtotal em contexto de crédito com repasse,
        # mostrar o "subtotal" como o valor que será cobrado no crédito (remaining)
        try:
            if show_subtotal:
                try:
                    paid_tmp = get_paid_total()
                except Exception:
                    paid_tmp = 0.0
                try:
                    sub_val = max(0.0, current_total - paid_tmp)
                except Exception:
                    sub_val = current_total
                subtotal_text.value = f"R$ {sub_val:.2f}".replace(".", ",")
                subtotal_text.value = f"R$ {sub_val:.2f}".replace(".", ",")
            else:
                subtotal_text.value = f"R$ {current_total:.2f}".replace(".", ",")
        except Exception:
            subtotal_text.value = f"R$ {current_total:.2f}".replace(".", ",")
        acrescimo_text.value = f"R$ {acrescimo_valor:.2f}".replace(".", ",")
        total_final_text.value = f"R$ {total_valor:.2f}".replace(".", ",")
        subtotal_text.visible = show_subtotal
        acrescimo_text.visible = show_acrescimo

        if (
            selected_payment_type.current.value == "Dinheiro"
            and money_received_field.current
            and money_received_field.current.visible
        ):
            calculate_change(None)

        page.update()

    # Atualiza apenas a parte visual (UI) de um item do carrinho
    def update_cart_item_ui(product_id, new_quantity):
        if product_id in cart_data:
            item = cart_data[product_id]
            item["qtd_ref"].current.value = f"x{new_quantity}"
            new_line_total = item["preco"] * new_quantity
            item["total_row_ref"].current.value = f"R$ {new_line_total:.2f}".replace(
                ".", ","
            )
        page.update()

    # Atualiza a quantidade de um item no carrinho, respeitando estoque
    def update_cart_item(product_id, quantity_change):
        if product_id not in cart_data:
            return

        item = cart_data[product_id]
        new_quantity = item["qtd"] + quantity_change

        if quantity_change > 0:
            prod_obj = get_product_from_cache(product_id)
            available = get_stock_for_product_obj(prod_obj)
            qtd_atual = int(item.get("qtd", 0))
            ok, msg = validar_estoque_disponivel(available, qtd_atual, quantity_change)
            if not ok:
                show_snackbar(msg, COLORS["danger"])
                return

        if new_quantity <= 0:
            cart_items_column.controls.remove(item["card_ref"].current)
            del cart_data[product_id]
        else:
            item["qtd"] = new_quantity
            update_cart_item_ui(product_id, new_quantity)

        calculate_total()
        page.update()

    # Linha visual do item do carrinho movida para components

    # Adiciona um produto ao carrinho (ou incrementa se já existir)
    def add_to_cart(product, quantity: int = 1):
        """Adiciona produto ao carrinho com proteção contra erros."""
        try:
            product_id = str(product.codigo_barras).strip()

            if product_id in cart_data:
                update_cart_item(product_id, quantity)
            else:
                item_data = {
                    "nome": product.nome,
                    "preco": product.preco_venda,
                    "qtd": quantity,
                    "card_ref": ft.Ref[ft.Container](),
                }

                # Passar índice atual para permitir zebra (linhas alternadas)
                try:
                    idx = len(cart_items_column.controls)
                except Exception:
                    idx = 0
                item_container = create_cart_item_row_ext(
                    item_data, product_id, COLORS, update_cart_item, idx
                )
                item_data["card_ref"].current = item_container

                cart_data[product_id] = item_data
                last_added_product_id_box.value = product_id
                # Adiciona o item à lista e aplica destaque visual momentâneo
                cart_items_column.controls.append(item_container)
                # Tocar bip ao adicionar produto (Windows: winsound). Fallback: campainha terminal.
                try:
                    import winsound

                    try:
                        winsound.Beep(1000, 120)
                    except Exception:
                        pass
                except Exception:
                    try:
                        print("\a", end="")
                    except Exception:
                        pass
                try:
                    # aplicar fundo azul claro por 1 segundo
                    try:
                        item_container.bgcolor = "#E3F7FF"
                    except Exception:
                        pass

                    def _clear_highlight():
                        try:
                            page.sleep(1000)
                        except Exception:
                            try:
                                import time

                                time.sleep(1)
                            except Exception:
                                pass
                        try:
                            item_container.bgcolor = COLORS["card_bg"]
                            page.update()
                        except Exception:
                            pass

                    try:
                        page.run_task(_clear_highlight)
                    except Exception:
                        # fallback: usar threading.Timer se run_task não estiver disponível
                        try:
                            import threading

                            threading.Timer(
                                1.0,
                                lambda: (
                                    setattr(
                                        item_container, "bgcolor", COLORS["card_bg"]
                                    ),
                                    page.update(),
                                ),
                            ).start()
                        except Exception:
                            pass
                except Exception:
                    pass

                calculate_total()
                cart_items_column.scroll_to(offset=-1, duration=300)
        except Exception as ex:
            print(f"[ADD_TO_CART] ERRO ao adicionar produto: {ex}")
            import traceback

            traceback.print_exc()
            show_snackbar(f"Erro ao adicionar ao carrinho: {str(ex)}", COLORS["danger"])

    # Wrapper para on_submit do search_field com validação
    # Wrapper para tratar exceções no on_submit
    def on_search_field_submit_wrapper(e):
        print("[SEARCH_FIELD_SUBMIT_WRAPPER] Chamado")
        try:
            # Se houver sugestões visíveis, selecionar a atual em vez de tratar como código
            try:
                if (
                    suggestion_container
                    and getattr(suggestion_container, "visible", False)
                    and suggestion_items
                ):
                    try:
                        idx = (
                            suggestion_selected_idx.current
                            if suggestion_selected_idx
                            and getattr(suggestion_selected_idx, "current", None)
                            is not None
                            else 0
                        )
                        select_suggestion_by_index(idx)
                        return
                    except Exception:
                        pass
            except Exception:
                pass

            on_search_field_submit(e)
        except Exception as ex:
            print(f"[SEARCH_FIELD_SUBMIT_WRAPPER] ERRO NÃO CAPTURADO: {ex}")
            import traceback

            traceback.print_exc()

    def on_search_field_submit(e):
        """Valida se o código é um código de barras antes de processar."""
        print("[SEARCH_SUBMIT] ENTER PRESSIONADO - Iniciando processamento...")
        try:
            raw = e.control.value if e and e.control else ""
            print(f"[SEARCH_SUBMIT] Codigo recebido: '{raw}'")
            # Sanitizar: remover espaços e qualquer caractere não numérico
            code = re.sub(r"\D+", "", str(raw))
            if raw != code:
                print(f"[SEARCH_SUBMIT] Sanitizado para: '{code}'")
                try:
                    e.control.value = code
                except Exception:
                    pass
            if not code:
                print("[SEARCH_SUBMIT] Codigo vazio, ignorando")
                return

            # Evitar processar códigos que parecem ser códigos PIX (muito longos ou com padrão especial)
            # Códigos PIX geralmente têm 143+ caracteres e começam com "00020126"
            if len(code) > 100 or code.startswith("00020126"):
                print(
                    f"[SEARCH_SUBMIT] Ignorando código PIX/longo (tamanho: {len(code)})"
                )
                # Limpar o campo e deixar no focus
                e.control.value = ""
                e.control.focus()
                page.update()
                return

            # Procesar como código de barras normal
            add_by_code(code)
        except Exception as ex:
            print(f"[SEARCH_SUBMIT] ERRO: {ex}")
            import traceback

            traceback.print_exc()

    # Entrada principal de venda: adiciona produto usando código de barras
    def add_by_code(code):
        """Adiciona produto ao carrinho pelo código de barras com proteção contra erros."""
        try:
            if not code:
                print(" Código vazio, ignorando...")
                return

            print(f"[SEARCH] Buscando codigo: '{code}' (tipo: {type(code)})")

            if not cache_loaded.current:
                print(" Cache não carregado! Tentando recarregar...")
                if not carregar_produtos_cache(force_reload=True):
                    show_snackbar(
                        "ERRO: Nenhum produto cadastrado no sistema!", COLORS["danger"]
                    )
                    search_field_ref.current.value = ""
                    search_field_ref.current.focus()
                    return

            codigo_busca = str(code).strip()
            print(f"[SEARCH] Buscando codigo normalizado: '{codigo_busca}'")
            print(f"[SEARCH] Cache tem {len(produtos_cache)} produtos")
            try:
                keys_preview = list(produtos_cache.keys())[:12]
            except Exception:
                keys_preview = []
            print(f"[SEARCH] Preview das chaves do cache: {keys_preview}")
            print(f"[SEARCH] Chave exata presente? {codigo_busca in produtos_cache}")

            produto = produtos_cache.get(codigo_busca)

            if produto:
                nome_prod = (
                    produto.nome
                    if not isinstance(produto, dict)
                    else produto.get("nome", "")
                )

                if isinstance(produto, dict):
                    prod_key = str(
                        produto.get("codigo_barras")
                        or produto.get("codigo")
                        or produto.get("id", "")
                    ).strip()
                else:
                    prod_key = str(
                        getattr(produto, "codigo_barras", "")
                        or getattr(produto, "codigo", "")
                        or getattr(produto, "id", "")
                    ).strip()

                available = get_stock_for_product_obj(produto)
                print(f"✅ Produto encontrado: {nome_prod} (estoque: {available})")

                try:
                    product_name_text.value = f"{nome_prod} — Estoque: {available}"
                    product_name_text.color = (
                        COLORS["primary"] if available > 0 else COLORS["danger"]
                    )
                except Exception as e:
                    print(f" Erro ao atualizar nome do produto: {e}")

                current_in_cart = 0
                if prod_key in cart_data:
                    current_in_cart = int(cart_data[prod_key].get("qtd", 0))

                if available <= 0:
                    show_snackbar(
                        "Estoque insuficiente: produto sem unidades disponíveis.",
                        COLORS["danger"],
                    )
                    if search_field_ref.current:
                        search_field_ref.current.focus()
                    return

                if available < (current_in_cart + 1):
                    show_snackbar(
                        "Estoque insuficiente para adicionar outra unidade.",
                        COLORS["danger"],
                    )
                    if search_field_ref.current:
                        search_field_ref.current.focus()
                    return

                add_to_cart(produto)
                print("[SEARCH] Produto adicionado ao carrinho com sucesso!")
                search_field_ref.current.value = ""
                search_field_ref.current.focus()
                page.update()
            else:
                print(f" Produto com código '{codigo_busca}' não encontrado")
                try:
                    preview = list(produtos_cache.items())[:10]
                    pretty = [(k, type(v).__name__) for k, v in preview]
                    print(f"[SEARCH] Preview cache items (key, type): {pretty}")
                except Exception as e:
                    print(f" Falha ao gerar preview do cache: {e}")
                try:
                    product_name_text.value = ""
                except Exception:
                    pass
                # tocar bip de erro duplo ao código inválido
                try:
                    from utils.beep import error_beep

                    try:
                        print("[BEEP] Chamando error_beep() (search add_by_code)")
                        error_beep()
                        print("[BEEP] error_beep() retornou (search add_by_code)")
                    except Exception as _be:
                        print(f"[BEEP] error_beep() gerou exceção: {_be}")
                except Exception:
                    try:
                        print("\a\a", end="")
                    except Exception:
                        pass
                if produtos_cache:
                    exemplos = list(produtos_cache.keys())[:3]
                    show_snackbar(
                        f"Código inválido! Tente: {', '.join(exemplos)}",
                        COLORS["danger"],
                    )
                else:
                    show_snackbar(
                        "NENHUM PRODUTO CADASTRADO NO SISTEMA!", COLORS["danger"]
                    )
                search_field_ref.current.focus()
                if search_field_ref.current:
                    search_field_ref.current.focus()

        except Exception as ex:
            print(f"[ADD_BY_CODE] ERRO CAPTURADO: {ex}")
            import traceback

            traceback.print_exc()
            show_snackbar(f"Erro ao adicionar produto: {str(ex)}", COLORS["danger"])
            if search_field_ref.current:
                search_field_ref.current.focus()

        print("[ADD_BY_CODE] Fim da execução")

    # Calcula o troco com base no valor recebido digitado
    def calculate_change(e):
        try:
            recebido_str = money_received_field.current.value or ""
            recebido = float(
                recebido_str.replace("R$", "").replace(",", ".").strip() or 0
            )
            total = float(total_value.current.get())
            change = recebido - total

            # Atualiza campo 'Pago:' e 'Restante' instantaneamente usando refs já criados
            try:
                if payment_status_refs:
                    t_ref, p_ref, r_ref = payment_status_refs
                    if getattr(p_ref, "current", None):
                        p_ref.current.value = f"R$ {recebido:.2f}".replace(".", ",")
                    if getattr(r_ref, "current", None):
                        remaining = max(0.0, total - recebido)
                        r_ref.current.value = f"R$ {remaining:.2f}".replace(".", ",")
            except Exception:
                pass

            # Mostrar troco quando o método selecionado for Dinheiro
            try:
                if (
                    getattr(selected_payment_type, "current", None)
                    and getattr(selected_payment_type.current, "value", None)
                    == "Dinheiro"
                ):
                    # sempre mostrar a caixa de troco ao selecionar Dinheiro
                    if change > 0:
                        change_text.current.value = f"Troco: R$ {change:.2f}".replace(
                            ".", ","
                        )
                    else:
                        change_text.current.value = f"Troco: R$ 0,00"
                    change_text.current.color = (
                        COLORS["secondary"] if change >= 0 else COLORS["danger"]
                    )
                    change_text.current.visible = True
                else:
                    # esconder troco quando não for Dinheiro
                    if getattr(change_text, "current", None):
                        change_text.current.visible = False
            except Exception:
                pass

            page.update()
        except ValueError:
            try:
                change_text.current.value = "Valor inválido."
                change_text.current.color = COLORS["danger"]
                change_text.current.visible = True
            except Exception:
                pass
            page.update()
        # Atualizar labels dos botões de pagamento enquanto o usuário digita
        try:
            paid_now = get_paid_total()
            try:
                total_now = float(total_value.current.get())
            except Exception:
                try:
                    total_now = float(total_value.current)
                except Exception:
                    total_now = 0.0
            remaining_now = max(0.0, total_now - paid_now)
            # carregar taxas para ajustar exibição do botão Crédito
            try:
                from utils.tax_calculator_view import carregar_taxas

                taxas_tmp = carregar_taxas()
                credito_pct_tmp = float(taxas_tmp.get("credito_avista", 0.0))
                repassar_tmp = bool(taxas_tmp.get("repassar", False))
            except Exception:
                credito_pct_tmp = 0.0
                repassar_tmp = False

            if payment_amount_text_refs:
                for i, t_ref in enumerate(payment_amount_text_refs):
                    try:
                        if not t_ref or not getattr(t_ref, "current", None):
                            continue
                        pm = PAYMENT_METHODS[i]
                        pm_name = pm.get("name") if isinstance(pm, dict) else str(pm)
                        # se já houver pagamento confirmado para este método, manter
                        method_paid = sum(
                            (
                                float(p.get("amount", 0) or 0)
                                for p in payments
                                if p.get("method") == pm_name
                            )
                        )
                        if method_paid > 0:
                            continue
                        # mostrar restante, aplicando acrescimo quando necessário (Crédito ou Débito)
                        try:
                            method_tax_map = {
                                "Débito": "debito",
                                "Crédito": "credito_avista",
                            }
                            tax_key = method_tax_map.get(pm_name)
                            tax_pct = (
                                float(taxas_tmp.get(tax_key, 0.0)) if tax_key else 0.0
                            )
                        except Exception:
                            tax_key = None
                            tax_pct = 0.0

                        if tax_key and repassar_tmp and tax_pct and tax_pct > 0:
                            total_with_acrescimo = remaining_now * (1 + tax_pct / 100.0)
                            try:
                                if (
                                    getattr(parcel_selected_ref, "current", None)
                                    and parcel_selected_ref.current == 2
                                ):
                                    per = (
                                        total_with_acrescimo / 2.0
                                        if total_with_acrescimo
                                        else 0.0
                                    )
                                    t_ref.current.value = f"R$ {total_with_acrescimo:.2f} (2x R$ {per:.2f})".replace(
                                        ".", ","
                                    )
                                else:
                                    t_ref.current.value = (
                                        f"R$ {total_with_acrescimo:.2f}".replace(
                                            ".", ","
                                        )
                                    )
                            except Exception:
                                t_ref.current.value = (
                                    f"R$ {total_with_acrescimo:.2f}".replace(".", ",")
                                )
                        else:
                            t_ref.current.value = f"R$ {remaining_now:.2f}".replace(
                                ".", ","
                            )
                    except Exception:
                        pass
        except Exception:
            pass

    # Atualiza o JSON de estoque com base no carrinho (pós-venda)
    def persistir_estoque_apos_venda():
        base_dir = os.path.dirname(os.path.dirname(__file__))
        caminho = os.path.join(base_dir, "data", "produtos.json")
        persistir_estoque_json(caminho, cart_data)

    # Busca um produto no cache pelo identificador
    def get_product_from_cache(product_id):
        return produtos_cache.get(str(product_id).strip())

    # Extrai o estoque disponível de um objeto/dict de produto
    def get_stock_for_product_obj(p):
        try:
            if p is None:
                return 0
            if isinstance(p, dict):
                return int(p.get("quantidade", 0) or 0)
            return int(getattr(p, "quantidade", 0) or 0)
        except Exception:
            return 0

    # Lista de pagamentos parciais e helpers
    def get_paid_total():
        try:
            return sum((float(p.get("amount", 0) or 0) for p in payments))
        except Exception:
            return 0.0

    def update_payment_buttons_labels(selected_method: str = None):
        try:
            paid = get_paid_total()
            try:
                total = float(total_value.current.get())
            except Exception:
                try:
                    total = float(total_value.current)
                except Exception:
                    total = 0.0
            remaining = max(0.0, total - paid)
            # carregar taxas para ajustar exibição do botão Crédito
            try:
                from utils.tax_calculator_view import carregar_taxas

                taxas_tmp = carregar_taxas()
                credito_pct_tmp = float(taxas_tmp.get("credito_avista", 0.0))
                repassar_tmp = bool(taxas_tmp.get("repassar", False))
            except Exception:
                credito_pct_tmp = 0.0
                repassar_tmp = False
        except Exception:
            remaining = 0.0

        try:
            for i, pm in enumerate(PAYMENT_METHODS):
                try:
                    amt_ref = payment_amount_text_refs[i]
                    if not (amt_ref and getattr(amt_ref, "current", None)):
                        continue
                    # se já houver pagamentos confirmados para este método, mostrar o valor pago
                    pm_name = pm.get("name") if isinstance(pm, dict) else str(pm)
                    try:
                        method_paid = sum(
                            (
                                float(p.get("amount", 0) or 0)
                                for p in payments
                                if p.get("method") == pm_name
                            )
                        )
                    except Exception:
                        method_paid = 0.0

                    if method_paid > 0:
                        try:
                            # se o pagamento confirmado for Crédito e houver repasse, mostrar o valor cobrado ao cliente (com acréscimo)
                            try:
                                method_tax_map = {
                                    "Débito": "debito",
                                    "Crédito": "credito_avista",
                                }
                                tax_key = method_tax_map.get(pm_name)
                                tax_pct = (
                                    float(taxas_tmp.get(tax_key, 0.0))
                                    if tax_key
                                    else 0.0
                                )
                            except Exception:
                                tax_key = None
                                tax_pct = 0.0

                            if tax_key and repassar_tmp and tax_pct and tax_pct > 0:
                                charged = method_paid * (1 + tax_pct / 100.0)
                                # mostrar valor total cobrado; se houver parcelamento, mostrar também por parcela
                                try:
                                    if (
                                        getattr(parcel_selected_ref, "current", None)
                                        and parcel_selected_ref.current == 2
                                    ):
                                        per = charged / 2.0 if charged else 0.0
                                        amt_ref.current.value = f"R$ {charged:.2f} (2x R$ {per:.2f})".replace(
                                            ".", ","
                                        )
                                    else:
                                        amt_ref.current.value = (
                                            f"R$ {charged:.2f}".replace(".", ",")
                                        )
                                except Exception:
                                    amt_ref.current.value = f"R$ {charged:.2f}".replace(
                                        ".", ","
                                    )
                            else:
                                amt_ref.current.value = f"R$ {method_paid:.2f}".replace(
                                    ".", ","
                                )
                        except Exception:
                            amt_ref.current.value = f"R$ {method_paid:.2f}".replace(
                                ".", ","
                            )
                    else:
                        # mostrar o restante sugerido quando não houver pagamento confirmado
                        if remaining > 0:
                            try:
                                try:
                                    method_tax_map = {
                                        "Débito": "debito",
                                        "Crédito": "credito_avista",
                                    }
                                    tax_key = method_tax_map.get(pm_name)
                                    tax_pct = (
                                        float(taxas_tmp.get(tax_key, 0.0))
                                        if tax_key
                                        else 0.0
                                    )
                                except Exception:
                                    tax_key = None
                                    tax_pct = 0.0

                                if tax_key and repassar_tmp and tax_pct and tax_pct > 0:
                                    total_with_acrescimo = remaining * (
                                        1 + tax_pct / 100.0
                                    )
                                    try:
                                        if (
                                            getattr(
                                                parcel_selected_ref, "current", None
                                            )
                                            and parcel_selected_ref.current == 2
                                        ):
                                            per = (
                                                total_with_acrescimo / 2.0
                                                if total_with_acrescimo
                                                else 0.0
                                            )
                                            amt_ref.current.value = f"R$ {total_with_acrescimo:.2f} (2x R$ {per:.2f})".replace(
                                                ".", ","
                                            )
                                        else:
                                            amt_ref.current.value = f"R$ {total_with_acrescimo:.2f}".replace(
                                                ".", ","
                                            )
                                    except Exception:
                                        amt_ref.current.value = (
                                            f"R$ {total_with_acrescimo:.2f}".replace(
                                                ".", ","
                                            )
                                        )
                                else:
                                    amt_ref.current.value = (
                                        f"R$ {remaining:.2f}".replace(".", ",")
                                    )
                            except Exception:
                                amt_ref.current.value = f"R$ {remaining:.2f}".replace(
                                    ".", ","
                                )
                        else:
                            amt_ref.current.value = ""
                except Exception:
                    pass
        except Exception:
            pass

    def show_payment_amount_dialog(method_name: str, btn_ref=None):
        try:
            # valor sugerido: restante
            paid = get_paid_total()
            try:
                total = float(total_value.current.get())
            except Exception:
                try:
                    total = float(total_value.current)
                except Exception:
                    total = 0.0
            remaining = max(0.0, total - paid)

            val_ref = ft.Ref[ft.TextField]()
            val_ref_field = ft.TextField(
                ref=val_ref,
                label=f"Valor a pagar em {method_name}",
                value=f"{remaining:.2f}".replace(".", ","),
                prefix="R$",
                keyboard_type=ft.KeyboardType.NUMBER,
                border_radius=8,
                filled=True,
                height=50,
            )

            def _confirm_pay(e=None):
                try:
                    vstr = (
                        (val_ref.current.value or "")
                        .replace("R$", "")
                        .replace(",", ".")
                        .strip()
                    )
                    amt = float(vstr) if vstr else 0.0
                    if amt <= 0:
                        show_snackbar(
                            "Informe um valor maior que zero.", COLORS["warning"]
                        )
                        return
                    # limitar ao restante
                    amt = min(amt, remaining)
                    payments.append({"method": method_name, "amount": amt})
                    # se for Dinheiro, refletir no campo de dinheiro
                    if method_name == "Dinheiro":
                        try:
                            # somar pagamentos em dinheiro
                            cash_paid = sum(
                                (
                                    p["amount"]
                                    for p in payments
                                    if p.get("method") == "Dinheiro"
                                )
                            )
                            if money_received_field.current:
                                money_received_field.current.value = (
                                    f"{cash_paid:.2f}".replace(".", ",")
                                )
                                calculate_change(None)
                        except Exception:
                            pass
                    update_payment_buttons_labels(selected_method=method_name)
                    try:
                        update_payment_status()
                    except Exception:
                        pass
                except Exception as ex:
                    print(f"[PAY_DIALOG] erro ao confirmar pagamento: {ex}")
                finally:
                    try:
                        if pay_overlay in page.overlay:
                            page.overlay.remove(pay_overlay)
                    except Exception:
                        pass
                    page.update()

            def _cancel(e=None):
                try:
                    if pay_overlay in page.overlay:
                        page.overlay.remove(pay_overlay)
                except Exception:
                    pass
                page.update()

            pay_overlay = ft.AlertDialog(
                title=ft.Text(f"Pagar com {method_name}"),
                content=ft.Column([val_ref_field]),
                actions=[
                    ft.TextButton("Cancelar", on_click=_cancel),
                    ft.ElevatedButton("Confirmar", on_click=_confirm_pay),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            if pay_overlay not in page.overlay:
                page.overlay.append(pay_overlay)
            pay_overlay.open = True
            page.update()
        except Exception as ex:
            print(f"[PAY_DIALOG] erro: {ex}")

    # Seleciona o método de pagamento (dinheiro, cartão, Pix, etc.)
    def select_payment(type_name, btn_ref):
        # Garantir que qualquer aviso residual na appbar seja removido ao selecionar
        try:
            if appbar is not None:
                # limpar explicitamente o aviso caso esteja presente
                try:
                    cur_t = getattr(appbar, "title", None)
                    txt = None
                    if isinstance(cur_t, ft.Text):
                        txt = getattr(cur_t, "value", None)
                    elif isinstance(cur_t, str):
                        txt = cur_t
                    if txt and "Selecione a forma de pagamento" in txt:
                        try:
                            orig = appbar_orig.get("title")
                            if orig is not None:
                                appbar.title = orig
                            # se não houver título original, não sobrescrever o título atual
                        except Exception:
                            # não forçar título em caso de erro
                            pass
                        try:
                            appbar.bgcolor = appbar_orig.get("bg") or None
                        except Exception:
                            appbar.bgcolor = None
                        appbar_notice_active.value = False
                        appbar_orig["title"] = None
                        appbar_orig["bg"] = None
                        page.update()
                except Exception:
                    pass
        except Exception:
            pass

        # capturar seleção anterior para UX específico (Crédito -> Dinheiro)
        prev_selected = None
        try:
            prev_selected = getattr(selected_payment_type.current, "value", None)
        except Exception:
            prev_selected = None
        selected_payment_type.current.value = type_name
        print(
            f"[SELECT-PAYMENT] called type_name={type_name} appbar_notice_active={appbar_notice_active.value}"
        )
        # Reverter aviso fixe na appbar caso esteja ativo ou o título atual
        try:
            cur_title = getattr(appbar, "title", None) if appbar is not None else None
            is_warning_title = False
            try:
                if (
                    isinstance(cur_title, ft.Text)
                    and getattr(cur_title, "value", "")
                    == "Selecione a forma de pagamento"
                ):
                    is_warning_title = True
            except Exception:
                is_warning_title = False

            if (appbar_notice_active.value or is_warning_title) and appbar is not None:
                print(
                    f"[SELECT-PAYMENT] reverting appbar orig={appbar_orig} cur_title={cur_title}"
                )
                try:
                    # Restaurar título/bkg anterior quando possível;
                    # caso contrário, limpar explicitamente o título de aviso.
                    orig_title = appbar_orig.get("title")
                    if orig_title is not None:
                        appbar.title = orig_title
                    # se não houver título original, não modificar o título atual
                    orig_bg = appbar_orig.get("bg")
                    if orig_bg is not None:
                        appbar.bgcolor = orig_bg
                    else:
                        appbar.bgcolor = None
                    page.update()
                    print("[SELECT-PAYMENT] appbar reverted and page updated")
                except Exception as ex:
                    print(f"[SELECT-PAYMENT] error reverting appbar: {ex}")
                appbar_notice_active.value = False
                appbar_orig["title"] = None
                appbar_orig["bg"] = None
        except Exception:
            pass
        # Tornar visível somente o campo do método selecionado (um TextField por método)
        try:
            paid = get_paid_total()
            try:
                total = float(total_value.current.get())
            except Exception:
                try:
                    total = float(total_value.current)
                except Exception:
                    total = 0.0
            remaining = max(0.0, total - paid)
        except Exception:
            remaining = 0.0

        try:
            for i, ref in enumerate(payment_value_field_refs):
                try:
                    method_name = PAYMENT_METHODS[i]["name"]
                    should = method_name == type_name
                    if getattr(ref, "current", None) is not None:
                        # visibilidade
                        ref.current.visible = bool(should)
                        # preencher automaticamente com o restante
                        if should:
                            try:
                                display_amt = remaining
                                if method_name == "Crédito":
                                    try:
                                        from utils.tax_calculator_view import (
                                            carregar_taxas,
                                        )

                                        taxas_tmp = carregar_taxas()
                                        credito_pct_tmp = float(
                                            taxas_tmp.get("credito_avista", 0.0)
                                        )
                                        repassar_tmp = bool(
                                            taxas_tmp.get("repassar", False)
                                        )
                                    except Exception:
                                        credito_pct_tmp = 0.0
                                        repassar_tmp = False
                                    if (
                                        repassar_tmp
                                        and credito_pct_tmp
                                        and credito_pct_tmp > 0
                                    ):
                                        display_amt = remaining * (
                                            1 + credito_pct_tmp / 100.0
                                        )
                                ref.current.value = f"{display_amt:.2f}".replace(
                                    ".", ","
                                )
                            except Exception:
                                ref.current.value = f"{remaining:.2f}".replace(".", ",")

                        # se for Dinheiro, também refletir no campo money_received_field
                        if method_name == "Dinheiro":
                            try:
                                if getattr(money_received_field, "current", None):
                                    money_received_field.current.value = (
                                        ref.current.value
                                    )
                            except Exception:
                                pass

                        # dar foco ao campo recém-ativado
                        try:
                            # algumas versões do Flet exigem que o controle esteja visível antes de focar
                            ref.current.focus()
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        # UX extra: se mudou de Crédito para Dinheiro, esconder subtotal/acréscimo e recalcular
        try:
            # se estava em Crédito e mudou para qualquer outro método, ocultar subtotal/acréscimo
            if prev_selected == "Crédito" and type_name != "Crédito":
                try:
                    try:
                        subtotal_text.visible = False
                    except Exception:
                        pass
                    try:
                        acrescimo_text.visible = False
                    except Exception:
                        pass
                    try:
                        calculate_total()
                    except Exception as ex:
                        print(f"[SELECT-PAYMENT] erro chamando calculate_total: {ex}")
                    try:
                        # recalcular troco caso aplicável
                        calculate_change(None)
                    except Exception:
                        pass
                except Exception:
                    pass

        except Exception:
            pass

        # Se for Dinheiro, mostrar troco (recalcular)
        try:
            if type_name == "Dinheiro":
                try:
                    # garantir que campo de dinheiro atualizado seja usado
                    calculate_change(None)
                    if getattr(change_text, "current", None):
                        change_text.current.visible = True
                except Exception:
                    pass
            else:
                try:
                    if getattr(change_text, "current", None):
                        change_text.current.visible = False
                except Exception:
                    pass
        except Exception:
            pass

        # Mostrar/ocultar mini-botões de parcelamento (ex.: 2x) quando aplicável
        try:
            # calcular total atual para condições de exibição (parcelamento só para vendas maiores que R$100)
            try:
                total_now = float(total_value.current.get())
            except Exception:
                try:
                    total_now = float(total_value.current)
                except Exception:
                    total_now = 0.0

            if payment_parcel_button_refs:
                for i, p_ref in enumerate(payment_parcel_button_refs):
                    try:
                        if not p_ref or not getattr(p_ref, "current", None):
                            continue
                        # visível apenas quando 'Crédito' está selecionado e venda > 100
                        visible_now = (
                            type_name == "Crédito"
                            and PAYMENT_METHODS[i]["name"] == "Crédito"
                            and (total_now > 100.0)
                        )
                        p_ref.current.visible = bool(visible_now)
                        # reset estilo se oculto
                        if not visible_now:
                            try:
                                p_ref.current.style.bgcolor = ft.Colors.WHITE
                                p_ref.current.style.color = ft.Colors.BLACK
                            except Exception:
                                pass
                        else:
                            # aplicar destaque se já selecionado como 2x
                            try:
                                if (
                                    getattr(parcel_selected_ref, "current", None)
                                    and parcel_selected_ref.current == 2
                                ):
                                    p_ref.current.style.bgcolor = COLORS.get(
                                        "secondary", "#4CAF50"
                                    )
                                    p_ref.current.style.color = ft.Colors.WHITE
                                else:
                                    p_ref.current.style.bgcolor = ft.Colors.WHITE
                                    p_ref.current.style.color = ft.Colors.BLACK
                            except Exception:
                                pass
                    except Exception:
                        pass
        except Exception:
            pass

        for i, ref in enumerate(payment_buttons_refs):
            try:
                # verificar se este método já recebeu valor confirmado (pagamento parcial)
                paid = False
                try:
                    method_name_check = PAYMENT_METHODS[i]["name"]
                    # buscar na lista de pagamentos confirmados (payments)
                    paid = any(
                        (
                            p.get("method") == method_name_check
                            and float(p.get("amount", 0) or 0) > 0
                        )
                        for p in payments
                    )
                except Exception:
                    paid = False

                if ref.current == btn_ref.current:
                    # botão selecionado: aplicar destaque, mas não sobrescrever cor verde se já pago
                    if paid:
                        ref.current.style.bgcolor = COLORS.get("secondary", "#4CAF50")
                        ref.current.style.color = ft.Colors.WHITE
                        ref.current.style.side = ft.border.BorderSide(
                            1, ft.Colors.BLACK12
                        )
                    else:
                        ref.current.style.bgcolor = ft.Colors.WHITE
                        ref.current.style.side = ft.border.BorderSide(3, "#007BFF")
                        ref.current.style.color = ft.Colors.BLACK
                else:
                    # botão não selecionado: manter verde se pago, caso contrário estilo padrão
                    if paid:
                        ref.current.style.bgcolor = COLORS.get("secondary", "#4CAF50")
                        ref.current.style.color = ft.Colors.WHITE
                        ref.current.style.side = ft.border.BorderSide(
                            1, ft.Colors.BLACK12
                        )
                    else:
                        ref.current.style.bgcolor = ft.Colors.WHITE
                        ref.current.style.side = ft.border.BorderSide(
                            1, ft.Colors.BLACK12
                        )
                        ref.current.style.color = ft.Colors.BLACK
            except Exception:
                pass

        # atualizar labels (não abrir modal automaticamente)
        try:
            update_payment_buttons_labels(selected_method=type_name)
        except Exception:
            pass

        try:
            # recalcular para atualizar Subtotal/Acréscimo quando necessário
            try:
                calculate_total()
                print("[SELECT-PAYMENT] called calculate_total()")
            except Exception as ex:
                print(f"[SELECT-PAYMENT] erro chamando calculate_total: {ex}")
        except Exception:
            pass
        # Garantir visibilidade consistente das labels de Subtotal/Acréscimo
        try:
            if type_name == "Crédito":
                try:
                    from utils.tax_calculator_view import carregar_taxas

                    taxas_tmp = carregar_taxas()
                    credito_pct_tmp = float(taxas_tmp.get("credito_avista", 0.0))
                    repassar_tmp = bool(taxas_tmp.get("repassar", False))
                except Exception:
                    credito_pct_tmp = 0.0
                    repassar_tmp = False

                if repassar_tmp and credito_pct_tmp and credito_pct_tmp > 0:
                    try:
                        if getattr(subtotal_label_ref, "current", None):
                            subtotal_label_ref.current.visible = True
                    except Exception:
                        pass
                    try:
                        if getattr(acrescimo_label_ref, "current", None):
                            acrescimo_label_ref.current.visible = True
                    except Exception:
                        pass
                    try:
                        subtotal_text.visible = True
                    except Exception:
                        pass
                    try:
                        acrescimo_text.visible = True
                    except Exception:
                        pass
                else:
                    try:
                        if getattr(subtotal_label_ref, "current", None):
                            subtotal_label_ref.current.visible = False
                    except Exception:
                        pass
                    try:
                        if getattr(acrescimo_label_ref, "current", None):
                            acrescimo_label_ref.current.visible = False
                    except Exception:
                        pass
                    try:
                        subtotal_text.visible = False
                    except Exception:
                        pass
                    try:
                        acrescimo_text.visible = False
                    except Exception:
                        pass
        except Exception:
            pass
        page.update()

    # Finaliza a venda: valida carrinho, grava no banco e emite cupom
    def finalize_transaction(e=None):
        # Antes de finalizar, garantir que não haja aviso ativo na appbar
        try:
            if appbar is not None:
                try:
                    orig = appbar_orig.get("title")
                    if orig is not None:
                        appbar.title = orig
                    # caso não haja título original, não sobrescrever o título atual
                except Exception:
                    # não forçar título em caso de erro
                    pass
                try:
                    appbar.bgcolor = appbar_orig.get("bg") or None
                except Exception:
                    appbar.bgcolor = None
                appbar_notice_active.value = False
                appbar_orig["title"] = None
                appbar_orig["bg"] = None
                page.update()
        except Exception:
            pass

        try:
            try:
                print(
                    f"[FINALIZE-DELEGATE] delegando finalize_transaction_impl reset_cart={reset_cart}"
                )
            except Exception:
                pass
            # calcular info de parcelamento se aplicável
            try:
                installments_count_arg = None
                per_installment_arg = None
                sel_pay = None
                try:
                    sel_pay = getattr(selected_payment_type.current, "value", None)
                except Exception:
                    sel_pay = None
                try:
                    total_now_val = float(total_value.current.get())
                except Exception:
                    try:
                        total_now_val = float(total_value.current)
                    except Exception:
                        total_now_val = 0.0
                if (
                    sel_pay == "Crédito"
                    and getattr(parcel_selected_ref, "current", None) == 2
                ):
                    try:
                        from utils.tax_calculator_view import carregar_taxas

                        taxas_tmp = carregar_taxas()
                        credito_pct_tmp = float(taxas_tmp.get("credito_avista", 0.0))
                        repassar_tmp = bool(taxas_tmp.get("repassar", False))
                    except Exception:
                        credito_pct_tmp = 0.0
                        repassar_tmp = False
                    if repassar_tmp and credito_pct_tmp and credito_pct_tmp > 0:
                        total_with_acrescimo = total_now_val * (
                            1 + credito_pct_tmp / 100.0
                        )
                    else:
                        total_with_acrescimo = total_now_val
                    installments_count_arg = 2
                    per_installment_arg = round(total_with_acrescimo / 2.0, 2)
            except Exception:
                installments_count_arg = None
                per_installment_arg = None

            finalize_transaction_impl(
                page=page,
                pdv_core=pdv_core,
                cart_data=cart_data,
                total_value_ref=total_value,
                selected_payment_type_ref=selected_payment_type,
                money_received_field_ref=money_received_field,
                payment_buttons_refs=payment_buttons_refs,
                PAYMENT_METHODS=PAYMENT_METHODS,
                payments=payments,
                persistir_estoque_apos_venda=persistir_estoque_apos_venda,
                montar_itens_cupom=montar_itens_cupom,
                calcular_troco=calcular_troco,
                montar_payload_pix=montar_payload_pix,
                show_cupom_dialog=show_cupom_dialog,
                create_pix_overlay=create_pix_overlay,
                COLORS=COLORS,
                show_snackbar=show_snackbar,
                reset_cart=reset_cart,
                post_finalize_callback=lambda: (
                    search_field_ref.current.focus()
                    if getattr(search_field_ref, "current", None)
                    else None
                ),
                set_finalizing=set_finalizing,
                is_finalizing_ref=is_finalizing_box,
                installments_count=installments_count_arg,
                per_installment=per_installment_arg,
            )
        except Exception as ex:
            print(f"[FINALIZE-DELEGATE] Erro ao delegar finalização: {ex}")
            try:
                show_snackbar(f"Erro ao finalizar: {ex}", COLORS["danger"])
            except Exception:
                pass
            set_finalizing(False)

    # Painel da direita com métodos de pagamento, campo de valor recebido e troco
    # Criar botão Devolver & Trocar
    # Usar o username real armazenado na sessão (chave 'user_username')
    # Fallback para 'user_caixa' quando indisponível
    try:
        role = page.session.get("role")
    except Exception:
        role = None
    try:
        usuario_responsavel = page.session.get("user_username")
    except Exception:
        usuario_responsavel = None
    # Para gerente, listar vendas de todos (devolve/troca precisa ver geral)
    if str(role or "").lower() == "gerente":
        usuario_responsavel = None
    elif not usuario_responsavel:
        usuario_responsavel = "user_caixa"
    botao_devolver_trocar = criar_botao_devolver_trocar(
        page=page,
        pdv_core=pdv_core,
        usuario_responsavel=usuario_responsavel,
        callback_nova_venda=iniciar_venda_com_sugestao_troca,
        colors=COLORS,
    )

    def handle_method_value_submit(method_name: str, idx: int, e=None):
        try:
            # obter ref do campo correspondente
            ref = None
            try:
                ref = payment_value_field_refs[idx]
            except Exception:
                pass
            if not ref or getattr(ref, "current", None) is None:
                return
            raw = (
                (ref.current.value or "")
                .replace("R$", "")
                .replace(".", "")
                .replace(",", ".")
            )
            try:
                val = float(raw) if raw else 0.0
            except Exception:
                show_snackbar("Valor inválido.", COLORS["warning"])
                return

            if val <= 0:
                show_snackbar("Informe um valor maior que zero.", COLORS["warning"])
                return

            # Para 'Dinheiro' permitir receber valor maior que o restante (mostrar troco).
            paid = get_paid_total()
            try:
                total = float(total_value.current.get())
            except Exception:
                try:
                    total = float(total_value.current)
                except Exception:
                    total = 0.0
            remaining = max(0.0, total - paid)
            if method_name == "Dinheiro":
                amt = val
            else:
                amt = min(val, remaining)

            # Substituir pagamento existente deste método em vez de somar
            try:
                replaced = False
                for p in payments:
                    if p.get("method") == method_name:
                        p["amount"] = amt
                        replaced = True
                        break
                if not replaced:
                    payments.append({"method": method_name, "amount": amt})
            except Exception:
                # fallback seguro: remover quaisquer entradas antigas e adicionar a nova
                try:
                    payments[:] = [
                        p for p in payments if p.get("method") != method_name
                    ]
                except Exception:
                    payments.clear()
                payments.append({"method": method_name, "amount": amt})

            # Propagar valor restante/atual para todos os botões e campos,
            # para que o valor não fique apenas associado à primeira opção.
            try:
                paid_now = get_paid_total()
                try:
                    total_now = float(total_value.current.get())
                except Exception:
                    try:
                        total_now = float(total_value.current)
                    except Exception:
                        total_now = 0.0
                remaining_after = max(0.0, total_now - paid_now)
                # atualizar valores exibidos nos botões (amt labels)
                if payment_amount_text_refs:
                    for j, t_ref in enumerate(payment_amount_text_refs):
                        try:
                            if not t_ref or not getattr(t_ref, "current", None):
                                continue
                            # se este método já tiver pagamento confirmado, manter seu valor
                            pm = PAYMENT_METHODS[j]
                            pm_name_j = (
                                pm.get("name") if isinstance(pm, dict) else str(pm)
                            )
                            method_paid_j = sum(
                                (
                                    float(p.get("amount", 0) or 0)
                                    for p in payments
                                    if p.get("method") == pm_name_j
                                )
                            )
                            if method_paid_j > 0:
                                # manter o valor já pago exibido
                                continue
                            # caso contrário exibir o restante sugerido
                            t_ref.current.value = f"R$ {remaining_after:.2f}".replace(
                                ".", ","
                            )
                        except Exception:
                            pass
            except Exception:
                pass

            # atualizar label do botão
            try:
                if payment_amount_text_refs and len(payment_amount_text_refs) > idx:
                    t_ref = payment_amount_text_refs[idx]
                    if getattr(t_ref, "current", None):
                        t_ref.current.value = f"R$ {amt:.2f}".replace(".", ",")
                        try:
                            # esconder o campo após confirmação
                            ref.current.visible = False
                        except Exception:
                            pass
            except Exception:
                pass

            # pintar botão de verde (indica pago parcialmente)
            try:
                if payment_buttons_refs and len(payment_buttons_refs) > idx:
                    b_ref = payment_buttons_refs[idx]
                    if getattr(b_ref, "current", None):
                        b_ref.current.style.bgcolor = COLORS.get("secondary", "#4CAF50")
                        b_ref.current.style.color = ft.Colors.WHITE
            except Exception:
                pass

            # se Dinheiro, refletir no campo principal e recalcular troco
            try:
                if method_name == "Dinheiro":
                    if money_received_field.current:
                        money_received_field.current.value = f"{amt:.2f}".replace(
                            ".", ","
                        )
                    calculate_change(None)
                    if getattr(change_text, "current", None):
                        change_text.current.visible = True
            except Exception:
                pass

            try:
                update_payment_buttons_labels(selected_method=method_name)
            except Exception:
                pass
            try:
                update_payment_status()
            except Exception:
                pass

            page.update()
        except Exception as ex:
            print(f"[PAY-SUBMIT] erro: {ex}")

    (
        payment_options_panel,
        payment_buttons_refs_new,
        money_received_input,
        change_display,
        payment_amount_text_refs_new,
        payment_value_field_refs_new,
        payment_status_refs_new,
        payment_parcel_button_refs_new,
    ) = create_payment_panel_ext(
        COLORS,
        PAYMENT_METHODS,
        on_select_payment=select_payment,
        money_received_field_ref=money_received_field,
        change_text_ref=change_text,
        calculate_change_cb=calculate_change,
        on_method_value_submit=handle_method_value_submit,
        on_parcel_select=lambda idx, cnt: on_parcel_select(idx, cnt),
    )
    # sincronizar refs de botões e campos por método usados por select_payment
    payment_buttons_refs = payment_buttons_refs_new
    payment_amount_text_refs = payment_amount_text_refs_new
    payment_value_field_refs = payment_value_field_refs_new
    payment_status_refs = payment_status_refs_new
    # lista de refs para mini-botões de parcelamento (2x)
    payment_parcel_button_refs = payment_parcel_button_refs_new
    # se o objeto de ações existir, anexar refs e a lista de payments para que reset_cart possa limpá-los
    try:
        if "_actions" in locals() and _actions is not None:
            try:
                _actions.payment_amount_text_refs = payment_amount_text_refs
            except Exception:
                pass
            try:
                _actions.payment_value_field_refs = payment_value_field_refs
            except Exception:
                pass
            try:
                _actions.payments = payments
            except Exception:
                pass
            try:
                _actions.payment_parcel_button_refs = payment_parcel_button_refs
            except Exception:
                pass
    except Exception:
        pass

    def update_payment_status():
        try:
            total = 0.0
            try:
                total = float(total_value.current.get())
            except Exception:
                try:
                    total = float(total_value.current)
                except Exception:
                    total = 0.0
            paid = get_paid_total()
            remaining = max(0.0, total - paid)
            try:
                t_ref, p_ref, r_ref = payment_status_refs
                # Em condições normais: mostrar total, pago e restante
                if getattr(t_ref, "current", None):
                    t_ref.current.value = f"R$ {total:.2f}".replace(".", ",")

                # Se a forma selecionada for Crédito ou Débito e houver repasse,
                # exibir em 'Pago' o valor cobrado ao cliente (com acréscimo)
                # para manter consistência com o valor exibido no botão.
                try:
                    sel = None
                    try:
                        sel = selected_payment_type.current.value
                    except Exception:
                        sel = None

                    # carregar taxas
                    try:
                        from utils.tax_calculator_view import carregar_taxas

                        taxas_tmp = carregar_taxas()
                        repassar_tmp = bool(taxas_tmp.get("repassar", False))
                    except Exception:
                        taxas_tmp = {}
                        repassar_tmp = False

                    paid_display_value = paid

                    if sel in ("Crédito", "Débito") and repassar_tmp:
                        try:
                            method_tax_map = {
                                "Débito": "debito",
                                "Crédito": "credito_avista",
                            }
                            tax_key = method_tax_map.get(sel)
                            tax_pct = (
                                float(taxas_tmp.get(tax_key, 0.0)) if tax_key else 0.0
                            )
                        except Exception:
                            tax_pct = 0.0

                        if tax_pct and tax_pct > 0:
                            # Para Crédito: manter comportamento anterior (mostrar total com acréscimo)
                            if sel == "Crédito":
                                try:
                                    total_com_acrescimo = total * (1 + tax_pct / 100.0)
                                    paid_display_value = total_com_acrescimo
                                except Exception:
                                    paid_display_value = paid
                            else:
                                # Para Débito: mostrar o valor efetivamente pago ao cliente
                                try:
                                    charged = paid * (1 + tax_pct / 100.0)
                                    paid_display_value = charged
                                except Exception:
                                    paid_display_value = paid

                    if getattr(p_ref, "current", None):
                        try:
                            p_ref.current.value = (
                                f"R$ {paid_display_value:.2f}".replace(".", ",")
                            )
                        except Exception:
                            p_ref.current.value = f"R$ {paid:.2f}".replace(".", ",")
                except Exception:
                    try:
                        p_ref.current.value = f"R$ {paid:.2f}".replace(".", ",")
                    except Exception:
                        pass

                if getattr(r_ref, "current", None):
                    r_ref.current.value = f"R$ {remaining:.2f}".replace(".", ",")
            except Exception:
                pass
            page.update()
        except Exception:
            pass

    # Cabeçalho da lista de itens do carrinho
    cart_header = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "Produto",
                            expand=True,
                            size=14,
                            color="#000000",
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Container(
                            ft.Column(
                                [
                                    ft.Text(
                                        "F8 / F9",
                                        size=10,
                                        color=COLORS["text_muted"],
                                        italic=True,
                                    ),
                                    ft.Text(
                                        "Qtd",
                                        size=14,
                                        color="#000000",
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ],
                                spacing=2,
                            ),
                            width=150,
                            alignment=ft.alignment.center_right,
                        ),
                        ft.Text(
                            "Preço Unit.",
                            size=14,
                            color="#000000",
                            weight=ft.FontWeight.BOLD,
                            width=100,
                            text_align=ft.TextAlign.RIGHT,
                        ),
                        ft.Text(
                            "Total",
                            size=14,
                            color="#000000",
                            weight=ft.FontWeight.BOLD,
                            width=120,
                            text_align=ft.TextAlign.RIGHT,
                        ),
                    ],
                    spacing=10,
                ),
            ],
        ),
        padding=ft.padding.only(left=10, right=10, top=10, bottom=10),
        border=ft.border.only(bottom=ft.border.BorderSide(2, ft.Colors.BLACK12)),
        bgcolor=ft.Colors.BLACK12,
    )

    # Campo principal onde o operador digita / bipa o código de barras
    # Este campo tem autofocus=True
    search_field = ft.TextField(
        ref=search_field_ref,
        label="Produto",
        hint_text="Código ou nome do produto • Enter adiciona",
        autofocus=True,
        prefix_icon=ft.Icons.QR_CODE_SCANNER,
        border_radius=8,
        filled=True,
        bgcolor=ft.Colors.WHITE,
        height=50,
        content_padding=15,
        text_size=16,
        on_submit=on_search_field_submit_wrapper,
        on_change=lambda e: on_search_field_change(e),
    )

    # Sugestões por nome (visível quando o usuário digita letras)
    suggestion_container = ft.Column([], visible=False)
    # estado local de sugestões
    suggestion_items = []  # lista de dicts {code, name, price, stock}
    suggestion_selected_idx = ft.Ref[int]()
    suggestion_selected_idx.current = 0

    def clear_suggestions():
        try:
            suggestion_items.clear()
            suggestion_container.controls.clear()
            suggestion_container.visible = False
            suggestion_selected_idx.current = 0
            page.update()
        except Exception:
            pass

    def select_suggestion_by_index(idx: int = 0):
        try:
            if not suggestion_items:
                return
            if idx is None:
                idx = 0
            idx = max(0, min(len(suggestion_items) - 1, int(idx)))
            item = suggestion_items[idx]
            code = item.get("code")
            if code:
                # fechar sugestões e adicionar pelo código (reusa add_by_code)
                clear_suggestions()
                try:
                    add_by_code(code)
                except Exception:
                    pass
        except Exception:
            pass

    def build_suggestion_control(item, idx):
        name = item.get("name", "")
        price = item.get("price", "")
        stock = item.get("stock", "")

        def _on_click(e=None, _idx=idx):
            try:
                select_suggestion_by_index(_idx)
            except Exception:
                pass

        bg = "#E8F7FF" if suggestion_selected_idx.current == idx else None
        return ft.Container(
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(name, size=14, weight=ft.FontWeight.W_500),
                            ft.Row(
                                [
                                    ft.Text(
                                        (
                                            f"R$ {price:.2f}"
                                            if isinstance(price, (int, float))
                                            else str(price)
                                        ),
                                        size=12,
                                    ),
                                    ft.Container(width=12),
                                    ft.Text(f"Estoque: {stock}", size=12),
                                ],
                                spacing=8,
                            ),
                        ]
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            on_click=_on_click,
            padding=ft.padding.all(8),
            bgcolor=bg,
        )

    def update_suggestions(query: str):
        try:
            q = (query or "").strip()
            if not q:
                clear_suggestions()
                return
            # buscar por nome no cache (insensível a maiúsculas)
            candidates = []
            qq = q.lower()
            seen = set()
            seen_names = set()
            for k, v in produtos_cache.items():
                try:
                    if isinstance(v, dict):
                        nome_raw = str(v.get("nome", "") or "")
                        nome = nome_raw.lower()
                        preco = float(v.get("preco_venda", 0) or 0)
                        id_val = str(v.get("id", "") or "").strip()
                        # tentar usar helper de estoque se disponível
                        estoque = 0
                        try:
                            gst = globals().get("get_stock_for_product_obj", None)
                            if callable(gst):
                                estoque = int(gst(v) or 0)
                            else:
                                estoque = int(v.get("quantidade", 0) or 0)
                        except Exception:
                            try:
                                estoque = int(v.get("quantidade", 0) or 0)
                            except Exception:
                                estoque = 0
                    else:
                        nome_raw = str(getattr(v, "nome", "") or "")
                        nome = nome_raw.lower()
                        preco = float(getattr(v, "preco_venda", 0) or 0)
                        id_val = str(getattr(v, "id", "") or "").strip()
                        estoque = 0
                        try:
                            gst = globals().get("get_stock_for_product_obj", None)
                            if callable(gst):
                                estoque = int(gst(v) or 0)
                            else:
                                estoque = int(
                                    getattr(
                                        v, "quantidade", getattr(v, "estoque_atual", 0)
                                    )
                                    or 0
                                )
                        except Exception:
                            try:
                                estoque = int(
                                    getattr(
                                        v, "quantidade", getattr(v, "estoque_atual", 0)
                                    )
                                    or 0
                                )
                            except Exception:
                                estoque = 0
                        id_val = str(getattr(v, "id", "") or "").strip()

                    if qq in nome:
                        # evitar repetir produtos com mesmo nome
                        if nome in seen_names:
                            continue
                        seen_names.add(nome)
                        # deduplicar por id quando disponível, senão por nome+preço
                        key_id = id_val if id_val else f"{nome}_{preco}"
                        if key_id in seen:
                            continue
                        seen.add(key_id)
                        # obter métrica de 'popularidade' se existir
                        pop = 0
                        try:
                            if isinstance(v, dict):
                                pop = int(v.get("vendas", v.get("vendido", 0)) or 0)
                            else:
                                pop = int(
                                    getattr(v, "vendas", getattr(v, "vendido", 0)) or 0
                                )
                        except Exception:
                            pop = 0
                        candidates.append(
                            {
                                "code": str(k),
                                "name": nome_raw,
                                "name_lower": nome,
                                "price": preco,
                                "stock": estoque,
                                "id": id_val,
                                "pop": pop,
                            }
                        )
                except Exception:
                    pass
            # Ordenar candidatos: 1) começa com query, 2) mais vendidos (pop desc), 3) ordem alfabética
            try:
                # Ordenar candidatos: 1) começa com query, 2) ordem alfabética
                # (removido ordenação por 'pop' para evitar saltos inesperados
                # ao navegar com as teclas)
                def sort_key(it):
                    starts = 0 if it["name_lower"].startswith(qq) else 1
                    return (starts, it["name_lower"])

                candidates.sort(key=sort_key)
                results = candidates[:8]
            except Exception:
                results = candidates[:8]

            suggestion_items.clear()
            suggestion_container.controls.clear()
            if not results:
                suggestion_container.visible = False
                page.update()
                return

            # Popular controles a partir da lista ordenada
            for i, it in enumerate(results):
                # normalizar para formato esperado: code, name, price, stock
                suggestion_items.append(
                    {
                        "code": it.get("code"),
                        "name": it.get("name"),
                        "price": it.get("price"),
                        "stock": it.get("stock"),
                    }
                )
                suggestion_container.controls.append(build_suggestion_control(it, i))

            suggestion_container.visible = True
            suggestion_selected_idx.current = 0
            # Garantir que o handler de teclado do Caixa esteja ativo
            try:
                kh = page.app_data.get("caixa_keyboard_handler")
                if callable(kh):
                    try:
                        page.on_keyboard_event = kh
                    except Exception:
                        pass
                    try:
                        # também restaurar em `view` se disponível
                        if (
                            globals().get("view")
                            and getattr(
                                globals().get("view"), "on_keyboard_event", None
                            )
                            != kh
                        ):
                            globals().get("view").on_keyboard_event = kh
                    except Exception:
                        pass
            except Exception:
                pass
            page.update()
        except Exception:
            pass

    def on_search_field_change(e=None):
        try:
            val = e.control.value if e and e.control else ""
            # se contém letras, ativar busca por nome
            has_letter = any((c.isalpha() for c in (val or "")))
            if has_letter:
                # garantir cache carregado antes de buscar por nome
                try:
                    if not cache_loaded.current:
                        carregar_produtos_cache(force_reload=False)
                except Exception:
                    pass
                update_suggestions(val)
            else:
                clear_suggestions()
        except Exception:
            pass

    def refresh_suggestion_highlight():
        try:
            for i, ctrl in enumerate(suggestion_container.controls):
                try:
                    ctrl.bgcolor = (
                        "#E8F7FF" if suggestion_selected_idx.current == i else None
                    )
                except Exception:
                    pass
            page.update()
        except Exception:
            pass

    def next_suggestion():
        try:
            if not suggestion_items:
                return
            suggestion_selected_idx.current = min(
                len(suggestion_items) - 1, suggestion_selected_idx.current + 1
            )
            refresh_suggestion_highlight()
        except Exception:
            pass

    def prev_suggestion():
        try:
            if not suggestion_items:
                return
            suggestion_selected_idx.current = max(
                0, suggestion_selected_idx.current - 1
            )
            refresh_suggestion_highlight()
        except Exception:
            pass

    def activate_selected_suggestion():
        try:
            if not suggestion_items:
                return
            select_suggestion_by_index(suggestion_selected_idx.current)
        except Exception:
            pass

    # Handler quando mini-botão de parcelamento é acionado
    def on_parcel_select(idx: int, count: int = 2):
        try:
            try:
                parcel_selected_ref.current = int(count)
            except Exception:
                parcel_selected_ref.current = 1
            # atualizar aparência dos mini-botões
            try:
                if payment_parcel_button_refs:
                    for j, pr in enumerate(payment_parcel_button_refs):
                        try:
                            if not pr or not getattr(pr, "current", None):
                                continue
                            if j == idx and parcel_selected_ref.current == 2:
                                pr.current.style.bgcolor = COLORS.get(
                                    "secondary", "#4CAF50"
                                )
                                pr.current.style.color = ft.Colors.WHITE
                            else:
                                pr.current.style.bgcolor = ft.Colors.WHITE
                                pr.current.style.color = ft.Colors.BLACK
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                update_payment_buttons_labels()
            except Exception:
                pass
            try:
                page.update()
            except Exception:
                pass
        except Exception:
            pass

    # Referências para status do caixa
    status_text_ref = ft.Ref[ft.Text]()

    # Painel principal do lado esquerdo (carrinho)
    def get_caixa_status():
        """Verifica se há QUALQUER sessão de caixa aberta (não apenas para este usuário)"""
        usuario_id = page.session.get("user_id")
        # Primeiro tenta a sessão do usuário atual
        sessao_caixa = pdv_core.get_current_open_session(usuario_id)
        # Se não houver, verifica se há QUALQUER sessão aberta (de qualquer usuário)
        if not sessao_caixa:
            sessao_caixa = pdv_core.get_current_open_session(None)
        if sessao_caixa:
            return "ABERTO"
        return "FECHADO"

    def get_caixa_status_color():
        return ft.Colors.GREEN if get_caixa_status() == "ABERTO" else ft.Colors.RED

    def update_status_display():
        """Atualiza o status do caixa na tela"""
        if status_text_ref.current:
            status_text_ref.current.value = get_caixa_status()
            status_text_ref.current.color = get_caixa_status_color()
            status_text_ref.current.update()

    def build_status_row():
        return ft.Row(
            [
                ft.Text(
                    "Status:",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color="#000000",
                ),
                ft.Text(
                    ref=status_text_ref,
                    value=get_caixa_status(),
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=get_caixa_status_color(),
                ),
            ],
            spacing=8,
        )

    cart_main_panel = ft.Container(
        ft.Column(
            [
                ft.Text(
                    "CAIXA LIVRE",
                    size=32,
                    weight="bold",
                    color=COLORS["primary"],
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(
                    ft.Column(
                        [
                            search_field,
                            suggestion_container,
                            product_name_text,
                            build_status_row(),
                        ],
                        spacing=5,
                    ),
                    padding=ft.padding.only(bottom=20),
                ),
                cart_header,
                ft.Container(cart_items_column, expand=True, bgcolor=COLORS["card_bg"]),
            ],
            spacing=15,
            expand=True,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.all(20),
        bgcolor=COLORS["card_bg"],
        expand=True,
        border_radius=12,
    )
    # Atualiza status visual do caixa
    # Atualiza status visual do caixa
    page.update()

    # Barra inferior com ações rápidas (cancelar venda, F6, F7, total, F12)
    # Ref para o botão de finalizar (para habilitar/desabilitar durante processamento)
    finalize_button_ref = ft.Ref[ft.FilledButton]()

    def set_finalizing(active: bool):
        try:
            is_finalizing_box.value = bool(active)
            if finalize_button_ref.current:
                finalize_button_ref.current.disabled = bool(active)
                finalize_button_ref.current.update()
        except Exception:
            pass

    # Wrapper do clique do botão FINALIZAR para assegurar seleção de pagamento padrão
    def on_click_finalizar(e=None):
        try:
            # Debug do clique
            try:
                btn_state = (
                    finalize_button_ref.current.disabled
                    if finalize_button_ref.current
                    else None
                )
            except Exception:
                btn_state = None
            print(
                f"[CLICK] FINALIZAR acionado: disabled={btn_state} is_finalizing={is_finalizing_box.value}"
            )
            # Evitar múltiplas finalizações simultâneas
            if bool(is_finalizing_box.value):
                show_snackbar("Finalização já em andamento...", COLORS["warning"])
                return
            if not selected_payment_type.current.value:
                try:
                    notify_missing_payment()
                except Exception:
                    pass
                return
        except Exception:
            pass
        # Feedback imediato para o operador de caixa
        try:
            show_snackbar("Processando finalização...", COLORS["orange"])
        except Exception:
            pass
        # Marcar como processando e desabilitar botão
        try:
            print("[CLICK] Chamando finalize_transaction...")
        except Exception:
            pass
        try:
            finalize_transaction(e)
        except Exception as ex_fin:
            print(f"[CLICK] ERRO ao chamar finalize_transaction: {ex_fin}")

    bottom_bar = ft.Container(
        ft.Row(
            [
                ft.FilledButton(
                    "CANCELAR VENDA (F11)",
                    on_click=lambda e: (
                        reset_cart(),
                        show_snackbar("Venda Cancelada.", COLORS["danger"]),
                    ),
                    style=ft.ButtonStyle(
                        bgcolor=COLORS["primary"],
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    height=38,
                    width=200,
                ),
                # NOVOS BOTÕES F6 / F7
                ft.Container(
                    ft.ElevatedButton(
                        "(F5) CONSULTAR PREÇO",
                        icon=ft.Icons.SEARCH,
                        bgcolor=COLORS["card_bg"],
                        on_click=open_price_check_dialog,
                    ),
                    shadow=ft.BoxShadow(
                        blur_radius=8,
                        spread_radius=2,
                        color="#007BFF",
                        offset=ft.Offset(2, 2),
                    ),
                ),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "(F6) ESTORNAR",
                            icon=ft.Icons.CANCEL,
                            bgcolor=COLORS["danger"],
                            color=ft.Colors.WHITE,
                            on_click=open_cancel_sale_dialog,
                            expand=True,
                        ),
                        botao_devolver_trocar,
                    ],
                    spacing=10,
                ),
                ft.Container(expand=True),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    "Subtotal:",
                                    size=20,
                                    color=COLORS["text_dark"],
                                    ref=subtotal_label_ref,
                                    visible=False,
                                ),
                                subtotal_text,
                            ],
                            spacing=10,
                            alignment=ft.MainAxisAlignment.END,
                        ),
                        ft.Row(
                            [
                                ft.Text(
                                    "Acréscimo:",
                                    size=20,
                                    color=COLORS["text_dark"],
                                    ref=acrescimo_label_ref,
                                    visible=False,
                                ),
                                acrescimo_text,
                            ],
                            spacing=10,
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ],
                    tight=True,
                ),
                ft.VerticalDivider(width=30, thickness=2, color=ft.Colors.BLACK12),
                ft.Container(
                    ft.Row(
                        [
                            ft.Text(
                                "TOTAL:",
                                size=30,
                                weight="bold",
                                color=COLORS["text_dark"],
                            ),
                            total_final_text,
                        ],
                        alignment=ft.MainAxisAlignment.END,
                        spacing=15,
                    ),
                    width=300,
                ),
                ft.FilledButton(
                    "FINALIZAR VENDA (F12)",
                    ref=finalize_button_ref,
                    icon=ft.Icons.PAYMENT,
                    on_click=on_click_finalizar,
                    style=ft.ButtonStyle(
                        bgcolor=COLORS["primary"],
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    height=38,
                    width=200,
                ),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.padding.symmetric(horizontal=20, vertical=10),
        bgcolor=COLORS["card_bg"],
        border=ft.border.only(top=ft.border.BorderSide(1, ft.Colors.BLACK12)),
    )

    # Layout principal em duas colunas: carrinho (esq) e pagamentos (dir)
    caixa_layout = ft.Row(
        [cart_main_panel, payment_options_panel],
        expand=True,
        spacing=15,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # ========================================
    # HANDLER DE TECLADO PARA CAIXA (externalizado)
    # ========================================

    caixa_keyboard_handler = build_caixa_keyboard_handler(
        page=page,
        FKEY_MAP=FKEY_MAP,
        PAYMENT_METHODS=PAYMENT_METHODS,
        select_payment=select_payment,
        payment_buttons_refs=payment_buttons_refs,
        botao_devolver_trocar=botao_devolver_trocar,
        open_price_check_dialog=open_price_check_dialog,
        open_cancel_sale_dialog=open_cancel_sale_dialog,
        last_added_product_id_box=last_added_product_id_box,
        cart_data=cart_data,
        update_cart_item=update_cart_item,
        reset_cart=reset_cart,
        show_snackbar=show_snackbar,
        COLORS=COLORS,
        on_click_finalizar=on_click_finalizar,
        handle_logout=handle_logout,
        carregar_produtos_cache=carregar_produtos_cache,
        selected_payment_ref=selected_payment_type,
        notify_missing_payment=notify_missing_payment,
        # callbacks para navegação/ativação de sugestões
        suggestion_next=next_suggestion,
        suggestion_prev=prev_suggestion,
        suggestion_activate=activate_selected_suggestion,
        suggestions_visible=lambda: bool(suggestion_container.visible),
        # parcel buttons and callback
        parcel_button_refs=payment_parcel_button_refs,
        parcel_select_callback=lambda idx, cnt: on_parcel_select(idx, cnt),
        parcel_selected_ref=parcel_selected_ref,
    )

    # Expor handler no app_data para que outras rotinas (ex: sugestões)
    # possam restaurá-lo caso seja sobrescrito por overlays temporários.
    try:
        page.app_data["caixa_keyboard_handler"] = caixa_keyboard_handler
    except Exception:
        pass

    # Expor callbacks úteis para o manipulador de teclado (desselcionar -> atualizar labels)
    try:
        page.app_data["caixa_refresh_payment_labels"] = update_payment_buttons_labels
        page.app_data["caixa_calculate_change"] = calculate_change
    except Exception:
        pass
    try:
        page.app_data["caixa_payments_list"] = payments
    except Exception:
        pass

    # Container para data e hora no canto superior esquerdo
    from datetime import datetime

    caixa_label = (page.session.get("user_display_name") or "CAIXA 1").upper()

    datetime_text = ft.Text(
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        size=16,
        color=COLORS["text_dark"],
        weight="w500",
    )

    caixa_text = ft.Text(
        caixa_label,
        size=14,
        color=COLORS["text_dark"],
        weight=ft.FontWeight.W_600,
    )

    datetime_container = ft.Container(
        content=ft.Column(
            [
                caixa_text,
                datetime_text,
            ],
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        ),
        padding=ft.padding.only(left=15, top=8, bottom=5),
    )

    # Removido título duplicado abaixo do AppBar (solicitado)

    # View associada à rota "/caixa"
    view = ft.View(
        "/caixa",
        [
            appbar,
            datetime_container,
            ft.Container(
                content=caixa_layout,
                padding=ft.padding.only(left=15, right=15, top=15, bottom=0),
                expand=True,
            ),
            # Barra de status inferior (mensagens como "Troca Confirmada" / "Venda Estornada")
            ft.Container(ref=status_bar_ref, height=0),
            bottom_bar,
        ],
        bgcolor=COLORS["background"],
    )

    # Expor handler de teclado
    view.caixa_keyboard_handler = caixa_keyboard_handler
    # Também associar diretamente ao evento de teclado da View (compat 0.28.x)
    try:
        view.on_keyboard_event = caixa_keyboard_handler
    except Exception:
        pass
    try:
        # Encadear handler local e garantir que ESC leve ao Painel Gerencial
        original_caixa_key = getattr(view, "caixa_keyboard_handler", None)

        def _caixa_combined_key(e, _orig=original_caixa_key):
            try:
                if callable(_orig):
                    _orig(e)
            except Exception:
                pass
            # Se o handler original já marcou o evento como tratado, não prosseguir
            try:
                if getattr(e, "handled", False):
                    return
            except Exception:
                pass
            # Se um modal do caixa estiver aberto, não processar atalhos globais
            try:
                if getattr(page, "app_data", {}).get("caixa_modal_open"):
                    try:
                        e.handled = True
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            try:
                key_upper = (str(e.key) or "").upper()

                # Navegação entre sugestões (quando visível)
                try:
                    if suggestion_container and getattr(
                        suggestion_container, "visible", False
                    ):
                        # descer
                        if key_upper in ("ARROWDOWN", "DOWN"):
                            try:
                                n = len(suggestion_items)
                                if n:
                                    suggestion_selected_idx.current = min(
                                        n - 1, suggestion_selected_idx.current + 1
                                    )
                                    # atualizar destaque
                                    for i, ctrl in enumerate(
                                        suggestion_container.controls
                                    ):
                                        try:
                                            ctrl.bgcolor = (
                                                "#E8F7FF"
                                                if i == suggestion_selected_idx.current
                                                else None
                                            )
                                        except Exception:
                                            pass
                                    page.update()

                                    # ----- DEBUG: auto-teste opcional (selecionar pagamento + ESC) -----
                                    try:
                                        if page.app_data.get("auto_test_payment"):
                                            try:
                                                import threading

                                                def _auto_test_sequence():
                                                    try:
                                                        # escolher primeiro método disponível
                                                        if (
                                                            PAYMENT_METHODS
                                                            and payment_buttons_refs
                                                        ):
                                                            name = (
                                                                PAYMENT_METHODS[0][
                                                                    "name"
                                                                ]
                                                                if isinstance(
                                                                    PAYMENT_METHODS[0],
                                                                    dict,
                                                                )
                                                                else str(
                                                                    PAYMENT_METHODS[0]
                                                                )
                                                            )
                                                            try:
                                                                select_payment(
                                                                    name,
                                                                    payment_buttons_refs[
                                                                        0
                                                                    ],
                                                                )
                                                            except Exception:
                                                                pass
                                                            # simular confirmação de pequeno pagamento
                                                            try:
                                                                payments.append(
                                                                    {
                                                                        "method": name,
                                                                        "amount": 1.0,
                                                                    }
                                                                )
                                                                update_payment_buttons_labels(
                                                                    selected_method=name
                                                                )
                                                                update_payment_status()
                                                            except Exception:
                                                                pass
                                                            try:
                                                                # disparar ESC local (handler da view)
                                                                class _Evt:
                                                                    def __init__(
                                                                        self, key
                                                                    ):
                                                                        self.key = key

                                                                try:
                                                                    # chamar o handler combinado local caso exista
                                                                    if callable(
                                                                        getattr(
                                                                            view,
                                                                            "on_keyboard_event",
                                                                            None,
                                                                        )
                                                                    ):
                                                                        view.on_keyboard_event(
                                                                            _Evt(
                                                                                "Escape"
                                                                            )
                                                                        )
                                                                    else:
                                                                        try:
                                                                            page.on_keyboard_event(
                                                                                _Evt(
                                                                                    "Escape"
                                                                                )
                                                                            )
                                                                        except (
                                                                            Exception
                                                                        ):
                                                                            pass
                                                                except Exception:
                                                                    pass
                                                            except Exception:
                                                                pass
                                                    except Exception:
                                                        pass

                                                t = threading.Timer(
                                                    0.8, _auto_test_sequence
                                                )
                                                t.daemon = True
                                                t.start()
                                            except Exception:
                                                pass
                                    except Exception:
                                        pass
                                    return
                            except Exception:
                                pass
                        # subir
                        if key_upper in ("ARROWUP", "UP"):
                            try:
                                if len(suggestion_items):
                                    suggestion_selected_idx.current = max(
                                        0, suggestion_selected_idx.current - 1
                                    )
                                    for i, ctrl in enumerate(
                                        suggestion_container.controls
                                    ):
                                        try:
                                            ctrl.bgcolor = (
                                                "#E8F7FF"
                                                if i == suggestion_selected_idx.current
                                                else None
                                            )
                                        except Exception:
                                            pass
                                    page.update()
                                    return
                            except Exception:
                                pass
                        # Enter: selecionar
                        if key_upper in ("ENTER", "RETURN"):
                            try:
                                select_suggestion_by_index(
                                    suggestion_selected_idx.current
                                )
                                return
                            except Exception:
                                pass
                except Exception:
                    pass

                if key_upper == "ESCAPE":
                    # Primeiro: se houver overlays/dialogs abertos, fechar o mais superior
                    try:
                        overlays = getattr(page, "overlay", []) or []
                        for ov in reversed(list(overlays)):
                            try:
                                if getattr(ov, "open", False):
                                    ov.open = False
                                    try:
                                        if ov in getattr(page, "overlay", []):
                                            page.overlay.remove(ov)
                                    except Exception:
                                        pass
                                    try:
                                        try:
                                            page.app_data[
                                                "caixa_last_modal_closed_ts"
                                            ] = time.time()
                                        except Exception:
                                            pass
                                        try:
                                            page.app_data[
                                                "caixa_prevent_handle_back"
                                            ] = True
                                        except Exception:
                                            pass
                                    except Exception:
                                        pass
                                    try:
                                        e.handled = True
                                    except Exception:
                                        pass
                                    page.update()
                                    return
                            except Exception:
                                pass
                            try:
                                if getattr(ov, "visible", False):
                                    try:
                                        ov.visible = False
                                    except Exception:
                                        pass
                                    try:
                                        if ov in getattr(page, "overlay", []):
                                            page.overlay.remove(ov)
                                    except Exception:
                                        pass
                                    try:
                                        try:
                                            page.app_data[
                                                "caixa_last_modal_closed_ts"
                                            ] = time.time()
                                        except Exception:
                                            pass
                                        try:
                                            page.app_data[
                                                "caixa_prevent_handle_back"
                                            ] = True
                                        except Exception:
                                            pass
                                    except Exception:
                                        pass
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

                    # Se não havia overlays abertos: desselecionar método de pagamento (se houver)
                    try:
                        sel = None
                        try:
                            sel = selected_payment_type.current.value
                        except Exception:
                            try:
                                sel = getattr(selected_payment_type, "value", None)
                            except Exception:
                                sel = None

                        if sel:
                            try:
                                selected_payment_type.current.value = None
                            except Exception:
                                try:
                                    setattr(selected_payment_type, "value", None)
                                except Exception:
                                    pass

                            # evitar que o ESC provoque navegação para fora do Caixa
                            try:
                                e.handled = True
                            except Exception:
                                pass
                            try:
                                page.app_data["caixa_prevent_handle_back"] = True
                            except Exception:
                                pass
                            try:
                                page.app_data["caixa_last_modal_closed_ts"] = (
                                    time.time()
                                )
                            except Exception:
                                pass

                            # esconder campos por método (não remover pagamentos confirmados)
                            try:
                                if payment_value_field_refs:
                                    for v_ref in payment_value_field_refs:
                                        try:
                                            if getattr(v_ref, "current", None):
                                                try:
                                                    v_ref.current.visible = False
                                                except Exception:
                                                    pass
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                            try:
                                # recalcular para ocultar Subtotal/Acréscimo quando desselecionado
                                try:
                                    _actions.calculate_total()
                                    print(
                                        "[DESELECT-PAYMENT] called _actions.calculate_total()"
                                    )
                                except Exception as ex:
                                    print(
                                        f"[DESELECT-PAYMENT] erro chamando _actions.calculate_total: {ex}"
                                    )
                            except Exception:
                                pass

                            try:
                                update_payment_buttons_labels()
                            except Exception:
                                pass
                            try:
                                update_payment_status()
                            except Exception:
                                pass
                            try:
                                # Restaurar estilo visual dos botões de pagamento
                                if payment_buttons_refs:
                                    for i, b_ref in enumerate(payment_buttons_refs):
                                        try:
                                            if not b_ref or not getattr(
                                                b_ref, "current", None
                                            ):
                                                continue
                                            pm = PAYMENT_METHODS[i]
                                            pm_name = (
                                                pm.get("name")
                                                if isinstance(pm, dict)
                                                else str(pm)
                                            )
                                            # verificar se esse método já foi pago
                                            paid = any(
                                                (
                                                    float(p.get("amount", 0) or 0) > 0
                                                    and p.get("method") == pm_name
                                                )
                                                for p in payments
                                            )
                                            if paid:
                                                b_ref.current.style.bgcolor = (
                                                    COLORS.get("secondary", "#4CAF50")
                                                )
                                                b_ref.current.style.color = (
                                                    ft.Colors.WHITE
                                                )
                                                b_ref.current.style.side = (
                                                    ft.border.BorderSide(
                                                        1, ft.Colors.BLACK12
                                                    )
                                                )
                                            else:
                                                b_ref.current.style.bgcolor = (
                                                    ft.Colors.WHITE
                                                )
                                                b_ref.current.style.color = (
                                                    ft.Colors.BLACK
                                                )
                                                b_ref.current.style.side = (
                                                    ft.border.BorderSide(
                                                        1, ft.Colors.BLACK12
                                                    )
                                                )
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                            page.update()
                            return

                        # Se não há seleção e o usuário for gerente, permitir voltar ao painel gerencial
                        try:
                            role_val = None
                            try:
                                role_val = role
                            except Exception:
                                try:
                                    role_val = page.session.get("role")
                                except Exception:
                                    role_val = None
                            # debug log
                            try:
                                print(
                                    f"[CAIXA-ESC-DEBUG] sel={sel} role_val={role_val} handle_back_exists={callable(handle_back)}"
                                )
                            except Exception:
                                pass
                            if role_val and str(role_val).lower() == "gerente":
                                try:
                                    # se fechou um modal há pouco, não voltar ao painel
                                    try:
                                        if page.app_data.get(
                                            "caixa_prevent_handle_back"
                                        ):
                                            try:
                                                print(
                                                    "[CAIXA-ESC-DEBUG] prevent flag set; skipping handle_back and clearing flag"
                                                )
                                            except Exception:
                                                pass
                                            try:
                                                page.app_data[
                                                    "caixa_prevent_handle_back"
                                                ] = False
                                            except Exception:
                                                pass
                                            return
                                    except Exception:
                                        pass
                                    try:
                                        last = page.app_data.get(
                                            "caixa_last_modal_closed_ts", 0
                                        )
                                        if last and (time.time() - float(last) < 0.6):
                                            try:
                                                print(
                                                    "[CAIXA-ESC-DEBUG] recent modal closed; skipping handle_back"
                                                )
                                            except Exception:
                                                pass
                                            return
                                    except Exception:
                                        pass

                                    if callable(handle_back):
                                        print(
                                            "[CAIXA-ESC-DEBUG] calling handle_back(None) now"
                                        )
                                        handle_back(None)
                                        return
                                    else:
                                        print(
                                            "[CAIXA-ESC-DEBUG] handle_back not callable"
                                        )
                                except Exception as ex:
                                    print(
                                        f"[CAIXA-ESC-DEBUG] error calling handle_back: {ex}"
                                    )
                        except Exception as e:
                            print(f"[CAIXA-ESC-DEBUG] unexpected error: {e}")
                    except Exception:
                        pass
            except Exception:
                pass

        view.on_keyboard_event = _caixa_combined_key
        try:
            view.handle_keyboard_shortcuts = _caixa_combined_key
        except Exception:
            pass
    except Exception:
        pass
    # Compatibilidade com o despachante do app: ele procura por `handle_keyboard_shortcuts`
    # então expomos o mesmo handler também com esse nome.
    try:
        view.handle_keyboard_shortcuts = caixa_keyboard_handler
    except Exception:
        pass
    # Expor finalização para fallback global (F12)
    try:
        view.on_click_finalizar = on_click_finalizar
    except Exception:
        pass
    try:
        view.finalize_transaction = finalize_transaction
    except Exception:
        pass

    # Handler chamado quando a view vai aparecer
    def on_view_will_appear(e):
        print("[CAIXA] View apareceu - inicializando")

        # Garantir estado inicial: sem forma de pagamento selecionada e sem subtotal/acréscimo
        try:
            try:
                if getattr(selected_payment_type, "current", None):
                    selected_payment_type.current.value = None
            except Exception:
                try:
                    setattr(selected_payment_type, "current", None)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            try:
                subtotal_text.visible = False
            except Exception:
                pass
            try:
                acrescimo_text.visible = False
            except Exception:
                pass
            try:
                total_final_text.value = f"R$ {0.0:.2f}".replace(".", ",")
            except Exception:
                pass
            try:
                page.update()
            except Exception:
                pass
        except Exception:
            pass
        # Compatibilidade: forçar fundo da página para o background da aplicação.
        # Em versões recentes do Flet o `page.bgcolor` pode ser alterado por temas
        # ou componentes; garantir branco aqui evita a tela cinza observada.
        try:
            page.bgcolor = COLORS["background"]
            try:
                view.bgcolor = COLORS["background"]
            except Exception:
                pass
            try:
                page.update()
            except Exception:
                pass
        except Exception:
            pass

        # Remover SnackBar persistentes que possam cobrir a tela (causa da tela cinza)
        try:
            removed_snack = 0
            ov_list = list(getattr(page, "overlay", []))
            for ov in ov_list:
                try:
                    is_snack = False
                    try:
                        if isinstance(ov, ft.SnackBar):
                            is_snack = True
                    except Exception:
                        pass
                    try:
                        # fallback: checar nome do tipo ou atributo interno `_c`
                        if not is_snack and (
                            type(ov).__name__ == "SnackBar"
                            or getattr(ov, "_c", None) == "SnackBar"
                        ):
                            is_snack = True
                    except Exception:
                        pass

                    if is_snack:
                        try:
                            # tentar fechar via propriedade `open` quando disponível
                            try:
                                ov.open = False
                            except Exception:
                                pass
                            if ov in getattr(page, "overlay", []):
                                try:
                                    page.overlay.remove(ov)
                                except Exception:
                                    pass
                            # Log detalhado da remoção
                            try:
                                print(
                                    f"[CAIXA-DEBUG] Removed SnackBar overlay id={id(ov)} bgcolor={getattr(ov, 'bgcolor', None)} open={getattr(ov, 'open', None)} repr={repr(ov)[:200]}"
                                )
                            except Exception:
                                print(
                                    f"[CAIXA-DEBUG] Removed SnackBar overlay id={id(ov)}"
                                )
                            removed_snack += 1
                        except Exception:
                            pass
                except Exception:
                    pass

            # Também garantir que `page.snack_bar` seja fechado e limpo
            try:
                sb = getattr(page, "snack_bar", None)
                if sb is not None:
                    try:
                        if (
                            isinstance(sb, ft.SnackBar)
                            or type(sb).__name__ == "SnackBar"
                        ):
                            try:
                                sb.open = False
                            except Exception:
                                pass
                            try:
                                if sb in getattr(page, "overlay", []):
                                    try:
                                        page.overlay.remove(sb)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            try:
                                page.snack_bar = None
                            except Exception:
                                pass
                            try:
                                print(
                                    f"[CAIXA-DEBUG] Removed page.snack_bar id={id(sb)} bgcolor={getattr(sb, 'bgcolor', None)} open={getattr(sb, 'open', None)} repr={repr(sb)[:200]}"
                                )
                            except Exception:
                                print("[CAIXA-DEBUG] Removed page.snack_bar")
                            removed_snack += 1
                    except Exception:
                        pass
            except Exception:
                pass

            if removed_snack:
                print(
                    f"[CAIXA-DEBUG] Removed {removed_snack} SnackBar overlay(s) on enter"
                )
                try:
                    page.update()
                except Exception:
                    pass
        except Exception:
            pass

        # DEBUG: listar overlays presentes ao entrar na view
        try:
            ov_count = (
                len(page.overlay) if getattr(page, "overlay", None) is not None else 0
            )
            print(f"[CAIXA-DEBUG] overlays before cleanup: {ov_count}")
            idx = 0
            for ov in list(getattr(page, "overlay", [])):
                try:
                    bg = getattr(ov, "bgcolor", None)
                    exp = getattr(ov, "expand", None)
                    vis = getattr(ov, "visible", None)
                    t = type(ov)
                    print(
                        f"[CAIXA-DEBUG] overlay[{idx}] type={t.__name__} bgcolor={bg} expand={exp} visible={vis}"
                    )
                except Exception as _:
                    print(f"[CAIXA-DEBUG] overlay[{idx}] repr={repr(ov)}")
                idx += 1
        except Exception as _:
            pass

        # Debug: remover overlays full-screen sem querer (prevenção de tela cinza)
        try:
            removed = 0
            for ov in list(page.overlay):
                try:
                    bg = getattr(ov, "bgcolor", None)
                    exp = getattr(ov, "expand", False)
                    vis = getattr(ov, "visible", None)
                    # Remover overlays que parecem máscaras (expand full-screen e bgcolor semitransparente)
                    if (
                        exp
                        and isinstance(bg, str)
                        and (
                            "rgba(0, 0, 0" in bg
                            or "transparent" not in bg
                            and bg.strip().lower() in ("#000000", "#000", "black")
                        )
                    ):
                        try:
                            page.overlay.remove(ov)
                            removed += 1
                            print(
                                f"[CAIXA-DEBUG] Removed suspicious overlay: bgcolor={bg}, visible={vis}"
                            )
                        except Exception:
                            pass
                except Exception:
                    pass
            if removed:
                try:
                    page.update()
                except Exception:
                    pass
        except Exception:
            pass

        # Se este operador for o user_caixa e o caixa estiver FECHADO,
        # desabilitar campos e botões para deixar a tela no modo 'FECHADO'.
        try:
            if is_user_caixa and get_caixa_status() == "FECHADO":
                try:
                    # Desabilitar campo de busca
                    search_field.disabled = True
                    search_field.autofocus = False
                    if search_field_ref.current:
                        try:
                            search_field_ref.current.disabled = True
                        except Exception:
                            pass
                except Exception:
                    pass

                # Desabilitar botões de pagamento
                for btn_ref in payment_buttons_refs:
                    try:
                        if btn_ref.current:
                            try:
                                btn_ref.current.disabled = True
                            except Exception:
                                pass
                            try:
                                btn_ref.current.style.bgcolor = ft.Colors.GREY_200
                            except Exception:
                                pass
                            try:
                                btn_ref.current.update()
                            except Exception:
                                pass
                    except Exception:
                        pass

                # Esconder campo de valor recebido e troco
                try:
                    money_received_field.current = money_received_field.current
                    if money_received_input:
                        money_received_input.visible = False
                except Exception:
                    pass
                try:
                    if change_display:
                        change_display.visible = False
                except Exception:
                    pass

                try:
                    page.update()
                except Exception:
                    pass
        except Exception:
            pass

        # Vincular handler de teclado diretamente na página enquanto a view estiver ativa
        try:
            page.on_keyboard_event = caixa_keyboard_handler
        except Exception:
            pass

        # Garantir que o botão de finalizar esteja habilitado ao entrar
        try:
            if finalize_button_ref.current:
                finalize_button_ref.current.disabled = False
                finalize_button_ref.current.update()
                print("[CAIXA] FINALIZAR habilitado na entrada da view")
        except Exception:
            pass

        # Certificar que o search_field tem foco para poder digitar
        if search_field_ref.current:
            search_field_ref.current.focus()
        if search_field_ref.current:
            search_field_ref.current.focus()

        # Tarefa de relógio via helpers
        run_clock_task(page, datetime_text)

        if carregar_produtos_cache():
            print("✅ Cache carregado na inicialização")
        else:
            print(" Cache vazio na inicialização, tentando novamente...")
            page.run_task(
                lambda: (page.sleep(300), carregar_produtos_cache(force_reload=True))
            )

        if search_field_ref.current:
            search_field_ref.current.focus()

        # Inicializar labels de pagamento e status
        try:
            update_payment_buttons_labels()
        except Exception:
            pass
        try:
            update_payment_status()
        except Exception:
            pass

        # Garantir que ao entrar na view Subtotal/Acréscimo fiquem ocultos
        try:
            sel = None
            try:
                sel = getattr(selected_payment_type.current, "value", None)
            except Exception:
                sel = None
            if sel != "Crédito":
                try:
                    subtotal_text.visible = False
                except Exception:
                    pass
                try:
                    acrescimo_text.visible = False
                except Exception:
                    pass
                try:
                    if getattr(subtotal_label_ref, "current", None):
                        subtotal_label_ref.current.visible = False
                except Exception:
                    pass
                try:
                    if getattr(acrescimo_label_ref, "current", None):
                        acrescimo_label_ref.current.visible = False
                except Exception:
                    pass
                try:
                    # atualizar total exibido sem acréscimo
                    total_val = 0.0
                    try:
                        total_val = float(total_value.current.get())
                    except Exception:
                        try:
                            total_val = float(total_value.current)
                        except Exception:
                            total_val = 0.0
                    try:
                        total_final_text.value = f"R$ {total_val:.2f}".replace(".", ",")
                    except Exception:
                        pass
                except Exception:
                    pass
            else:
                try:
                    # se já estiver credito selecionado, recalcular para exibir corretamente
                    # e mostrar labels
                    calculate_total()
                    try:
                        if getattr(subtotal_label_ref, "current", None):
                            subtotal_label_ref.current.visible = True
                    except Exception:
                        pass
                    try:
                        if getattr(acrescimo_label_ref, "current", None):
                            acrescimo_label_ref.current.visible = True
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

        # Monitor de máscaras escuras via helpers
        monitor = make_monitor_dark_masks(page, view)
        page.run_task(monitor)

    view.on_view_will_appear = on_view_will_appear

    # Remover handler quando sair da view
    def on_view_will_disappear():
        print("[CAIXA] Removendo handler de teclado...")
        # NÃO remover o handler completamente - o app.py gerencia isso globalmente
        # Apenas log para debug
        # Garantir que overlays/modal provenientes desta view sejam fechados
        try:
            # Overlays simples
            try:
                if price_check_dialog_ref and getattr(
                    price_check_dialog_ref, "current", None
                ):
                    dlg = price_check_dialog_ref.current
                    if dlg in page.overlay:
                        page.overlay.remove(dlg)
            except Exception:
                pass

            try:
                if cancel_sale_dialog_ref and getattr(
                    cancel_sale_dialog_ref, "current", None
                ):
                    dlg = cancel_sale_dialog_ref.current
                    if dlg in page.overlay:
                        page.overlay.remove(dlg)
            except Exception:
                pass

            try:
                # Remove any pix_overlay Container by type (since it's not globally available here)
                overlays_to_remove = [
                    ov
                    for ov in page.overlay
                    if type(ov).__name__ == "Container"
                    and getattr(ov, "bgcolor", None) == "rgba(0, 0, 0, 0.5)"
                ]
                for ov in overlays_to_remove:
                    page.overlay.remove(ov)
            except Exception:
                pass

            # AlertDialogs referenciados
            try:
                if cancel_sale_dialog_ref and getattr(
                    cancel_sale_dialog_ref, "current", None
                ):
                    cancel = cancel_sale_dialog_ref.current
                    try:
                        cancel.open = False
                    except Exception:
                        pass
                    try:
                        if cancel in page.overlay:
                            page.overlay.remove(cancel)
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                if price_check_dialog_ref and getattr(
                    price_check_dialog_ref, "current", None
                ):
                    dlg = price_check_dialog_ref.current
                    try:
                        dlg.open = False
                    except Exception:
                        pass
                    try:
                        if dlg in page.overlay:
                            page.overlay.remove(dlg)
                    except Exception:
                        pass
            except Exception:
                pass

            # Atualizar a página para remover qualquer máscara visual
            try:
                page.update()
            except Exception:
                pass
        except Exception:
            pass

    view.on_view_will_disappear = on_view_will_disappear

    # Expor hooks de teste para permitir testes automatizados externos
    try:
        view.__test_api__ = {
            "add_to_cart": add_to_cart,
            "update_cart_item": update_cart_item,
            "calculate_total": calculate_total,
            "add_by_code": add_by_code,
        }
    except Exception:
        pass
    # Não exibir mensagens de boas-vindas automáticas nesta view.

    # Modo de teste (disparado externamente via page.app_data['auto_test_f7']):
    # caso a flag seja setada por testes, apenas abrir o diálogo.
    try:
        if getattr(page, "app_data", {}).get("auto_test_f7"):
            try:
                open_cancel_sale_dialog()
            except Exception:
                pass
    except Exception:
        pass

    return view
