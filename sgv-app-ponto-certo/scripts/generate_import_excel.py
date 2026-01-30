import os

import pandas as pd


def main():
    rows = [
        {
            "Nome": "Arroz Premium 5kg",
            "Categoria": "Mercearia",
            "Validade": "15/02/2026",
            "Quantidade": 25,
            "Preço": 22.90,
            "Código de Barras": "7890001112223",
        },
        {
            "Nome": "Feijão Carioca 1kg",
            "Categoria": "Mercearia",
            "Validade": "20/02/2026",
            "Quantidade": 18,
            "Preço": 7.50,
            "Código de Barras": "7890003334445",
        },
        {
            "Nome": "Leite Integral 1L",
            "Categoria": "Frios e laticínios",
            "Validade": "10/03/2026",
            "Quantidade": 60,
            "Preço": 5.99,
            "Código de Barras": "7890005556667",
        },
        {
            "Nome": "Café Torrado 250g",
            "Categoria": "Mercearia",
            "Validade": "30/04/2026",
            "Quantidade": 40,
            "Preço": 12.49,
            "Código de Barras": "7890007778889",
        },
    ]
    df = pd.DataFrame(rows)
    out_path = os.path.join(
        os.path.dirname(__file__), "..", "estoque_import_teste.xlsx"
    )
    out_path = os.path.abspath(out_path)
    df.to_excel(out_path, index=False)
    print(out_path)


if __name__ == "__main__":
    main()
