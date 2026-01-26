#!/usr/bin/env python3
"""Gera documentação técnica do aplicativo como PDF.

Cria um PDF com seções: visão geral, estrutura de pastas, ponto de entrada,
principais módulos, instruções de build/execução, alterações recentes.
"""
from pathlib import Path
import os
import sys
from datetime import datetime

# garantir que o diretório do projeto esteja no path para importar `utils`
sys.path.insert(0, str(Path.cwd()))
from utils.export_utils import generate_pdf_file


def read_readme():
    try:
        p = Path("README.md")
        if p.exists():
            return p.read_text(encoding="utf-8").strip().splitlines()[:40]
    except Exception:
        pass
    return ["README não encontrado ou não legível."]


def list_top_level():
    root = Path.cwd()
    items = []
    try:
        for p in sorted(root.iterdir()):
            if p.name.startswith("."):
                continue
            if p.is_dir():
                items.append(f"DIR: {p.name}")
            else:
                items.append(f"FILE: {p.name}")
    except Exception:
        items = ["Erro ao listar estrutura de pastas."]
    return items


def parse_models():
    """Extrai classes e colunas de `models/db_models.py` de forma heurística."""
    p = Path("models/db_models.py")
    if not p.exists():
        return ["models/db_models.py não encontrado."]

    lines = p.read_text(encoding="utf-8").splitlines()
    results = []
    current_class = None
    for ln in lines:
        # detectar definição de classe
        if ln.strip().startswith("class ") and "Base" in ln:
            # exemplo: class Produto(Base):
            name = ln.strip().split()[1].split("(")[0].strip()
            current_class = {"name": name, "fields": []}
            results.append(current_class)
            continue
        if current_class is not None:
            # heurística: linhas com ' = Column(' ou 'Column(' definem colunas
            if "Column(" in ln or "Column (" in ln:
                # pegar o identificador à esquerda quando possível
                try:
                    left = ln.split("=")[0].strip()
                    field_name = left
                except Exception:
                    field_name = ln.strip()
                current_class["fields"].append(field_name)
            # terminar classe ao encontrar linha em branco dupla ou 'def '
            if ln.strip().startswith("def "):
                current_class = None
    out = []
    for cls in results:
        out.append(f"{cls['name']}: {', '.join(cls['fields'])}")
    return out or ["Nenhuma classe detectada em models/db_models.py"]


def summarize_file(path: Path, max_lines=40):
    """Retorna as primeiras linhas relevantes (docstring/comentários) do arquivo."""
    if not path.exists():
        return f"{path} não encontrado."
    try:
        txt = path.read_text(encoding="utf-8")
        # tentar pegar docstring
        stripped = txt.lstrip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            delim = stripped[0:3]
            end = stripped.find(delim, 3)
            if end != -1:
                doc = stripped[3:end].strip()
                return '\\n'.join(doc.splitlines()[:max_lines])
        # fallback: pegar primeiros comentários e linhas
        hs = []
        for i, l in enumerate(txt.splitlines()[: max_lines * 3]):
            if l.strip().startswith('#'):
                hs.append(l.strip().lstrip('#').strip())
            else:
                hs.append(l.rstrip())
            if len(hs) >= max_lines:
                break
        return '\\n'.join(hs[:max_lines])
    except Exception as ex:
        return f"Erro lendo {path}: {ex}"


def find_in_readme(keyword: str):
    try:
        p = Path("README.md")
        if p.exists():
            txt = p.read_text(encoding="utf-8")
            for line in txt.splitlines():
                if keyword.lower() in line.lower():
                    return line.strip()
    except Exception:
        pass
    return None


def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = "Documentação Técnica - Mercadinho Ponto Certo"

    readme_lines = read_readme()

    # Montar seções conforme solicitado
    sections = []

    # 1) Introdução
    intro = "\n".join(readme_lines[:8]) if readme_lines else ""
    sections.append(("Introdução", intro or "Visão geral do sistema."))

    # 2) Objetivo do sistema
    objetivo = find_in_readme("objetivo") or find_in_readme("objetivos")
    if not objetivo:
        objetivo = (
            "Aplicativo PDV para mercearias/mini-mercados que gerencia vendas, estoque, "
            "fornecedores, financeiro e integrações de pagamento (PIX/TEF)."
        )
    sections.append(("Objetivo do sistema", objetivo))

    # 3) Escopo
    top = list_top_level()
    features = [p for p in top if p.startswith("DIR:")]
    escopo = (
        "O escopo inclui as seguintes áreas/funções:\n"
        + "\n".join([f"- {f.replace('DIR: ', '')}" for f in features[:12]])
    )
    sections.append(("Escopo", escopo))

    # 4) Tecnologias utilizadas
    try:
        req_text = Path("requirements.txt").read_text(encoding="utf-8")
        techs = "\n".join(req_text.splitlines()[:30])
    except Exception:
        techs = "Ver requirements.txt"
    sections.append(("Tecnologias utilizadas", techs))

    # 5) Arquitetura / Diagrama
    er = parse_models()
    arch = (
        "Componentes:\n- UI: Flet (desktop)\n- Aplicação: módulos Python (caixa, vendas, estoque, financeiro)\n"
        "- Persistência: SQLite/SQLAlchemy\n- Integrações: TEF adapter, Pix generator\n\n"
        "Resumo do modelo (entidades):\n" + "\n".join(er[:40])
    )
    sections.append(("Arquitetura / Diagrama", arch))

    # 6) Funcionalidades
    funcionalidades = (
        "Principais funcionalidades:\n"
        "- Registrar vendas e pagamentos (Dinheiro, Débito, Crédito, Pix)\n"
        "- Impressão/geração de cupom (PDF/RAW)\n"
        "- Controle de estoque e alertas\n"
        "- Gestão de fornecedores e importação de XML\n"
        "- Financeiro: movimentos, contas a pagar/receber\n"
        "- Relatórios e exportação CSV/PDF\n"
    )
    sections.append(("Funcionalidades", funcionalidades))

    # 7) Regras de negócio
    regras = []
    regras.append("Regras principais detectadas:")
    regras.append("- Repassar taxa de transação ao cliente (crédito/débito) quando habilitado.")
    regras.append("- Cálculo de parcelamento: base + por_parcela por parcela adicional.")
    regras.append("- Validação de estoque antes de concluir venda; persistência em produtos.json quando necessário.")
    regras.append("- Armazenamento de transações com transaction_id e payment_status para integração TEF.")
    regras.append("- Usuários padrão criados automaticamente se banco vazio (admin, user_caixa, estoque1).")
    sections.append(("Regras de negócio", "\n".join(regras)))

    # 8) Requisitos
    import sys as _sys

    requisitos = []
    requisitos.append(f"Python: {_sys.version.splitlines()[0]}")
    requisitos.append("Sistema operacional: Windows recomendado (suporte a pywin32, win32print)")
    try:
        req_excerpt = Path("requirements.txt").read_text(encoding="utf-8").splitlines()[:40]
        requisitos.append("Dependências (excerpt):\n" + "\n".join(req_excerpt))
    except Exception:
        requisitos.append("Ver requirements.txt")
    sections.append(("Requisitos", "\n".join(requisitos)))

    # 9) Conclusão
    concl = (
        "Aplicação PDV completa para micro/pequenos comércios; modular, com exportações, "
        "integrações de pagamento e personalização de taxas. Recomenda-se testes de integração "
        "(impressão, TEF, leitura de XML) no ambiente alvo antes de produção."
    )
    sections.append(("Conclusão", concl))

    # convert sections -> rows
    rows = [[s[0], s[1]] for s in sections]

    # sanitização: fpdf usa latin-1; remover caracteres não-encodáveis
    def sanitize(s: str) -> str:
        try:
            return str(s).encode("latin-1", errors="ignore").decode("latin-1")
        except Exception:
            return str(s)

    rows = [[sanitize(r[0]), sanitize(r[1])] for r in rows]

    # Gerar PDF
    headers = ["Seção", "Conteúdo"]
    caminho = generate_pdf_file(headers, rows, nome_base="documentacao_tecnica", title=title)
    print(f"PDF gerado: {caminho}")


if __name__ == "__main__":
    main()
