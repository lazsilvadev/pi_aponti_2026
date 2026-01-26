"""Handlers extraídos da view do Caixa.

Fornece um factory `build_caixa_keyboard_handler(...)` que retorna o
handler de teclado usado pela view. O handler delega ações para callbacks
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
):
    """Retorna uma função de manipulador de teclado para a view do Caixa.

    Todos os objetos com estado (listas, dicionários, refs) pertencem à view e
    são passados ao handler, mantendo-o como um wrapper leve.
    """

    def caixa_keyboard_handler(e: ft.KeyboardEvent):
        key = str(e.key).upper() if e.key else ""
        print(f"[CAIXA-HANDLER] ⌨️ Tecla: '{key}' (original: '{e.key}')")

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

            # ESC: gerente volta ao painel; demais perfis saem direto.
            if key == "ESCAPE":
                print("[CAIXA-HANDLER] ESC pressionado")
                import time

                now = time.time()
                # Debounce é tratado pela view se necessário; o handler mantém-se simples
                try:
                    role = None
                    try:
                        role = page.session.get("role")
                    except Exception:
                        role = None
                    if str(role or "").lower() == "gerente":
                        try:
                            page.go("/gerente")
                        except Exception:
                            try:
                                page.push_route("/gerente")
                            except Exception:
                                pass
                        return
                except Exception:
                    pass

                # Demais perfis: deslogar imediatamente
                try:
                    if callable(handle_logout):
                        handle_logout(None)
                    else:
                        try:
                            page.session.clear()
                        except Exception:
                            pass
                        try:
                            page.go("/login")
                        except Exception:
                            try:
                                page.push_route("/login")
                            except Exception:
                                pass
                except Exception as ex:
                    print(f"[CAIXA-HANDLER] falha ao efetuar logout direto: {ex}")
                return

            # ENTER: não processar aqui - on_submit do TextField trata
            if key in ("ENTER", "RETURN") or e.key in (
                "Enter",
                "Return",
                "\r",
                "NewLine",
            ):
                print(
                    "[CAIXA-HANDLER] ENTER detectado - IGNORANDO (tratado pelo TextField)"
                )
                return

            print(f"[CAIXA-HANDLER] Tecla '{key}' não mapeada (e.key='{e.key}')")

        except Exception as ex:
            print(f"[CAIXA-HANDLER] ERRO: {ex}")

    return caixa_keyboard_handler
