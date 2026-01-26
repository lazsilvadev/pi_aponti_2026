import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from estoque.formatters import converter_texto_para_preco
from estoque.view import read_products_from_file

print("[TEST] Converters:")
print("12,50 ->", converter_texto_para_preco("12,50"))
print("12.50 ->", converter_texto_para_preco("12.50"))
print("1.249,00 ->", converter_texto_para_preco("1.249,00"))

print("\n[TEST] read_products_from_file:")
prods = read_products_from_file("exports/test_import_estoque.csv", starting_id=0)
for p in prods:
    print(p["nome"], p["preco_venda"])
