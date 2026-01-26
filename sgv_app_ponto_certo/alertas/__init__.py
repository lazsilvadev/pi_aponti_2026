"""
Módulo de Alertas de Estoque
Gerencia alertas de produtos com estoque baixo
"""

from .alertas_init import (
    inicializar_alertas,
    obter_resumo_para_dashboard,
    verificar_estoque_ao_atualizar,
)
from .alertas_manager import AlertasManager

__all__ = [
    "AlertasManager",
    "inicializar_alertas",
    "verificar_estoque_ao_atualizar",
    "obter_resumo_para_dashboard",
]
