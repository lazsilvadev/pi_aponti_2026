"""Adaptador TEF simulável.

Fornece uma implementação simples para permitir testes locais sem hardware.
Em produção substitua por um adaptador específico do adquirente.
"""

import logging
import random
import time
from datetime import datetime

logger = logging.getLogger("payments.tef_adapter")


class TefAdapter:
    """Adaptador mínimo para autorizar e estornar transações.

    - `simulate=True` faz autorizações sempre aprovadas por padrão.
    - para forçar um erro de autorização passe `options={'simulate_fail': True}`.
    """

    def __init__(self, simulate: bool = True):
        self.simulate = bool(simulate)

    def authorize(
        self, amount: float, method: str = "Crédito", options: dict | None = None
    ) -> dict:
        """Solicita autorização da transação.

        Retorna dicionário com chaves: `ok` (bool), `transaction_id` (str|None), `message` (str).
        """
        options = options or {}
        logger.info(
            "TEF authorize called: amount=%s method=%s simulate=%s",
            amount,
            method,
            self.simulate,
        )
        if self.simulate:
            # simular tempo de rede/terminal
            time.sleep(0.4)
            if options.get("simulate_fail"):
                logger.warning("TEF simulado: autorização recusada")
                return {
                    "ok": False,
                    "transaction_id": None,
                    "message": "Autorização recusada (simulada)",
                }

            tx_id = f"SIM-{int(time.time()*1000)}-{random.randint(100,999)}"
            logger.info("TEF simulado: autorização aprovada tx=%s", tx_id)
            return {
                "ok": True,
                "transaction_id": tx_id,
                "message": "Autorização aprovada (simulada)",
            }

        # Stub para integração real: retornar negativo para forçar implementação
        logger.error("TEF adapter real não configurado")
        return {"ok": False, "transaction_id": None, "message": "TEF não configurado"}

    def refund(self, transaction_id: str, amount: float | None = None) -> dict:
        """Solicita estorno de transação. Em modo simulado sempre retorna ok."""
        logger.info(
            "TEF refund called: tx=%s amount=%s simulate=%s",
            transaction_id,
            amount,
            self.simulate,
        )
        if self.simulate:
            time.sleep(0.2)
            return {"ok": True, "message": f"Estorno simulado para {transaction_id}"}
        return {"ok": False, "message": "TEF não configurado"}
