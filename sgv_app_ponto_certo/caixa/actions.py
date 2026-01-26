"""Ações centrais do Caixa extraídas de `view.py`.

Fornece a classe `CaixaActions` que encapsula operações como adicionar ao
carrinho, atualizar quantidades, calcular total, reset do carrinho e
finalizar venda. A classe mantém referências aos objetos de UI e ao estado
passados pela `view` para não depender de variáveis globais.
"""

import io
import json
import os
from typing import Any

import flet as ft

from utils.tax_calculator_view import carregar_taxas


class CaixaActions:
    def __init__(
        self,
        page: ft.Page,
        pdv_core,
        produtos_cache: dict,
        cart_data: dict,
        cart_items_column: ft.Column,
        total_value_ref,
        subtotal_text: ft.Text,
        acrescimo_text: ft.Text,
        selected_payment_type,
        total_final_text: ft.Text,
        search_field_ref,
        product_name_text: ft.Text,
        last_added_product_id_box,
        payment_buttons_refs: list,
        money_received_field,
        change_text,
        is_finalizing_box,
        COLORS: dict,
        subtotal_label_ref=None,
        acrescimo_label_ref=None,
    ):
        self.page = page
        self.pdv_core = pdv_core
        self.produtos_cache = produtos_cache
        self.cart_data = cart_data
        self.cart_items_column = cart_items_column
        self.total_value_ref = total_value_ref
        self.subtotal_text = subtotal_text
        self.acrescimo_text = acrescimo_text
        # Optional label refs passed by the view (for hiding/showing the label text)
        self.selected_payment_type = selected_payment_type
        self.subtotal_label_ref = subtotal_label_ref
        self.acrescimo_label_ref = acrescimo_label_ref
        self.total_final_text = total_final_text
        self.search_field_ref = search_field_ref
        # Optional refs para labels de subtotal/acréscimo (view pode passar)
        self.product_name_text = product_name_text
        self.last_added_product_id_box = last_added_product_id_box
        self.payment_buttons_refs = payment_buttons_refs
        self.money_received_field = money_received_field
        self.change_text = change_text
        self.is_finalizing_box = is_finalizing_box
        self.COLORS = COLORS
        # refs adicionados dinamicamente pela view se disponíveis
        self.payment_amount_text_refs = None
        self.payment_value_field_refs = None
        self.payments = None

    def calculate_total(self):
        current_total = sum(
            item["preco"] * item["qtd"] for item in self.cart_data.values()
        )
        try:
            self.total_value_ref.current.set(current_total)
        except Exception:
            try:
                self.total_value_ref.set(current_total)
            except Exception:
                pass

        try:
            # carregar taxa de crédito (configuração da maquininha)
            try:
                taxas = carregar_taxas()
                credito_pct = float(taxas.get("credito_avista", 0.0))
                repassar = bool(taxas.get("repassar", False))
            except Exception:
                credito_pct = 0.0
                repassar = False

            # Mostrar subtotal apenas quando o método selecionado for 'Crédito'
            try:
                sel = None
                if getattr(self, "selected_payment_type", None) and getattr(
                    self.selected_payment_type, "current", None
                ):
                    sel = getattr(self.selected_payment_type.current, "value", None)
                try:
                    print(
                        f"[CAIXA-CALC] sel={sel} credito_pct={credito_pct} repassar={repassar} current_total={current_total}"
                    )
                except Exception:
                    pass
                # Mapear nome do método para chave de taxa
                method_tax_map = {
                    "Débito": "debito",
                    "Crédito": "credito_avista",
                }
                try:
                    tax_key = method_tax_map.get(sel)
                    pct = 0.0
                    if tax_key:
                        pct = float(taxas.get(tax_key, 0.0))
                    # Exibir subtotal e acréscimo somente se houver método selecionado,
                    # taxa configurada (>0) e opção de repassar ativada
                    if sel and pct and pct > 0 and repassar:
                        acrecimo = current_total * (pct / 100.0)
                        total_com_acrescimo = current_total + acrecimo
                        # Exibir Subtotal e Acréscimo em linhas separadas
                        try:
                            self.subtotal_text.value = (
                                f"R$ {current_total:.2f}".replace(".", ",")
                            )
                            self.subtotal_text.visible = True
                        except Exception:
                            pass
                        try:
                            self.acrescimo_text.value = f"R$ {acrecimo:.2f}".replace(
                                ".", ","
                            )
                            self.acrescimo_text.visible = True
                        except Exception:
                            pass
                        try:
                            if getattr(self, "subtotal_label_ref", None) and getattr(
                                self.subtotal_label_ref, "current", None
                            ):
                                self.subtotal_label_ref.current.visible = True
                        except Exception:
                            pass
                        try:
                            if getattr(self, "acrescimo_label_ref", None) and getattr(
                                self.acrescimo_label_ref, "current", None
                            ):
                                self.acrescimo_label_ref.current.visible = True
                        except Exception:
                            pass
                        # total_final_text deve incluir o acréscimo
                        try:
                            self.total_final_text.value = (
                                f"R$ {total_com_acrescimo:.2f}".replace(".", ",")
                            )
                        except Exception:
                            pass
                    else:
                        # não mostrar Subtotal/Acréscimo quando não houver taxa/repasse
                        try:
                            self.subtotal_text.visible = False
                        except Exception:
                            pass
                        try:
                            self.acrescimo_text.visible = False
                        except Exception:
                            pass
                        try:
                            if getattr(self, "subtotal_label_ref", None) and getattr(
                                self.subtotal_label_ref, "current", None
                            ):
                                self.subtotal_label_ref.current.visible = False
                        except Exception:
                            pass
                        try:
                            if getattr(self, "acrescimo_label_ref", None) and getattr(
                                self.acrescimo_label_ref, "current", None
                            ):
                                self.acrescimo_label_ref.current.visible = False
                        except Exception:
                            pass
                        try:
                            self.total_final_text.value = (
                                f"R$ {current_total:.2f}".replace(".", ",")
                            )
                        except Exception:
                            pass
                except Exception:
                    # fallback conservador: ocultar subtotal e exibir total
                    try:
                        self.subtotal_text.visible = False
                    except Exception:
                        pass
                    try:
                        self.total_final_text.value = f"R$ {current_total:.2f}".replace(
                            ".", ","
                        )
                    except Exception:
                        pass
            except Exception:
                # fallback conservador: ocultar subtotal e exibir total
                try:
                    self.subtotal_text.visible = False
                except Exception:
                    pass
                try:
                    self.total_final_text.value = f"R$ {current_total:.2f}".replace(
                        ".", ","
                    )
                except Exception:
                    pass
        except Exception:
            pass

        # Se pagamento em dinheiro, recalcular troco
        try:
            if (
                getattr(self, "selected_payment_type", None)
                and getattr(self.selected_payment_type, "current", None)
                and getattr(self.selected_payment_type.current, "value", None)
                == "Dinheiro"
                and self.money_received_field
                and getattr(self.money_received_field, "current", None)
                and getattr(self.money_received_field.current, "visible", False)
            ):
                # cálculo externo (view pode sobrescrever) -- apenas sinalizar
                try:
                    # view fornece calculate_change se necessário
                    getattr(self, "calculate_change_cb", lambda e: None)(None)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self.page.update()
        except Exception:
            pass

    def update_cart_item_ui(self, product_id, new_quantity):
        if product_id in self.cart_data:
            item = self.cart_data[product_id]
            try:
                item["qtd_ref"].current.value = f"x{new_quantity}"
            except Exception:
                pass
            try:
                new_line_total = item["preco"] * new_quantity
                item[
                    "total_row_ref"
                ].current.value = f"R$ {new_line_total:.2f}".replace(".", ",")
            except Exception:
                pass
        try:
            self.page.update()
        except Exception:
            pass

    def update_cart_item(self, product_id, quantity_change):
        if product_id not in self.cart_data:
            return

        item = self.cart_data[product_id]
        new_quantity = item["qtd"] + quantity_change

        if quantity_change > 0:
            prod_obj = self.get_product_from_cache(product_id)
            available = self.get_stock_for_product_obj(prod_obj)
            qtd_atual = int(item.get("qtd", 0))
            try:
                from .logic import validar_estoque_disponivel

                ok, msg = validar_estoque_disponivel(
                    available, qtd_atual, quantity_change
                )
            except Exception:
                ok, msg = True, ""
            if not ok:
                try:
                    # fallback snackbar
                    self.page.snack_bar = ft.SnackBar(
                        ft.Text(msg), bgcolor=self.COLORS["danger"], duration=2000
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                except Exception:
                    pass
                return

        if new_quantity <= 0:
            try:
                self.cart_items_column.controls.remove(item["card_ref"].current)
            except Exception:
                pass
            try:
                del self.cart_data[product_id]
            except Exception:
                pass
        else:
            item["qtd"] = new_quantity
            self.update_cart_item_ui(product_id, new_quantity)

        self.calculate_total()
        try:
            self.page.update()
        except Exception:
            pass

    def add_to_cart(self, product, quantity: int = 1, create_cart_item_row_ext=None):
        try:
            # Bloquear adição ao carrinho se não houver sessão de caixa aberta
            try:
                sess = self.pdv_core.get_current_open_session(None)
                if not sess:
                    try:
                        self.page.snack_bar = ft.SnackBar(
                            ft.Text(
                                "O caixa está fechado. Abra o caixa para registrar vendas."
                            ),
                            bgcolor=self.COLORS["danger"],
                            duration=3000,
                        )
                        self.page.snack_bar.open = True
                        self.page.update()
                    except Exception:
                        pass
                    return
            except Exception:
                # Se houver erro ao consultar o PDVCore, prevenir ação por segurança
                try:
                    self.page.snack_bar = ft.SnackBar(
                        ft.Text("Não foi possível verificar o estado do caixa."),
                        bgcolor=self.COLORS["danger"],
                        duration=3000,
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                except Exception:
                    pass
                return
            product_id = str(
                getattr(product, "codigo_barras", product.get("codigo_barras", ""))
            ).strip()

            if product_id in self.cart_data:
                self.update_cart_item(product_id, quantity)
            else:
                item_data = {
                    "nome": getattr(product, "nome", product.get("nome", "")),
                    "preco": float(
                        getattr(product, "preco_venda", product.get("preco_venda", 0.0))
                    ),
                    "qtd": quantity,
                    "card_ref": ft.Ref[ft.Container](),
                }

                if create_cart_item_row_ext:
                    item_container = create_cart_item_row_ext(
                        item_data, product_id, self.COLORS, self.update_cart_item
                    )
                    item_data["card_ref"].current = item_container
                else:
                    # fallback: simple container
                    item_container = ft.Container(ft.Text(item_data["nome"]))
                    item_data["card_ref"].current = item_container

                self.cart_data[product_id] = item_data
                self.last_added_product_id_box.value = product_id
                try:
                    self.cart_items_column.controls.append(item_container)
                except Exception:
                    pass

                self.calculate_total()
                try:
                    self.cart_items_column.scroll_to(offset=-1, duration=300)
                except Exception:
                    pass
        except Exception as ex:
            print(f"[ADD_TO_CART] ERRO ao adicionar produto: {ex}")
            try:
                import traceback

                traceback.print_exc()
            except Exception:
                pass
            try:
                self.page.snack_bar = ft.SnackBar(
                    ft.Text(f"Erro ao adicionar ao carrinho: {str(ex)}"),
                    bgcolor=self.COLORS["danger"],
                    duration=2000,
                )
                self.page.snack_bar.open = True
                self.page.update()
            except Exception:
                pass

    def reset_cart(self):
        try:
            try:
                print(
                    f"[RESET_CART] before: cart_items={len(getattr(self.cart_items_column, 'controls', []))} cart_data={len(getattr(self, 'cart_data', {}))}"
                )
            except Exception:
                pass
            self.cart_items_column.controls.clear()
            self.cart_data.clear()
            try:
                print(
                    f"[RESET_CART] after clear: cart_items={len(getattr(self.cart_items_column, 'controls', []))} cart_data={len(getattr(self, 'cart_data', {}))}"
                )
            except Exception:
                pass
            # Garantir que o método de pagamento esteja desselecionado antes de recalcular
            try:
                self.selected_payment_type.current.value = None
            except Exception:
                try:
                    setattr(self.selected_payment_type, "current", None)
                except Exception:
                    pass
            self.calculate_total()

            try:
                if self.money_received_field and getattr(
                    self.money_received_field, "current", None
                ):
                    self.money_received_field.current.value = ""
                    self.money_received_field.current.visible = False
            except Exception:
                pass
            try:
                if self.change_text and getattr(self.change_text, "current", None):
                    self.change_text.current.value = "Troco: R$ 0,00"
                    self.change_text.current.visible = False
            except Exception:
                pass

            try:
                for btn in self.payment_buttons_refs:
                    try:
                        btn.current.style.bgcolor = ft.Colors.WHITE
                        btn.current.style.side = ft.border.BorderSide(
                            1, ft.Colors.BLACK12
                        )
                        btn.current.style.color = ft.Colors.BLACK
                    except Exception:
                        pass
            except Exception:
                pass

            # esconder/resetar mini-botões de parcelamento (2x)
            try:
                if getattr(self, "payment_parcel_button_refs", None):
                    for p_ref in self.payment_parcel_button_refs:
                        try:
                            if not p_ref or not getattr(p_ref, "current", None):
                                continue
                            try:
                                p_ref.current.visible = False
                            except Exception:
                                pass
                            try:
                                p_ref.current.style.bgcolor = ft.Colors.WHITE
                                p_ref.current.style.color = ft.Colors.BLACK
                            except Exception:
                                pass
                        except Exception:
                            pass
            except Exception:
                pass

            # limpar os valores exibidos dentro dos botões (amt refs)
            try:
                if getattr(self, "payment_amount_text_refs", None):
                    for t_ref in self.payment_amount_text_refs:
                        try:
                            if getattr(t_ref, "current", None):
                                t_ref.current.value = ""
                        except Exception:
                            pass
            except Exception:
                pass

            # esconder e limpar os campos de valor por método
            try:
                if getattr(self, "payment_value_field_refs", None):
                    for v_ref in self.payment_value_field_refs:
                        try:
                            if getattr(v_ref, "current", None):
                                try:
                                    v_ref.current.value = ""
                                except Exception:
                                    pass
                                try:
                                    v_ref.current.visible = False
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass

            # limpar lista de pagamentos parciais se fornecida
            try:
                if getattr(self, "payments", None) is not None:
                    try:
                        self.payments.clear()
                    except Exception:
                        # fallback: atribuir nova lista vazia
                        try:
                            self.payments = []
                        except Exception:
                            pass
            except Exception:
                pass

            try:
                if self.search_field_ref and getattr(
                    self.search_field_ref, "current", None
                ):
                    self.search_field_ref.current.value = ""
                    self.search_field_ref.current.focus()
            except Exception:
                pass

                try:
                    # garantir que Subtotal e Acréscimo fiquem ocultos após reset
                    try:
                        self.subtotal_text.visible = False
                        self.acrescimo_text.visible = False
                    except Exception:
                        pass
                except Exception:
                    pass

            try:
                self.page.update()
            except Exception:
                pass
        except Exception:
            pass

    def persistir_estoque_apos_venda(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            caminho = os.path.join(base_dir, "data", "produtos.json")
            try:
                from .logic import persistir_estoque_json

                persistir_estoque_json(caminho, self.cart_data)
            except Exception:
                # fallback: escrever localmente se a função não estiver disponível
                try:
                    with open(caminho, "w", encoding="utf-8") as f:
                        json.dump([], f)
                except Exception:
                    pass
        except Exception:
            pass

    def get_product_from_cache(self, product_id):
        try:
            return self.produtos_cache.get(str(product_id).strip())
        except Exception:
            return None

    def get_stock_for_product_obj(self, p: Any):
        try:
            if p is None:
                return 0
            if isinstance(p, dict):
                return int(p.get("quantidade", 0) or 0)
            return int(getattr(p, "quantidade", 0) or 0)
        except Exception:
            return 0

    def iniciar_venda_com_sugestao_troca(self, produtos_sugestao: list = None):
        self.reset_cart()
        if produtos_sugestao:
            try:
                self.page.snack_bar = ft.SnackBar(
                    ft.Text(
                        f"✓ Venda devolvida! Adicione os novos produtos para trocar ({len(produtos_sugestao)} itens sugeridos)"
                    ),
                    bgcolor=self.COLORS["secondary"],
                    duration=3000,
                )
                self.page.snack_bar.open = True
                self.page.update()
            except Exception:
                pass

    # finalize_transaction is intentionally left to the view if it depends on many UI overlays
