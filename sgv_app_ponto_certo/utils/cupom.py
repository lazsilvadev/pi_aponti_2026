import os
from datetime import datetime
from pathlib import Path

import flet as ft

from utils.export_utils import generate_pdf_file
from utils.tax_calculator_view import carregar_taxas

# tentativa de usar win32print para enviar dados RAW ao driver do Windows
try:
    import win32print

    HAS_WIN32 = True
except Exception:
    HAS_WIN32 = False


def show_cupom_dialog(
    page: ft.Page,
    itens_cupom,
    titulo_cupom,
    current_total,
    p_type,
    received=None,
    change=None,
    auto_print: bool = False,
    transaction_id: str = None,
    payment_status: str = None,
    partial_payments: list = None,
    installments_count: int = None,
    per_installment: float = None,
    is_fiscal: bool = True,
):
    """Monta e exibe o diálogo do cupom fiscal e possibilita salvar como PDF.

    - `itens_cupom`: lista de linhas [nome, qtd, preco_u, total_str]
    - `titulo_cupom`: título do diálogo
    - `current_total`: valor numérico do total
    - `p_type`: método de pagamento (string)
    - `received`, `change`: valores numéricos opcionalmente exibidos
    """

    # Cabeçalho
    if is_fiscal:
        title_display = "CUPOM FISCAL - MERCADINHO PONTO CERTO"
    else:
        title_display = "CUPOM NÃO FISCAL - MERCADINHO PONTO CERTO"

    # merchant_name: tentar extrair a parte após o ' - ' quando possível
    if isinstance(titulo_cupom, str) and " - " in titulo_cupom:
        merchant_name = titulo_cupom.split(" - ", 1)[1]
    else:
        merchant_name = titulo_cupom
    # construir linha de pagamento: se houver partial_payments, mostrar métodos e valores na mesma linha
    payment_display = f"{p_type}"
    try:
        if partial_payments:
            parts = []
            for p in partial_payments:
                m = p.get("method", "")
                a = float(p.get("amount", 0) or 0)
                parts.append(f"{m} R$ {a:.2f}".replace(".", ","))
            if parts:
                payment_display = " | ".join(parts).replace(" | ", " ∣ ")
    except Exception:
        pass

    # Calcular acréscimo a ser repassado ao cliente (se aplicável)
    try:
        taxas = carregar_taxas() or {}
        credito_pct = float(taxas.get("credito_avista", 0) or 0)
        debito_pct = float(taxas.get("debito", 0) or 0)
        repassar_flag = bool(taxas.get("repassar", False))
    except Exception:
        credito_pct = 0.0
        debito_pct = 0.0
        repassar_flag = False

    # Calcular separadamente acréscimos por método para exibir detalhes
    acrescimo_credito = 0.0
    acrescimo_debito = 0.0
    try:
        if repassar_flag:
            # Se houver pagamentos parciais, somar acréscimo sobre quantias pagas
            # conforme método (Crédito ou Débito)
            if partial_payments:
                for p in partial_payments:
                    try:
                        method = (p.get("method") or "")
                        a = float(p.get("amount", 0) or 0)
                        if method == "Crédito":
                            acrescimo_credito += a * (credito_pct / 100.0)
                        elif method == "Débito":
                            acrescimo_debito += a * (debito_pct / 100.0)
                    except Exception:
                        pass
            else:
                # Sem pagamentos parciais: aplicar sobre o total quando forma for Crédito ou Débito
                try:
                    if (p_type or "") == "Crédito":
                        acrescimo_credito = float(current_total or 0.0) * (
                            credito_pct / 100.0
                        )
                    elif (p_type or "") == "Débito":
                        acrescimo_debito = float(current_total or 0.0) * (
                            debito_pct / 100.0
                        )
                except Exception:
                    acrescimo_credito = 0.0
                    acrescimo_debito = 0.0
    except Exception:
        acrescimo_credito = 0.0
        acrescimo_debito = 0.0

    acrescimo_total = acrescimo_credito + acrescimo_debito

    header_items = [
        ft.Text(
            f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            size=12,
            text_align=ft.TextAlign.CENTER,
        ),
        ft.Text(
            f"Pagamento: {payment_display}", size=12, text_align=ft.TextAlign.CENTER
        ),
    ]
    # (Pagamento já exibido em `payment_display` acima) -- evitar linhas duplicadas
    # se houver informação de parcelas, mostrá-la logo abaixo
    try:
        if installments_count and per_installment is not None:
            header_items.append(
                ft.Text(
                    f"Parcelas: {installments_count}x de R$ {per_installment:.2f}".replace(
                        ".", ","
                    ),
                    size=12,
                    text_align=ft.TextAlign.CENTER,
                )
            )
    except Exception:
        pass
    # Exibir acréscimo caso tenha sido calculado e repassado ao cliente
    try:
        # Mostrar acréscimos por método quando aplicáveis
        if acrescimo_credito and float(acrescimo_credito or 0.0) > 0.0:
            header_items.append(
                ft.Text(
                    f"Acréscimo (Crédito {credito_pct:.2f}%): R$ {acrescimo_credito:.2f}".replace(
                        ".", ","
                    ),
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                )
            )
        if acrescimo_debito and float(acrescimo_debito or 0.0) > 0.0:
            header_items.append(
                ft.Text(
                    f"Acréscimo (Débito {debito_pct:.2f}%): R$ {acrescimo_debito:.2f}".replace(
                        ".", ","
                    ),
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                )
            )
        # fallback: se houver acréscimo total mas não especificado, mostrar genérico
        if (acrescimo_total and float(acrescimo_total or 0.0) > 0.0) and not (
            (acrescimo_credito and float(acrescimo_credito or 0.0) > 0.0)
            or (acrescimo_debito and float(acrescimo_debito or 0.0) > 0.0)
        ):
            header_items.append(
                ft.Text(
                    f"Acréscimo: R$ {acrescimo_total:.2f}".replace(".", ","),
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                )
            )
    except Exception:
        pass
    # mostrar dados de transação se presentes
    if transaction_id:
        header_items.append(
            ft.Text(
                f"Autorização: {transaction_id}",
                size=12,
                text_align=ft.TextAlign.CENTER,
            )
        )
    if payment_status:
        header_items.append(
            ft.Text(
                f"Status: {payment_status}", size=12, text_align=ft.TextAlign.CENTER
            )
        )
    if received is not None:
        header_items.append(
            ft.Text(
                f"Recebido: R$ {received:.2f}".replace(".", ","),
                size=12,
                text_align=ft.TextAlign.CENTER,
            )
        )
        header_items.append(
            ft.Text(
                f"Troco: R$ {change:.2f}".replace(".", ","),
                size=12,
                text_align=ft.TextAlign.CENTER,
            )
        )

    # Cabeçalho da tabela de itens
    itens_rows = []
    itens_rows.append(
        ft.Row(
            [
                ft.Text("Produto", size=13, weight=ft.FontWeight.BOLD, expand=True),
                ft.Text(
                    "Qtd",
                    size=13,
                    weight=ft.FontWeight.BOLD,
                    width=50,
                    text_align=ft.TextAlign.RIGHT,
                ),
                ft.Text(
                    "Preço",
                    size=13,
                    weight=ft.FontWeight.BOLD,
                    width=90,
                    text_align=ft.TextAlign.RIGHT,
                ),
                ft.Text(
                    "Total",
                    size=13,
                    weight=ft.FontWeight.BOLD,
                    width=90,
                    text_align=ft.TextAlign.RIGHT,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
    )

    for nome, qtd, preco_u, tot in itens_cupom:
        itens_rows.append(
            ft.Row(
                [
                    ft.Text(nome, size=13, expand=True),
                    ft.Text(qtd, size=13, width=50, text_align=ft.TextAlign.RIGHT),
                    ft.Text(preco_u, size=13, width=90, text_align=ft.TextAlign.RIGHT),
                    ft.Text(tot, size=13, width=90, text_align=ft.TextAlign.RIGHT),
                ],
                spacing=6,
            )
        )

    total_text = ft.Text(
        f"TOTAL: R$ {(float(current_total or 0.0) + float(acrescimo_total or 0.0)):.2f}".replace(
            ".", ","
        ),
        size=18,
        weight=ft.FontWeight.BOLD,
        text_align=ft.TextAlign.RIGHT,
    )
    footer_text = ft.Text(
        "Muito obrigado, volte sempre!",
        size=14,
        weight=ft.FontWeight.BOLD,
        text_align=ft.TextAlign.CENTER,
    )

    receipt_column = ft.Column(
        header_items
        + [ft.Divider()]
        + itens_rows
        + [ft.Divider(), total_text, ft.Divider(), footer_text],
        spacing=6,
    )

    def _send_raw_to_printer(printer_name: str, data: bytes) -> None:
        """Envia bytes RAW para impressora via win32print."""
        hPrinter = None
        try:
            hPrinter = win32print.OpenPrinter(printer_name)
            win32print.StartDocPrinter(hPrinter, 1, ("Cupom", None, "RAW"))
            win32print.StartPagePrinter(hPrinter)
            win32print.WritePrinter(hPrinter, data)
            win32print.EndPagePrinter(hPrinter)
            win32print.EndDocPrinter(hPrinter)
        finally:
            if hPrinter:
                win32print.ClosePrinter(hPrinter)

    def _build_receipt_text(
        merchant_name,
        itens_cupom,
        current_total,
        p_type,
        received=None,
        change=None,
        transaction_id: str = None,
        payment_status: str = None,
        installments_count: int = None,
        per_installment: float = None,
    ):
        lines = []
        lines.append(title_display)
        lines.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        # construir linha de pagamento para o texto simples (métodos mistos com valores)
        payment_txt = f"{p_type}"
        try:
            if partial_payments:
                parts = []
                for p in partial_payments:
                    m = p.get("method", "")
                    a = float(p.get("amount", 0) or 0)
                    parts.append(f"{m} R$ {a:.2f}")
                if parts:
                    payment_txt = " | ".join(parts).replace(" | ", " ∣ ")
        except Exception:
            pass
        lines.append(f"Pagamento: {payment_txt}")
        # (Pagamento já exibido em `payment_txt` acima) -- evitar linhas duplicadas
        try:
            if installments_count and per_installment is not None:
                lines.append(
                    f"Parcelas: {installments_count}x de R$ {per_installment:.2f}".replace(
                        ".", ","
                    )
                )
        except Exception:
            pass
        # incluir dados de transação no texto simples (se houver)
        try:
            if transaction_id:
                lines.append(f"Autorização: {transaction_id}")
            if payment_status:
                lines.append(f"Status: {payment_status}")
        except Exception:
            pass
        if received is not None:
            lines.append(f"Recebido: R$ {received:.2f}".replace(".", ","))
            lines.append(f"Troco: R$ {change:.2f}".replace(".", ","))
        lines.append("--------------------------------")
        for nome, qtd, preco_u, tot in itens_cupom:
            # formato simples: Produto (qtd x unit)  total
            lines.append(f"{nome} {qtd} x {preco_u}  {tot}")
        lines.append("--------------------------------")
        try:
            total_with_acrescimo = float(current_total or 0.0) + float(
                acrescimo_total or 0.0
            )
        except Exception:
            total_with_acrescimo = float(current_total or 0.0)
        # inserir linhas detalhadas de acréscimo por método quando existirem
        try:
            if acrescimo_credito and float(acrescimo_credito or 0.0) > 0.0:
                lines.append(
                    f"Acréscimo (Crédito {credito_pct:.2f}%): R$ {acrescimo_credito:.2f}"
                )
            if acrescimo_debito and float(acrescimo_debito or 0.0) > 0.0:
                lines.append(
                    f"Acréscimo (Débito {debito_pct:.2f}%): R$ {acrescimo_debito:.2f}"
                )
            # fallback genérico
            if (acrescimo_total and float(acrescimo_total or 0.0) > 0.0) and not (
                (acrescimo_credito and float(acrescimo_credito or 0.0) > 0.0)
                or (acrescimo_debito and float(acrescimo_debito or 0.0) > 0.0)
            ):
                lines.append(f"Acréscimo: R$ {acrescimo_total:.2f}")
        except Exception:
            pass
        lines.append(f"TOTAL: R$ {total_with_acrescimo:.2f}".replace(".", ","))
        lines.append("")
        lines.append("Muito obrigado, volte sempre!")
        # juntar e retornar bytes (usar encoding compatível com impressora)
        text = "\n".join(lines) + "\n\n"
        return text.encode("utf-8")

    def salvar_pdf_cupom(_e):
        try:
            headers = ["Produto", "Qtd", "Preço Unit.", "Total"]
            pdf_rows = list(itens_cupom) + [
                ["", "", "", "Muito obrigado, volte sempre!"]
            ]
            caminho = generate_pdf_file(
                headers, pdf_rows, nome_base="cupom_fiscal", title=title_display
            )
            # abrir arquivo no sistema (Windows: os.startfile)
            try:
                os.startfile(caminho)
            except Exception:
                pass
            page.snack_bar = ft.SnackBar(
                ft.Text(f"✅ Cupom salvo: {Path(caminho).name}"),
                bgcolor=ft.Colors.GREEN_600,
            )
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"❌ Erro ao salvar cupom: {ex}"), bgcolor=ft.Colors.RED_600
            )
            page.snack_bar.open = True
            page.update()

    # Mostrar título conforme solicitado pelo cliente
    cupom_dialog = ft.AlertDialog(
        modal=False,
        title=ft.Container(
            content=ft.Text(title_display, size=16, weight=ft.FontWeight.BOLD),
            alignment=ft.alignment.center,
        ),
        content=receipt_column,
        actions_alignment=ft.MainAxisAlignment.END,
    )

    original_keyboard_handler = page.on_keyboard_event

    def fechar_cupom(_e=None):
        # Restaura handler global antes de fechar
        page.on_keyboard_event = original_keyboard_handler
        if cupom_overlay in page.overlay:
            page.overlay.remove(cupom_overlay)
        page.update()

    cupom_dialog.actions = [
        ft.TextButton(
            "Fechar",
            on_click=fechar_cupom,
        ),
        ft.ElevatedButton("Salvar PDF", on_click=salvar_pdf_cupom),
    ]

    # Criar overlay container em vez de usar AlertDialog modal
    cupom_overlay = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(
                                                title_display,
                                                size=16,
                                                weight=ft.FontWeight.BOLD,
                                            )
                                        ],
                                        alignment=ft.MainAxisAlignment.CENTER,
                                    ),
                                    ft.Divider(height=10),
                                    ft.Column(
                                        [receipt_column],
                                        width=500,
                                        height=600,
                                        scroll=ft.ScrollMode.AUTO,
                                    ),
                                    ft.Divider(height=10),
                                    ft.Row(
                                        [
                                            ft.TextButton(
                                                "Fechar",
                                                on_click=fechar_cupom,
                                            ),
                                            ft.ElevatedButton(
                                                "Salvar PDF", on_click=salvar_pdf_cupom
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.END,
                                    ),
                                ],
                                spacing=8,
                            ),
                            width=550,
                            bgcolor="white",
                            border_radius=8,
                            padding=20,
                        ),
                        ft.Container(expand=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        visible=True,
        bgcolor="rgba(0, 0, 0, 0.5)",
        expand=True,
    )

    if cupom_overlay not in page.overlay:
        page.overlay.append(cupom_overlay)

    # Enquanto o cupom estiver aberto, Enter fecha o diálogo
    def cupom_keyboard_handler(e: ft.KeyboardEvent):
        key_cupom = str(e.key).upper() if e.key else ""
        # ENTER fecha o cupom
        if e.key == "Enter" or key_cupom in ("ENTER", "RETURN"):
            fechar_cupom()
            return
        # ESC fecha o cupom
        if e.key == "Escape" or key_cupom in ("ESCAPE", "ESC"):
            fechar_cupom()
            return

    page.on_keyboard_event = cupom_keyboard_handler
    page.update()

    # Impressão automática opcional
    if auto_print:
        try:
            data = _build_receipt_text(
                merchant_name,
                itens_cupom,
                current_total,
                p_type,
                received,
                change,
                transaction_id=transaction_id,
                payment_status=payment_status,
                installments_count=installments_count,
                per_installment=per_installment,
            )
            if HAS_WIN32:
                printer_name = win32print.GetDefaultPrinter()
                _send_raw_to_printer(printer_name, data)
            else:
                # Fallback: gerar PDF e enviar para impressão pelo app associado
                headers = ["Produto", "Qtd", "Preço Unit.", "Total"]
                pdf_rows = list(itens_cupom) + [
                    ["", "", "", "Muito obrigado, volte sempre!"]
                ]
                caminho = generate_pdf_file(
                    headers,
                    pdf_rows,
                    nome_base="cupom_fiscal",
                    title=title_display,
                )
                try:
                    os.startfile(caminho, "print")
                except Exception:
                    # platform fallback: abrir sem imprimir
                    try:
                        os.startfile(caminho)
                    except Exception:
                        raise

            page.snack_bar = ft.SnackBar(
                ft.Text("✅ Cupom enviado para impressora"), bgcolor=ft.Colors.GREEN_600
            )
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"❌ Erro ao imprimir cupom: {ex}"), bgcolor=ft.Colors.RED_600
            )
            page.snack_bar.open = True
            page.update()
