"""
Integração de Alertas de Estoque com a Aplicação
Inicializa o gerenciador e fornece funções de callback
"""

from alertas.alertas_manager import AlertasManager


def inicializar_alertas(page, pdv_core):
    """Inicializa o sistema de alertas ao abrir a aplicação"""
    try:
        alertas_manager = AlertasManager()

        # Fazer verificação inicial de estoque
        resumo = alertas_manager.obter_resumo_alertas(pdv_core)

        if resumo["total"] > 0:
            print("\n[ALERTAS-INIT] [ALERT] ESTOQUE BAIXO DETECTADO!")
            print(
                f"[ALERTAS-INIT] [WARN] Total: {resumo['total']} | Crítico: {resumo['critico']} | Moderado: {resumo['moderado']}"
            )

            # Listar produtos críticos
            if resumo["produtos_criticos"]:
                print("[ALERTAS-INIT] [CRITICO] (>50% de falta):")
                for prod in resumo["produtos_criticos"]:
                    print(
                        f"  -> {prod['nome']}: {prod['estoque_atual']}/{prod['estoque_minimo']} (falta {prod['falta']})"
                    )

            # Listar produtos moderados
            if resumo["produtos_moderados"]:
                print("[ALERTAS-INIT] [MODERADO]:")
                for prod in resumo["produtos_moderados"]:
                    print(
                        f"  -> {prod['nome']}: {prod['estoque_atual']}/{prod['estoque_minimo']} (falta {prod['falta']})"
                    )
        else:
            print("[ALERTAS-INIT] [OK] Estoque OK - Nenhum alerta ativo")

        # Verificar contas a pagar
        contas_info = alertas_manager.obter_resumo_contas(pdv_core)

        if contas_info["contas_vencidas"] > 0:
            print(
                f"\n[ALERTAS-INIT] [CRITICO] CONTAS VENCIDAS: {contas_info['contas_vencidas']} | Total: R$ {contas_info['total_vencido']:.2f}"
            )
            for conta in contas_info["detalhes_vencidas"]:
                print(
                    f"  -> {conta['descricao']}: R$ {conta['valor']:.2f} (vencida ha {conta['dias_atraso']} dias)"
                )

        if contas_info["contas_proximas_vencimento"] > 0:
            print(
                f"\n[ALERTAS-INIT] [MODERADO] CONTAS PROXIMAS AO VENCIMENTO: {contas_info['contas_proximas_vencimento']} | Total: R$ {contas_info['total_proximo_vencimento']:.2f}"
            )
            for conta in contas_info["detalhes_proximas"]:
                print(
                    f"  -> {conta['descricao']}: R$ {conta['valor']:.2f} (vence em {conta['dias_para_vencer']} dias)"
                )

        # Limpar alertas antigos
        alertas_manager.limpar_alertas_resolvidos(dias_retencao=30)

        # Armazenar no app_data
        page.app_data["alertas_manager"] = alertas_manager

        print("[ALERTAS-INIT] [OK] Sistema de alertas inicializado\n")
        return alertas_manager

    except Exception as e:
        print(f"[ALERTAS-INIT] [ERROR] Erro ao inicializar alertas: {e}")
        return None


def verificar_estoque_ao_atualizar(page, pdv_core):
    """Verifica estoque quando há atualizações (para chamar após venda, etc)"""
    try:
        alertas_manager = page.app_data.get("alertas_manager")
        if alertas_manager:
            alertas = alertas_manager.verificar_estoque_baixo(pdv_core)
            return alertas
    except Exception as e:
        print(f"[ALERTAS] [ERROR] Erro na verificação: {e}")
    return []


def obter_resumo_para_dashboard(page, pdv_core) -> dict:
    """Retorna resumo de alertas para exibir no dashboard"""
    try:
        alertas_manager = page.app_data.get("alertas_manager")
        if alertas_manager:
            return alertas_manager.obter_resumo_alertas(pdv_core)
    except Exception as e:
        print(f"[ALERTAS] [ERROR] Erro ao obter resumo: {e}")

    return {
        "total": 0,
        "critico": 0,
        "moderado": 0,
        "produtos_criticos": [],
        "produtos_moderados": [],
    }


def atualizar_badge_alertas_no_gerente(page, pdv_core):
    """Atualiza o badge do sino no painel do gerente.

    - Usa resumo único do AlertasManager (estoque + contas)
    - Considera alertas "lidos" ao comparar com `alerts_last_seen_total`
      armazenado em `page.app_data` quando o popup é aberto.
    - Se não houver novos alertas desde a última visualização, oculta o badge.
    """
    try:
        print("\n[ALERTAS-BADGE] [INFO] Iniciando atualização do badge...")
        alertas_manager = page.app_data.get("alertas_manager")
        if not alertas_manager:
            print("[ALERTAS-BADGE] [ERROR] Alertas manager não encontrado")
            return

        # Resumo único (estoque + contas)
        resumo = alertas_manager.obter_resumo_alertas(pdv_core)
        total_alertas = int(resumo.get("total", 0) or 0)
        total_critico = int(resumo.get("critico", 0) or 0)

        # Calcular não lidos: diferença entre total atual e último visto
        last_seen = int(page.app_data.get("alerts_last_seen_total", 0) or 0)
        nao_lidos = max(0, total_alertas - last_seen)

        # Atualizar o badge na view gerencial (se ela estiver aberta)
        try:
            alerta_numero_ref = page.app_data.get("alerta_numero_ref")
            alerta_container_ref = page.app_data.get("alerta_container_ref")

            print("[ALERTAS-BADGE] [INFO] Verificando referências do badge...")
            print(f"  - alerta_numero_ref: {alerta_numero_ref}")
            print(f"  - alerta_container_ref: {alerta_container_ref}")

            if (
                alerta_numero_ref
                and alerta_container_ref
                and alerta_numero_ref.current
                and alerta_container_ref.current
            ):
                print("[ALERTAS-BADGE] [OK] Referências encontradas!")
                print(
                    f"[ALERTAS-BADGE] [INFO] TOTAL: {total_alertas} | CRITICO: {total_critico} | NAO_LIDOS: {nao_lidos}"
                )

                if nao_lidos > 0:
                    alerta_numero_ref.current.value = str(nao_lidos)
                    alerta_numero_ref.current.color = "#FFFFFF"
                    alerta_container_ref.current.bgcolor = (
                        "#DC3545" if total_critico > 0 else "#FF9800"
                    )
                    alerta_container_ref.current.visible = True
                else:
                    # Não mostrar '0' — ocultar o badge quando não há novos alertas
                    alerta_numero_ref.current.value = ""
                    alerta_numero_ref.current.color = "#FFFFFF"
                    alerta_container_ref.current.visible = False
                try:
                    alerta_numero_ref.current.update()
                    alerta_container_ref.current.update()
                except Exception:
                    pass
                page.update()
        except Exception as e:
            print(
                f"[ALERTAS-BADGE] [WARN] Badge nao pode ser atualizado neste momento: {e}"
            )
    except Exception as e:
        print(f"[ALERTAS-BADGE] [ERROR] Erro ao atualizar badge: {e}")
