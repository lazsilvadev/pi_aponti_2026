import json
import os
from datetime import datetime
from pathlib import Path

import flet as ft

from utils.path_resolver import get_data_path

# Compat: garantir alias `ft.icons` quando apenas `ft.Icons` existir
try:
    if not hasattr(ft, "icons") and hasattr(ft, "Icons"):
        ft.icons = ft.Icons
except Exception:
    pass

# Caminho para salvar as taxas configuradas (na pasta data)
CONFIG_FILE = get_data_path("config_maquininha.json")


def carregar_taxas():
    try:
        p = Path(CONFIG_FILE)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "debito": 1.99,
        "credito_avista": 3.49,
        "parcelado_base": 4.50,
        "por_parcela": 1.10,
        # persistir opção de repassar taxas ao cliente (False por padrão)
        "repassar": False,
    }


def salvar_taxas(taxas):
    try:
        p = Path(CONFIG_FILE)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(taxas, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def criar_calculadora_view(page: ft.Page):
    taxas = carregar_taxas()
    try:
        print(f"[TAX-CALC] carregar_taxas -> {taxas}")
    except Exception:
        pass

    # --- CAMPOS DE CONFIGURAÇÃO ---
    txt_taxa_debito = ft.TextField(
        label="Taxa Débito (%)",
        value=str(taxas.get("debito", 1.99)),
        keyboard_type=ft.KeyboardType.NUMBER,
        expand=True,
    )
    txt_taxa_credito = ft.TextField(
        label="Crédito à Vista (%)",
        value=str(taxas.get("credito_avista", 3.49)),
        keyboard_type=ft.KeyboardType.NUMBER,
        expand=True,
    )

    # label para exibir a hora da última alteração
    last_edit_label = ft.Text("", size=12, italic=True)
    # label local para mensagens de status (visível dentro do modal)
    status_text = ft.Text("", size=12, italic=False)
    status_container = ft.Container(
        content=status_text,
        visible=False,
        padding=ft.padding.all(10),
        bgcolor=ft.Colors.GREEN_50,
        border_radius=8,
    )

    # --- CAMPOS DE CÁLCULO ---
    txt_valor_venda = ft.TextField(
        label="Valor da Venda (R$)",
        prefix_text="R$ ",
        hint_text="0,00",
        text_align=ft.TextAlign.RIGHT,
    )

    opcoes_pagamento = ft.Dropdown(
        label="Forma de Pagamento",
        value="debito",
        options=[
            ft.dropdown.Option("debito", "Cartão de Débito"),
            ft.dropdown.Option("credito", "Crédito à Vista"),
            ft.dropdown.Option("parcelado", "Crédito Parcelado"),
        ],
    )

    num_parcelas = ft.Slider(
        min=2, max=12, divisions=10, label="{value}x", visible=False
    )

    lbl_receber = ft.Text(
        "Você recebe: R$ 0,00",
        size=16,
        weight=ft.FontWeight.W_600,
        color=ft.Colors.GREEN,
    )
    lbl_cliente_paga = ft.Text("Cliente paga: R$ 0,00", size=14, italic=True)

    mode_switch = ft.Switch(
        label="Repassar taxas ao cliente?", value=bool(taxas.get("repassar", False))
    )

    def _on_mode_switch_change(e=None):
        try:
            taxas_atual = carregar_taxas()
            taxas_atual["repassar"] = bool(mode_switch.value)
            ok = salvar_taxas(taxas_atual)
            try:
                print(
                    f"[TAX-CALC] switch changed -> repassar={taxas_atual['repassar']} saved={ok}"
                )
            except Exception:
                pass
        except Exception:
            pass

    # botão de debug para forçar salvar e inspecionar o arquivo
    def _debug_forcar_salvar(e=None):
        try:
            taxas_atual = carregar_taxas()
            taxas_atual["repassar"] = bool(mode_switch.value)
            ok = salvar_taxas(taxas_atual)
            print(
                f"[TAX-CALC-DEBUG] forcar_salvar repassar={taxas_atual['repassar']} ok={ok}"
            )
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = f.read()
                print(f"[TAX-CALC-DEBUG] config file content:\n{data}")
            except Exception as ex:
                print(f"[TAX-CALC-DEBUG] erro lendo config: {ex}")
        except Exception as ex:
            print(f"[TAX-CALC-DEBUG] erro: {ex}")

    # Garantir que o change handler salve a opção e atualize o cálculo.
    def _mode_change_wrapper(e=None):
        try:
            _on_mode_switch_change(e)
        except Exception:
            pass
        try:
            calcular(e)
        except Exception:
            pass

    try:
        mode_switch.on_change = _mode_change_wrapper
    except Exception:
        try:
            mode_switch.on_click = _mode_change_wrapper
        except Exception:
            pass

    # botão de debug visível na calculadora para forçar salvar e inspecionar
    debug_btn = ft.ElevatedButton(
        "Debug: forçar salvar repassar", on_click=_debug_forcar_salvar
    )

    def atualizar_ui_parcelas(e=None):
        num_parcelas.visible = opcoes_pagamento.value == "parcelado"
        num_parcelas.update()
        calcular()

    # Preencher label de última alteração com base no arquivo salvo (se existir)
    try:
        p = Path(CONFIG_FILE)
        if p.exists():
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            last_edit_label.value = (
                f"Última alteração: {mtime.strftime('%d/%m/%Y %H:%M')}"
            )
    except Exception:
        pass

    def calcular(e=None):
        try:
            valor_str = (txt_valor_venda.value or "").replace("R$", "").strip()
            valor = float(valor_str.replace(",", ".")) if valor_str else 0.0
            if valor <= 0:
                lbl_receber.value = "Você recebe: R$ 0,00"
                lbl_cliente_paga.value = "Cliente paga: R$ 0,00"
                lbl_receber.update()
                lbl_cliente_paga.update()
                return

            # Pega taxas atuais da UI
            t_deb = (
                float(
                    (txt_taxa_debito.value or taxas.get("debito", 1.99)).replace(
                        ",", "."
                    )
                )
                / 100.0
            )
            t_cre = (
                float(
                    (
                        txt_taxa_credito.value or taxas.get("credito_avista", 3.49)
                    ).replace(",", ".")
                )
                / 100.0
            )
            t_base_parc = float(taxas.get("parcelado_base", 4.50)) / 100.0
            t_mensal = float(taxas.get("por_parcela", 1.10)) / 100.0

            # Se a taxa de crédito à vista for zero, considerar que
            # não há taxa de parcelamento também (requisito do usuário).
            # Assim, mesmo que `parcelado_base`/`por_parcela` estejam
            # preenchidos, serão ignorados quando `credito_avista` == 0.
            try:
                if t_cre <= 0.0:
                    t_base_parc = 0.0
                    t_mensal = 0.0
            except Exception:
                pass

            # Determina a taxa final com base na escolha
            if opcoes_pagamento.value == "debito":
                taxa_final = t_deb
            elif opcoes_pagamento.value == "credito":
                taxa_final = t_cre
            else:
                parcelas = int(num_parcelas.value) if num_parcelas.visible else 2
                taxa_final = t_base_parc + (t_mensal * (parcelas - 1))

            if mode_switch.value:  # REPASSE (O cliente paga a taxa)
                valor_final_cliente = (
                    valor / (1 - taxa_final) if (1 - taxa_final) != 0 else valor
                )
                valor_recebido_loja = valor
            else:  # DESCONTO (A loja paga a taxa)
                valor_final_cliente = valor
                valor_recebido_loja = valor * (1 - taxa_final)

            lbl_receber.value = f"Você recebe: R$ {valor_recebido_loja:.2f}"
            lbl_cliente_paga.value = (
                f"Valor cobrado na máquina: R$ {valor_final_cliente:.2f}"
            )

            lbl_receber.update()
            lbl_cliente_paga.update()
        except Exception:
            pass

    # montar layout da calculadora: incluir o debug_btn abaixo do mode_switch
    def salvar_config(e):
        try:
            novas_taxas = {
                "debito": float(txt_taxa_debito.value.replace(",", ".")),
                "credito_avista": float(txt_taxa_credito.value.replace(",", ".")),
                "repassar": bool(mode_switch.value),
                "parcelado_base": taxas.get("parcelado_base", 4.50),
                "por_parcela": taxas.get("por_parcela", 1.10),
            }
            ok = salvar_taxas(novas_taxas)

            def set_status(msg, color=ft.Colors.GREEN, duration_ms=3000):
                try:
                    status_text.value = msg
                    try:
                        status_text.color = color
                    except Exception:
                        pass
                    try:
                        status_container.visible = True
                        status_container.update()
                        try:
                            page.update()
                        except Exception:
                            pass
                    except Exception:
                        pass

                    def _hide():
                        page.sleep(duration_ms)
                        try:
                            status_container.visible = False
                            status_container.update()
                            try:
                                page.update()
                            except Exception:
                                pass
                        except Exception:
                            pass

                    page.run_task(_hide)
                except Exception:
                    pass

            if ok:
                # atualizar label de última alteração
                try:
                    last_edit_label.value = (
                        f"Última alteração: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                    )
                    last_edit_label.update()
                except Exception:
                    pass

                # Mostrar mensagem local dentro do modal (melhor compatibilidade)
                try:
                    set_status(
                        "📌 Configurações salvas com sucesso", color=ft.Colors.GREEN
                    )
                except Exception:
                    pass
                print("[CALC] Configurações da operadora salvas com sucesso")
            if ok:
                # mostrar snackbar global para feedback do usuário
                try:
                    try:
                        page.show_snack_bar(
                            ft.SnackBar(
                                content=ft.Text("✅ Configurações salvas com sucesso"),
                                bgcolor=ft.Colors.GREEN,
                            )
                        )
                        try:
                            page.update()
                        except Exception:
                            pass
                    except Exception:
                        # fallback para versões antigas do Flet
                        page.snack_bar = ft.SnackBar(
                            content=ft.Text("✅ Configurações salvas com sucesso"),
                            bgcolor=ft.Colors.GREEN,
                        )
                        page.snack_bar.open = True
                        try:
                            page.update()
                        except Exception:
                            pass
                except Exception:
                    pass
                # atualizar memória
                taxas.update(novas_taxas)
                calcular()
        except Exception as _ex:
            try:
                set_status(
                    "Erro ao salvar as configurações da operadora.", color=ft.Colors.RED
                )
            except Exception:
                pass
            print(f"[CALC] Erro ao salvar configurações da operadora: {_ex}")

    # eventos
    txt_valor_venda.on_change = calcular
    opcoes_pagamento.on_change = atualizar_ui_parcelas
    num_parcelas.on_change = calcular
    # Atualizar cálculo quando as taxas forem alteradas (reconhecer débito/crédito imediatamente)
    txt_taxa_debito.on_change = calcular
    txt_taxa_credito.on_change = calcular
    # manter o wrapper acima (executa salvar + calcular)

    # Layout das Abas
    # Tornar o painel mais compacto: reduzir padding/spacing e agrupar resultados
    result_box = ft.Container(
        content=ft.Column([lbl_receber, lbl_cliente_paga], spacing=4),
        padding=ft.padding.symmetric(horizontal=8, vertical=6),
        border_radius=8,
    )

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text="Calculadora",
                content=ft.Container(
                    padding=8,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Simulador de Venda",
                                size=18,
                                weight=ft.FontWeight.W_600,
                            ),
                            txt_valor_venda,
                            opcoes_pagamento,
                            num_parcelas,
                            mode_switch,
                            ft.Divider(),
                            result_box,
                        ],
                        spacing=8,
                    ),
                ),
            ),
            ft.Tab(
                text="Configurar Operadora",
                content=ft.Container(
                    padding=12,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Ajuste as taxas do seu contrato",
                                size=16,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.Row([txt_taxa_debito, txt_taxa_credito]),
                            ft.Text(
                                "As taxas acima serão usadas para os cálculos automáticos.",
                                size=12,
                                italic=True,
                            ),
                            ft.ElevatedButton(
                                "Salvar Configurações", on_click=salvar_config
                            ),
                            status_container,
                            last_edit_label,
                        ],
                        spacing=12,
                    ),
                ),
            ),
        ],
        expand=0,
    )

    # Compat: nem todas as versões do Flet expõem `Colors.SURFACE_VARIANT`.
    appbar_bg = getattr(ft.Colors, "SURFACE_VARIANT", None)
    if appbar_bg is None:
        # fallback seguro
        try:
            appbar_bg = ft.Colors.BLUE
        except Exception:
            appbar_bg = None

    return ft.View(
        "/calculadora",
        appbar=ft.AppBar(title=ft.Text("Calculadora de Taxas"), bgcolor=appbar_bg),
        controls=[tabs],
    )
