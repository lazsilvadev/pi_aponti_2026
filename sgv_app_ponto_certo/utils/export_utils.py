# export_utils.py
import csv
import sys
from datetime import datetime
from pathlib import Path

from fpdf import FPDF


def _resolve_exports_dir() -> Path:
    """Resolve a pasta de exports, compatível com exe empacotado.

    - Quando `frozen` (PyInstaller/Flet pack), cria ao lado do executável.
    - Caso falhe, usa a pasta do usuário: ~/Mercadinho Ponto Certo/exports.
    - Como último recurso, usa o cwd/exports.
    """
    try:
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent
        else:
            base = Path.cwd()
        p = base / "exports"
        p.mkdir(exist_ok=True)
        return p
    except Exception:
        try:
            p = Path.home() / "Mercadinho Ponto Certo" / "exports"
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            p = Path("exports")
            p.mkdir(exist_ok=True)
            return p


EXPORTS_DIR = _resolve_exports_dir()


def format_currency(value):
    """Formata valor monetário para BRL com 2 casas decimais"""
    try:
        val = float(value)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(value)


def generate_csv_file(headers, data, nome_base="relatorio"):
    """Gera CSV na pasta exports/ com nome base + timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = EXPORTS_DIR / f"{nome_base}_{timestamp}.csv"
    try:
        with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data)
        return str(file_path)
    except Exception as e:
        raise Exception(f"Erro ao gerar CSV: {e}")


def generate_pdf_file(
    headers, data, nome_base="relatorio", title="Relatório", col_widths=None
):
    """Gera PDF com tabela organizada e colunas proporcionais."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = EXPORTS_DIR / f"{nome_base}_{timestamp}.pdf"

    try:
        pdf = FPDF(orientation="L")  # Landscape para melhor aproveitar espaço
        pdf.add_page()

        # Adicionar título (sem logo)
        pdf.set_font("Arial", "B", 14)
        pdf.set_xy(10, 10)
        pdf.cell(0, 10, title, ln=True, align="C")
        pdf.ln(8)

        # Configurar dimensões
        ncols = max(1, len(headers))
        page_width = pdf.w - 2 * pdf.l_margin

        # Determinar larguras das colunas
        if col_widths and isinstance(col_widths, (list, tuple)):
            # Tratar col_widths como pesos relativos (somatório → page_width)
            total_weight = float(sum(col_widths)) or float(ncols)
            col_widths = [page_width * (float(w) / total_weight) for w in col_widths]
        else:
            # Heurística para pesos das colunas quando não informado
            weights = []
            for h in headers:
                lh = str(h).lower()
                if (
                    "produto" in lh
                    or "descricao" in lh
                    or "nome" in lh
                    or "contato" in lh
                ):
                    weights.append(2.2)
                elif any(
                    k in lh
                    for k in (
                        "valor",
                        "preco",
                        "total",
                        "custo",
                        "venda",
                        "margem",
                        "lucro",
                    )
                ):
                    weights.append(1.5)
                elif any(k in lh for k in ("id", "qtd", "quantidade", "estoque")):
                    weights.append(1)
                else:
                    weights.append(1.2)

            total_weight = sum(weights) or ncols
            col_widths = [page_width * (w / total_weight) for w in weights]

        # Desenhar cabeçalho
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(200, 200, 200)

        x_start = pdf.l_margin
        for i, header in enumerate(headers):
            pdf.set_xy(x_start, pdf.get_y())
            pdf.cell(col_widths[i], 8, str(header), border=1, align="C", fill=True)
            x_start += col_widths[i]

        pdf.ln(8)

        # Desenhar dados
        pdf.set_font("Arial", "", 8)
        numeric_keys = {
            "qtd",
            "quantidade",
            "preco",
            "valor",
            "total",
            "custo",
            "venda",
            "margem",
            "lucro",
            "estoque",
            "id",
        }

        for row in data:
            row_cells = [str(x) for x in row]
            if len(row_cells) < ncols:
                row_cells += [""] * (ncols - len(row_cells))

            x_start = pdf.l_margin
            for i, item in enumerate(row_cells):
                h = str(headers[i]).lower()
                align = "R" if any(k in h for k in numeric_keys) else "L"

                # Formatar valores monetários
                if any(
                    k in h
                    for k in (
                        "valor",
                        "preco",
                        "total",
                        "custo",
                        "venda",
                        "margem",
                        "lucro",
                    )
                ):
                    item = format_currency(item)

                # Garantir que o texto não ultrapasse a largura da célula
                pdf.set_xy(x_start, pdf.get_y())
                safe_text = str(item)
                try:
                    max_width = max(5, col_widths[i] - 2)  # margem de 2mm
                    if pdf.get_string_width(safe_text) > max_width:
                        ellipsis = "..."
                        # Reduz até caber, preservando indicador de truncamento
                        while (
                            safe_text
                            and pdf.get_string_width(safe_text + ellipsis) > max_width
                        ):
                            safe_text = safe_text[:-1]
                        safe_text = (safe_text + ellipsis) if safe_text else ""
                except Exception:
                    # Fallback: truncar a um tamanho razoável
                    safe_text = safe_text[:35]

                pdf.cell(col_widths[i], 7, safe_text, border=1, align=align)
                x_start += col_widths[i]

            pdf.ln(7)

        pdf.output(str(file_path))
        return str(file_path)
    except Exception as e:
        raise Exception(f"Erro ao gerar PDF: {e}")
