"""Gerador de BR Code (PIX) baseado no padrão EMV/BRCode.

Esta implementação usa `crcmod` para calcular o CRC16 e `qrcode` para gerar
o PNG em base64 pronto para uso em Flet (`Image.src_base64`).

Exemplo de uso:
    from payments.pix_generator import PixGenerator
    g = PixGenerator('suachave@email.com', 'Mercadinho Ponto Certo', 'Recife')
    b64 = g.gerar_qr_base64(45.90)
    image.src_base64 = b64
"""

import base64
import io
import unicodedata

try:
    from crcmod.predefined import mkPredefinedCrcFun
except Exception:
    mkPredefinedCrcFun = None

try:
    import qrcode
except Exception:
    qrcode = None


class PixGenerator:
    """Gera Payloads PIX no padrão BR Code (EMV) aceitos por todos os bancos."""

    def __init__(self, chave_pix: str, nome_recebedor: str, cidade_recebedor: str):
        self.chave = chave_pix
        self.nome = self.limpar_texto(nome_recebedor).upper()
        self.cidade = self.limpar_texto(cidade_recebedor).upper()

    def limpar_texto(self, texto: str) -> str:
        """Remove acentos para evitar erros em leitores de bancos antigos."""
        return "".join(
            c
            for c in unicodedata.normalize("NFD", str(texto))
            if unicodedata.category(c) != "Mn"
        )

    def _format(self, id: str, valor: str) -> str:
        """Formata o campo no padrão ID + Tamanho (2 dígitos) + Valor."""
        return f"{id}{len(str(valor)):02}{valor}"

    def calcular_crc16(self, payload: str) -> str:
        """Calcula o Checksum CRC16 (CCITT-FALSE) usando crcmod quando disponível."""
        if mkPredefinedCrcFun is None:
            # Fallback: implementar CRC manual simples compatível
            crc = 0xFFFF
            for byte in payload.encode("utf-8"):
                crc ^= byte << 8
                for _ in range(8):
                    if crc & 0x8000:
                        crc = (crc << 1) ^ 0x1021
                    else:
                        crc <<= 1
                    crc &= 0xFFFF
            return f"{crc:04X}"
        # Tentar nomes conhecidos do crcmod; alguns ambientes registram nomes diferentes
        tried = []
        for name in (
            "crc-16-ccitt-false",
            "crc-ccitt-false",
            "crc-16",
            "crc-ccitt",
            "crc-16-ccitt",
        ):
            try:
                crc16_func = mkPredefinedCrcFun(name)
                payload_bin = payload.encode("utf-8")
                crc_val = crc16_func(payload_bin)
                crc_hex = hex(crc_val).upper().replace("0X", "")
                return crc_hex.zfill(4)
            except Exception:
                tried.append(name)

        # Se falhar, cair para implementação manual
        crc = 0xFFFF
        for byte in payload.encode("utf-8"):
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        return f"{crc:04X}"

    def gerar_payload(self, valor: float) -> str:
        """Monta a string final do PIX Copia e Cola (BR Code)."""
        info_conta = self._format("00", "br.gov.bcb.pix") + self._format(
            "01", self.chave
        )
        # garantir formato consistente do valor (ponto decimal) e calcular tamanho corretamente
        try:
            amount_str = f"{float(valor):.2f}"
        except Exception:
            amount_str = "0.00"

        payload = [
            self._format("00", "01"),
            self._format("26", info_conta),
            self._format("52", "0000"),
            self._format("53", "986"),
            self._format("54", amount_str),
            self._format("58", "BR"),
            self._format("59", self.nome[:25]),
            self._format("60", self.cidade[:15]),
            self._format("62", self._format("05", "***")),
            "6304",
        ]

        resultado_parcial = "".join(payload)
        return resultado_parcial + self.calcular_crc16(resultado_parcial)

    def gerar_qr_base64(self, valor: float) -> str:
        """Gera a imagem do QR (PNG) em base64 pronta para ser exibida no Flet."""
        payload = self.gerar_payload(valor)

        if qrcode is None:
            raise RuntimeError(
                "Biblioteca 'qrcode' não encontrada. Instale via pip install qrcode[pil]"
            )

        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("ascii")


if __name__ == "__main__":
    # Pequeno teste manual
    g = PixGenerator("test@example.com", "Mercadinho Ponto Certo", "Recife")
    b64 = g.gerar_qr_base64(12.5)
    print(b64[:200])
