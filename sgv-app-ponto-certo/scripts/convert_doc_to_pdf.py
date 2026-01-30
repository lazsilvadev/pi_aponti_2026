from fpdf import FPDF
from pathlib import Path

TXT_PATH = Path("exports") / "documentacao_tecnica_completa.txt"
PDF_PATH = Path("exports") / "documentacao_tecnica_completa.pdf"

if not TXT_PATH.exists():
    print(f"Arquivo fonte não encontrado: {TXT_PATH}")
    raise SystemExit(1)

with open(TXT_PATH, "r", encoding="utf-8") as f:
    text = f.read()

pdf = FPDF(orientation="P", unit="mm", format="A4")
pdf.set_auto_page_break(True, margin=15)
pdf.add_page()
pdf.set_font("Arial", size=12)

# Quebrar em parágrafos e escrever com multi_cell; sanitizar para latin-1
for para in text.split("\n\n"):
    p = para.strip()
    if not p:
        pdf.ln(4)
        continue
    safe = p.encode("latin-1", errors="replace").decode("latin-1")
    pdf.multi_cell(0, 6, safe)
    pdf.ln(2)

pdf.output(str(PDF_PATH))
print(f"PDF gerado: {PDF_PATH}")
