"""Finalização de venda (extraída de `caixa/view.py`).

Função `finalize_transaction` contém a lógica de validação do carrinho,
interação com `pdv_core.finalizar_venda`, persistência de estoque e
exibição de cupom/Pix. Recebe todas as dependências como parâmetros para
manter isolamento e facilitar testes.
"""

import io
import os
from typing import Callable

import flet as ft

# TEF adapter (simulado)
try:
    from payments.tef_adapter import TefAdapter
except Exception:
    TefAdapter = None

# Guard em nível de módulo para evitar reentrância entre chamadas rápidas
_finalize_in_progress = False


def finalize_transaction(
    page: ft.Page,
    pdv_core,
    cart_data: dict,
    total_value_ref,
    selected_payment_type_ref,
    money_received_field_ref,
    payment_buttons_refs: list,
    PAYMENT_METHODS: list,
    payments: list,
    persistir_estoque_apos_venda: Callable,
    montar_itens_cupom: Callable,
    calcular_troco: Callable,
    montar_payload_pix: Callable,
    show_cupom_dialog: Callable,
    create_pix_overlay: Callable,
    COLORS: dict,
    show_snackbar: Callable,
    reset_cart: Callable,
    installments_count: int = None,
    per_installment: float = None,
    post_finalize_callback: Callable = None,
    set_finalizing: Callable = None,
    is_finalizing_ref=None,
):
    """Executa o fluxo de finalização da venda."""
    global _finalize_in_progress
    # Proteção contra chamadas concorrentes: checagem rápida em nível de módulo
    try:
        if _finalize_in_progress:
            return
        _finalize_in_progress = True
    except Exception:
        pass

    try:
        # também sinalizar via callback/UI
        try:
            set_finalizing(True)
        except Exception:
            pass

        try:
            p_type = None
            try:
                p_type = selected_payment_type_ref.current.value
            except Exception:
                p_type = getattr(selected_payment_type_ref, "value", None)

            current_total_val = float(total_value_ref.current.get())
            # Se a finalização acabou de ocorrer, suprimir avisos de "carrinho vazio"
            just_finalized = False
            try:
                just_finalized = bool(page.session.get("_just_finalized"))
                if just_finalized:
                    # limpar a flag para chamadas subsequentes
                    page.session.pop("_just_finalized", None)
            except Exception:
                just_finalized = False

            if current_total_val <= 0:
                if just_finalized:
                    set_finalizing(False)
                    return
                # não mostrar modal; apenas snackbar
                try:
                    show_snackbar(
                        "O carrinho está vazio. Adicione itens antes de finalizar.",
                        COLORS["danger"],
                    )
                except Exception:
                    pass
                set_finalizing(False)
                return

            if not p_type:
                try:
                    if payment_buttons_refs and len(payment_buttons_refs) > 0:
                        sel = PAYMENT_METHODS[0]["name"]
                        # simulate selection visual
                        selected_payment_type_ref.current.value = sel
                        p_type = sel
                    else:
                        selected_payment_type_ref.current.value = "Dinheiro"
                        p_type = "Dinheiro"
                except Exception:
                    selected_payment_type_ref.current.value = "Dinheiro"
                    p_type = "Dinheiro"

            carrinho_itens = []
            for codigo, item in cart_data.items():
                carrinho_itens.append(
                    {
                        "cod": str(codigo).strip(),
                        "qtd": int(item.get("qtd", 0) or 0),
                        "nome": item.get("nome", ""),
                        "preco": float(item.get("preco", 0) or 0),
                    }
                )

            if not carrinho_itens:
                if just_finalized:
                    set_finalizing(False)
                    return
                try:
                    show_snackbar(
                        "O carrinho está vazio. Nenhum item para finalizar.",
                        COLORS["danger"],
                    )
                except Exception:
                    pass
                set_finalizing(False)
                return

            # Valor recebido (dinheiro)
            if p_type == "Dinheiro":
                received_raw = None
                try:
                    received_raw = (
                        money_received_field_ref.current.value
                        if money_received_field_ref.current
                        else None
                    )
                except Exception:
                    received_raw = None
                received_str = (
                    (received_raw or "").replace("R$", "").replace(",", ".").strip()
                )
                if not received_str:
                    valor_pago = current_total_val
                else:
                    valor_pago = float(received_str)
                    if valor_pago < current_total_val:
                        # tocar bip de erro duplo
                        try:
                            from utils.beep import error_beep

                            try:
                                print(
                                    "[BEEP] Chamando error_beep() (finalize insuficiente)"
                                )
                                error_beep()
                                print(
                                    "[BEEP] error_beep() retornou (finalize insuficiente)"
                                )
                            except Exception as _be:
                                print(f"[BEEP] error_beep() gerou exceção: {_be}")
                        except Exception:
                            try:
                                print("\a\a", end="")
                            except Exception:
                                pass
                        show_snackbar("Valor recebido insuficiente.", COLORS["danger"])
                        set_finalizing(False)
                        return
            else:
                valor_pago = current_total_val

            usuario_id = page.session.get("user_id")
            sessao_caixa = None
            try:
                sessao_caixa = pdv_core.get_current_open_session(
                    usuario_id
                ) or pdv_core.get_current_open_session(None)
            except Exception:
                sessao_caixa = None
            if not sessao_caixa:
                # Não abrir automaticamente o caixa quando estiver fechado.
                # Exigir que o operador abra o caixa manualmente no painel.
                try:
                    show_snackbar(
                        "O caixa está fechado. Abra o caixa antes de finalizar vendas.",
                        COLORS["danger"],
                    )
                except Exception:
                    pass
                set_finalizing(False)
                return

            # Para pagamentos com cartão (Crédito/Débito) autorizar via TEF antes
            if p_type in ("Crédito", "Débito"):
                try:
                    if TefAdapter is None:
                        show_snackbar(
                            "TEF não disponível (adaptador ausente).", COLORS["danger"]
                        )
                        set_finalizing(False)
                        return
                    tef = TefAdapter(simulate=True)
                    auth = tef.authorize(current_total_val, method=p_type, options={})
                    if not auth.get("ok"):
                        show_snackbar(
                            f"Transação recusada: {auth.get('message')}",
                            COLORS["danger"],
                        )
                        set_finalizing(False)
                        return
                    # armazenar id da transação na sessão para depuração
                    try:
                        page.session["_last_tx_id"] = auth.get("transaction_id")
                    except Exception:
                        pass
                except Exception as e:
                    try:
                        show_snackbar(f"Erro TEF: {e}", COLORS["danger"])
                    except Exception:
                        pass
                    set_finalizing(False)
                    return

            sucesso, resultado, troco_core = pdv_core.finalizar_venda(
                carrinho_itens, p_type, valor_pago, usuario_id
            )
            if not sucesso:
                try:
                    dlg = ft.AlertDialog(
                        modal=False,
                        title=ft.Text("Erro ao finalizar"),
                        content=ft.Text(str(resultado)),
                        actions=[
                            ft.TextButton(
                                "OK", on_click=lambda e: setattr(dlg, "open", False)
                            )
                        ],
                    )
                    if dlg not in page.overlay:
                        page.overlay.append(dlg)
                    dlg.open = True
                    page.update()
                except Exception:
                    show_snackbar(
                        f"Erro ao finalizar venda: {resultado}", COLORS["danger"]
                    )
                set_finalizing(False)
                return

            try:
                persistir_estoque_apos_venda()
            except Exception:
                pass

            # Após atualizar o JSON de estoque, revalidar alertas de estoque
            try:
                from alertas.alertas_init import (
                    atualizar_badge_alertas_no_gerente,
                    verificar_estoque_ao_atualizar,
                )

                # Executa verificação e atualiza badge do gerente
                try:
                    verificar_estoque_ao_atualizar(page, pdv_core)
                except Exception:
                    pass

                try:
                    atualizar_badge_alertas_no_gerente(page, pdv_core)
                except Exception:
                    pass
            except Exception:
                pass

            titulo_cupom = f"Cupom Fiscal - Mercadinho Ponto Certo"
            itens_cupom = montar_itens_cupom(cart_data)

            received = None
            change = None
            if p_type == "Dinheiro":
                try:
                    received, change = calcular_troco(
                        total_value_ref.current, money_received_field_ref.current.value
                    )
                except Exception:
                    pass

            if p_type == "Pix":
                # montar payload e QR usando configuração do banco quando disponível
                pix_cfg = None
                try:
                    pix_cfg = page.app_data.get("pix_settings")
                except Exception:
                    pix_cfg = None

                merchant_name = (
                    pix_cfg.get("merchant_name") if pix_cfg else None
                ) or "Mercadinho Ponto Certo"
                chave_pix = pix_cfg.get("chave_pix") if pix_cfg else None
                cpf_cnpj = pix_cfg.get("cpf_cnpj") if pix_cfg else None
                cidade = pix_cfg.get("cidade") if pix_cfg else "Recife"
                tipo_pix = pix_cfg.get("tipo_pix") if pix_cfg else "dinamico"

                # Se pagamentos parciais foram feitos, embutir apenas o restante no QR
                try:
                    paid_total = sum(
                        (float(p.get("amount", 0) or 0) for p in (payments or []))
                    )
                except Exception:
                    paid_total = 0.0
                remaining_amount = max(0.0, current_total_val - (paid_total or 0.0))

                # Se houver restante (pagamento parcial), forçar QR com valor
                tipo_for_payload = tipo_pix
                try:
                    if remaining_amount > 0:
                        tipo_for_payload = "com_valor"
                except Exception:
                    tipo_for_payload = tipo_pix

                # Gerar payload usando o tipo determinado (se 'com_valor', o valor será embutido)
                # garantir arredondamento para 2 casas antes de gerar payload
                try:
                    remaining_to_use = round(float(remaining_amount or 0.0), 2)
                except Exception:
                    remaining_to_use = 0.0

                payload_text = montar_payload_pix(
                    merchant_name,
                    remaining_to_use,
                    chave_pix,
                    cpf_cnpj,
                    cidade,
                    tipo_for_payload,
                )
                print(f"[PIX-PAYLOAD-FINAL] {payload_text}")

                qr_base64 = None
                # Se a configuração contém uma imagem de QR fornecida pelo gerente,
                # só usá-la quando NÃO estivermos embutindo valor (i.e., tipo != 'com_valor').
                try:
                    if (
                        pix_cfg
                        and pix_cfg.get("qr_image")
                        and tipo_for_payload != "com_valor"
                    ):
                        qr_base64 = pix_cfg.get("qr_image")
                    else:
                        import base64

                        import qrcode

                        qr = qrcode.QRCode(box_size=6, border=2)
                        qr.add_data(payload_text)
                        qr.make(fit=True)
                        img = qr.make_image(fill_color="black", back_color="white")
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        qr_base64 = base64.b64encode(buf.getvalue()).decode("ascii")
                except Exception:
                    qr_base64 = None

                original_keyboard_handler = page.on_keyboard_event

                def finalizar_e_mostrar_cupom():
                    page.on_keyboard_event = original_keyboard_handler
                    try:
                        show_cupom_dialog(
                            page,
                            itens_cupom,
                            titulo_cupom,
                            current_total_val,
                            p_type,
                            received,
                            change,
                            auto_print=True,
                            is_fiscal=False,
                            partial_payments=payments,
                            installments_count=installments_count,
                            per_installment=per_installment,
                        )
                    except Exception:
                        pass
                    try:
                        if pix_overlay in page.overlay:
                            page.overlay.remove(pix_overlay)
                    except Exception:
                        pass
                    page.update()
                    try:
                        # sinalizar que acabamos de finalizar para suprimir avisos de "carrinho vazio"
                        try:
                            page.session["_just_finalized"] = True
                        except Exception:
                            pass
                        try:
                            reset_cart()
                        except Exception:
                            pass
                        try:
                            if callable(post_finalize_callback):
                                post_finalize_callback()
                        except Exception:
                            pass
                    except Exception:
                        pass
                    try:
                        show_snackbar(
                            f"Venda de R$ {current_total_val:.2f} finalizada em {p_type}.",
                            COLORS["secondary"],
                        )
                    except Exception:
                        pass
                    try:
                        set_finalizing(False)
                    except Exception:
                        pass

                def confirmar_pix(e=None):
                    finalizar_e_mostrar_cupom()

                def cancelar_pix(e=None):
                    page.on_keyboard_event = original_keyboard_handler
                    try:
                        try:
                            pix_overlay.visible = False
                        except Exception:
                            pass
                        try:
                            setattr(pix_overlay, "open", False)
                        except Exception:
                            pass
                        try:
                            if pix_overlay in page.overlay:
                                page.overlay.remove(pix_overlay)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    try:
                        try:
                            page.app_data["caixa_modal_open"] = False
                        except Exception:
                            pass
                        page.update()
                    except Exception:
                        pass
                    set_finalizing(False)

                display_amount_str = f"R$ {remaining_to_use:.2f}".replace(".", ",")
                pix_overlay = create_pix_overlay(
                    payload_text,
                    qr_base64,
                    on_confirm=confirmar_pix,
                    on_cancel=cancelar_pix,
                    merchant_name=merchant_name,
                    chave_pix=chave_pix,
                    cidade=cidade,
                    tipo_pix=tipo_pix,
                    remaining_amount=remaining_to_use,
                )
                if pix_overlay not in page.overlay:
                    try:
                        try:
                            page.app_data["caixa_modal_open"] = True
                        except Exception:
                            pass
                        try:
                            setattr(pix_overlay, "open", True)
                        except Exception:
                            pass
                        page.overlay.append(pix_overlay)
                    except Exception:
                        try:
                            page.overlay.append(pix_overlay)
                        except Exception:
                            pass
                pix_overlay.visible = True

                def pix_keyboard_handler(e: ft.KeyboardEvent):
                    key_pix = str(e.key).upper() if e.key else ""
                    if key_pix == "ENTER":
                        finalizar_e_mostrar_cupom()
                    elif key_pix == "ESCAPE":
                        cancelar_pix(e)
                    else:
                        if original_keyboard_handler:
                            original_keyboard_handler(e)

                page.on_keyboard_event = pix_keyboard_handler
                page.update()
                return

            # Não-Pix: exibir cupom direto
            try:
                show_cupom_dialog(
                    page,
                    itens_cupom,
                    titulo_cupom,
                    current_total_val,
                    p_type,
                    received,
                    change,
                    auto_print=True,
                    is_fiscal=False,
                    partial_payments=payments,
                    installments_count=installments_count,
                    per_installment=per_installment,
                )
            except Exception:
                # Evitar diálogos modais duplicados: mostrar apenas uma notificação não bloqueante
                try:
                    show_snackbar(
                        f"Venda de R$ {current_total_val:.2f} finalizada em {p_type}.",
                        COLORS["secondary"],
                    )
                except Exception:
                    pass

            # Remover qualquer diálogo residual "Carrinho vazio" que possa aparecer
            try:
                overlays = list(page.overlay)
                for o in overlays:
                    try:
                        if not isinstance(o, ft.AlertDialog):
                            continue
                        title = getattr(o, "title", None)
                        title_text = None
                        if title is None:
                            title_text = None
                        else:
                            title_text = getattr(title, "value", None) or getattr(
                                title, "text", None
                            )
                            if not title_text:
                                try:
                                    title_text = str(title)
                                except Exception:
                                    title_text = None
                        if title_text and "Carrinho vazio" in title_text:
                            try:
                                page.overlay.remove(o)
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass

            try:
                # sinalizar que acabamos de finalizar para suprimir avisos de "carrinho vazio"
                try:
                    page.session["_just_finalized"] = True
                except Exception:
                    pass
            except Exception:
                pass
            try:
                reset_cart()
            except Exception:
                pass
            try:
                if callable(post_finalize_callback):
                    post_finalize_callback()
            except Exception:
                pass
            except Exception:
                pass
            show_snackbar(
                f"Venda de R$ {current_total_val:.2f} finalizada em {p_type}.",
                COLORS["secondary"],
            )
            set_finalizing(False)

        except Exception as ex:
            try:
                show_snackbar(f"Erro ao finalizar: {ex}", COLORS["danger"])
            except Exception:
                pass
            set_finalizing(False)
            return

    finally:
        # Garantir limpeza do lock ao final
        try:
            _finalize_in_progress = False
        except Exception:
            pass
