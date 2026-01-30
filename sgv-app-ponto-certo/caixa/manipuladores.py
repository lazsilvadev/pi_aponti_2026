"""Manipuladores extraídos da view do Caixa.

Fornece um factory `build_caixa_keyboard_handler(...)` que retorna o
manipulador de teclado usado pela view. O manipulador delega ações para callbacks
passadas pela view, mantendo o estado (cart_data, refs) na view.
"""

from typing import Callable

import flet as ft


def build_caixa_keyboard_handler(
    page: ft.Page,
    FKEY_MAP: dict,
    PAYMENT_METHODS: list,
    select_payment: Callable,
    payment_buttons_refs: list,
    botao_devolver_trocar,
    open_price_check_dialog: Callable,
    open_cancel_sale_dialog: Callable,
    last_added_product_id_box,
    cart_data: dict,
    update_cart_item: Callable,
    reset_cart: Callable,
    show_snackbar: Callable,
    COLORS: dict,
    on_click_finalizar: Callable,
    handle_logout: Callable,
    carregar_produtos_cache: Callable,
    # novo: referência para verificar se há forma de pagamento selecionada
    selected_payment_ref=None,
    # novo: callback para notificar que falta selecionar pagamento (exibe appbar)
    notify_missing_payment: Callable = None,
    # callbacks para navegação/ativação de sugestões (opcional)
    suggestion_next: Callable = None,
    suggestion_prev: Callable = None,
    suggestion_activate: Callable = None,
    suggestions_visible: Callable = None,
    # refs e callback para mini-botões de parcelamento (ex.: 2x)
    parcel_button_refs: list = None,
    parcel_select_callback: Callable = None,
    parcel_selected_ref: object = None,
):
    """Retorna uma função de manipulador de teclado para a view do Caixa.

            last = page.app_data.get("caixa_last_modal_closed_ts", 0)
            handled_overlay = False
    são passados ao handler, mantendo-o como um wrapper leve.
    """

    def caixa_keyboard_handler(e: ft.KeyboardEvent):
        # Se houver um modal do Caixa aberto (flag), consumir o evento para
        # evitar que o handler global processe ESC enquanto modal aberto.
        try:
            if page.app_data.get("caixa_modal_open"):
                try:
                    overlays_now = getattr(page, "overlay", []) or []
                    dialog_now = getattr(page, "dialog", None)
                    # se não houver overlays nem dialog, limpar flag stale
                    if not overlays_now and not dialog_now:
                        try:
                            page.app_data["caixa_modal_open"] = False
                        except Exception:
                            pass
                    else:
                        try:
                            e.handled = True
                        except Exception:
                            pass
                        return
                except Exception:
                    try:
                        e.handled = True
                    except Exception:
                        pass
                    return
        except Exception:
            pass

        # Se a modal do Caixa foi fechada pela view há pouco, ignorar este evento
        try:
            import time

            last = page.app_data.get("caixa_last_modal_closed_ts", 0)
            if last and (time.time() - float(last) < 0.6):
                return
        except Exception:
            pass

        key = str(e.key).upper() if e.key else ""
        print(f"[CAIXA-HANDLER] ⌨️ Tecla: '{key}' (original: '{e.key}')")
        try:
            state_modal = page.app_data.get("caixa_modal_open")
            dialog_now = getattr(page, "dialog", None)
            overlays_now = getattr(page, "overlay", []) or []
            print(
                f"[CAIXA-HANDLER] state: caixa_modal_open={state_modal} dialog={type(dialog_now).__name__ if dialog_now else None} overlays_count={len(overlays_now)}"
            )
        except Exception:
            pass

        try:
            # F1 a F4: Métodos de pagamento
            if key in FKEY_MAP:
                idx = FKEY_MAP[key]
                if idx < len(PAYMENT_METHODS):
                    method = PAYMENT_METHODS[idx]
                    print(
                        f"[CAIXA-HANDLER] ✅ Selecionando {method['name']} (F{idx + 1})"
                    )
                    btn_ref = payment_buttons_refs[idx]
                    select_payment(method["name"], btn_ref)
                    page.update()
                return

            # F7: Devolver & Trocar (mapeado para F7 now)
            if key == "F7":
                print("[CAIXA-HANDLER] (F7) TROCA")
                try:
                    # limpar flag stale se não houver dialog/overlays
                    if page.app_data.get("caixa_modal_open"):
                        if not (getattr(page, "overlay", []) or []) and not getattr(
                            page, "dialog", None
                        ):
                            try:
                                page.app_data["caixa_modal_open"] = False
                            except Exception:
                                pass
                except Exception:
                    pass
                if botao_devolver_trocar and getattr(
                    botao_devolver_trocar, "on_click", None
                ):
                    try:
                        botao_devolver_trocar.on_click(None)
                    except Exception:
                        pass
                return

            # F5: Consulta de Preço (mapeado para F5)
            if key == "F5":
                print("[CAIXA-HANDLER] (F5) CONSULTAR PREÇO")
                open_price_check_dialog()
                return

            # F6: Cancelar Venda (Estornar)
            if key == "F6":
                print("[CAIXA-HANDLER] (F6) ESTORNAR")
                try:
                    # limpar flag stale se não houver dialog/overlays
                    if page.app_data.get("caixa_modal_open"):
                        if not (getattr(page, "overlay", []) or []) and not getattr(
                            page, "dialog", None
                        ):
                            try:
                                page.app_data["caixa_modal_open"] = False
                            except Exception:
                                pass
                except Exception:
                    pass
                open_cancel_sale_dialog()
                return

            # F8: Diminuir Qtd
            if key == "F8":
                print("[CAIXA-HANDLER] F8 - Diminuir Qtd")
                if (
                    last_added_product_id_box.value
                    and last_added_product_id_box.value in cart_data
                ):
                    update_cart_item(last_added_product_id_box.value, -1)
                return

            # F9: Aumentar Qtd
            if key == "F9":
                print("[CAIXA-HANDLER] F9 - Aumentar Qtd")
                if (
                    last_added_product_id_box.value
                    and last_added_product_id_box.value in cart_data
                ):
                    update_cart_item(last_added_product_id_box.value, 1)
                return

            # F11: Cancelar
            if key == "F11":
                print("[CAIXA-HANDLER] F11 - Cancelar")
                reset_cart()
                show_snackbar("Venda Cancelada.", COLORS["danger"])
                return

            # F12: Finalizar (aceitar Enter+Ctrl também)
            ctrl = False
            try:
                ctrl = bool(getattr(e, "ctrl", False))
            except Exception:
                ctrl = False
            if key == "F12" or (ctrl and key in ("F12", "ENTER", "RETURN")):
                # Se não houver forma de pagamento selecionada, não disparar
                # a finalização via atalho. Em vez disso, notificar a view
                # para exibir a appbar de aviso (se fornecido).
                try:
                    if selected_payment_ref and getattr(
                        selected_payment_ref, "current", None
                    ):
                        sel = getattr(selected_payment_ref.current, "value", None)
                    else:
                        sel = None
                except Exception:
                    sel = None

                if not sel:
                    print(
                        "[CAIXA-HANDLER] F12 pressionado, mas sem forma selecionada - ignorando atalho"
                    )
                    try:
                        if callable(notify_missing_payment):
                            notify_missing_payment()
                        else:
                            # fallback: feedback rápido
                            show_snackbar(
                                "Escolha uma forma de pagamento antes de finalizar.",
                                COLORS.get("warning", "#f0ad4e"),
                            )
                    except Exception:
                        pass
                    return

                print("[CAIXA-HANDLER] F12 - Finalizar Venda")
                try:
                    show_snackbar("Finalizando (F12)...", COLORS["orange"])
                except Exception:
                    pass
                # Reutiliza o fluxo de finalização da view
                try:
                    on_click_finalizar()
                except Exception as ex:
                    print(f"[CAIXA-HANDLER] Erro em finalizar: {ex}")
                return

            # ESC: primeiro fechar qualquer overlay/dialog aberto (F6/F7)
            if key == "ESCAPE":
                print("[CAIXA-HANDLER] ESC pressionado")
                import time

                try:
                    overlays_now = getattr(page, "overlay", []) or []
                    if overlays_now:
                        try:
                            e.handled = True
                        except Exception:
                            pass
                except Exception:
                    pass

                try:
                    overlays = getattr(page, "overlay", []) or []
                    # Se existe um dialog atribuído (AlertDialog) aberto, fechá-lo
                    try:
                        dialog_now = getattr(page, "dialog", None)
                        if dialog_now and getattr(dialog_now, "open", False):
                            try:
                                dialog_now.open = False
                            except Exception:
                                pass
                            try:
                                # remover referência ao dialog para forçar limpeza
                                page.dialog = None
                            except Exception:
                                pass
                            try:
                                page.app_data["caixa_last_modal_closed_ts"] = (
                                    time.time()
                                )
                            except Exception:
                                pass
                            try:
                                page.app_data["caixa_prevent_handle_back"] = True
                            except Exception:
                                pass
                            try:
                                e.handled = True
                            except Exception:
                                pass
                            try:
                                page.update()
                            except Exception:
                                pass
                            return
                    except Exception:
                        pass
                    for ov in reversed(list(overlays)):
                        try:
                            if getattr(ov, "open", False):
                                print(
                                    f"[CAIXA-DEBUG] Manipulador fechando AlertDialog overlay={type(ov).__name__}"
                                )
                                ov.open = False
                                try:
                                    if ov in getattr(page, "overlay", []):
                                        page.overlay.remove(ov)
                                        print(
                                            f"[CAIXA-DEBUG] Manipulador removeu de page.overlay: {type(ov).__name__}"
                                        )
                                except Exception:
                                    pass
                                try:
                                    try:
                                        page.app_data["caixa_last_modal_closed_ts"] = (
                                            time.time()
                                        )
                                    except Exception:
                                        pass
                                    try:
                                        page.app_data["caixa_prevent_handle_back"] = (
                                            True
                                        )
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
                                        page.app_data["caixa_last_modal_closed_ts"] = (
                                            time.time()
                                        )
                                    except Exception:
                                        pass
                                    try:
                                        page.app_data["caixa_prevent_handle_back"] = (
                                            True
                                        )
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
                    # Remoção agressiva: detectar camadas 'dim' com bgcolor rgba e removê-las
                    try:
                        for ov in reversed(list(getattr(page, "overlay", []) or [])):
                            try:
                                bg = getattr(ov, "bgcolor", None)
                                if isinstance(bg, str) and "rgba" in bg.lower():
                                    try:
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
                                            print(
                                                f"[CAIXA-DEBUG] Removed rgba overlay: {type(ov).__name__}"
                                            )
                                    except Exception:
                                        pass
                                    try:
                                        page.app_data["caixa_last_modal_closed_ts"] = (
                                            time.time()
                                        )
                                    except Exception:
                                        pass
                                    try:
                                        page.app_data["caixa_prevent_handle_back"] = (
                                            True
                                        )
                                    except Exception:
                                        pass
                                    try:
                                        e.handled = True
                                    except Exception:
                                        pass
                                    try:
                                        page.update()
                                    except Exception:
                                        pass
                                    return
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass

                # Se não havia overlays abertos, usar ESC para desselcionar
                # o parcelamento 2x quando ativo; caso contrário, apenas permanecer
                # na tela do Caixa.
                try:
                    if (
                        parcel_selected_ref
                        and getattr(parcel_selected_ref, "current", None) == 2
                    ):
                        sel = None
                        try:
                            if selected_payment_ref and getattr(
                                selected_payment_ref, "current", None
                            ):
                                sel = getattr(
                                    selected_payment_ref.current, "value", None
                                )
                        except Exception:
                            sel = None
                        if sel == "Crédito" and callable(parcel_select_callback):
                            try:
                                credit_idx = None
                                try:
                                    for ii, m in enumerate(PAYMENT_METHODS):
                                        name = (
                                            m.get("name")
                                            if isinstance(m, dict)
                                            else str(m)
                                        )
                                        if name == "Crédito":
                                            credit_idx = ii
                                            break
                                except Exception:
                                    credit_idx = 0
                                if credit_idx is None:
                                    credit_idx = 0
                                parcel_select_callback(credit_idx, 1)
                                try:
                                    page.update()
                                except Exception:
                                    pass
                                return
                            except Exception:
                                pass
                except Exception:
                    pass

                # Se houve uma forma de pagamento selecionada, desselcioná-la
                try:
                    sel_pay = None
                    if selected_payment_ref and getattr(
                        selected_payment_ref, "current", None
                    ):
                        try:
                            sel_pay = getattr(
                                selected_payment_ref.current, "value", None
                            )
                        except Exception:
                            sel_pay = None
                    if sel_pay:
                        try:
                            # desselcionar semanticamente
                            try:
                                if (
                                    getattr(selected_payment_ref.current, "value", None)
                                    is not None
                                ):
                                    selected_payment_ref.current.value = None
                                else:
                                    try:
                                        setattr(selected_payment_ref, "current", None)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            # remover último pagamento confirmado para este método (se existir)
                            try:
                                payments_list = page.app_data.get("caixa_payments_list")
                                if isinstance(payments_list, list):
                                    for pi in range(len(payments_list) - 1, -1, -1):
                                        try:
                                            if (
                                                payments_list[pi].get("method")
                                                == sel_pay
                                            ):
                                                payments_list.pop(pi)
                                                break
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                            # reset visual dos botões de pagamento (remover destaque)
                            if payment_buttons_refs:
                                for pref in payment_buttons_refs:
                                    try:
                                        if not pref or not getattr(
                                            pref, "current", None
                                        ):
                                            continue
                                        pref.current.style.bgcolor = ft.Colors.WHITE
                                        pref.current.style.color = ft.Colors.BLACK
                                        try:
                                            pref.current.style.side = (
                                                ft.border.BorderSide(
                                                    1, ft.Colors.BLACK12
                                                )
                                            )
                                        except Exception:
                                            pass
                                    except Exception:
                                        pass
                            try:
                                # após desselcionar, forçar atualização dos labels dos botões
                                try:
                                    cb = page.app_data.get(
                                        "caixa_refresh_payment_labels"
                                    )
                                    if callable(cb):
                                        try:
                                            cb()
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                page.update()
                            except Exception:
                                pass
                            return
                        except Exception:
                            pass
                except Exception:
                    pass

                return

            # Navegação de sugestões via setas quando visíveis
            try:
                sv = (
                    bool(suggestions_visible())
                    if callable(suggestions_visible)
                    else False
                )
            except Exception:
                sv = False

            if key in ("ARROW DOWN", "ARROWDOWN", "DOWN") or e.key in (
                "ArrowDown",
                "Down",
            ):
                if sv and callable(suggestion_next):
                    try:
                        suggestion_next()
                    except Exception:
                        pass
                    return

            if key in ("ARROW UP", "ARROWUP", "UP") or e.key in (
                "ArrowUp",
                "Up",
            ):
                if sv and callable(suggestion_prev):
                    try:
                        suggestion_prev()
                    except Exception:
                        pass
                    return

            # ENTER: ativar sugestão quando visível, caso contrário ignorar (TextField trata)
            if key in ("ENTER", "RETURN") or e.key in (
                "Enter",
                "Return",
                "\r",
                "NewLine",
            ):
                if sv and callable(suggestion_activate):
                    try:
                        suggestion_activate()
                    except Exception:
                        pass
                    return
                print(
                    "[CAIXA-HANDLER] ENTER detectado - IGNORANDO (tratado pelo TextField)"
                )
                return

            # Atalho rápido: tecla '2' seleciona parcelamento 2x quando Crédito estiver selecionado
            if key == "2":
                try:
                    sv = (
                        bool(suggestions_visible())
                        if callable(suggestions_visible)
                        else False
                    )
                except Exception:
                    sv = False
                if not sv:
                    try:
                        sel = None
                        if selected_payment_ref and getattr(
                            selected_payment_ref, "current", None
                        ):
                            sel = getattr(selected_payment_ref.current, "value", None)
                        if sel == "Crédito" and callable(parcel_select_callback):
                            try:
                                # encontrar índice do método Crédito para passar ao callback
                                credit_idx = None
                                try:
                                    for ii, m in enumerate(PAYMENT_METHODS):
                                        name = (
                                            m.get("name")
                                            if isinstance(m, dict)
                                            else str(m)
                                        )
                                        if name == "Crédito":
                                            credit_idx = ii
                                            break
                                except Exception:
                                    credit_idx = 0
                                if credit_idx is None:
                                    credit_idx = 0
                                parcel_select_callback(credit_idx, 2)
                            except Exception:
                                pass
                            return
                    except Exception:
                        pass

            print(f"[CAIXA-HANDLER] Tecla '{key}' não mapeada (e.key='{e.key}')")

        except Exception as ex:
            print(f"[CAIXA-HANDLER] ERRO: {ex}")

    return caixa_keyboard_handler
