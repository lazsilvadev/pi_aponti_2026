from datetime import datetime
from typing import Optional


def converter_texto_para_data(texto) -> Optional[datetime]:
    """Converte texto dd/mm/aaaa em datetime ou None."""
    if texto is None:
        return None
    try:
        if hasattr(texto, "strftime"):
            return texto
        return datetime.strptime(str(texto).strip(), "%d/%m/%Y")
    except Exception:
        return None


def converter_texto_para_preco(texto) -> float:
    """Converte string de preço (com R$, vírgula/ponto) em float."""
    if texto is None:
        return 0.0
    try:
        if isinstance(texto, (int, float)):
            return float(texto)
        s = str(texto).strip()
        # Normalizações comuns
        s = s.replace("R$", "").replace("r$", "").strip()
        s = s.replace("\u00a0", "")  # NBSP
        s = s.replace(" ", "")
        # Remover quaisquer caracteres incomuns mantendo dígitos, vírgula, ponto e sinal
        s = "".join(ch for ch in s if ch.isdigit() or ch in ",.-")
        if s == "":
            return 0.0
        # Se possuir vírgula, assume formato brasileiro: ponto milhar, vírgula decimal
        if "," in s:
            s = s.replace(".", "")
            s = s.replace(",", ".")
        else:
            # Apenas ponto presente: manter como separador decimal
            # Se houver múltiplos pontos, remover todos exceto o último (milhares)
            if s.count(".") > 1:
                parts = s.split(".")
                s = "".join(parts[:-1]) + "." + parts[-1]
        return float(s)
    except Exception:
        return 0.0


def validar_produto(nome, categoria, quantidade, validade_obj) -> int:
    """Valida campos básicos do produto e retorna quantidade como int.

    Versão usada pela UI (mensagens amigáveis).
    """
    if not (nome and categoria and quantidade):
        raise ValueError("⚠️ Todos os campos são obrigatórios!")
    if validade_obj is None:
        raise ValueError("⚠️ Data inválida! Use o formato DD/MM/AAAA.")
    try:
        qtd = int(quantidade)
        if qtd < 0:
            raise ValueError()
        return qtd
    except Exception:
        raise ValueError("Quantidade deve ser um número inteiro positivo")
