import time


def error_beep():
    """Toca dois bips graves curtos em sequência (fallbacks protegidos).

    Frequências escolhidas na faixa 300-400 Hz, duração ~100 ms cada,
    com intervalo curto entre eles.
    """
    try:
        import winsound

        try:
            winsound.Beep(320, 100)
        except Exception:
            try:
                winsound.Beep(300, 90)
            except Exception:
                pass
        try:
            time.sleep(0.08)
        except Exception:
            pass
        try:
            winsound.Beep(400, 100)
        except Exception:
            try:
                winsound.Beep(380, 90)
            except Exception:
                pass
        return
    except Exception:
        # fallback: emitir campainha do terminal duas vezes
        try:
            print("\a", end="")
            time.sleep(0.08)
            print("\a", end="")
        except Exception:
            pass
        return
