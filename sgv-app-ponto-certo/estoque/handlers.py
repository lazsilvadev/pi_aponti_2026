"""Handlers reutilizáveis para a view de Estoque.

Atualmente contém fábrica para o handler de teclado da view `/estoque`.
Ele é simples, sem dependências em controles UI internos — recebe `page`
e um `original` opcional para encadear comportamento existente.
"""

from typing import Callable, Optional

import flet as ft


def create_estoque_key_handler(page: ft.Page, original: Optional[Callable] = None):
    """Retorna um handler de teclado para uso em `view.on_keyboard_event`.

    - `page`: objeto Flet Page (usado para navegação e sessão).
    - `original`: função opcional a ser chamada antes do tratamento local.
    """

    def _handler(e: ft.KeyboardEvent):
        # Chama handler original, se houver
        try:
            if callable(original):
                original(e)
        except Exception:
            pass

        # Se o evento já foi consumido por um handler anterior (p.ex. fechar modal),
        # não executar a navegação/logout padrão.
        try:
            if getattr(e, "handled", False):
                return
        except Exception:
            pass

        # Tratamento local: ESC -> voltar para gerente ou efetuar logout
        try:
            key = (str(e.key) or "").upper()
            if key == "ESCAPE" or e.key == "Escape":
                role = page.session.get("role")
                if role == "gerente":
                    page.go("/gerente")
                else:
                    # marca logout e limpa sessão
                    page.session.set("_logout_flag", "true")
                    page.session.clear()
                    page.session.set("_logout_flag", "true")
                    page.update()
                    page.go("/login")
        except Exception:
            pass

    return _handler
