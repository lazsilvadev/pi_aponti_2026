"""
Lógica de suporte para Devolver & Trocar no Caixa.

Fornece funções utilizadas pela UI para listar vendas recentes
por usuário e preparar itens da venda para operação de troca.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from models.db_models import ItemVenda, Produto, Venda


def _format_datetime(dt: datetime) -> str:
    try:
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(dt)


def buscar_vendas_do_caixa(
    pdv_core, usuario_responsavel: Optional[str], limite: int = 20
) -> List[Dict[str, Any]]:
    """Retorna vendas recentes do usuário informado com resumo dos itens.

    Estrutura de retorno por venda:
    {
        "id": int,
        "data": "dd/mm/aaaa HH:MM",
        "total": float,
        "pagamento": str,
        "resumo": "Produto x qtd, Produto y qtd, ..."
    }
    """
    try:
        q = pdv_core.session.query(Venda)
        # Se um usuário específico foi informado, filtrar; caso contrário, listar todas
        if usuario_responsavel:
            q = q.filter(Venda.usuario_responsavel == usuario_responsavel)
        q = q.order_by(Venda.data_venda.desc())
        if limite and limite > 0:
            q = q.limit(limite)
        vendas = q.all()

        saida: List[Dict[str, Any]] = []
        for v in vendas:
            nomes = []
            for it in getattr(v, "itens", []):
                nome = None
                try:
                    if it.produto:
                        nome = it.produto.nome
                    else:
                        nome = "(produto)"
                except Exception:
                    nome = "(produto)"
                qtd = getattr(it, "quantidade", 0) or 0
                nomes.append(f"{nome} x {qtd}")
            resumo = ", ".join(nomes) if nomes else "Sem itens"
            saida.append(
                {
                    "id": v.id,
                    "data": _format_datetime(v.data_venda),
                    "total": float(getattr(v, "total", 0.0) or 0.0),
                    "pagamento": getattr(v, "forma_pagamento", ""),
                    "resumo": resumo,
                }
            )
        return saida
    except Exception as ex:
        print(f"[DEVOLUCOES LOGIC] Erro ao buscar vendas: {ex}")
        return []


def processar_devolucao_e_trocar(
    pdv_core, venda_id: int, usuario_responsavel: str
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    """Prepara itens da venda para operação de troca (não efetiva alterações).

    Retorna: (sucesso, mensagem, carrinho)
    onde carrinho = [{"produto_id": int, "nome": str, "qtd": int, "preco": float}, ...]
    """
    try:
        venda = pdv_core.session.query(Venda).filter_by(id=venda_id).first()
        if not venda:
            return False, "Venda não encontrada.", []

        # Opcional: validar usuário responsável
        # if venda.usuario_responsavel != usuario_responsavel:
        #     return False, "Venda pertence a outro usuário.", []

        carrinho: List[Dict[str, Any]] = []
        for it in getattr(venda, "itens", []):
            try:
                produto_id = getattr(it, "produto_id", None)
                produto_nome = (
                    it.produto.nome if getattr(it, "produto", None) else "Produto"
                )
                qtd = getattr(it, "quantidade", 0) or 0
                preco = float(getattr(it, "preco_unitario", 0.0) or 0.0)
                carrinho.append(
                    {
                        "produto_id": produto_id,
                        "nome": produto_nome,
                        "qtd": qtd,
                        "preco": preco,
                    }
                )
            except Exception:
                pass

        if not carrinho:
            return False, "Venda sem itens para trocar.", []
        return True, "Itens carregados para troca.", carrinho
    except Exception as ex:
        print(f"[DEVOLUCOES LOGIC] Erro ao preparar troca: {ex}")
        return False, "Erro ao preparar troca.", []
