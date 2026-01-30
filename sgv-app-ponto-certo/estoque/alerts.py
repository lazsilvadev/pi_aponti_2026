import traceback
from typing import Any


def sincronizar_estoque(page, pdv_core, produtos, Produto):
    """Sincroniza itens de `produtos` com o banco via `pdv_core` e modelo `Produto`.
    Mantém o mesmo comportamento anterior da view.
    """
    try:
        if not pdv_core:
            print("[ESTOQUE] ❌ PDVCore não encontrado")
            return
        print("[ESTOQUE] 🔄 Sincronizando estoque...")
        for produto_json in produtos:
            try:
                codigo_barras = produto_json.get("codigo_barras", "")
                if not codigo_barras:
                    continue
                produto_banco = (
                    pdv_core.session.query(Produto)
                    .filter_by(codigo_barras=codigo_barras)
                    .first()
                )
                quantidade = produto_json.get("quantidade", 0)
                nome = produto_json.get("nome")
                preco_venda = float(
                    produto_json.get("preco_venda", produto_json.get("preco", 0.0))
                    or 0.0
                )
                preco_custo = float(produto_json.get("preco_custo", 0.0) or 0.0)
                validade_dt = produto_json.get("validade")
                validade_str = (
                    validade_dt.strftime("%d/%m/%Y")
                    if hasattr(validade_dt, "strftime")
                    else (validade_dt or "")
                )
                if produto_banco:
                    if produto_banco.estoque_atual != quantidade:
                        print(
                            f"[ESTOQUE] ✅ Atualizando {nome}: {produto_banco.estoque_atual} → {quantidade}"
                        )
                        produto_banco.estoque_atual = quantidade
                    try:
                        if nome and produto_banco.nome != nome:
                            produto_banco.nome = nome
                        if (
                            preco_venda
                            and float(produto_banco.preco_venda or 0.0) != preco_venda
                        ):
                            produto_banco.preco_venda = preco_venda
                        if (
                            preco_custo is not None
                            and float(produto_banco.preco_custo or 0.0) != preco_custo
                        ):
                            produto_banco.preco_custo = preco_custo
                        if (
                            validade_str
                            and (produto_banco.validade or "") != validade_str
                        ):
                            produto_banco.validade = validade_str
                    except Exception:
                        pass
                else:
                    try:
                        novo_prod = Produto(
                            codigo_barras=codigo_barras,
                            nome=nome or "Produto",
                            preco_custo=preco_custo,
                            preco_venda=preco_venda,
                            estoque_atual=quantidade,
                            estoque_minimo=10,
                            validade=validade_str,
                        )
                        pdv_core.session.add(novo_prod)
                        print(
                            f"[ESTOQUE] ➕ Criado no banco: {nome} (qtd={quantidade})"
                        )
                    except Exception as ce:
                        print(f"[ESTOQUE] ⚠️  Falha ao criar produto no banco: {ce}")
            except Exception as e:
                print(f"[ESTOQUE] ⚠️  Erro: {e}")
        pdv_core.session.commit()
        print("[ESTOQUE] ✅ Banco de dados sincronizado")
    except Exception as e:
        print(f"[ESTOQUE] ❌ Erro: {e}")
        traceback.print_exc()


def atualizar_badge_gerente(page, pdv_core: Any):
    try:
        from alertas.alertas_init import atualizar_badge_alertas_no_gerente

        atualizar_badge_alertas_no_gerente(page, pdv_core)
    except Exception as e:
        print(f"[ESTOQUE] ⚠️  Falha ao atualizar badge de alertas (gerente): {e}")


def atualizar_badge_local(page, alerta_numero_ref, alerta_container_ref):
    try:
        from alertas.alertas_manager import AlertasManager

        pdv_core_local = page.app_data.get("pdv_core")
        alertas_manager = page.app_data.get("alertas_manager")
        if not alertas_manager:
            alertas_manager = AlertasManager()
            page.app_data["alertas_manager"] = alertas_manager
        resumo = alertas_manager.obter_resumo_alertas(pdv_core_local)
        total = int(resumo.get("total", 0) or 0)
        critico = int(resumo.get("critico", 0) or 0)
        if alerta_numero_ref.current and alerta_container_ref.current:
            if total > 0:
                alerta_numero_ref.current.value = str(total)
                alerta_numero_ref.current.color = (
                    "#DC3545" if critico > 0 else "#FF9800"
                )
                alerta_container_ref.current.visible = True
            else:
                # Não exibir '0' — ocultar badge quando não há alertas
                alerta_numero_ref.current.value = ""
                alerta_numero_ref.current.color = "#FFFFFF"
                alerta_container_ref.current.visible = False
            page.update()
    except Exception as ex:
        print(f"[ALERTAS-ESTOQUE] ❌ Erro ao atualizar badge local: {ex}")


def atualizar_tudo(
    page, pdv_core, produtos, Produto, alerta_numero_ref, alerta_container_ref
):
    sincronizar_estoque(page, pdv_core, produtos, Produto)
    atualizar_badge_gerente(page, pdv_core)
    try:
        atualizar_badge_local(page, alerta_numero_ref, alerta_container_ref)
    except Exception as ex:
        print(f"[ESTOQUE] ⚠️  Falha ao atualizar badge local: {ex}")
