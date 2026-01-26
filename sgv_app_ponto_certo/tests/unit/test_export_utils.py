import os
from pathlib import Path

from utils.export_utils import generate_csv_file


def test_generate_csv_file_creates_file(tmp_path):
    headers = ["col1", "col2"]
    data = [[1, 2], [3, 4]]
    # gera o arquivo
    path = generate_csv_file(headers, data, nome_base="test_rel")
    p = Path(path)
    assert p.exists()
    # checa que o arquivo está na pasta exports
    assert p.parent.name == "exports"
    # limpa
    try:
        p.unlink()
    except Exception:
        pass
