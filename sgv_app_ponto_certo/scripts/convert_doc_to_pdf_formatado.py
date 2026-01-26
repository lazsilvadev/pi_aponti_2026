from fpdf import FPDF
from pathlib import Path
import re

TXT_PATH = Path("exports") / "documentacao_tecnica_completa.txt"
PDF_PATH = Path("exports") / "documentacao_tecnica_completa_formatado.pdf"

if not TXT_PATH.exists():
    print(f"Arquivo fonte não encontrado: {TXT_PATH}")
    raise SystemExit(1)


class PDF(FPDF):
    def footer(self):
        # Rodapé com número de página
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f"Página {self.page_no()}", 0, 0, "C")


pdf = PDF(orientation="P", unit="mm", format="A4")
pdf.alias_nb_pages()
pdf.set_auto_page_break(True, margin=15)
pdf.add_page()
pdf.set_left_margin(18)
pdf.set_right_margin(18)

# Leituras e configuração de fonte
with open(TXT_PATH, "r", encoding="utf-8") as f:
    text = f.read()

lines = text.splitlines()
heading_re = re.compile(r"^(\d+)\.\s+(.*)$")

pdf.set_font("Arial", size=12)

for line in lines:
    s = line.strip()
    if not s:
        pdf.ln(4)
        continue

    # Top-level numerado (ex.: "1. Introdução")
    m = heading_re.match(s)
    if m:
        # Título de seção
        pdf.set_font("Arial", "B", 14)
        safe = s.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 8, safe)
        pdf.ln(2)
        pdf.set_font("Arial", size=11)
        continue

    # Subtítulos curtos terminando em ':' -> destacar
    if s.endswith(":") and len(s) < 80:
        pdf.set_font("Arial", "B", 12)
        safe = s.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 7, safe)
        pdf.ln(1)
        pdf.set_font("Arial", size=11)
        continue

    # Parágrafo normal
    safe = s.encode("latin-1", errors="replace").decode("latin-1")
    pdf.multi_cell(0, 6, safe)
    pdf.ln(2)

pdf.output(str(PDF_PATH))
print(f"PDF gerado: {PDF_PATH}")
