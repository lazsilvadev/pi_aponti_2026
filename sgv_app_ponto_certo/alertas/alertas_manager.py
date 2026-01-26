"""
Gerenciador de Alertas de Estoque Baixo
Monitora produtos com estoque abaixo do mínimo configurado
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Alinha fonte de dados de estoque com a tela de Estoque (JSON)
try:
    from estoque.repository import carregar_produtos as carregar_produtos_estoque
except Exception:
    carregar_produtos_estoque = None


class AlertasManager:
    """Gerencia alertas de estoque baixo"""

    def __init__(self, alertas_dir="alertas"):
        """Inicializa o gerenciador de alertas"""
        self.alertas_dir = Path(alertas_dir)
        self.alertas_dir.mkdir(exist_ok=True)
        self.arquivo_alertas = self.alertas_dir / "alertas_estoque.json"
        self.carregados = self._carregar_alertas()

    def _carregar_alertas(self) -> Dict:
        """Carrega alertas salvos do arquivo"""
        try:
            if self.arquivo_alertas.exists():
                with open(self.arquivo_alertas, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[ALERTAS] [WARN] Erro ao carregar alertas: {e}")
        return {}

    def _salvar_alertas(self):
        """Salva alertas em arquivo JSON"""
        try:
            with open(self.arquivo_alertas, "w", encoding="utf-8") as f:
                json.dump(self.carregados, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ALERTAS] [ERROR] Erro ao salvar alertas: {e}")

    def verificar_estoque_baixo(self, pdv_core) -> List[Dict]:
        """
        Verifica produtos com estoque abaixo do mínimo,
        usando a mesma fonte da tela de Estoque (JSON via estoque.repository).
        Retorna lista de alertas calculados no momento.
        """
        alertas: List[Dict] = []
        try:
            print(
                "\n[ALERTAS-MANAGER] [INFO] Iniciando verificação de estoque baixo (JSON)..."
            )

            if carregar_produtos_estoque is None:
                raise RuntimeError(
                    "estoque.repository indisponível para leitura de produtos"
                )

            produtos_json = carregar_produtos_estoque() or []
            print(
                f"[ALERTAS-MANAGER] [INFO] Total de produtos (JSON): {len(produtos_json)}"
            )

            if not produtos_json:
                print("[ALERTAS-MANAGER] [WARN] Nenhum produto encontrado no JSON!")
                return alertas

            # Mantém o limiar de 'baixo estoque' consistente com a tela (quantidade < 10)
            LIMIAR_MINIMO = 10

            for i, p in enumerate(produtos_json):
                estoque_atual = int(p.get("quantidade") or 0)
                estoque_minimo = LIMIAR_MINIMO

                is_zerado = estoque_atual <= 0
                is_baixo = estoque_atual < estoque_minimo
                comparacao = (
                    "OK"
                    if (not is_zerado and not is_baixo)
                    else ("ZERADO" if is_zerado else "BAIXO")
                )

                print(
                    f"[ALERTAS-MANAGER] #{i + 1} {p.get('nome')}: atual={estoque_atual}, minimo={estoque_minimo} -> {comparacao}"
                )

                if is_zerado or is_baixo:
                    alerta_id = f"produto_{p.get('id')}"
                    alerta = {
                        "id": p.get("id"),
                        "alerta_id": alerta_id,
                        "codigo": p.get("codigo_barras") or "",
                        "nome": p.get("nome"),
                        "estoque_atual": estoque_atual,
                        "estoque_minimo": estoque_minimo,
                        "falta": estoque_minimo - estoque_atual,
                        "data_deteccao": datetime.now().isoformat(),
                        "status": "ativo",
                    }
                    alertas.append(alerta)
                    print(
                        f"[ALERTAS-MANAGER] [ALERT] ALERTA DETECTADO: {p.get('nome')}"
                    )

            print(
                f"[ALERTAS-MANAGER] [OK] Verificação concluída: {len(alertas)} alerta(s)"
            )
            return alertas

        except Exception as e:
            print(f"[ALERTAS] [ERROR] Erro ao verificar estoque: {e}")
            return []

    def obter_alertas_ativos(self) -> List[Dict]:
        """Retorna todos os alertas ainda ativos"""
        alertas_ativos = [
            alerta
            for alerta in self.carregados.values()
            if alerta.get("status") == "ativo"
        ]
        return sorted(alertas_ativos, key=lambda x: x["falta"], reverse=True)

    def marcar_como_resolvido(self, alerta_id: str) -> bool:
        """Marca um alerta como resolvido"""
        try:
            if alerta_id in self.carregados:
                self.carregados[alerta_id]["status"] = "resolvido"
                self.carregados[alerta_id][
                    "data_resolucao"
                ] = datetime.now().isoformat()
                self._salvar_alertas()
                print(f"[ALERTAS] [OK] Alerta {alerta_id} marcado como resolvido")
                return True
        except Exception as e:
            print(f"[ALERTAS] [ERROR] Erro ao resolver alerta: {e}")
        return False

    def marcar_como_nao_aplicavel(self, alerta_id: str) -> bool:
        """Marca um alerta como não aplicável (produto descontinuado, etc)"""
        try:
            if alerta_id in self.carregados:
                self.carregados[alerta_id]["status"] = "nao_aplicavel"
                self.carregados[alerta_id]["data_na"] = datetime.now().isoformat()
                self._salvar_alertas()
                print(f"[ALERTAS] [INFO] Alerta {alerta_id} marcado como não aplicável")
                return True
        except Exception as e:
            print(f"[ALERTAS] [ERROR] Erro ao marcar N/A: {e}")
        return False

    def obter_resumo_alertas(self, pdv_core) -> Dict:
        """Retorna resumo de TODOS os alertas: estoque + contas a pagar - SEM usar cache"""
        print("\n[ALERTAS-MANAGER] [INFO] obter_resumo_alertas: INICIO")
        # ========== Alertas de Estoque - Sempre calcular do zero ==========
        print("[ALERTAS-MANAGER] [INFO] Verificando estoque...")
        alertas_estoque = self.verificar_estoque_baixo(pdv_core)
        print(
            f"[ALERTAS-MANAGER] [INFO] Alertas de estoque encontrados: {len(alertas_estoque)}"
        )
        # Estoque zerado deve ser considerado crítico mesmo se mínimo for 0
        critico_estoque = [
            a
            for a in alertas_estoque
            if a["estoque_atual"] == 0 or a["falta"] >= a["estoque_minimo"] * 0.5
        ]
        moderado_estoque = [a for a in alertas_estoque if a not in critico_estoque]
        print(
            f"[ALERTAS-MANAGER] [INFO] Estoque - Críticos: {len(critico_estoque)}, Moderados: {len(moderado_estoque)}"
        )

        # ========== Alertas de Contas a Pagar - Sempre calcular do zero ==========
        print("[ALERTAS-MANAGER] [INFO] Verificando contas a pagar...")
        contas_info = self.verificar_contas_pagar(pdv_core)
        contas_vencidas = contas_info.get("vencidas", [])
        contas_proximas = contas_info.get("proximas", [])
        print(
            f"[ALERTAS-MANAGER] [INFO] Contas - Vencidas: {len(contas_vencidas)}, Próximas: {len(contas_proximas)}"
        )

        # ========== Total Combinado ==========
        total_alertas = (
            len(alertas_estoque) + len(contas_vencidas) + len(contas_proximas)
        )
        total_critico = len(critico_estoque) + len(
            contas_vencidas
        )  # Contas vencidas = críticas

        resultado = {
            "total": total_alertas,
            "critico": total_critico,
            "moderado": len(moderado_estoque) + len(contas_proximas),
            # Estoque
            "estoque_critico": len(critico_estoque),
            "estoque_moderado": len(moderado_estoque),
            "produtos_criticos": critico_estoque,
            "produtos_moderados": moderado_estoque,
            # Contas a Pagar
            "contas_vencidas": len(contas_vencidas),
            "contas_proximas": len(contas_proximas),
            "detalhes_vencidas": contas_vencidas,
            "detalhes_proximas": contas_proximas,
        }
        print(
            f"[ALERTAS-MANAGER] [INFO] Resultado final: total={total_alertas}, critico={total_critico}"
        )
        print(f"[ALERTAS-MANAGER] [INFO] Chaves do resultado: {list(resultado.keys())}")
        print("[ALERTAS-MANAGER] [INFO] obter_resumo_alertas: FIM\n")
        return resultado

    def limpar_alertas_resolvidos(self, dias_retencao=30):
        """Remove alertas resolvidos com mais de X dias"""
        try:
            agora = datetime.now()
            limite = agora - timedelta(days=dias_retencao)

            removidos = 0
            para_remover = []

            for alerta_id, alerta in self.carregados.items():
                if alerta.get("status") in ["resolvido", "nao_aplicavel"]:
                    data_resolucao = alerta.get("data_resolucao") or alerta.get(
                        "data_na"
                    )
                    if data_resolucao:
                        data = datetime.fromisoformat(data_resolucao)
                        if data < limite:
                            para_remover.append(alerta_id)
                            removidos += 1

            for alerta_id in para_remover:
                del self.carregados[alerta_id]

            if removidos > 0:
                self._salvar_alertas()
                print(f"[ALERTAS] [INFO] {removidos} alerta(s) antigo(s) removido(s)")

            return removidos

        except Exception as e:
            print(f"[ALERTAS] [ERROR] Erro ao limpar alertas: {e}")
            return 0

    def obter_historico_alerta(self, alerta_id: str) -> Optional[Dict]:
        """Retorna o histórico completo de um alerta"""
        return self.carregados.get(alerta_id)

    def exportar_alertas_csv(self, pdv_core, caminho_export="alertas_estoque.csv"):
        """Exporta alertas atuais em formato CSV"""
        try:
            alertas_ativos = self.verificar_estoque_baixo(pdv_core)

            if not alertas_ativos:
                print("[ALERTAS] [INFO] Nenhum alerta ativo para exportar")
                return False

            with open(caminho_export, "w", encoding="utf-8") as f:
                f.write("Código;Produto;Estoque Atual;Estoque Mínimo;Falta;Data\n")

                for alerta in alertas_ativos:
                    data = alerta["data_deteccao"].split("T")[0]
                    f.write(
                        f"{alerta['codigo']};{alerta['nome']};{alerta['estoque_atual']};{alerta['estoque_minimo']};{alerta['falta']};{data}\n"
                    )

            print(f"[ALERTAS] [OK] Alertas exportados para: {caminho_export}")
            return True

        except Exception as e:
            print(f"[ALERTAS] [ERROR] Erro ao exportar: {e}")
            return False

    # ========== ALERTAS DE CONTAS A PAGAR ==========

    def verificar_contas_pagar(self, pdv_core) -> Dict:
        """
        Verifica contas a pagar e retorna resumo de alertas
        - Contas vencidas (vencimento ANTES de hoje - atrasadas)
        - Contas próximas ao vencimento (hoje até próximos 3 dias)
        """
        resultado = {
            "vencidas": [],
            "proximas": [],
            "total_vencido": 0,
            "total_proximo_vencimento": 0,
        }

        try:
            # Usar get_pending_expenses para contas a pagar
            if hasattr(pdv_core, "get_pending_expenses"):
                contas = pdv_core.get_pending_expenses()
            else:
                print(
                    "[ALERTAS-CONTAS] [WARN] PDVCore não possui método get_pending_expenses"
                )
                return resultado

            agora = datetime.now().date()
            print(f"\n[ALERTAS-CONTAS] [INFO] Data de hoje: {agora}")
            print(
                f"[ALERTAS-CONTAS] [INFO] Total de contas a pagar: {len(contas) if contas else 0}"
            )

            for i, conta in enumerate(contas):
                try:
                    # Obtém a data de vencimento - pode ser 'vencimento' ou 'due_date'
                    data_vencimento = getattr(conta, "vencimento", None) or getattr(
                        conta, "due_date", None
                    )
                    if not data_vencimento:
                        print(
                            f"[ALERTAS-CONTAS] [WARN] Conta #{i + 1} SEM data de vencimento"
                        )
                        continue

                    # DEBUG: Mostrar tipo e valor original
                    print(
                        f"[ALERTAS-CONTAS] #{i + 1} Vencimento bruto: {data_vencimento} (tipo: {type(data_vencimento).__name__})"
                    )

                    if isinstance(data_vencimento, str):
                        # Se for string em formato "DD/MM/YYYY", converter
                        try:
                            data_vencimento = datetime.strptime(
                                data_vencimento, "%d/%m/%Y"
                            ).date()
                            print(
                                f"[ALERTAS-CONTAS]    -> Convertido de DD/MM/YYYY: {data_vencimento}"
                            )
                        except Exception as e:
                            print(
                                f"[ALERTAS-CONTAS]    [WARN] Falhou DD/MM/YYYY, tentando ISO: {e}"
                            )
                            data_vencimento = datetime.fromisoformat(
                                data_vencimento
                            ).date()
                            print(
                                f"[ALERTAS-CONTAS]    -> Convertido de ISO: {data_vencimento}"
                            )

                    valor = float(conta.valor or getattr(conta, "value", 0))
                    descricao = conta.descricao or getattr(
                        conta, "description", "Sem descrição"
                    )

                    print(f"[ALERTAS-CONTAS]    Descricao: {descricao}, Valor: {valor}")
                    print(
                        f"[ALERTAS-CONTAS]    Comparacao: {data_vencimento} < {agora}? {data_vencimento < agora}"
                    )

                    # CONTAS VENCIDAS (atrasadas - vencimento ANTES de hoje)
                    if data_vencimento < agora:
                        dias_atraso = (agora - data_vencimento).days
                        print(
                            f"[ALERTAS-CONTAS]    [CRITICO] VENCIDA! Atraso: {dias_atraso} dia(s)"
                        )
                        resultado["vencidas"].append(
                            {
                                "id": conta.id,
                                "descricao": descricao,
                                "valor": valor,
                                "vencimento": str(data_vencimento),
                                "dias_atraso": dias_atraso,
                                "categoria": getattr(
                                    conta,
                                    "categoria",
                                    getattr(conta, "category", "Geral"),
                                ),
                            }
                        )
                        resultado["total_vencido"] += valor

                    # CONTAS PRÓXIMAS AO VENCIMENTO (hoje ou próximos 3 dias)
                    elif data_vencimento <= agora + timedelta(days=3):
                        dias_para_vencer = (data_vencimento - agora).days
                        print(
                            f"[ALERTAS-CONTAS]    [WARN] PROXIMA! Dias: {dias_para_vencer}"
                        )
                        resultado["proximas"].append(
                            {
                                "id": conta.id,
                                "descricao": descricao,
                                "valor": valor,
                                "vencimento": str(data_vencimento),
                                "dias_para_vencer": dias_para_vencer,
                                "categoria": getattr(
                                    conta,
                                    "categoria",
                                    getattr(conta, "category", "Geral"),
                                ),
                            }
                        )
                        resultado["total_proximo_vencimento"] += valor
                    else:
                        dias_futuro = (data_vencimento - agora).days
                        print(
                            f"[ALERTAS-CONTAS]    [INFO] OK (vence em {dias_futuro} dias)"
                        )

                except Exception as e:
                    print(
                        f"[ALERTAS-CONTAS] [WARN] Erro ao processar conta #{i + 1}: {e}"
                    )
                    import traceback

                    traceback.print_exc()

            # Log de resumo
            print(
                f"[ALERTAS-CONTAS] [INFO] RESUMO FINAL: {len(resultado['vencidas'])} vencida(s), {len(resultado['proximas'])} proxima(s)\n"
            )

            return resultado

        except Exception as e:
            print(f"[ALERTAS-CONTAS] [ERROR] Erro ao verificar contas a pagar: {e}")
            import traceback

            traceback.print_exc()
            return resultado

    def obter_resumo_contas(self, pdv_core) -> Dict:
        """Retorna resumo de alertas de contas a pagar"""
        contas_info = self.verificar_contas_pagar(pdv_core)

        return {
            "contas_vencidas": len(contas_info["vencidas"]),
            "contas_proximas_vencimento": len(contas_info["proximas"]),
            "total_vencido": contas_info["total_vencido"],
            "total_proximo_vencimento": contas_info["total_proximo_vencimento"],
            "detalhes_vencidas": contas_info["vencidas"],
            "detalhes_proximas": contas_info["proximas"],
        }
