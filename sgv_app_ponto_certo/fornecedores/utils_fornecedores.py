from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MEIOS_PAGAMENTO = ["Débito", "Dinheiro", "Crédito", "Pix", "Boleto"]
CATEGORIA_OPCOES = [
    ("alimentos", "Alimentos"),
    ("bebidas", "Bebidas"),
    ("higiene", "Higiene e Limpeza"),
    ("limpeza", "Produtos de Limpeza"),
    ("outros", "Outros"),
]


def normalize_key(s: str) -> str:
    return (s or "").strip().lower().replace("/", " ").replace("  ", " ")


def get_any(row: Dict[str, Any], keys: List[str]) -> str:
    for k in keys:
        for rk in row.keys():
            if normalize_key(rk) == normalize_key(k):
                return str(row.get(rk) or "").strip()
    return ""


def parse_meios(s: str) -> str:
    if not s:
        return ""
    partes = [p.strip() for p in s.replace(";", ",").split(",") if p.strip()]
    filtrados = [p for p in partes if p in MEIOS_PAGAMENTO]
    return ", ".join(filtrados) if filtrados else ", ".join(partes)


def map_status(s: str) -> str:
    v = (s or "").strip().lower()
    return (
        "ativo" if v in ("ativo", "1", "sim", "true") else ("inativo" if v else "ativo")
    )


def map_categoria(val: str) -> Optional[str]:
    v = (val or "").strip()
    if not v:
        return None
    values = {value for value, _ in CATEGORIA_OPCOES}
    if v in values:
        return v
    labels = {label: value for value, label in CATEGORIA_OPCOES}
    return labels.get(v, None)


def clean_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def find_fornecedor_by_doc_ou_nome(pdv_core, cnpj_cpf: str, nome: str):
    try:
        if cnpj_cpf:
            f = pdv_core.session.query(
                pdv_core.model_classes.get("Fornecedor")
                if hasattr(pdv_core, "model_classes")
                else None
            )
        # Fallback handled in caller (view) where pdv_core.get_all_fornecedores is available
    except Exception:
        return None
    return None


from pathlib import Path
from typing import Any, Dict, List, Optional

MEIOS_PAGAMENTO = ["Débito", "Dinheiro", "Crédito", "Pix", "Boleto"]
CATEGORIA_OPCOES = [
    ("alimentos", "Alimentos"),
    ("bebidas", "Bebidas"),
    ("higiene", "Higiene e Limpeza"),
    ("limpeza", "Produtos de Limpeza"),
    ("outros", "Outros"),
]


def _normalize_key(s: str) -> str:
    return (s or "").strip().lower().replace("/", " ").replace("  ", " ")


def get_any(row: Dict[str, Any], keys: List[str]) -> str:
    """Retorna o valor da primeira chave equivalente encontrada na linha."""
    for k in keys:
        for rk in row.keys():
            if _normalize_key(rk) == _normalize_key(k):
                return str(row.get(rk) or "").strip()
    return ""


def parse_meios(s: str) -> str:
    if not s:
        return ""
    partes = [p.strip() for p in s.replace(";", ",").split(",") if p.strip()]
    filtrados = [p for p in partes if p in MEIOS_PAGAMENTO]
    return ", ".join(filtrados) if filtrados else ", ".join(partes)


def map_status(s: str) -> str:
    v = (s or "").strip().lower()
    return (
        "ativo" if v in ("ativo", "1", "sim", "true") else ("inativo" if v else "ativo")
    )


def map_categoria(val: str) -> Optional[str]:
    v = (val or "").strip()
    if not v:
        return None
    values = {value for value, _ in CATEGORIA_OPCOES}
    if v in values:
        return v
    labels = {label: value for value, label in CATEGORIA_OPCOES}
    return labels.get(v, None)


def clean_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def find_fornecedor_by_doc_ou_nome(pdv_core, cnpj_cpf: str, nome: str):
    try:
        if cnpj_cpf:
            f = (
                pdv_core.session.query(pdv_core.models.Fornecedor)
                .filter_by(cnpj_cpf=cnpj_cpf)
                .first()
            )
            if f:
                return f
        if nome:
            candidatos = pdv_core.get_all_fornecedores()
            target = (nome or "").strip().lower()
            for f in candidatos:
                if (
                    getattr(f, "nome_razao_social", "") or getattr(f, "nome", "")
                ).strip().lower() == target:
                    return f
    except Exception:
        return None
    return None
