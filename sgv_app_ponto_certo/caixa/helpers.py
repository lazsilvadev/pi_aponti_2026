import os
from typing import Any

import flet as ft


def show_snackbar(page: ft.Page, message: str, color: Any) -> None:
    page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=color, duration=2000)
    page.snack_bar.open = True
    page.update()


def log_overlay_event(action: str, overlay: Any) -> None:
    import time
    import traceback

    try:
        stack = traceback.extract_stack()[:-1]
        short = " -> ".join(
            f"{os.path.basename(f.filename)}:{f.lineno}" for f in stack[-6:]
        )
    except Exception:
        short = "stack-unavailable"
    try:
        bgcolor = getattr(overlay, "bgcolor", None)
    except Exception:
        bgcolor = None
    try:
        expand = getattr(overlay, "expand", None)
    except Exception:
        expand = None
    try:
        visible = getattr(overlay, "visible", None)
    except Exception:
        visible = None

    ts = time.time()
    print(
        f"[OVERLAY-TRACE] {action} overlay={type(overlay).__name__} bgcolor={bgcolor} expand={expand} visible={visible} t={ts} caller={short}"
    )


def make_monitor_dark_masks(page: ft.Page, view: ft.View):
    """Retorna um monitor que loga overlays/máscaras escuras e mudanças na árvore de controles."""

    def scan_controls(ctrl, path="root"):
        results = []
        try:
            bgcolor = getattr(ctrl, "bgcolor", None)
            exp = getattr(ctrl, "expand", None)
            vis = getattr(ctrl, "visible", None)
            t = type(ctrl).__name__
            if isinstance(bgcolor, str):
                bgs = bgcolor.strip().lower()
                if ("rgba(0, 0, 0" in bgs) or ("#000" in bgs) or ("black" in bgs):
                    results.append((path, t, bgcolor, exp, vis, repr(ctrl)))
        except Exception:
            pass

        try:
            children = getattr(ctrl, "controls", None) or getattr(ctrl, "content", None)
            if isinstance(children, (list, tuple)):
                for i, c in enumerate(children):
                    results += scan_controls(c, f"{path}.{type(ctrl).__name__}[{i}]")
            else:
                if children is not None:
                    results += scan_controls(
                        children, f"{path}.{type(ctrl).__name__}.content"
                    )
        except Exception:
            pass
        return results

    def monitor_dark_masks():
        import time

        last_report = set()
        try:
            while getattr(page, "route", None) == "/caixa":
                try:
                    new_report = set()
                    ov = list(getattr(page, "overlay", []))
                    for i, o in enumerate(ov):
                        try:
                            bg = getattr(o, "bgcolor", None)
                            exp = getattr(o, "expand", None)
                            vis = getattr(o, "visible", None)
                            key = (
                                "overlay",
                                i,
                                type(o).__name__,
                                str(bg),
                                str(exp),
                                str(vis),
                            )
                            if (
                                bg
                                and isinstance(bg, str)
                                and (
                                    "rgba(0, 0, 0" in bg
                                    or "#000" in bg
                                    or "black" in bg
                                )
                            ):
                                new_report.add(key)
                            new_report.add(key)
                        except Exception:
                            new_report.add(("overlay", i, repr(o)[:100]))

                    for i, c in enumerate(getattr(view, "controls", []) or []):
                        findings = scan_controls(c, f"view.controls[{i}]")
                        for f in findings:
                            key = (f[0], f[1], str(f[2]), str(f[3]), str(f[4]))
                            new_report.add(key)

                    added = new_report - last_report
                    removed = last_report - new_report
                    for a in added:
                        try:
                            print(f"[MONITOR] NEW: {a}")
                        except Exception:
                            print(f"[MONITOR] NEW (repr): {a}")
                    for r in removed:
                        try:
                            print(f"[MONITOR] GONE: {r}")
                        except Exception:
                            print(f"[MONITOR] GONE (repr): {r}")

                    last_report = new_report
                except Exception as ex:
                    print(f"[MONITOR] erro interno: {ex}")
                try:
                    page.sleep(250)
                except Exception:
                    time.sleep(0.25)
        except Exception:
            pass

    return monitor_dark_masks


def run_clock_task(page: ft.Page, datetime_text: ft.Text) -> None:
    """Inicia tarefa de atualização do relógio no texto fornecido."""
    from datetime import datetime

    def update_clock():
        while True:
            try:
                now = datetime.now()
                new_time = now.strftime("%d/%m/%Y %H:%M")
                if datetime_text.value != new_time:
                    datetime_text.value = new_time
                    page.update()
                page.sleep(1000)
            except Exception as ex:
                print(f"Erro no relógio: {ex}")
                break

    page.run_task(update_clock)
