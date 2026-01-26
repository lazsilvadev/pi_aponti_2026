"""Camada de compatibilidade para diferenças da API do Flet entre versões.
Garante aliases em minúsculas como `ft.colors` quando apenas `ft.Colors` estiver disponível.
Importe este módulo cedo (por exemplo, em `app.py`) para garantir compatibilidade.
"""

import flet as ft

try:
    if not hasattr(ft, "colors") and hasattr(ft, "Colors"):
        ft.colors = ft.Colors
    if not hasattr(ft, "icons") and hasattr(ft, "Icons"):
        ft.icons = ft.Icons
except Exception:
    pass
