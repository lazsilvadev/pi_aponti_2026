import json
import os
from types import SimpleNamespace
from typing import Any, Dict

import flet as ft

from .logic import carregar_produtos_de_json, montar_cache_produtos


def carregar_produtos_cache(
    page: ft.Page,
    pdv_core: Any,
    produtos_cache: Dict[str, Any],
    cache_loaded_ref: ft.Ref,
    cache_marker: object,
    force_reload: bool = False,
) -> bool:
    """Carrega produtos em cache combinando JSON e banco via pdv_core.

    Atualiza `produtos_cache` e marca `cache_loaded_ref.current = cache_marker` quando concluído.
    Retorna True em sucesso, False caso contrário.
    """
    if cache_loaded_ref.current and not force_reload:
        print(f"✅ Cache já carregado com {len(produtos_cache)} produtos")
        return True

    print("📦 Carregando cache de produtos...")

    try:
        produtos = []
        base_dir = os.path.dirname(os.path.dirname(__file__))
        arquivo = os.path.join(base_dir, "data", "produtos.json")
        if os.path.exists(arquivo):
            try:
                with open(arquivo, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                produtos = carregar_produtos_de_json(dados)
                print(f"✅ Carregou {len(produtos)} produtos de {arquivo} (priorizado)")
            except Exception as e:
                print(f" Falha ao ler {arquivo}: {e}")

        if not produtos:
            pdv_core_local = page.app_data.get("pdv_core")
            if not pdv_core_local:
                print(
                    " pdv_core não encontrado em page.app_data e produtos.json vazio!"
                )
                return False

            if hasattr(pdv_core_local, "get_produtos_list"):
                produtos = pdv_core_local.get_produtos_list()
                print(
                    f"✅ Método get_produtos_list() retornou {len(produtos)} produtos (pdv_core)"
                )
            elif hasattr(pdv_core_local, "get_all_produtos"):
                produtos = pdv_core_local.get_all_produtos()
                print(
                    f"✅ Método get_all_produtos() retornou {len(produtos)} produtos (pdv_core)"
                )
            else:
                print(" Nenhum método de busca de produtos encontrado no pdv_core!")
                return False

        if not produtos:
            print(
                " Nenhum produto disponível após tentativas de fallback (json e pdv_core)"
            )
            return False

        id_map = {}
        for p in produtos:
            if isinstance(p, dict):
                id_map[str(p.get("id", "")).strip()] = p
            else:
                id_map[str(getattr(p, "id", "")).strip()] = p

        extra_mappings = {}
        if os.path.exists(arquivo):
            try:
                with open(arquivo, "r", encoding="utf-8") as f:
                    dados_json = json.load(f)
                for pj in dados_json:
                    cod = str(pj.get("codigo_barras") or pj.get("codigo", "")).strip()
                    idv = str(pj.get("id", "")).strip()
                    if not cod:
                        continue
                    if idv and idv in id_map:
                        extra_mappings[cod] = id_map[idv]
                    else:
                        pj.setdefault(
                            "preco_venda",
                            float(pj.get("preco_venda", pj.get("preco", 0.0))),
                        )
                        pj.setdefault(
                            "nome", pj.get("nome", pj.get("descricao", "Produto"))
                        )
                        pj.setdefault("quantidade", int(pj.get("quantidade", 0)))
                        extra_mappings[cod] = SimpleNamespace(**pj)
            except Exception as e:
                print(f" Falha ao ler {arquivo} para overlay de códigos: {e}")

        produtos_cache.clear()
        produtos_cache.update(montar_cache_produtos(produtos, extra_mappings))

        cache_loaded_ref.current = cache_marker
        sample_keys = list(produtos_cache.keys())[:10]
        print(f"✅ Cache criado com {len(produtos_cache)} produtos")
        print(f"🔎 Sample keys: {sample_keys}")
        try:
            present_1000 = "1000" in produtos_cache
        except Exception:
            present_1000 = False
        print(f"🔔 Código '1000' presente no cache? {present_1000}")
        return True
    except Exception as e:
        print(f" ERRO CRÍTICO ao carregar produtos: {e}")
        import traceback

        traceback.print_exc()
        return False
