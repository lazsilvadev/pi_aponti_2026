import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
PROD_FILE = BASE / "data" / "produtos.json"
OUT_XLS = BASE / "scripts" / "test_import.xlsx"

# Carrega produtos atuais
with open(PROD_FILE, "r", encoding="utf-8") as f:
    produtos = json.load(f)

# Criar um Excel com um produto duplicado e um novo
rows = [
    {
        "Nome": produtos[0]["nome"],
        "Categoria": produtos[0]["categoria"],
        "Validade": produtos[0]["validade"],
        "Quantidade": produtos[0]["quantidade"],
        "Preço": produtos[0].get("preco_venda", ""),
        "Código de Barras": produtos[0]["codigo_barras"],
    },
    {
        "Nome": "Produto Novo Teste",
        "Categoria": "Mercearia",
        "Validade": "01/01/2027",
        "Quantidade": 10,
        "Preço": 1.5,
        "Código de Barras": "9999999999999",
    },
]

df = pd.DataFrame(rows)
df.to_excel(OUT_XLS, index=False, engine="openpyxl")
print(f"Arquivo de teste gerado: {OUT_XLS}")

# Agora simula a lógica de normalização e detecção de duplicados (leitura simplificada)
import unicodedata as _ud


def _norm(s: str) -> str:
    if not s:
        return ""
    nf = _ud.normalize("NFD", str(s))
    return "".join(c for c in nf if _ud.category(c) != "Mn").strip().lower()


def _norm_cb(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.endswith(".0") and s.replace(".0", "").isdigit():
        s = s[:-2]
    return s


existentes_cod = {
    _norm_cb(p.get("codigo_barras")) for p in produtos if p.get("codigo_barras")
}
existentes_nome_cat = {
    (_norm(p.get("nome")), _norm(p.get("categoria"))) for p in produtos
}

# Ler o arquivo gerado
df2 = pd.read_excel(OUT_XLS, engine="openpyxl")
records = df2.to_dict(orient="records")

importados_dedup = []
duplicados = []
for row in records:
    nome = row.get("Nome") or row.get("nome")
    categoria = row.get("Categoria") or row.get("categoria")
    quantidade = row.get("Quantidade") or row.get("quantidade")
    codigo_barras = row.get("Código de Barras") or row.get("codigo_barras")

    cb = _norm_cb(codigo_barras)
    key_nome_cat = (_norm(nome), _norm(categoria))

    if (cb and cb in existentes_cod) or (key_nome_cat in existentes_nome_cat):
        duplicados.append(nome or cb or "(sem nome)")
        continue

    importados_dedup.append({"nome": nome, "categoria": categoria})

print("Duplicados detectados:", duplicados)
print("Importáveis:", importados_dedup)
