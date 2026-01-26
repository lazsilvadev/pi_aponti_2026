"""Exemplo: gerar QR Code PIX dinamicamente.

Uso:
    python payments/examples/generate_pix_qr.py --merchant "Loja Exemplo" --amount 12.5 \
        --chave "meu@email.com" --cpf 12345678901 --cidade "Recife" --out pix.png

O script imprime o payload (BRCode) e salva `pix.png` (ou imprime base64 se `--stdout`).
"""

import argparse
import base64
import io
import os
from pathlib import Path

from caixa.logic import montar_payload_pix


def generate_qr(
    merchant, amount, chave, cpf, cidade, tipo, out_path=None, stdout=False
):
    payload = montar_payload_pix(merchant, float(amount), chave, cpf, cidade, tipo)

    try:
        import qrcode
    except Exception as e:
        raise RuntimeError(
            "Biblioteca 'qrcode' não encontrada. Instale via pip install qrcode[pil]"
        ) from e

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()

    if out_path:
        out_dir = Path(out_path).parent
        if out_dir and not out_dir.exists():
            out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(data)

    b64 = base64.b64encode(data).decode("ascii")
    return payload, b64


def main():
    parser = argparse.ArgumentParser(description="Gerar QR PIX (BRCode) de exemplo")
    parser.add_argument("--merchant", default="Mercadinho Ponto Certo")
    parser.add_argument("--amount", type=float, required=True)
    parser.add_argument("--chave", default=None)
    parser.add_argument("--cpf", default=None)
    parser.add_argument("--cidade", default="Recife")
    parser.add_argument(
        "--tipo", default="com_valor", choices=["com_valor", "dinamico", "minimo"]
    )
    parser.add_argument("--out", default="pix_qr.png")
    parser.add_argument(
        "--stdout", action="store_true", help="Imprime base64 do PNG no stdout"
    )

    args = parser.parse_args()

    payload, b64 = generate_qr(
        args.merchant,
        args.amount,
        args.chave,
        args.cpf,
        args.cidade,
        args.tipo,
        args.out,
        args.stdout,
    )

    print("Payload PIX (BRCode):")
    print(payload)
    print()
    if args.stdout:
        print(b64)
    else:
        print(f"QR salvo em: {args.out}")


if __name__ == "__main__":
    main()
