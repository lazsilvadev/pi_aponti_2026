"""
Helper para expor assets embutidos como data URIs (base64).
Usado para garantir que imagens apareçam em executáveis onefile.
"""

import base64
from pathlib import Path

from .path_resolver import get_asset_path


def _read_base64(filename: str) -> str:
    p = Path(get_asset_path(filename))
    try:
        with p.open("rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode("ascii")
        return b64
    except Exception:
        return ""


def logo_data_uri() -> str:
    """Retorna data URI (image/png) da logo embutida.

    Retorna string vazia se não for possível ler o arquivo.
    """
    b64 = _read_base64("Mercadinho_Ponto_Certo.png")
    if not b64:
        return ""
    return f"data:image/png;base64,{b64}"


def animacao_data_uri() -> str:
    b64 = _read_base64("animacao.gif")
    if not b64:
        return ""
    return f"data:image/gif;base64,{b64}"
