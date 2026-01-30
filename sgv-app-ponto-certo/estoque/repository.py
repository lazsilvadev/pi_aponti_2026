import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Caminho base do projeto (um nível acima da pasta "estoque")
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ARQUIVO_DADOS = os.path.join(BASE_DIR, "data", "produtos.json")

# Nota: a importação de pandas pode ser pesada ou travar em alguns ambientes.
# Fazemos a importação de forma lazy dentro da função que necessita de Excel
# para evitar bloquear o startup do aplicativo quando pandas não for usado.

from .formatters import converter_texto_para_data as _conv_data
from .formatters import converter_texto_para_preco as _conv_preco


def carregar_produtos() -> List[Dict[str, Any]]:
    """Carrega produtos do arquivo JSON e converte campos.

    - Converte a string de validade para datetime.
    - Garante que preco_venda seja float.
    """
    if os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
            dados = json.load(f)
            for p in dados:
                p["validade"] = datetime.strptime(p["validade"], "%d/%m/%Y")
                p["preco_venda"] = float(p.get("preco_venda", p.get("preco", 0.0)))
                p["preco_custo"] = float(p.get("preco_custo", 0.0))
                # Garantir compatibilidade com campo lote (pode não existir em arquivos antigos)
                p["lote"] = p.get("lote", "")
            return dados
    return []


def salvar_produtos(produtos: List[Dict[str, Any]]) -> None:
    """Persiste a lista de produtos no arquivo JSON padronizando campos."""
    dados: List[Dict[str, Any]] = []
    for p in produtos:
        dados.append(
            {
                "id": p["id"],
                "nome": p["nome"],
                "categoria": p["categoria"],
                "validade": p["validade"].strftime("%d/%m/%Y"),
                "lote": p.get("lote", ""),
                "quantidade": p["quantidade"],
                "preco_venda": float(p.get("preco_venda", p.get("preco", 0.0))),
                "preco_custo": float(p.get("preco_custo", 0.0)),
                "codigo_barras": p.get("codigo_barras", ""),
            }
        )
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def read_products_from_file(
    file_path: str, starting_id: int = 0
) -> List[Dict[str, Any]]:
    """Lê um arquivo CSV ou Excel e retorna lista de produtos normalizados.

    - `file_path`: caminho para .csv, .xls ou .xlsx
    - `starting_id`: id inicial (os ids retornados começam em starting_id+1)
    """
    ext = Path(file_path).suffix.lower()
    novos: List[Dict[str, Any]] = []

    if ext in (".xls", ".xlsx"):
        try:
            import pandas as pd  # opcional para .xls/.xlsx
        except Exception:
            raise RuntimeError(
                "Falha ao importar pandas (necessário para ler arquivos Excel). Instale 'pandas' e 'openpyxl' se quiser suporte a Excel."
            )
        df = pd.read_excel(file_path, engine="openpyxl")
        records = df.to_dict(orient="records")
    else:
        with open(file_path, encoding="utf-8-sig") as f:
            records = list(csv.DictReader(f))

    for row in records:
        nome = row.get("Nome") or row.get("nome")
        categoria = row.get("Categoria") or row.get("categoria")
        validade = row.get("Validade") or row.get("validade")
        quantidade = row.get("Quantidade") or row.get("quantidade")
        codigo_barras = (
            row.get("Código de Barras")
            or row.get("codigo_barras")
            or row.get("Codigo de Barras")
        )
        lote = row.get("Lote") or row.get("lote") or ""

        # normaliza validade
        if hasattr(validade, "strftime"):
            validade_str = validade.strftime("%d/%m/%Y")
        else:
            validade_str = str(validade) if validade is not None else ""

        validade_obj = _conv_data(validade_str)
        try:
            # Valida campos e retorna quantidade
            if not (nome and categoria and quantidade):
                raise ValueError("Campos obrigatórios ausentes")
            if validade_obj is None:
                raise ValueError("Data inválida")
            qtd = int(quantidade)
            if qtd < 0:
                raise ValueError("Quantidade negativa")
        except Exception:
            # ignora linhas inválidas
            continue

        preco_venda = _conv_preco(
            row.get("Preço")
            or row.get("Preco")
            or row.get("preco_venda")
            or row.get("preco")
            or row.get("Preço de Venda")
        )

        preco_custo = _conv_preco(
            row.get("Preço de Custo")
            or row.get("Preco de Custo")
            or row.get("Custo")
            or row.get("custo")
            or row.get("preco_custo")
        )

        novo = {
            "id": starting_id + len(novos) + 1,
            "nome": nome,
            "categoria": categoria,
            "validade": validade_obj,
            "quantidade": qtd,
            "lote": lote,
            "preco_venda": preco_venda,
            "preco_custo": preco_custo,
            "codigo_barras": codigo_barras or "",
        }
        novos.append(novo)

    return novos
