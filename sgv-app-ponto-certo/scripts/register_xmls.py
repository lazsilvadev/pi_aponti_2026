"""Script para registrar XMLs de `exports/xmls/` em `data/imported_xmls.json`.

Uso: python scripts/register_xmls.py

Ele não altera compras — apenas extrai dados principais do XML e grava registros
no arquivo JSON que a UI usa como fallback para "Últimos XMLs importados".
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XML_DIR = ROOT / "exports" / "xmls"
OUT_FILE = ROOT / "data" / "imported_xmls.json"

if not XML_DIR.exists():
    print(f"Pasta de XMLs não encontrada: {XML_DIR}")
    raise SystemExit(1)

records = []
for p in sorted(XML_DIR.glob("*.xml")):
    try:
        tree = ET.parse(p)
        root = tree.getroot()

        def find_text(name, ctx=root, default=""):
            for el in ctx.iter():
                if el.tag.split("}")[-1] == name:
                    return (el.text or "").strip()
            return default

        nro = find_text("nNF")
        chave = find_text("chNFe") or find_text("NFe")
        data_emissao = find_text("dhEmi") or find_text("dEmi")
        fornecedor_nome = find_text("xNome", ctx=root) or find_text("xNome", ctx=root)
        fornecedor_doc = find_text("CNPJ") or find_text("CPF")
        total_valor = find_text("vNF") or find_text("vProd")

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
                nome = find_text("xProd", ctx=prod)
                qt = find_text("qCom", ctx=prod)
                vprod = find_text("vProd", ctx=prod)
                itens.append({"nome": nome, "q": qt, "v": vprod})

        record = {
            "nf": nro,
            "chave": chave,
            "data": data_emissao,
            "fornecedor": fornecedor_nome,
            "cnpj": fornecedor_doc,
            "total": total_valor,
            "itens": itens,
            "path": str(p.resolve()),
        }
        records.append(record)
    except Exception as e:
        print(f"Falha ao processar {p}: {e}")

OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
# carregar existentes
existing = []
if OUT_FILE.exists():
    try:
        existing = json.loads(OUT_FILE.read_text(encoding="utf-8")) or []
    except Exception:
        existing = []

# concatenar novos (evitar duplicatas por chave)
existing_keys = {(r.get("chave") or r.get("nf") or "") for r in existing}
for r in records:
    key = r.get("chave") or r.get("nf") or ""
    if key in existing_keys:
        continue
    existing.append(r)

OUT_FILE.write_text(
    json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"Registrados {len(records)} XML(s) em {OUT_FILE}")
