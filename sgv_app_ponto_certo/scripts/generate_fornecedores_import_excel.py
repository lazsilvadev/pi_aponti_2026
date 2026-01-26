import os
from pathlib import Path

try:
    import pandas as pd  # type: ignore
except Exception as ex:  # pragma: no cover
    raise SystemExit(
        "Pandas não está instalado. Instale com: pip install pandas openpyxl"
    ) from ex


def main() -> str:
    # Cabeçalhos compatíveis com o importador da tela de Fornecedores
    # Reconhecidos: Nome/Razão Social, CNPJ/CPF, Telefone, Email, Condição Pagamento,
    # Prazo Entrega, Categoria, Status
    rows = [
        {
            "Nome / Razão Social": "Fornecedor Exemplo LTDA",
            "CNPJ/CPF": "12.345.678/0001-99",
            "Telefone": "(11) 99999-0000",
            "Email": "contato@exemplo.com",
            "Condição Pagamento": "Débito, Dinheiro, Pix",
            "Prazo Entrega": "7 dias úteis",
            "Categoria": "Alimentos",
            "Status": "Ativo",
        },
        {
            "Nome / Razão Social": "Distribuidora Bebidas ME",
            "CNPJ/CPF": "11.222.333/0001-44",
            "Telefone": "(21) 98888-7777",
            "Email": "vendas@bebidas.com",
            "Condição Pagamento": "Crédito, Pix",
            "Prazo Entrega": "3 dias úteis",
            "Categoria": "Bebidas",
            "Status": "Ativo",
        },
    ]

    df = pd.DataFrame(rows)

    root = Path(__file__).resolve().parent.parent
    exports_dir = root / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    out_path = exports_dir / "fornecedores_import_modelo.xlsx"

    # Usa openpyxl para .xlsx
    df.to_excel(out_path, index=False, engine="openpyxl")
    return str(out_path)


if __name__ == "__main__":
    path = main()
    print(path)
