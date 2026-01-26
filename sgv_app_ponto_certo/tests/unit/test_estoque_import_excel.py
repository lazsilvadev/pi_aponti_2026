from datetime import datetime

import pandas as pd

from estoque.view import read_products_from_file


def test_import_excel(tmp_path):
    # cria um DataFrame com alguns produtos válidos
    data = [
        {
            "Nome": "Maçã",
            "Categoria": "Hortifrúti",
            "Validade": datetime(2025, 12, 31),
            "Quantidade": 10,
            "Preço": 4.5,
            "Código de Barras": "123",
        },
        {
            "Nome": "Pão",
            "Categoria": "Padaria",
            "Validade": datetime(2025, 11, 30),
            "Quantidade": 5,
            "Preço": 2.3,
            "Código de Barras": "456",
        },
    ]
    df = pd.DataFrame(data)
    path = tmp_path / "produtos_test.xlsx"
    # salva usando openpyxl engine
    df.to_excel(path, index=False, engine="openpyxl")

    records = read_products_from_file(str(path), starting_id=0)

    assert len(records) == 2
    first = records[0]
    assert first["nome"] == "Maçã"
    assert first["categoria"] == "Hortifrúti"
    assert isinstance(first["validade"], datetime)
    assert first["quantidade"] == 10
    assert abs(first["preco_venda"] - 4.5) < 0.01
