import os

import flet as ft

COLORS = {
    "primary": "#0078D4",
    "secondary": "#4CAF50",
    "background": "#F3F6F9",
    "card_bg": "#FFFFFF",
    "danger": "#D60E0E",
    "warning": "#FFA000",
    "orange": "#FF8C00",
    "text_dark": "#333333",
    "text_muted": "#757575",
}

PAYMENT_METHODS = [
    {"name": "Dinheiro", "icon": ft.Icons.MONETIZATION_ON, "key": "F1"},
    {"name": "Pix", "icon": ft.Icons.QR_CODE_2, "key": "F2"},
    {"name": "Débito", "icon": ft.Icons.CREDIT_CARD_OFF, "key": "F3"},
    {"name": "Crédito", "icon": ft.Icons.CREDIT_CARD, "key": "F4"},
    # Observação: pagamentos por cartão sem TEF são feitos via 'Crédito'/'Débito' normais.
]

# Mapear teclas de função para índices (atualizável conforme PAYMENT_METHODS)
FKEY_MAP = {m["key"]: i for i, m in enumerate(PAYMENT_METHODS)}

# Feature flag: permitir TEF apenas se explicitly ativado (ex: ENABLE_TEF=1)
TEF_ENABLED = bool(
    str(os.environ.get("ENABLE_TEF", "0")).lower() in ("1", "true", "yes")
)
