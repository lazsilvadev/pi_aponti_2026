import xml.etree.ElementTree as ET
from pathlib import Path


def find_text(root, name, ctx=None, default=""):
    if ctx is None:
        ctx = root
    for el in ctx.iter():
        if el.tag.split("}")[-1] == name:
            return (el.text or "").strip()
    return default


p = Path("tests/sample_nfe.xml")
if not p.exists():
    print("Arquivo tests/sample_nfe.xml não encontrado")
    raise SystemExit(1)

try:
    tree = ET.parse(p)
    root = tree.getroot()

    nro = find_text(root, "nNF") or find_text(root, "cNF")
    fornecedor = find_text(root, "xNome")
    total = find_text(root, "vNF") or find_text(root, "vProd")
    itens = []
    for det in root.iter():
        if det.tag.split("}")[-1] == "det":
            prod = None
            for c in det.iter():
                if c.tag.split("}")[-1] == "prod":
                    prod = c
                    break
            if prod is None:
                continue
            nome = find_text(prod, "xProd")
            q = find_text(prod, "qCom")
            v = find_text(prod, "vProd")
            itens.append((nome, q, v))

    print("nNF:", nro)
    print("Fornecedor:", fornecedor)
    print("Total:", total)
    print("Itens:")
    for i, it in enumerate(itens, 1):
        print(f"  {i}. {it[0]} — qt={it[1]} — v={it[2]}")
except Exception as e:
    print("Erro ao parsear XML:", e)
    raise
