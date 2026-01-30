import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from estoque.view import read_products_from_file

path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "tests", "estoque_import_teste.xlsx"
)
print("[TEST] Lendo:", path)

try:
    prods = read_products_from_file(path, starting_id=0)
    print("[RESULT] Produtos lidos:")
    for p in prods:
        print(
            f"- {p['nome']} | categoria={p['categoria']} | qtd={p['quantidade']} | preco_venda={p['preco_venda']} | codigo_barras={p.get('codigo_barras', '')}"
        )
except Exception as ex:
    print("[ERROR] Falha ao ler Excel:", ex)
    print("Se for falta de pandas/openpyxl, instale-os: pip install pandas openpyxl")
