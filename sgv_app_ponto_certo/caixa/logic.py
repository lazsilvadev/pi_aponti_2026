"""Regras de negócio do módulo de caixa.

Este arquivo concentra funções puras (ou quase puras) que não
dependem diretamente de widgets do Flet. A view (`caixa.view`)
usa estas funções para montar UI e reagir a eventos.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


@dataclass
class ProdutoBasico:
    id: str | None
    nome: str
    preco_venda: float
    quantidade: int
    codigo_barras: str | None = None


def carregar_produtos_de_json(
    dados: Sequence[Mapping[str, Any]],
) -> List[SimpleNamespace]:
    """Normaliza lista de dicts de produtos vindos do JSON.

    Não toca em Flet, apenas normaliza campos e devolve objetos simples.
    """

    produtos: List[SimpleNamespace] = []
    for p in dados:
        p = dict(p)
        p.setdefault("preco_venda", float(p.get("preco_venda", p.get("preco", 0.0))))
        p.setdefault("codigo_barras", p.get("codigo", p.get("codigo_barras", "")))
        p.setdefault("nome", p.get("nome", p.get("descricao", "Produto")))
        p.setdefault("quantidade", int(p.get("quantidade", 0)))
        produtos.append(SimpleNamespace(**p))
    return produtos


def montar_cache_produtos(
    produtos: Iterable[Any],
    overlay_por_codigo: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Monta dicionário de cache indexado por id e por código de barras.

    - `produtos` pode conter dicts ou objetos com atributos.
    - `overlay_por_codigo`, se fornecido, sobrescreve chaves existentes.
    """

    cache: Dict[str, Any] = {}

    for p in produtos:
        if isinstance(p, dict):
            id_val = str(p.get("id", "")).strip()
            codigo_barras = str(p.get("codigo_barras") or p.get("codigo") or "").strip()
        else:
            id_val = str(getattr(p, "id", "")).strip()
            codigo_barras = str(
                getattr(p, "codigo_barras", "") or getattr(p, "codigo", "") or ""
            ).strip()

        if id_val:
            cache[id_val] = p
        if codigo_barras:
            cache[codigo_barras] = p

    if overlay_por_codigo:
        cache.update(overlay_por_codigo)

    return cache


def calcular_troco(valor_total: float, recebido_str: str) -> Tuple[float, float]:
    """Calcula valor recebido e troco a partir de uma string de entrada.

    A string pode conter prefixo "R$" e usar vírgula ou ponto.
    Retorna `(recebido, troco)`.
    Lança `ValueError` se o valor não puder ser convertido.
    """

    limpo = recebido_str.replace("R$", "").replace(",", ".").strip()
    if not limpo:
        limpo = "0"
    recebido = float(limpo)
    troco = recebido - float(valor_total)
    return recebido, troco


def montar_itens_cupom(cart_data: Mapping[str, Mapping[str, Any]]) -> List[List[str]]:
    """Gera lista de linhas de cupom a partir do carrinho.

    Cada item do carrinho deve ter chaves `nome`, `qtd`, `preco`.
    Retorna lista de listas: [nome, qtd, preco_fmt, total_fmt].
    """

    itens: List[List[str]] = []
    for _pid, item in cart_data.items():
        nome = str(item.get("nome", ""))
        qtd = int(item.get("qtd", 0))
        preco = float(item.get("preco", 0.0))
        total_linha = preco * qtd
        itens.append(
            [
                nome,
                str(qtd),
                f"R$ {preco:.2f}".replace(".", ","),
                f"R$ {total_linha:.2f}".replace(".", ","),
            ]
        )
    return itens


def validar_estoque_disponivel(
    estoque_atual: int, quantidade_em_carrinho: int, quantidade_nova: int
) -> Tuple[bool, str | None]:
    """Valida se há estoque suficiente para adicionar unidades.

    Retorna (ok, mensagem_erro). Se ok=False, mensagem_erro contém o motivo.
    """

    if estoque_atual <= 0:
        return False, "Estoque insuficiente: produto sem unidades disponíveis."

    if estoque_atual < quantidade_em_carrinho + quantidade_nova:
        return False, "Estoque insuficiente para adicionar outra unidade."

    return True, None


def persistir_estoque_json(
    caminho_arquivo: str, cart_data: Mapping[str, Mapping[str, Any]]
) -> None:
    """Atualiza o arquivo JSON de produtos decrementando as quantidades vendidas.

    Esta função não conhece Flet nem UI; apenas lê e escreve JSON.
    """

    if not os.path.exists(caminho_arquivo):
        print(f"⚠️ Não encontrou {caminho_arquivo} para persistir estoque")
        return

    try:
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            dados = json.load(f)

        for codigo, item in list(cart_data.items()):
            vendida = int(item.get("qtd", 0))
            if vendida <= 0:
                continue
            for p in dados:
                p_codigo = str(
                    p.get("codigo_barras", p.get("codigo", p.get("id", "")))
                ).strip()
                if p_codigo == str(codigo).strip():
                    p["quantidade"] = max(0, int(p.get("quantidade", 0)) - vendida)
                    break

        with open(caminho_arquivo, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        print("✅ Estoque atualizado em produtos.json após venda")
    except Exception as e:
        print(f"❌ Falha ao persistir estoque: {e}")


def montar_payload_pix(
    merchant_name: str,
    valor_total: float,
    chave_pix: str = None,
    cpf_cnpj: str = None,
    cidade: str = "Recife",
    tipo_pix: str = "dinamico",
) -> str:
    """
    Monta payload PIX (BRCode) válido para Banco do Brasil usando formato padrão FEBRABAN.

    Args:
        merchant_name: Nome do comerciante
        valor_total: Valor em reais
        chave_pix: Chave PIX (email, CPF, CNPJ ou telefone)
        cpf_cnpj: CPF ou CNPJ do recebedor
        cidade: Cidade do recebedor
        tipo_pix: "dinamico", "com_valor" ou "minimo"
    """
    # NOTA: Para que o pagamento via Pix seja reconhecido pelo app/terminal,
    # você deve fornecer aqui os dados reais do recebedor:
    # - `merchant_name`: nome do comerciante visível no BRCode (máx 25 chars)
    # - `chave_pix`: a chave Pix (e-mail, CPF/CNPJ ou telefone) cadastrada pelo recebedor
    # - `cpf_cnpj`: (opcional) CPF ou CNPJ do recebedor, sem pontuação
    # - `cidade`: cidade do recebedor (máx 15 chars)
    # Recomenda-se guardar `chave_pix` e `cpf_cnpj` em configuração segura (ex.: arquivo de config privado
    # ou variável de ambiente) e passar esses valores para esta função quando gerar o payload.

    # Se não há chave, retornar texto amigável (apenas para UX)
    if not chave_pix:
        return f"PIX {merchant_name.upper()} - Valor R$ {valor_total:.2f}".replace(
            ".", ","
        )

    # Delegar geração do BR Code para o gerador dedicado (mais confiável)
    try:
        from payments.pix_generator import PixGenerator

        gen = PixGenerator(chave_pix, merchant_name, cidade)
        payload_final = gen.gerar_payload(
            valor_total if tipo_pix == "com_valor" else 0.0
        )
        # Log básico para depuração
        print(
            f"[PIX] Tipo: {tipo_pix} | Tamanho: {len(payload_final)} | CRC: {payload_final[-4:]}"
        )
        return payload_final
    except Exception as e:
        # Se falhar, tentar montar payload simples (fallback)
        print(f"[PIX] Erro ao usar PixGenerator: {e}")
        # montar payload mínimo sem valor
        payload = "000201"  # header simplificado
        payload += f"59{len(str(merchant_name)[:25]):02d}{str(merchant_name)[:25]}"
        payload += f"60{len(str(cidade)[:15]):02d}{str(cidade)[:15]}"
        payload += "6304"
        crc = _calcular_crc16_pix(payload)
        return payload + crc


def _calcular_crc16_pix(data: str) -> str:
    """Calcula CRC16 CCITT-FALSE para BRCode PIX.
    Polinômio: 0x1021, Inicialização: 0xFFFF"""
    # Remover campo CRC se já existir
    if "6304" in data:
        data = data.split("6304")[0] + "6304"

    crc = 0xFFFF

    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc = crc << 1
            crc &= 0xFFFF

    return f"{crc:04X}"
