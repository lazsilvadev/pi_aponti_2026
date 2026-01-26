"""Utilitários de Devoluções e Trocas no estoque.

Persistência simples em JSON para registros de devolução
+ operações de validação e ajuste de estoque via SQLAlchemy.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models.db_models import ItemVenda, Produto, Venda

# Caminho do arquivo de persistência das devoluções
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DEVOLUCOES_FILE = os.path.join(DATA_DIR, "devolucoes.json")
HIDDEN_FILE = os.path.join(DATA_DIR, "devolucoes_hidden.json")


def _ensure_data_dir():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        pass


def _load_json(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_json(path: str, data: List[Dict]) -> None:
    _ensure_data_dir()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        # Em caso de falha, não interromper o fluxo da aplicação
        pass


# =========================
# Devoluções (arquivo JSON)
# =========================


def carregar_devol() -> List[Dict]:
    """Carrega a lista de devoluções do arquivo JSON."""
    return _load_json(DEVOLUCOES_FILE)


def carregar_hidden_ids() -> List[int]:
    """Carrega lista de ids escondidos (inteiros) do arquivo JSON.

    Retorna lista vazia se o arquivo não existir ou estiver malformado.
    """
    arr = _load_json(HIDDEN_FILE)
    try:
        return [int(x) for x in arr]
    except Exception:
        return []


def add_hidden_id(hid: int) -> None:
    """Adiciona um id à lista de escondidos e salva no arquivo.

    Não gera exceção em caso de falha; apenas tenta persistir.
    """
    try:
        ids = carregar_hidden_ids() or []
        try:
            hid_int = int(hid)
        except Exception:
            return
        if hid_int in ids:
            return
        ids.append(hid_int)
        _save_json(HIDDEN_FILE, ids)
    except Exception:
        pass


def remover_devolucao(dev_id: int) -> None:
    """Remove uma devolução pelo ID e salva o arquivo."""
    try:
        devs = carregar_devol()
        devs = [d for d in devs if int(d.get("id", -1)) != int(dev_id)]
        _save_json(DEVOLUCOES_FILE, devs)
    except Exception:
        pass


def adicionar_troca(
    devolucao_id: int, novo_produto_id: int, novo_produto_nome: str
) -> None:
    """Marca a devolução como trocada e registra o produto de troca."""
    try:
        devs = carregar_devol()
        for d in devs:
            if int(d.get("id", -1)) == int(devolucao_id):
                d["foi_trocado"] = True
                d["troca_para_id"] = int(novo_produto_id)
                d["troca_para_nome"] = novo_produto_nome
                d["troca_data"] = datetime.now().isoformat()
                break
        _save_json(DEVOLUCOES_FILE, devs)
    except Exception:
        pass


def registrar_devolucoes_por_venda(
    pdv_core, venda_id: int, motivo: str | None = None
) -> bool:
    """Registra devoluções (estorno) no arquivo JSON a partir de uma venda.

    Para cada item da venda, cria um registro com:
    - id (sequencial)
    - produto_id, produto_nome
    - quantidade
    - valor_total (preco_unitario * quantidade)
    - motivo (ex.: "Estorno da venda #123")
    - data (ISO agora)
    - foi_trocado = False
    """
    try:
        session = _get_session_from_pdv(pdv_core)
        if session is None:
            return False

        venda = session.query(Venda).filter_by(id=int(venda_id)).first()
        if not venda:
            return False

        devs = carregar_devol() or []
        base_id = max([int(d.get("id", 0)) for d in devs], default=0)

        registro_motivo = motivo.strip() if motivo else f"Estorno da venda #{venda.id}"
        agora_iso = datetime.now().isoformat()

        novos: List[Dict] = []
        for it in getattr(venda, "itens", []) or []:
            try:
                pid = int(getattr(it, "produto_id", 0) or 0)
                qtd = int(getattr(it, "quantidade", 0) or 0)
                preco = float(getattr(it, "preco_unitario", 0.0) or 0.0)
                nome = None
                try:
                    if getattr(it, "produto", None):
                        nome = it.produto.nome
                except Exception:
                    nome = None
                nome = nome or "Produto"

                base_id += 1
                novos.append(
                    {
                        "id": base_id,
                        "produto_id": pid,
                        "produto_nome": nome,
                        "quantidade": qtd,
                        "valor_total": preco * qtd,
                        "motivo": registro_motivo,
                        "data": agora_iso,
                        "foi_trocado": False,
                    }
                )
            except Exception:
                # ignora item malformado, continua os demais
                pass

        if novos:
            devs.extend(novos)
            _save_json(DEVOLUCOES_FILE, devs)
            return True
        return False
    except Exception:
        return False

    def registrar_devolucao_item(
        pdv_core, venda_id: int, item_venda_id: int, motivo: str | None = None
    ) -> bool:
        """Registra uma devolução única (item da venda) no arquivo JSON.

        - procura o ItemVenda pelo `item_venda_id` e `venda_id` e cria um registro único
        - similar a `registrar_devolucoes_por_venda` mas apenas para um item
        """
        try:
            session = _get_session_from_pdv(pdv_core)
            if session is None:
                return False

            it = (
                session.query(ItemVenda)
                .filter_by(id=int(item_venda_id), venda_id=int(venda_id))
                .first()
            )
            if not it:
                return False

            devs = carregar_devol() or []
            base_id = max([int(d.get("id", 0)) for d in devs], default=0)

            registro_motivo = (
                motivo.strip() if motivo else f"Estorno da venda #{venda_id}"
            )
            agora_iso = datetime.now().isoformat()

            try:
                pid = int(getattr(it, "produto_id", 0) or 0)
                qtd = int(getattr(it, "quantidade", 0) or 0)
                preco = float(getattr(it, "preco_unitario", 0.0) or 0.0)
                nome = None
                try:
                    if getattr(it, "produto", None):
                        nome = it.produto.nome
                except Exception:
                    nome = None
                nome = nome or "Produto"

                base_id += 1
                registro = {
                    "id": base_id,
                    "produto_id": pid,
                    "produto_nome": nome,
                    "quantidade": qtd,
                    "valor_total": preco * qtd,
                    "motivo": registro_motivo,
                    "data": agora_iso,
                    "foi_trocado": False,
                }
                devs.append(registro)
                _save_json(DEVOLUCOES_FILE, devs)
                return True
            except Exception:
                return False
        except Exception:
            return False


# =========================
# Estoque (via banco)
# =========================


def _get_session_from_pdv(pdv_core) -> Optional[Session]:
    return getattr(pdv_core, "session", None)


def validar_produto_existe(pdv_core, valor: str) -> Tuple[bool, Optional[Produto]]:
    """Tenta localizar um produto por ID numérico ou por código de barras.

    Retorna (True, Produto) se encontrado, caso contrário (False, None).
    """
    session = _get_session_from_pdv(pdv_core)
    if session is None:
        return False, None

    produto: Optional[Produto] = None
    # Primeiro: sempre tentar por código de barras (string)
    try:
        valor_str = str(valor)
        produto = (
            session.query(Produto).filter(Produto.codigo_barras == valor_str).first()
        )
    except Exception:
        produto = None

    # Se não achou e entrada é numérica, tentar como ID do produto
    if not produto:
        try:
            if str(valor).isdigit():
                produto = session.get(Produto, int(valor))
        except Exception:
            produto = None

    # Tratamento adicional: zeros à esquerda (ex.: "01300" vs "1300")
    if not produto:
        try:
            valor_sem_zeros = str(valor).lstrip("0")
            if valor_sem_zeros and valor_sem_zeros != str(valor):
                produto = (
                    session.query(Produto)
                    .filter(Produto.codigo_barras == valor_sem_zeros)
                    .first()
                )
        except Exception:
            produto = None

    if produto:
        return True, produto
    return False, None


def atualizar_estoque_troca(
    pdv_core,
    produto_original_id: int,
    novo_produto_id: int,
    quantidade: int,
) -> Tuple[bool, str]:
    """Atualiza estoque para uma troca:
    - Aumenta o estoque do produto original em `quantidade`.
    - Diminui o estoque do novo produto em `quantidade` (se suficiente).
    """
    session = _get_session_from_pdv(pdv_core)
    if session is None:
        return False, "Sessão do banco indisponível"

    try:
        original = session.get(Produto, int(produto_original_id))
        novo = session.get(Produto, int(novo_produto_id))
        if not original or not novo:
            return False, "Produto(s) não encontrados"

        qtd = int(quantidade or 0)
        if qtd <= 0:
            return False, "Quantidade inválida"

        if (novo.estoque_atual or 0) < qtd:
            return False, "Estoque insuficiente do produto novo"

        original.estoque_atual = (original.estoque_atual or 0) + qtd
        novo.estoque_atual = (novo.estoque_atual or 0) - qtd
        session.commit()
        return True, "Estoque atualizado com sucesso"
    except Exception as e:
        try:
            session.rollback()
        except Exception:
            pass
        return False, f"Erro ao atualizar estoque: {e}"
