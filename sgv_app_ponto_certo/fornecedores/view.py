"""View de Fornecedores: listagem, importação, exportação e edição.

Refatorações pequenas aplicadas para melhorar legibilidade e anotações de tipos.
"""

import csv
import logging
import os
import platform
import subprocess
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import flet as ft

from models.db_models import Fornecedor
from utils.export_utils import generate_csv_file, generate_pdf_file

try:
    import pandas as pd  # opcional para .xls/.xlsx
except Exception:
    pd = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


COLORS = {
    "background": "#F0F4F8",
    "primary": "#034986",
    "accent": "#FFB347",
    "green": "#8FC74F",
    "red": "#DC3545",
    "orange": "#FFB347",
    "text": "#2D3748",
    "text_muted": "#757575",
    "card": "#FFFFFF",
}

MEIOS_PAGAMENTO = ["Débito", "Dinheiro", "Crédito", "Pix", "Boleto"]
STATUS_OPCOES = [("ativo", "Ativo"), ("inativo", "Inativo")]
CATEGORIA_OPCOES = [
    ("alimentos", "Alimentos"),
    ("bebidas", "Bebidas"),
    ("higiene", "Higiene e Limpeza"),
    ("limpeza", "Produtos de Limpeza"),
    ("outros", "Outros"),
]


class FornecedorData(TypedDict, total=False):
    nome_razao_social: str
    cnpj_cpf: Optional[str]
    contato: Optional[str]
    condicao_pagamento: Optional[str]
    prazo_entrega_medio: Optional[str]
    categoria: Optional[str]
    status: str


def show_snackbar(page: ft.Page, message: str, color: str) -> None:
    """Mostra um SnackBar na página."""
    page.snack_bar = ft.SnackBar(ft.Text(message), bgcolor=color)
    page.snack_bar.open = True
    page.update()


def validar_cnpj_cpf(value: str) -> tuple[bool, str]:
    if not value:
        return True, ""

    cleaned = "".join(filter(str.isdigit, value))

    if len(cleaned) == 11:
        return True, cleaned
    elif len(cleaned) == 14:
        return True, cleaned

    return False, value


def formatar_cnpj_cpf(value: str) -> str:
    """Formata CNPJ ou CPF retornando string vazia se inválido."""
    if not value:
        return ""

    digits = "".join(filter(str.isdigit, value))

    if len(digits) <= 11:
        # CPF (ou parcial)
        part1 = digits[:3]
        part2 = digits[3:6]
        part3 = digits[6:9]
        rest = digits[9:]
        return f"{part1}.{part2}.{part3}-{rest}" if digits else ""
    else:
        # CNPJ
        return (
            f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
            if len(digits) >= 14
            else digits
        )


def create_fornecedores_view(
    page: ft.Page, pdv_core: Any, handle_back: callable
) -> ft.View:
    assert isinstance(page, ft.Page), "page deve ser instância de ft.Page"

    # Armazenar pdv_core em page.app_data para acessar nas funções internas
    page.app_data["pdv_core"] = pdv_core

    loading_ref = ft.Ref[ft.ProgressRing]()
    fornecedores_dt_ref = ft.Ref[ft.DataTable]()
    fornecedores_list_ref = ft.Ref()
    form_title_ref = ft.Ref[ft.Text]()
    selected_id_ref = ft.Ref[ft.TextField]()
    nome_ref = ft.Ref[ft.TextField]()
    cnpj_cpf_ref = ft.Ref[ft.TextField]()
    contato_ref = ft.Ref[ft.TextField]()
    prazo_entrega_ref = ft.Ref[ft.TextField]()
    categoria_ref = ft.Ref[ft.Dropdown]()
    status_ref = ft.Ref[ft.Dropdown]()
    search_ref = ft.Ref[ft.TextField]()
    # Ref do botão de refresh e do indicador de progresso (animação)
    refresh_btn_ref = ft.Ref[ft.IconButton]()
    refresh_pr_ref = ft.Ref[ft.ProgressRing]()
    detalhes_container_ref = ft.Ref[ft.Container]()
    obs_text_ref = ft.Ref[ft.TextField]()
    highlight_id_ref = ft.Ref()
    bottom_bar_ref = ft.Ref[ft.Container]()
    bottom_bar_text_ref = ft.Ref[ft.Text]()
    bottom_panel_ref = ft.Ref[ft.Container]()
    # Estado persistente para dados do XML
    # Inicializa estado persistente do XML somente se a chave não existir
    try:
        try:
            has_key = "xml_data" in page.session
        except Exception:
            # fallback quando page.session não suporta 'in'
            has_key = page.session.get("xml_data") is not None

        if not has_key:
            page.session.set("xml_data", None)
    except Exception:
        pass
    appbar_ref = ft.Ref[ft.AppBar]()
    appbar_main_title = ft.Text(
        "Fornecedores", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
    )

    checkboxes_ref: Dict[str, ft.Ref[ft.Checkbox]] = {
        meio: ft.Ref[ft.Checkbox]() for meio in MEIOS_PAGAMENTO
    }

    # =============================
    # Importação CSV de Fornecedores
    # =============================
    # Import helpers from module to keep this view focused on UI logic
    from .utils_fornecedores import (
        clean_digits,
        find_fornecedor_by_doc_ou_nome,
        get_any,
        map_categoria,
        map_status,
        parse_meios,
    )

    def show_local_bottom_bar(
        message: str, color=ft.Colors.GREEN_600, duration_ms: int = 3000
    ):
        try:
            if bottom_bar_text_ref.current:
                bottom_bar_text_ref.current.value = message
                bottom_bar_text_ref.current.update()
            if bottom_bar_ref.current:
                bottom_bar_ref.current.bgcolor = color
                bottom_bar_ref.current.visible = True
                bottom_bar_ref.current.update()

            def _hide():
                page.sleep(duration_ms)
                if bottom_bar_ref.current:
                    bottom_bar_ref.current.visible = False
                    bottom_bar_ref.current.update()

            try:
                page.run_task(_hide)
            except Exception:
                try:
                    _hide()
                except Exception:
                    pass
        except Exception as _ex:
            print(f"[FORNECEDORES] Falha ao mostrar barra inferior: {_ex}")

    try:
        page.app_data["fornecedores_show_bottom_bar"] = show_local_bottom_bar
    except Exception:
        pass

    def show_appbar_alert(message: str, duration_ms: int = 3000):
        try:
            if appbar_ref.current is None:
                page.snack_bar = ft.SnackBar(
                    ft.Text(message, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.ORANGE_700,
                )
                page.snack_bar.open = True
                page.update()
                return

            # Update appbar with small message and change bgcolor
            appbar_ref.current.title = ft.Column(
                [appbar_main_title, ft.Text(message, size=12, color=ft.Colors.WHITE)],
                alignment="center",
                horizontal_alignment="center",
            )
            prev_bg = appbar_ref.current.bgcolor
            appbar_ref.current.bgcolor = ft.Colors.ORANGE_700
            appbar_ref.current.update()

            try:
                page.snack_bar = ft.SnackBar(
                    ft.Text(message, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.ORANGE_700,
                )
                page.snack_bar.open = True
                page.update()
            except Exception:
                pass

            import asyncio

            async def _revert():
                try:
                    await asyncio.sleep(duration_ms / 1000.0)
                    if appbar_ref.current is not None:
                        appbar_ref.current.title = appbar_main_title
                        appbar_ref.current.bgcolor = prev_bg
                        appbar_ref.current.update()
                except Exception:
                    pass

            try:
                page.run_task(_revert)
            except Exception:
                try:
                    # fallback sync
                    import time

                    time.sleep(duration_ms / 1000.0)
                    if appbar_ref.current is not None:
                        appbar_ref.current.title = appbar_main_title
                        appbar_ref.current.bgcolor = prev_bg
                        appbar_ref.current.update()
                except Exception:
                    pass
        except Exception:
            pass

    def on_fornecedores_file_selected(e: ft.FilePickerResultEvent):
        if not e.files:
            show_snackbar(page, "Nenhum arquivo selecionado.", COLORS["orange"])
            return

        path = e.files[0].path
        if not path:
            show_snackbar(page, "Caminho inválido.", COLORS["red"])
            return

        # continuar com importação CSV/XLS

        ext = Path(path).suffix.lower()
        criados = 0
        atualizados = 0
        ignorados = 0
        duplicados = 0
        try:
            # Carregar registros de CSV ou Excel
            if ext in (".xls", ".xlsx"):
                if pd is None:
                    show_snackbar(
                        page,
                        "Para importar Excel, instale pandas e openpyxl.",
                        COLORS["orange"],
                    )
                    return
                # Engine openpyxl para .xlsx; .xls pode usar fallback
                kwargs = {"engine": "openpyxl"} if ext == ".xlsx" else {}
                df = pd.read_excel(path, **kwargs)
                records = df.to_dict(orient="records")
            else:
                with open(path, encoding="utf-8-sig", newline="") as f:
                    records = list(csv.DictReader(f))

            for row in records:
                nome = get_any(
                    row,
                    [
                        "nome",
                        "razao social",
                        "razão social",
                        "nome razao social",
                        "nome / razao social",
                        "nome / razão social",
                    ],
                )
                if not (nome and nome.strip()):
                    ignorados += 1
                    continue
                doc = get_any(row, ["cnpj", "cpf", "cnpj cpf", "cnpj/cpf"]) or ""
                doc = clean_digits(doc)
                contato_tel = get_any(row, ["contato", "telefone", "celular"]) or ""
                contato_email = get_any(row, ["email", "e-mail"]) or ""
                contato = (
                    ", ".join([p for p in [contato_tel, contato_email] if p]) or None
                )
                meios = (
                    parse_meios(
                        get_any(
                            row,
                            [
                                "condicao pagamento",
                                "condição pagamento",
                                "meios",
                                "meios aceitos",
                            ],
                        )
                    )
                    or None
                )
                prazo = (
                    get_any(
                        row,
                        [
                            "prazo",
                            "prazo entrega",
                            "prazo medio entrega",
                            "prazo médio entrega",
                        ],
                    )
                    or None
                )
                categoria = map_categoria(get_any(row, ["categoria"]))
                status = map_status(get_any(row, ["status"]))

                dados: FornecedorData = {
                    "nome_razao_social": nome.strip(),
                    "cnpj_cpf": doc or None,
                    "contato": contato,
                    "condicao_pagamento": meios,
                    "prazo_entrega_medio": prazo,
                    "categoria": categoria,
                    "status": status,
                }

                existente = find_fornecedor_by_doc_ou_nome(pdv_core, doc, nome)
                if existente:
                    ok, msg = pdv_core.cadastrar_ou_atualizar_fornecedor(
                        dados, fornecedor_id=getattr(existente, "id", None)
                    )
                    if ok:
                        atualizados += 1
                    else:
                        logger.warning(f"Ignorado (update falhou): {msg}")
                        m = (msg or "").lower()
                        if any(
                            k in m
                            for k in (
                                "cnpj",
                                "cpf",
                                "já está cadastrado",
                                "ja está cadastrado",
                                "já esta cadastrado",
                                "already exists",
                            )
                        ):
                            duplicados += 1
                        else:
                            ignorados += 1
                else:
                    ok, msg = pdv_core.cadastrar_ou_atualizar_fornecedor(dados, None)
                    if ok:
                        criados += 1
                        try:
                            # tentar localizar o registro recém-criado pelo CNPJ ou nome
                            all_now = pdv_core.get_all_fornecedores()
                            found = None
                            for ff in reversed(all_now):
                                if (
                                    getattr(ff, "cnpj_cpf", None)
                                    and getattr(ff, "cnpj_cpf") == (doc or None)
                                ) or (
                                    (
                                        getattr(ff, "nome_razao_social", "")
                                        or getattr(ff, "nome", "")
                                    ).strip()
                                    == nome.strip()
                                ):
                                    found = ff
                                    break
                            if found:
                                logger.info(
                                    f"Fornecedor importado detectado: id={getattr(found,'id', None)} nome={getattr(found,'nome_razao_social', getattr(found,'nome',''))}"
                                )
                            else:
                                logger.warning(
                                    f"Fornecedor '{nome}' aparentemente criado mas NÃO encontrado por get_all_fornecedores()"
                                )
                        except Exception:
                            logger.exception(
                                "Erro ao verificar criação do fornecedor após cadastrar_ou_atualizar_fornecedor"
                            )
                    else:
                        logger.warning(f"Ignorado (create falhou): {msg}")
                        m = (msg or "").lower()
                        if any(
                            k in m
                            for k in (
                                "cnpj",
                                "cpf",
                                "já está cadastrado",
                                "ja está cadastrado",
                                "já esta cadastrado",
                                "already exists",
                            )
                        ):
                            duplicados += 1
                        else:
                            ignorados += 1

            load_fornecedores_table("")
            try:
                # Debug: listar fornecedores atuais após import
                try:
                    allf = pdv_core.get_all_fornecedores()
                    logger.info(
                        f"Após importação, pdv_core.get_all_fornecedores retornou {len(allf)} fornecedores"
                    )
                    # log nomes dos últimos 10
                    nomes = [
                        getattr(x, "nome_razao_social", getattr(x, "nome", ""))
                        for x in allf[-10:]
                    ]
                    logger.info(f"Fornecedores (últimos 10): {nomes}")
                except Exception:
                    logger.exception(
                        "Falha ao obter lista de fornecedores para debug após import"
                    )
                try:
                    if fornecedores_list_ref.current:
                        fornecedores_list_ref.current.update()
                except Exception:
                    pass
                try:
                    page.update()
                except Exception:
                    pass
            except Exception:
                pass
            summary = f"Importação concluída: {criados} criado(s), {atualizados} atualizado(s), {ignorados} ignorado(s)"
            # informar duplicados via barra inferior local para garantir visibilidade
            if duplicados:
                dup_msg = f"{duplicados} fornecedor(es) já existente(s) ignorado(s)."
                # Preferir mostrar no AppBar (top), senão barra inferior local, senão snackbar
                try:
                    try:
                        show_appbar_alert(dup_msg)
                    except Exception:
                        show_local_bottom_bar(dup_msg, color=ft.Colors.ORANGE_700)
                except Exception:
                    show_snackbar(page, dup_msg, ft.Colors.ORANGE_700)

            # mensagem resumida
            show_snackbar(page, summary, COLORS["green"])
        except Exception as err:
            logger.exception("Erro ao importar fornecedores")
            show_snackbar(page, f"Erro ao importar: {err}", COLORS["red"])

    def _build_panel_from_xml(data: dict) -> ft.Container:
        try:
            nro = data.get("nf")
            fornecedor = data.get("fornecedor")
            total = data.get("total")
            itens = data.get("itens") or []

            itens_col = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                f"{i+1}. {it.get('nome')}", weight=ft.FontWeight.W_500
                            ),
                            ft.Text(f"qt={it.get('q')}  v={it.get('v')}", size=12),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    )
                    for i, it in enumerate(itens)
                ],
                spacing=6,
                scroll=ft.ScrollMode.ADAPTIVE,
            )

            content = ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            f"NF-e: {nro or '-'}",
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(
                                            f"Fornecedor: {fornecedor or '-'}", size=12
                                        ),
                                    ],
                                    expand=True,
                                ),
                                ft.Column(
                                    [
                                        ft.Text(
                                            f"Total: R$ {total or '0.00'}",
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(f"Itens: {len(itens)}", size=12),
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(),
                        ft.Container(content=itens_col, expand=True, padding=6),
                    ],
                    spacing=10,
                ),
                padding=12,
                bgcolor="white",
                border_radius=8,
                expand=False,
            )
            return content
        except Exception:
            return ft.Container()
            return
        path = e.files[0].path
        if not path:
            show_snackbar(page, "Caminho inválido.", COLORS["red"])
            return
        ext = Path(path).suffix.lower()
        criados = 0
        atualizados = 0
        ignorados = 0
        duplicados = 0
        try:
            # Carregar registros de CSV ou Excel
            if ext in (".xls", ".xlsx"):
                if pd is None:
                    show_snackbar(
                        page,
                        "Para importar Excel, instale pandas e openpyxl.",
                        COLORS["orange"],
                    )
                    return
                # Engine openpyxl para .xlsx; .xls pode usar fallback
                kwargs = {"engine": "openpyxl"} if ext == ".xlsx" else {}
                df = pd.read_excel(path, **kwargs)
                records = df.to_dict(orient="records")
            else:
                with open(path, encoding="utf-8-sig", newline="") as f:
                    records = list(csv.DictReader(f))

            for row in records:
                nome = get_any(
                    row,
                    [
                        "nome",
                        "razao social",
                        "razão social",
                        "nome razao social",
                        "nome / razao social",
                        "nome / razão social",
                    ],
                )
                if not (nome and nome.strip()):
                    ignorados += 1
                    continue
                doc = get_any(row, ["cnpj", "cpf", "cnpj cpf", "cnpj/cpf"]) or ""
                doc = clean_digits(doc)
                contato_tel = get_any(row, ["contato", "telefone", "celular"]) or ""
                contato_email = get_any(row, ["email", "e-mail"]) or ""
                contato = (
                    ", ".join([p for p in [contato_tel, contato_email] if p]) or None
                )
                meios = (
                    parse_meios(
                        get_any(
                            row,
                            [
                                "condicao pagamento",
                                "condição pagamento",
                                "meios",
                                "meios aceitos",
                            ],
                        )
                    )
                    or None
                )
                prazo = (
                    get_any(
                        row,
                        [
                            "prazo",
                            "prazo entrega",
                            "prazo medio entrega",
                            "prazo médio entrega",
                        ],
                    )
                    or None
                )
                categoria = map_categoria(get_any(row, ["categoria"]))
                status = map_status(get_any(row, ["status"]))

                dados: FornecedorData = {
                    "nome_razao_social": nome.strip(),
                    "cnpj_cpf": doc or None,
                    "contato": contato,
                    "condicao_pagamento": meios,
                    "prazo_entrega_medio": prazo,
                    "categoria": categoria,
                    "status": status,
                }

                existente = find_fornecedor_by_doc_ou_nome(pdv_core, doc, nome)
                if existente:
                    ok, msg = pdv_core.cadastrar_ou_atualizar_fornecedor(
                        dados, fornecedor_id=getattr(existente, "id", None)
                    )
                    if ok:
                        atualizados += 1
                    else:
                        logger.warning(f"Ignorado (update falhou): {msg}")
                        # detectar se é erro por registro duplicado
                        m = (msg or "").lower()
                        if any(
                            k in m
                            for k in (
                                "cnpj",
                                "cpf",
                                "já está cadastrado",
                                "ja está cadastrado",
                                "já esta cadastrado",
                                "already exists",
                            )
                        ):
                            duplicados += 1
                        else:
                            ignorados += 1
                else:
                    ok, msg = pdv_core.cadastrar_ou_atualizar_fornecedor(dados, None)
                    if ok:
                        criados += 1
                    else:
                        # pode falhar por constraint unique
                        logger.warning(f"Ignorado (create falhou): {msg}")
                        m = (msg or "").lower()
                        if any(
                            k in m
                            for k in (
                                "cnpj",
                                "cpf",
                                "já está cadastrado",
                                "ja está cadastrado",
                                "já esta cadastrado",
                                "already exists",
                            )
                        ):
                            duplicados += 1
                        else:
                            ignorados += 1

            load_fornecedores_table("")
            summary = f"Importação concluída: {criados} criado(s), {atualizados} atualizado(s), {ignorados} ignorado(s)"
            # informar duplicados via barra inferior local para garantir visibilidade
            if duplicados:
                dup_msg = f"{duplicados} fornecedor(es) já existente(s) ignorado(s)."
                # Preferir mostrar no AppBar (top), senão barra inferior local, senão snackbar
                try:
                    try:
                        show_appbar_alert(dup_msg)
                    except Exception:
                        show_local_bottom_bar(dup_msg, color=ft.Colors.ORANGE_700)
                except Exception:
                    show_snackbar(page, dup_msg, ft.Colors.ORANGE_700)

            # mensagem resumida
            show_snackbar(page, summary, COLORS["green"])
        except Exception as err:
            logger.exception("Erro ao importar fornecedores")
            show_snackbar(page, f"Erro ao importar: {err}", COLORS["red"])

    fornecedores_file_picker = ft.FilePicker(on_result=on_fornecedores_file_selected)
    if fornecedores_file_picker not in page.overlay:
        page.overlay.append(fornecedores_file_picker)

    # =============================
    # Importação NF-e (XML)
    # =============================
    def on_fornecedores_xml_selected(e: ft.FilePickerResultEvent):
        if not e.files:
            show_snackbar(page, "Nenhum arquivo selecionado.", COLORS["orange"])
            return
        path = e.files[0].path
        if not path:
            show_snackbar(page, "Caminho inválido.", COLORS["red"])
            return

        # Ler o XML internamente e processar — não abrir no navegador
        # (anteriormente o código abria o arquivo externamente e retornava)

        # Parse NF-e XML de forma resiliente (procura por tags pelo localname)
        import xml.etree.ElementTree as ET

        try:
            tree = ET.parse(path)
            root = tree.getroot()

            def find_text(name, ctx=root, default=""):
                for el in ctx.iter():
                    if el.tag.split("}")[-1] == name:
                        return (el.text or "").strip()
                return default

            # Dados básicos
            nro = find_text("nNF")
            chave = find_text("chNFe") or find_text("NFe")
            data_emissao = find_text("dhEmi") or find_text("dEmi")
            fornecedor_nome = find_text("xNome", ctx=root) or find_text(
                "xNome", ctx=root
            )
            fornecedor_doc = find_text("CNPJ") or find_text("CPF")
            total_valor = find_text("vNF") or find_text("vProd")

            # Se a importação foi iniciada a partir do card de um fornecedor,
            # o id alvo é armazenado em page.app_data['fornecedores_xml_target_id']
            target_forn_id = page.app_data.pop("fornecedores_xml_target_id", None)
            target_forn = None
            if target_forn_id:
                try:
                    target_forn = pdv_core.get_fornecedor_by_id(target_forn_id)
                except Exception:
                    target_forn = None
            # Se houver fornecedor alvo, validar CNPJ do XML antes de vincular
            if target_forn is not None and fornecedor_doc:
                from re import sub

                try:
                    xml_doc = "".join(filter(str.isdigit, str(fornecedor_doc)))
                    forn_doc = getattr(target_forn, "cnpj_cpf", None) or getattr(
                        target_forn, "cnpj", ""
                    )
                    forn_doc_digits = "".join(filter(str.isdigit, str(forn_doc or "")))
                    if xml_doc and forn_doc_digits and xml_doc != forn_doc_digits:
                        show_snackbar(
                            page,
                            "Erro: CNPJ do XML não corresponde ao fornecedor selecionado.",
                            COLORS["red"],
                        )
                        return
                    # Se passar, forçar nome do fornecedor conhecido para consistência
                    fornecedor_nome = fornecedor_nome or getattr(
                        target_forn,
                        "nome_razao_social",
                        getattr(target_forn, "nome", ""),
                    )
                except Exception:
                    pass

            # Itens
            itens = []
            for det in root.iter():
                if det.tag.split("}")[-1] == "det":
                    prod = None
                    for c in det.iter():
                        if c.tag.split("}")[-1] == "prod":
                            prod = c
                            break
                    if prod is None:
                        continue
                    nome = find_text("xProd", ctx=prod)
                    qt = find_text("qCom", ctx=prod)
                    vprod = find_text("vProd", ctx=prod)
                    itens.append({"nome": nome, "q": qt, "v": vprod})

            summary = f"NF-e: {nro or '-'} | Fornecedor: {fornecedor_nome or '-'} | Total: R$ {total_valor or '0.00'} | Itens: {len(itens)}"
            logger.info(
                "Import XML parsed: nro=%s fornecedor=%s doc=%s total=%s itens=%d",
                nro,
                fornecedor_nome,
                fornecedor_doc,
                total_valor,
                len(itens),
            )
            try:
                # Não mostrar resumo na barra inferior (appbar) — preferir painel inferior fixo
                try:
                    if bottom_bar_ref.current is not None:
                        bottom_bar_ref.current.visible = False
                        bottom_bar_ref.current.update()
                except Exception:
                    pass
            except Exception:
                pass

            # Construir overlay de pré-visualização e painel inferior
            # Garantir que a lista de meios não contenha duplicatas
            payment_methods = list(dict.fromkeys(MEIOS_PAGAMENTO + ["Boleto"]))
            payment_dropdown = ft.Dropdown(
                label="Forma de Pagamento",
                options=[ft.dropdown.Option(m) for m in payment_methods],
                value=payment_methods[0],
            )

            # vencimento default: hoje +7 dias (string dd/mm/yyyy)
            from datetime import datetime, timedelta

            venc_default = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")
            vencimento_field = ft.TextField(label="Vencimento", value=venc_default)

            # Construir um painel inferior mais estruturado:
            # header (NF-e / fornecedor / total), lista de itens com rolagem, coluna de pagamento e botões
            items_column = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(f"{i+1}. {it['nome']}", weight=ft.FontWeight.W_500),
                            ft.Text(
                                f"qt={it['q']}  v={it['v']}", color="#000000", size=12
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    )
                    for i, it in enumerate(itens)
                ],
                spacing=6,
                scroll=ft.ScrollMode.ADAPTIVE,
            )

            items_container = ft.Container(
                content=items_column,
                height=150 if len(itens) > 0 else 80,
                padding=ft.padding.only(top=6, bottom=6),
            )

            header = ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(f"NF-e: {nro or '-'}", weight=ft.FontWeight.BOLD),
                            ft.Text(
                                f"Fornecedor: {fornecedor_nome or fornecedor_doc or '-'}",
                                size=12,
                                color="#666666",
                            ),
                        ],
                        expand=True,
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                f"Total: R$ {total_valor or '0.00'}",
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(f"Itens: {len(itens)}", size=12, color="#666666"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )

            controls_col = ft.Column(
                [
                    ft.Text("Pagamento", weight=ft.FontWeight.W_500),
                    payment_dropdown,
                    vencimento_field,
                ],
                spacing=8,
                width=300,
            )

            content_row = ft.Row(
                [
                    ft.Container(content=items_container, expand=True, padding=6),
                    ft.Container(width=12),
                    controls_col,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )

            footer = ft.Row(
                [
                    ft.Container(expand=True),
                    ft.ElevatedButton(
                        "Confirmar",
                        on_click=lambda ev: confirmar_import_xml(
                            ev,
                            nro,
                            fornecedor_nome,
                            fornecedor_doc,
                            total_valor,
                            payment_dropdown,
                            vencimento_field,
                            None,
                        ),
                    ),
                    ft.TextButton(
                        "Cancelar", on_click=lambda ev: fechar_xml_overlay(ev, None)
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=8,
            )

            # Painel inferior fixo com controles referenciados
            xml_nf_text = ft.Text("", weight=ft.FontWeight.BOLD)
            xml_fornecedor_text = ft.Text("", size=12, color="#666666")
            xml_total_text = ft.Text("", weight=ft.FontWeight.BOLD)
            xml_itens_text = ft.Text("", size=12, color="#666666")
            xml_itens_column = ft.Column([], spacing=6)
            xml_pagamento_dropdown = ft.Dropdown(
                label="Forma de Pagamento",
                options=[
                    ft.dropdown.Option(m)
                    for m in list(dict.fromkeys(MEIOS_PAGAMENTO + ["Boleto"]))
                ],
                value=MEIOS_PAGAMENTO[0],
            )
            xml_vencimento_field = ft.TextField(label="Vencimento", value="")
            xml_footer_row = ft.Row(
                [
                    ft.Container(expand=True),
                    ft.ElevatedButton(
                        "Confirmar",
                        on_click=lambda ev: confirmar_import_xml(
                            ev,
                            None,
                            None,
                            None,
                            None,
                            xml_pagamento_dropdown,
                            xml_vencimento_field,
                            None,
                        ),
                    ),
                    ft.TextButton(
                        "Cancelar", on_click=lambda ev: fechar_xml_overlay(ev, None)
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=8,
            )

            lower_panel = ft.Container(
                visible=False,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        xml_nf_text,
                                        xml_fornecedor_text,
                                    ],
                                    expand=True,
                                ),
                                ft.Column(
                                    [
                                        xml_total_text,
                                        xml_itens_text,
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(),
                        ft.Row(
                            [
                                ft.Container(
                                    content=ft.Column([xml_itens_column], spacing=6),
                                    expand=True,
                                    padding=6,
                                ),
                                ft.Container(width=12),
                                ft.Column(
                                    [
                                        ft.Text(
                                            "Pagamento", weight=ft.FontWeight.W_500
                                        ),
                                        xml_pagamento_dropdown,
                                        xml_vencimento_field,
                                    ],
                                    spacing=8,
                                    width=300,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Divider(),
                        xml_footer_row,
                    ],
                    spacing=10,
                    scroll=ft.ScrollMode.ADAPTIVE,
                ),
                padding=12,
                bgcolor=COLORS.get("card", "white"),
                border_radius=8,
                expand=False,
            )

            # Sempre criar overlay flutuante para garantir visibilidade
            xml_overlay = ft.Container(
                content=ft.Column(
                    [
                        ft.Container(expand=True),
                        ft.Container(
                            content=ft.Container(
                                content=lower_panel,
                                padding=ft.padding.only(bottom=60),
                                width=900,
                                height=300,
                            ),
                        ),
                    ],
                    expand=True,
                    alignment=ft.alignment.bottom_center,
                ),
                visible=True,
                bgcolor="rgba(0,0,0,0.45)",
                expand=True,
            )

            # Salvar dados do XML em estado persistente (lista em session)
            try:
                xml_record = {
                    "nf": nro,
                    "chave": chave,
                    "data": data_emissao,
                    "fornecedor": fornecedor_nome,
                    "cnpj": fornecedor_doc,
                    "total": total_valor,
                    "itens": itens,
                    "path": path,
                }
                # vincular explicitamente ao fornecedor alvo quando importado a partir do card
                try:
                    if "target_forn_id" in locals() and target_forn_id:
                        xml_record["fornecedor_id"] = target_forn_id
                except Exception:
                    pass

                pdv_core_ref = page.app_data.get("pdv_core")
                saved = False
                try:
                    if pdv_core_ref and hasattr(pdv_core_ref, "save_imported_xml"):
                        try:
                            pdv_core_ref.save_imported_xml(xml_record)
                            saved = True
                        except Exception:
                            saved = False
                except Exception:
                    saved = False

                if not saved:
                    try:
                        existing = page.session.get("xml_data")
                        if not existing:
                            existing = []
                        # garantir que seja lista
                        if not isinstance(existing, list):
                            existing = [existing]
                        existing.append(xml_record)
                        page.session.set("xml_data", existing)
                    except Exception:
                        pass
            except Exception:
                pass
            # Atualizar controles do painel inferior (bindings)
            xml_nf_text.value = f"NF-e: {nro or '-'}"
            xml_fornecedor_text.value = (
                f"Fornecedor: {fornecedor_nome or fornecedor_doc or '-'}"
            )
            xml_total_text.value = f"Total: R$ {total_valor or '0.00'}"
            xml_itens_text.value = f"Itens: {len(itens)}"
            xml_itens_column.controls.clear()
            for i, it in enumerate(itens):
                xml_itens_column.controls.append(
                    ft.Row(
                        [
                            ft.Text(f"{i+1}. {it['nome']}", weight=ft.FontWeight.W_500),
                            ft.Text(
                                f"qt={it['q']}  v={it['v']}", color="#000000", size=12
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    )
                )
            # Vencimento default: hoje +7 dias
            from datetime import datetime, timedelta

            venc_default = (datetime.now() + timedelta(days=7)).strftime("%d/%m/%Y")
            xml_vencimento_field.value = venc_default

            # Tentar anexar o painel construído ao painel inferior fixo.
            try:
                if getattr(bottom_panel_ref, "current", None) is not None:
                    try:
                        # garantir que a barra inferior laranja esteja escondida
                        if getattr(bottom_bar_ref, "current", None) is not None:
                            try:
                                bottom_bar_ref.current.visible = False
                                bottom_bar_ref.current.update()
                            except Exception:
                                pass

                        logger.info(
                            "bottom_panel_ref exists (id=%s). lower_panel id=%s",
                            id(bottom_panel_ref.current),
                            id(lower_panel),
                        )
                        logger.info(
                            "Antes: bottom_panel_ref.current.content=%s",
                            type(bottom_panel_ref.current.content),
                        )

                        # garantir que o painel inferior esteja visível
                        try:
                            lower_panel.visible = True
                        except Exception:
                            pass

                        # anexar painel inferior diretamente (removido debug visual)
                        try:
                            bottom_panel_ref.current.content = lower_panel
                        except Exception:
                            bottom_panel_ref.current.content = ft.Container(
                                content=lower_panel
                            )

                        bottom_panel_ref.current.visible = True

                        try:
                            bottom_panel_ref.current.update()
                        except Exception:
                            logger.exception(
                                "Erro ao chamar bottom_panel_ref.current.update()"
                            )

                        logger.info(
                            "Depois: bottom_panel_ref.current.content=%s",
                            type(bottom_panel_ref.current.content),
                        )
                        logger.info(
                            "Anexado lower_panel ao bottom_panel_ref e marcado visível"
                        )
                        logger.info(
                            "bottom_panel_ref.visible=%s",
                            getattr(bottom_panel_ref.current, "visible", None),
                        )
                    except Exception:
                        logger.exception("Falha ao configurar bottom_panel_ref")
                else:
                    # fallback simples: mostrar overlay flutuante com o painel interno
                    if xml_overlay not in page.overlay:
                        page.overlay.append(xml_overlay)
                page.update()
            except Exception:
                logger.exception("Falha ao anexar painel inferior; exibindo overlay")
                try:
                    if xml_overlay not in page.overlay:
                        page.overlay.append(xml_overlay)
                    page.update()
                except Exception:
                    pass
        except Exception as ex:
            logger.exception("Erro ao ler XML: %s", ex)
            show_snackbar(page, f"Erro ao ler XML: {ex}", COLORS["red"])

    fornecedores_file_picker = ft.FilePicker(on_result=on_fornecedores_file_selected)
    if fornecedores_file_picker not in page.overlay:
        page.overlay.append(fornecedores_file_picker)

    # FilePicker para XML (NF-e)
    fornecedores_xml_picker = ft.FilePicker(on_result=on_fornecedores_xml_selected)
    if fornecedores_xml_picker not in page.overlay:
        page.overlay.append(fornecedores_xml_picker)

    def fechar_xml_overlay(e: ft.ControlEvent, overlay_ref):
        try:
            # se for overlay, removê-lo; senão esconder painel inferior
            if overlay_ref and overlay_ref in page.overlay:
                try:
                    page.overlay.remove(overlay_ref)
                except Exception:
                    pass
            else:
                # tentar remover overlay global armazenado em page.app_data
                try:
                    stored = page.app_data.get("fornecedores_global_xml_repo")
                    if stored and stored in page.overlay:
                        try:
                            page.overlay.remove(stored)
                        except Exception:
                            pass
                        try:
                            page.app_data.pop("fornecedores_global_xml_repo", None)
                        except Exception:
                            pass
                except Exception:
                    pass
                # se não havia overlay global, esconder painel inferior
                try:
                    if bottom_panel_ref.current is not None:
                        bottom_panel_ref.current.visible = False
                        bottom_panel_ref.current.content = None
                        bottom_panel_ref.current.update()
                except Exception:
                    pass
            # remover painel inferior temporário se existir
            try:
                temp_key = "fornecedores_xml_temp_bottom"
                temp = page.app_data.get(temp_key)
                if temp and temp in page.overlay:
                    try:
                        page.overlay.remove(temp)
                    except Exception:
                        pass
                    page.app_data.pop(temp_key, None)
            except Exception:
                pass
            page.update()
        except Exception:
            pass

    def confirmar_import_xml(
        e: ft.ControlEvent,
        nro,
        fornecedor_nome,
        fornecedor_doc,
        total_valor,
        payment_dropdown,
        vencimento_field,
        overlay_ref,
    ):
        try:
            metodo = payment_dropdown.value if payment_dropdown else None
            valor_text = total_valor or "0"
            # normalizar valor (trocar vírgula por ponto)
            try:
                valor = float(str(valor_text).replace(",", "."))
            except Exception:
                # tentar extrair dígitos
                import re

                m = re.search(r"[0-9]+[\.,]?[0-9]*", str(valor_text))
                valor = float((m.group(0) if m else "0").replace(",", "."))

            # Se Boleto, criar despesa em aberto
            if metodo == "Boleto":
                from datetime import datetime as _dt

                venc_raw = vencimento_field.value if vencimento_field else ""
                try:
                    venc_dt = _dt.strptime(venc_raw.strip(), "%d/%m/%Y").date()
                except Exception:
                    venc_dt = _dt.now().date()

                descricao = f"Boleto NF-e {nro or '-'} - {fornecedor_nome or fornecedor_doc or 'Fornecedor'}"
                pdv_core_ref = page.app_data.get("pdv_core")
                if pdv_core_ref:
                    ok, msg = pdv_core_ref.create_expense(
                        descricao, valor, venc_dt, "Fornecedores"
                    )
                    if ok:
                        show_snackbar(
                            page,
                            msg or "✅ Conta a pagar criada (Boleto).",
                            COLORS["green"],
                        )
                        try:
                            show_local_bottom_bar(
                                "Alterações salvas", color=COLORS["green"]
                            )
                        except Exception:
                            pass
                        try:
                            show_appbar_alert("Alterações salvas", duration_ms=2500)
                        except Exception:
                            pass
                    else:
                        show_snackbar(
                            page,
                            msg or "❌ Falha ao criar conta a pagar.",
                            COLORS["red"],
                        )

                    # Atualizar tabelas/cards financeiros caso existam callbacks
                    try:
                        if hasattr(page, "atualizar_finance_tables") and callable(
                            page.atualizar_finance_tables
                        ):
                            page.atualizar_finance_tables(False)
                    except Exception:
                        pass
                    try:
                        if hasattr(page, "atualizar_dashboard_cards") and callable(
                            page.atualizar_dashboard_cards
                        ):
                            page.atualizar_dashboard_cards()
                    except Exception:
                        pass

            else:
                # Tentar criar/atualizar fornecedor a partir dos dados do XML
                try:
                    doc_clean = clean_digits(fornecedor_doc or "")
                    dados_forn: FornecedorData = {
                        "nome_razao_social": (fornecedor_nome or "").strip() or None,
                        "cnpj_cpf": doc_clean or None,
                        "contato": None,
                        "condicao_pagamento": metodo or None,
                        "prazo_entrega_medio": None,
                        "categoria": None,
                        "status": "ativo",
                    }

                    existente = find_fornecedor_by_doc_ou_nome(
                        pdv_core, doc_clean, fornecedor_nome
                    )
                    if existente:
                        ok, msg = pdv_core.cadastrar_ou_atualizar_fornecedor(
                            dados_forn, fornecedor_id=getattr(existente, "id", None)
                        )
                        if ok:
                            show_snackbar(
                                page,
                                "Fornecedor atualizado a partir do XML.",
                                COLORS["green"],
                            )
                            try:
                                show_local_bottom_bar(
                                    "Alterações salvas", color=COLORS["green"]
                                )
                            except Exception:
                                pass
                            try:
                                show_appbar_alert("Alterações salvas", duration_ms=2500)
                            except Exception:
                                pass
                        else:
                            show_snackbar(
                                page,
                                msg or "Falha ao atualizar fornecedor.",
                                COLORS["red"],
                            )
                    else:
                        ok, msg = pdv_core.cadastrar_ou_atualizar_fornecedor(
                            dados_forn, None
                        )
                        if ok:
                            show_snackbar(
                                page,
                                "Fornecedor criado a partir do XML.",
                                COLORS["green"],
                            )
                            try:
                                show_local_bottom_bar(
                                    "Alterações salvas", color=COLORS["green"]
                                )
                            except Exception:
                                pass
                            try:
                                show_appbar_alert("Alterações salvas", duration_ms=2500)
                            except Exception:
                                pass
                        else:
                            show_snackbar(
                                page, msg or "Falha ao criar fornecedor.", COLORS["red"]
                            )

                    try:
                        load_fornecedores_table("")
                        try:
                            import asyncio

                            async def _show_appbar_after_delay():
                                try:
                                    await asyncio.sleep(0.05)
                                    show_appbar_alert(
                                        "Alterações salvas", duration_ms=2000
                                    )
                                except Exception:
                                    pass

                            try:
                                page.run_task(_show_appbar_after_delay)
                            except Exception:
                                try:
                                    import time

                                    time.sleep(0.05)
                                    show_appbar_alert(
                                        "Alterações salvas", duration_ms=2000
                                    )
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        # Se a importação foi iniciada a partir do card, atualizar o painel de detalhes desse fornecedor
                        try:
                            if "target_forn_id" in locals() and target_forn_id:
                                try:
                                    forn_obj = pdv_core.get_fornecedor_by_id(
                                        target_forn_id
                                    )
                                    if forn_obj and detalhes_container_ref.current:
                                        detalhes_container_ref.current.content = (
                                            create_detalhes_fornecedor(forn_obj)
                                        )
                                        detalhes_container_ref.current.update()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    except Exception:
                        pass

                except Exception as _ex:
                    logger.exception(
                        "Erro ao criar/atualizar fornecedor a partir do XML"
                    )
                    show_snackbar(
                        page, f"Fornecedor não importado: {_ex}", COLORS["red"]
                    )

            # Fechar overlay se for um overlay; manter painel inferior fixo com as informações
            try:
                if overlay_ref and overlay_ref in page.overlay:
                    page.overlay.remove(overlay_ref)
                # intencionalmente NÃO removemos o conteúdo do `bottom_panel_ref` aqui
            except Exception:
                pass
            # remover painel inferior temporário se existir
            try:
                temp_key = "fornecedores_xml_temp_bottom"
                temp = page.app_data.get(temp_key)
                if temp and temp in page.overlay:
                    try:
                        page.overlay.remove(temp)
                    except Exception:
                        pass
                    page.app_data.pop(temp_key, None)
            except Exception:
                pass
            page.update()

        except Exception as ex:
            logger.exception("Erro ao confirmar importação NF-e")
            show_snackbar(page, f"Erro: {ex}", COLORS["red"])

    def importar_fornecedores_csv(e: ft.ControlEvent):
        try:
            fornecedores_file_picker.pick_files(
                allow_multiple=False, allowed_extensions=["csv", "xls", "xlsx"]
            )
        except Exception as ex:
            show_snackbar(page, f"Falha ao abrir seletor: {ex}", COLORS["red"])

    def importar_fornecedores_xml(e: ft.ControlEvent):
        try:
            # abrir seletor XML definido logo após o handler de seleção
            fornecedores_xml_picker.pick_files(
                allow_multiple=False, allowed_extensions=["xml"]
            )
        except Exception as ex:
            show_snackbar(page, f"Falha ao abrir seletor: {ex}", COLORS["red"])

    def _load_all_imported_xmls():
        """Retorna lista de registros de XML importados do pdv_core (se disponível) ou do session/file fallback."""
        try:
            pdv_core_ref = page.app_data.get("pdv_core")
            if pdv_core_ref and hasattr(pdv_core_ref, "get_all_imported_xmls"):
                try:
                    return pdv_core_ref.get_all_imported_xmls() or []
                except Exception:
                    pass
        except Exception:
            pass

        # fallback para session/data file
        try:
            xmls = page.session.get("xml_data")
            if not xmls:
                import json

                candidates = []
                try:
                    if getattr(page, "app_dir", None):
                        candidates.append(
                            Path(page.app_dir) / "data" / "imported_xmls.json"
                        )
                except Exception:
                    pass
                try:
                    root_candidate = Path(__file__).resolve().parent.parent
                    candidates.append(root_candidate / "data" / "imported_xmls.json")
                except Exception:
                    pass
                file_data = None
                for data_file in candidates:
                    try:
                        if data_file and data_file.exists():
                            with open(data_file, "r", encoding="utf-8") as fh:
                                file_data = json.load(fh) or []
                            break
                    except Exception:
                        continue
                if file_data is not None:
                    xmls = file_data
            if not xmls:
                return []
            # garantir que seja lista
            if not isinstance(xmls, list):
                return list(xmls)
            return xmls
        except Exception:
            return []

    def abrir_xml_no_navegador(path_or_record):
        """Tenta abrir o XML no navegador. path_or_record pode ser o caminho (str) ou um registro dict com 'path'."""
        try:
            p = None
            if isinstance(path_or_record, str):
                p = path_or_record
            elif isinstance(path_or_record, dict):
                p = path_or_record.get("path")
            if not p:
                show_snackbar(
                    page, "Arquivo XML não disponível para abertura.", COLORS["orange"]
                )
                return
            p = str(p)
            if os.path.exists(p):
                if platform.system() == "Windows":
                    os.startfile(os.path.abspath(p))
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", p])
                else:
                    subprocess.Popen(["xdg-open", p])
            else:
                show_snackbar(
                    page, "Arquivo XML não encontrado no disco: " + p, COLORS["red"]
                )
        except Exception as ex:
            logger.exception("Erro ao abrir XML no navegador: %s", ex)
            show_snackbar(page, f"Erro ao abrir XML: {ex}", COLORS["red"])

    def abrir_repositorio_global_xmls(e: ft.ControlEvent):
        """Exibe um repositório geral com todas as notas (somente VISUALIZAÇÃO)."""
        try:
            xmls = _load_all_imported_xmls()
            if not xmls:
                show_snackbar(
                    page, "Nenhum XML registrado no sistema.", COLORS["orange"]
                )
                return

            rows = []
            for x in xmls:
                try:
                    nf = x.get("nf") or x.get("numero") or "-"
                    dt = x.get("data") or x.get("date") or "-"
                    total = x.get("total") or x.get("valor") or x.get("vNF") or "-"
                    fornecedor_nome = x.get("fornecedor") or x.get("emitente") or ""
                    left = f"{nf} — {fornecedor_nome}" if fornecedor_nome else str(nf)
                    path = x.get("path")
                    row = ft.Row(
                        [
                            ft.Text(str(left), size=12),
                            ft.Container(expand=True),
                            ft.Text(str(dt), size=12, color=ft.Colors.BLACK45),
                            ft.Text(
                                (
                                    f"R$ {float(total):.2f}"
                                    if total and str(total).strip()
                                    else "-"
                                ),
                                size=12,
                            ),
                            ft.Container(width=8),
                            ft.IconButton(
                                icon=ft.Icons.OPEN_IN_NEW,
                                tooltip="Abrir no navegador",
                                on_click=lambda ev, p=path: abrir_xml_no_navegador(p),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    )
                    rows.append(row)
                except Exception:
                    continue

            overlay_key = "fornecedores_global_xml_repo"

            # Criar overlay flutuante para garantir visibilidade (desktop)
            repo_panel = ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Repositório de NF-e (XML)", weight=ft.FontWeight.BOLD),
                        ft.Divider(),
                        ft.Column(rows, spacing=6),
                        ft.Divider(),
                        ft.Row(
                            [
                                ft.ElevatedButton(
                                    "Fechar",
                                    on_click=lambda e, k=overlay_key: fechar_xml_overlay(
                                        e, page.app_data.get(k)
                                    ),
                                )
                            ],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ],
                    spacing=8,
                ),
                padding=12,
                width=900,
                height=400,
                bgcolor=COLORS.get("card", "white"),
                border_radius=8,
            )

            overlay_key = "fornecedores_global_xml_repo"
            # remover overlay antigo se existir
            try:
                existing = page.app_data.get(overlay_key)
                if existing and existing in page.overlay:
                    page.overlay.remove(existing)
            except Exception:
                pass

            page.app_data[overlay_key] = repo_panel
            page.overlay.append(repo_panel)
            page.update()
        except Exception as ex:
            logger.exception("Erro ao abrir repositório global de XMLs: %s", ex)
            show_snackbar(page, f"Erro: {ex}", COLORS["red"])

    def importar_xml_para_fornecedor(e: ft.ControlEvent):
        """Handler para iniciar importação de XML vinculada a um fornecedor específico (clicado no card)."""
        try:
            fornecedor_id = e.control.data if hasattr(e.control, "data") else None
            if not fornecedor_id:
                show_snackbar(page, "ID do fornecedor não encontrado.", COLORS["red"])
                return
            # armazenar alvo temporariamente para quando o FilePicker devolver o arquivo
            page.app_data["fornecedores_xml_target_id"] = fornecedor_id
            # abrir seletor de XML (já adicionado ao overlay)
            fornecedores_xml_picker.pick_files(
                allow_multiple=False, allowed_extensions=["xml"]
            )
        except Exception as ex:
            logger.exception("Erro ao iniciar importação XML para fornecedor: %s", ex)
            show_snackbar(page, f"Falha ao abrir seletor: {ex}", COLORS["red"])

    def get_produtos_fornecedor(fornecedor_id: int) -> List[Any]:
        try:
            pdv_core_local = page.app_data.get("pdv_core")
            if not pdv_core_local:
                logger.warning("pdv_core não disponível em page.app_data")
                return []

            if hasattr(pdv_core_local, "get_produtos_by_fornecedor"):
                produtos = pdv_core_local.get_produtos_by_fornecedor(fornecedor_id)
                logger.info(
                    f"get_produtos_by_fornecedor retornou {len(produtos)} produtos"
                )
                return produtos
            else:
                logger.warning(
                    "Método get_produtos_by_fornecedor não disponível, usando fallback"
                )

                if hasattr(pdv_core_local, "get_all_produtos"):
                    todos_produtos = pdv_core_local.get_all_produtos()
                    produtos = [
                        p
                        for p in todos_produtos
                        if getattr(p, "fornecedor_id", None) == fornecedor_id
                    ]
                    logger.info(f"Fallback retornou {len(produtos)} produtos")
                    return produtos

        except Exception as e:
            logger.error(
                f"Erro ao buscar produtos do fornecedor {fornecedor_id}: {e}",
                exc_info=True,
            )

        return []

    def load_fornecedores_table(search_term: str = ""):
        logger.info(f"Carregando lista de fornecedores (busca: '{search_term}')")

        if not fornecedores_list_ref.current:
            logger.warning("Lista ainda não montada, ignorando recarregamento")
            return

        try:
            loading_ref.current.visible = True
            page.update()

            fornecedores = pdv_core.get_all_fornecedores()
            if search_term:
                fornecedores = [
                    f
                    for f in fornecedores
                    if search_term.lower()
                    in (
                        (getattr(f, "nome_razao_social", "") or "").lower()
                        + (getattr(f, "nome", "") or "").lower()
                    )
                ]

            items: List[ft.Control] = []
            for f in fornecedores:
                produtos_fornecedor = get_produtos_fornecedor(f.id)
                produto_principal = "-"
                if produtos_fornecedor:
                    produto_principal = getattr(produtos_fornecedor[0], "nome", "-")
                    if len(produtos_fornecedor) > 1:
                        produto_principal += f" (+{len(produtos_fornecedor) - 1})"

                nome = getattr(f, "nome_razao_social", getattr(f, "nome", "N/A"))
                contato = getattr(f, "contato", "-")
                status_val = getattr(f, "status", "ativo")
                condicao_pagamento = getattr(f, "condicao_pagamento", "-")
                prazo_entrega = getattr(f, "prazo_entrega_medio", "-")
                cnpj_cpf = getattr(f, "cnpj_cpf", "-")
                categoria = getattr(f, "categoria", "-")

                # Encontrar o label da categoria
                categoria_label = "-"
                for cat_value, cat_label in CATEGORIA_OPCOES:
                    if cat_value == categoria:
                        categoria_label = cat_label
                        break

                # Normalizar para evitar diferenças de capitalização vindas do DB/import
                status_color = (
                    COLORS["green"]
                    if str(status_val).strip().lower() == "ativo"
                    else COLORS["red"]
                )

                actions = ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            tooltip="Editar",
                            data=getattr(f, "id", None),
                            on_click=preencher_formulario_edicao,
                            icon_color=COLORS["primary"],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DESCRIPTION,
                            tooltip="Importar XML (NF-e)",
                            data=getattr(f, "id", None),
                            on_click=lambda e, v=getattr(
                                f, "id", None
                            ): importar_xml_para_fornecedor(e),
                            icon_color=COLORS["primary"],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE,
                            tooltip="Excluir",
                            data=getattr(f, "id", None),
                            on_click=excluir_fornecedor,
                            icon_color=COLORS["red"],
                        ),
                    ],
                    spacing=0,
                )

                card = ft.Card(
                    elevation=1,
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Column(
                                            [
                                                ft.Text(
                                                    nome,
                                                    weight=ft.FontWeight.BOLD,
                                                    size=14,
                                                    color=COLORS["text"],
                                                ),
                                                ft.Text(
                                                    f"CNPJ/CPF: {cnpj_cpf}",
                                                    size=11,
                                                    color=COLORS["text_muted"],
                                                ),
                                                ft.Text(
                                                    f"Contato: {contato}",
                                                    size=14,
                                                    color=COLORS["text_muted"],
                                                ),
                                            ],
                                            expand=True,
                                        ),
                                        ft.Column(
                                            [
                                                ft.Text(
                                                    str(status_val).title(),
                                                    size=11,
                                                    weight="bold",
                                                    color=status_color,
                                                ),
                                            ],
                                            horizontal_alignment=ft.CrossAxisAlignment.END,
                                        ),
                                        actions,
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                                ft.Divider(height=8, thickness=0.5),
                                ft.Row(
                                    [
                                        ft.Column(
                                            [
                                                ft.Text(
                                                    "Pagamento:",
                                                    size=10,
                                                    weight="bold",
                                                    color=COLORS["text_muted"],
                                                ),
                                                ft.Text(
                                                    str(condicao_pagamento),
                                                    size=11,
                                                    color=COLORS["text"],
                                                ),
                                            ],
                                            width=150,
                                        ),
                                        ft.Column(
                                            [
                                                ft.Text(
                                                    "Categoria:",
                                                    size=10,
                                                    weight="bold",
                                                    color=COLORS["text_muted"],
                                                ),
                                                ft.Text(
                                                    str(categoria_label),
                                                    size=11,
                                                    color=COLORS["text"],
                                                ),
                                            ],
                                            width=120,
                                        ),
                                        ft.Column(
                                            [
                                                ft.Text(
                                                    "Prazo Entrega:",
                                                    size=10,
                                                    weight="bold",
                                                    color=COLORS["text_muted"],
                                                ),
                                                ft.Text(
                                                    str(prazo_entrega),
                                                    size=11,
                                                    color=COLORS["text"],
                                                ),
                                            ],
                                            expand=True,
                                        ),
                                    ],
                                    spacing=10,
                                ),
                            ],
                            spacing=5,
                        ),
                        padding=12,
                    ),
                )

                fid = getattr(f, "id", None)

                # cores/estilos para hover/seleção
                HOVER_BG = "#E8F4FF"
                SELECTED_BG = "#D6EBFF"
                LEFT_HIGHLIGHT = ft.border.only(
                    left=ft.BorderSide(4, ft.Colors.BLUE_300)
                )

                # determinar se este item está selecionado atualmente
                sel_id = page.app_data.get("fornecedores_selected_id")
                is_selected = sel_id == fid

                # criar o card interno e envolver em GestureDetector para clique
                def _on_tap_local(e, _fid=fid):
                    try:
                        # marcar seleção visual e mostrar detalhes no painel direito
                        page.app_data["fornecedores_selected_id"] = _fid
                        # atualizar lista para refletir seleção visual
                        load_fornecedores_table("")
                        # carregar objeto fornecedor e exibir detalhes (sem entrar em edição)
                        try:
                            fornecedor_obj = pdv_core.get_fornecedor_by_id(_fid)
                            if fornecedor_obj and detalhes_container_ref.current:
                                detalhes_container_ref.current.content = (
                                    create_detalhes_fornecedor(fornecedor_obj)
                                )
                                detalhes_container_ref.current.update()
                        except Exception:
                            pass
                    except Exception:
                        pass

                inner_gd = ft.GestureDetector(
                    content=card,
                    on_tap=_on_tap_local,
                    mouse_cursor=ft.MouseCursor.CLICK,
                )

                # container que responde ao hover e adiciona transição suave
                wrapper = ft.Container(
                    content=inner_gd,
                    padding=2,
                    bgcolor=SELECTED_BG if is_selected else COLORS.get("card", "white"),
                    border=LEFT_HIGHLIGHT if is_selected else None,
                    animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                )

                # on_hover handler para aplicar efeito visual ao pairar
                def _on_hover(ev, _wrapper=wrapper, _fid=fid):
                    try:
                        is_hover = getattr(ev, "data", False)
                        if is_hover:
                            _wrapper.bgcolor = HOVER_BG
                            _wrapper.border = LEFT_HIGHLIGHT
                        else:
                            if page.app_data.get("fornecedores_selected_id") == _fid:
                                _wrapper.bgcolor = SELECTED_BG
                                _wrapper.border = LEFT_HIGHLIGHT
                            else:
                                _wrapper.bgcolor = COLORS.get("card", "white")
                                _wrapper.border = None
                        _wrapper.update()
                    except Exception:
                        pass

                wrapper.on_hover = _on_hover
                items.append(wrapper)

            fornecedores_list_ref.current.controls = items
            fornecedores_list_ref.current.update()

            if not fornecedores:
                show_snackbar(page, "Nenhum fornecedor cadastrado.", COLORS["orange"])

            logger.info(f"{len(fornecedores)} fornecedores carregados")

        except Exception as e:
            logger.exception("Erro ao carregar fornecedores")
            show_snackbar(page, f"Erro ao carregar fornecedores: {e}", COLORS["red"])
        finally:
            loading_ref.current.visible = False
            page.update()

    def clear_highlight():
        try:
            highlight_id_ref.current = None
            load_fornecedores_table()
        except Exception:
            pass

    def excluir_fornecedor(e: ft.ControlEvent):
        fornecedor_id = e.control.data
        logger.info(f"excluir_fornecedor chamado com data: {fornecedor_id}")

        fornecedor = None
        try:
            fornecedor = pdv_core.get_fornecedor_by_id(fornecedor_id)
        except Exception:
            fornecedor = None

        if not fornecedor:
            show_snackbar(page, "Fornecedor não encontrado.", COLORS["red"])
            return

        produtos = get_produtos_fornecedor(fornecedor.id)
        if produtos:
            show_snackbar(page, "Fornecedor tem produtos vinculados!", COLORS["red"])
            return

        def confirmar_exclusao(e: ft.ControlEvent):
            if e.control.text == "Sim":
                try:
                    sucesso, msg = pdv_core.excluir_fornecedor(fornecedor.id)
                    if sucesso:
                        logger.info(f"Fornecedor {fornecedor.id} excluído com sucesso")
                        show_snackbar(
                            page, "Fornecedor excluído com sucesso!", COLORS["green"]
                        )
                        if delete_overlay in page.overlay:
                            page.overlay.remove(delete_overlay)
                        page.update()
                        load_fornecedores_table()
                    else:
                        if "FOREIGN KEY" in msg or "foreign key" in msg:
                            show_snackbar(
                                page,
                                "Não é possível excluir: fornecedor tem dados vinculados!",
                                COLORS["red"],
                            )
                        else:
                            show_snackbar(page, f"Erro: {msg}", COLORS["red"])
                except Exception as error:
                    logger.error(
                        f"Erro ao excluir fornecedor {fornecedor.id}: {error}",
                        exc_info=True,
                    )
                    show_snackbar(page, "Erro ao excluir fornecedor", COLORS["red"])
            if delete_overlay in page.overlay:
                page.overlay.remove(delete_overlay)
            page.update()

        def cancelar_exclusao(e):
            if delete_overlay in page.overlay:
                page.overlay.remove(delete_overlay)
            page.update()

        nome_fornecedor = getattr(
            fornecedor, "nome_razao_social", getattr(fornecedor, "nome", "")
        )

        # Criar overlay para confirmação de exclusão
        delete_overlay = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(expand=True),
                            ft.Container(
                                content=ft.Column(
                                    [
                                        ft.Row(
                                            [
                                                ft.Text(
                                                    "Confirmar Exclusão",
                                                    size=16,
                                                    weight=ft.FontWeight.BOLD,
                                                )
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER,
                                        ),
                                        ft.Divider(height=10),
                                        ft.Text(
                                            f"Excluir '{nome_fornecedor}'?", size=14
                                        ),
                                        ft.Divider(height=10),
                                        ft.Row(
                                            [
                                                ft.TextButton(
                                                    "Não", on_click=cancelar_exclusao
                                                ),
                                                ft.ElevatedButton(
                                                    "Sim", on_click=confirmar_exclusao
                                                ),
                                            ],
                                            alignment=ft.MainAxisAlignment.END,
                                        ),
                                    ],
                                    spacing=8,
                                ),
                                width=400,
                                bgcolor="white",
                                border_radius=8,
                                padding=20,
                            ),
                            ft.Container(expand=True),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                expand=True,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            visible=True,
            bgcolor="rgba(0, 0, 0, 0.5)",
            expand=True,
        )

        if delete_overlay not in page.overlay:
            page.overlay.append(delete_overlay)
        page.update()

    def preencher_formulario_edicao(e: ft.ControlEvent):
        # Aceitar vários formatos de evento/entrada para compatibilidade com handlers
        fornecedor_id = None
        try:
            if isinstance(e, ft.ControlEvent):
                fornecedor_id = getattr(e.control, "data", None)
            elif isinstance(e, int):
                fornecedor_id = e
            elif hasattr(e, "data"):
                fornecedor_id = getattr(e, "data", None)
            elif hasattr(e, "control") and hasattr(e.control, "data"):
                fornecedor_id = getattr(e.control, "data", None)
        except Exception:
            fornecedor_id = None

        logger.info(f"preencher_formulario_edicao chamado com data: {fornecedor_id}")
        fornecedor = None
        try:
            fornecedor = pdv_core.get_fornecedor_by_id(fornecedor_id)
        except Exception:
            fornecedor = None

        if not fornecedor:
            show_snackbar(page, "Fornecedor não encontrado para edição.", COLORS["red"])
            return

        logger.info(f"Preenchendo formulário para fornecedor ID: {fornecedor.id}")

        meios_aceitos = getattr(fornecedor, "condicao_pagamento", "") or ""
        meios_aceitos = meios_aceitos.split(", ") if meios_aceitos else []

        nome = getattr(fornecedor, "nome_razao_social", getattr(fornecedor, "nome", ""))

        form_title_ref.current.value = f"Editando: {nome}"
        selected_id_ref.current.value = str(fornecedor.id)
        nome_ref.current.value = nome
        cnpj_cpf_ref.current.value = formatar_cnpj_cpf(
            getattr(fornecedor, "cnpj_cpf", "") or ""
        )
        contato_ref.current.value = getattr(fornecedor, "contato", "") or ""

        for key, ref in checkboxes_ref.items():
            if ref.current:
                ref.current.value = key in meios_aceitos

        prazo_entrega_ref.current.value = (
            getattr(fornecedor, "prazo_entrega_medio", "") or ""
        )
        categoria_ref.current.value = getattr(fornecedor, "categoria", "")
        status_ref.current.value = getattr(fornecedor, "status", "ativo")

        detalhes_container_ref.current.content = create_detalhes_fornecedor(fornecedor)
        page.update()

    def limpar_formulario(e: Optional[ft.ControlEvent] = None):
        form_title_ref.current.value = "Cadastrar Novo Fornecedor"
        selected_id_ref.current.value = ""
        nome_ref.current.value = ""
        cnpj_cpf_ref.current.value = ""
        contato_ref.current.value = ""

        for ref in checkboxes_ref.values():
            if ref.current:
                ref.current.value = False

        prazo_entrega_ref.current.value = ""
        categoria_ref.current.value = ""
        status_ref.current.value = "ativo"
        detalhes_container_ref.current.content = create_detalhes_fornecedor(None)
        page.update()

    def salvar_fornecedor(e: ft.ControlEvent):
        if not nome_ref.current.value.strip():
            show_snackbar(page, "Nome/Razão Social é obrigatório!", COLORS["red"])
            nome_ref.current.focus()
            return

        cnpj_cpf_raw = cnpj_cpf_ref.current.value or ""
        is_valid, cleaned_cnpj_cpf = validar_cnpj_cpf(cnpj_cpf_raw)
        if cnpj_cpf_raw and not is_valid:
            show_snackbar(page, "CNPJ/CPF inválido!", COLORS["red"])
            cnpj_cpf_ref.current.focus()
            return

        meios_selecionados = [
            key
            for key, ref in checkboxes_ref.items()
            if ref.current and ref.current.value
        ]

        dados: FornecedorData = {
            "nome_razao_social": nome_ref.current.value.strip(),
            "cnpj_cpf": cleaned_cnpj_cpf or None,
            "contato": contato_ref.current.value.strip() or None,
            "condicao_pagamento": ", ".join(meios_selecionados) or None,
            "prazo_entrega_medio": prazo_entrega_ref.current.value.strip() or None,
            "categoria": categoria_ref.current.value or None,
            "status": status_ref.current.value,
            "observacoes_internas": (
                obs_text_ref.current.value.strip()
                if (
                    obs_text_ref.current
                    and getattr(obs_text_ref.current, "value", None) is not None
                )
                else None
            ),
        }

        fornecedor_id_str = selected_id_ref.current.value
        fornecedor_id = int(fornecedor_id_str) if fornecedor_id_str else None

        try:
            logger.info(f"Salvando fornecedor: {dados}")
            sucesso, msg = pdv_core.cadastrar_ou_atualizar_fornecedor(
                dados, fornecedor_id
            )

            if sucesso:
                logger.info(
                    f"Fornecedor {'atualizado' if fornecedor_id else 'criado'} com sucesso!"
                )
                show_snackbar(
                    page,
                    f"Fornecedor {'atualizado' if fornecedor_id else 'criado'} com sucesso!",
                    COLORS["green"],
                )
                limpar_formulario()
                try:
                    if search_ref.current:
                        search_ref.current.value = ""
                        search_ref.current.update()
                except Exception:
                    pass

                load_fornecedores_table()
                page.update()
                try:
                    fornecedores_all = pdv_core.get_all_fornecedores()
                    candidato = None
                    for fo in sorted(
                        fornecedores_all,
                        key=lambda x: getattr(x, "id", 0),
                        reverse=True,
                    ):
                        if getattr(
                            fo, "nome_razao_social", getattr(fo, "nome", "")
                        ) == dados.get("nome_razao_social"):
                            candidato = fo
                            break
                    if candidato:
                        highlight_id_ref.current = getattr(candidato, "id", None)
                        load_fornecedores_table()
                        page.update()
                        try:

                            async def _clear_highlight_delay():
                                try:
                                    import asyncio

                                    await asyncio.sleep(0.05)
                                except Exception:
                                    pass
                                try:
                                    clear_highlight()
                                except Exception:
                                    pass

                            try:
                                page.run_task(_clear_highlight_delay())
                            except Exception:
                                # fallback síncrono sem bloquear demasiado
                                try:
                                    clear_highlight()
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass
            else:
                logger.error(f"Erro ao salvar fornecedor: {msg}")
                show_snackbar(page, f"Erro: {msg}", COLORS["red"])

        except Exception as error:
            logger.error(f"Exceção ao salvar fornecedor: {error}", exc_info=True)
            show_snackbar(page, f"Erro inesperado: {error}", COLORS["red"])
        page.update()

    def create_detalhes_fornecedor(
        fornecedor: Optional[Fornecedor], obs_editing: bool = False
    ) -> ft.Column:
        try:
            if not fornecedor:
                return ft.Column(
                    [
                        ft.Text(
                            "Selecione um fornecedor para editar",
                            italic=True,
                            color=COLORS["text_muted"],
                            size=16,
                            text_align=ft.TextAlign.CENTER,
                        )
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                )

            # Helpers para obter dados via pdv_core com compatibilidade
            def _try_get_purchases(limit: int = 5):
                try:
                    # tentar nomes comuns de API
                    if hasattr(pdv_core, "get_purchases_for_fornecedor"):
                        return (
                            pdv_core.get_purchases_for_fornecedor(
                                fornecedor.id, limit=limit
                            )
                            or []
                        )
                    if hasattr(pdv_core, "buscar_compras_por_fornecedor"):
                        return (
                            pdv_core.buscar_compras_por_fornecedor(
                                fornecedor.id, limit=limit
                            )
                            or []
                        )
                except Exception:
                    pass
                return []

            def _try_get_xmls(limit: int = 5):
                try:
                    if hasattr(pdv_core, "get_imported_xmls_for_fornecedor"):
                        return (
                            pdv_core.get_imported_xmls_for_fornecedor(
                                fornecedor.id, limit=limit
                            )
                            or []
                        )
                except Exception:
                    pass
                # fallback: checar session xml_data
                try:
                    xmls = page.session.get("xml_data")
                    # fallback to persistent file if session has no xmls
                    if not xmls:
                        try:
                            import json

                            # tentar algumas localizações possíveis do arquivo
                            candidates = []
                            try:
                                if getattr(page, "app_dir", None):
                                    candidates.append(
                                        Path(page.app_dir)
                                        / "data"
                                        / "imported_xmls.json"
                                    )
                            except Exception:
                                pass
                            # relative ao pacote (workspace root)
                            try:
                                root_candidate = Path(__file__).resolve().parent.parent
                                candidates.append(
                                    root_candidate / "data" / "imported_xmls.json"
                                )
                            except Exception:
                                pass

                            file_data = None
                            for data_file in candidates:
                                try:
                                    if data_file and data_file.exists():
                                        with open(
                                            data_file, "r", encoding="utf-8"
                                        ) as fh:
                                            file_data = json.load(fh) or []
                                        break
                                except Exception:
                                    continue

                            if file_data is not None:
                                xmls = file_data
                            else:
                                xmls = None
                        except Exception:
                            xmls = None
                    if not xmls:
                        return []
                    # xmls pode ser lista de dicts com 'fornecedor' ou 'cnpj'
                    out = []
                    for x in reversed(list(xmls)):
                        if len(out) >= limit:
                            break
                        try:
                            f = x.get("fornecedor") or x.get("emitente") or ""
                            cnpj_xml = (
                                x.get("cnpj")
                                or x.get("emitente_cnpj")
                                or x.get("fornecedor_cnpj")
                                or ""
                            )

                            # tentar casar por CNPJ (digitos) primeiro
                            try:
                                fornecedor_doc = (
                                    getattr(fornecedor, "cnpj_cpf", None)
                                    or getattr(fornecedor, "cnpj", None)
                                    or ""
                                )
                                if fornecedor_doc and cnpj_xml:
                                    fd = "".join(
                                        filter(str.isdigit, str(fornecedor_doc))
                                    )
                                    xd = "".join(filter(str.isdigit, str(cnpj_xml)))
                                    if fd and xd and fd == xd:
                                        out.append(x)
                                        continue
                            except Exception:
                                pass

                            # fallback: casar por nome (substring)
                            if not f:
                                continue
                            try:
                                nome_forn = str(
                                    fornecedor.nome_razao_social
                                    or getattr(fornecedor, "nome", "")
                                )
                                if nome_forn and nome_forn.lower() in str(f).lower():
                                    out.append(x)
                            except Exception:
                                continue
                        except Exception:
                            continue
                    return out
                except Exception:
                    return []

            purchases = _try_get_purchases(5)
            xmls = _try_get_xmls(5)

            # calcular prazo médio real e total comprado no mês (simples heurística)
            prazo_real = None
            total_mes = 0.0
            try:
                import datetime as _dt

                now = _dt.datetime.now()
                first_day = _dt.datetime(now.year, now.month, 1)
                # purchases pode ter 'data' ou 'date' e 'total' ou 'valor'
                prazo_vals = []
                for p in purchases:
                    try:
                        dt = p.get("data") or p.get("date") or p.get("created_at")
                        if isinstance(dt, str):
                            try:
                                dt = _dt.datetime.fromisoformat(dt)
                            except Exception:
                                try:
                                    dt = _dt.datetime.strptime(
                                        dt.split(" ")[0], "%Y-%m-%d"
                                    )
                                except Exception:
                                    dt = None
                        total = float(
                            p.get("total") or p.get("valor") or p.get("amount") or 0
                        )
                        if dt and dt >= first_day:
                            total_mes += total
                        # lead time: se p tiver 'pedido_data' e 'recebimento_data'
                        pedido = p.get("pedido_data") or p.get("order_date")
                        recebido = p.get("recebimento_data") or p.get("received_date")
                        if pedido and recebido:
                            try:
                                d1 = (
                                    pedido
                                    if isinstance(pedido, _dt.datetime)
                                    else _dt.datetime.fromisoformat(str(pedido))
                                )
                                d2 = (
                                    recebido
                                    if isinstance(recebido, _dt.datetime)
                                    else _dt.datetime.fromisoformat(str(recebido))
                                )
                                prazo_vals.append((d2 - d1).days)
                            except Exception:
                                pass
                    except Exception:
                        pass
                if prazo_vals:
                    prazo_real = sum(prazo_vals) / len(prazo_vals)
            except Exception:
                prazo_real = None

            # construir UI
            title = ft.Text(
                "📑 Detalhes do Fornecedor Selecionado",
                size=16,
                weight=ft.FontWeight.BOLD,
            )

            compras_controls = []
            if purchases:
                for p in purchases:
                    try:
                        nro = p.get("nf") or p.get("invoice") or "-"
                        data = p.get("data") or p.get("date") or "-"
                        total = p.get("total") or p.get("valor") or p.get("amount") or 0
                        compras_controls.append(
                            ft.Row(
                                [
                                    ft.Text(str(nro), size=12),
                                    ft.Container(expand=True),
                                    ft.Text(
                                        str(data), size=12, color=ft.Colors.BLACK45
                                    ),
                                    ft.Text(
                                        (
                                            f"R$ {float(total):.2f}"
                                            if total
                                            else "R$ 0,00"
                                        ),
                                        size=12,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            )
                        )
                    except Exception:
                        pass
            else:
                # fallback: usar XMLs importados como compras provisórias (não persistem)
                if xmls:
                    for x in xmls[:5]:
                        try:
                            nro = x.get("nf") or x.get("numero") or "-"
                            dt = x.get("data") or x.get("date") or "-"
                            total = (
                                x.get("total") or x.get("valor") or x.get("vNF") or 0
                            )
                            compras_controls.append(
                                ft.Row(
                                    [
                                        ft.Text(str(nro), size=12),
                                        ft.Container(expand=True),
                                        ft.Text(
                                            str(dt), size=12, color=ft.Colors.BLACK45
                                        ),
                                        ft.Text(
                                            (
                                                f"R$ {float(total):.2f}"
                                                if total
                                                else "R$ 0,00"
                                            ),
                                            size=12,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                )
                            )
                        except Exception:
                            pass
                else:
                    compras_controls.append(
                        ft.Text(
                            "(Nenhuma compra recente encontrada)",
                            size=12,
                            color=COLORS["text_muted"],
                        )
                    )

            xml_controls = []
            if xmls:
                for x in xmls:
                    try:
                        nf = x.get("nf") or x.get("numero") or "-"
                        dt = x.get("data") or x.get("date") or "-"
                        f_nome = x.get("fornecedor") or x.get("emitente") or ""
                        left = f"{nf} — {f_nome}" if f_nome else str(nf)
                        xml_controls.append(
                            ft.Row(
                                [
                                    ft.Text(str(left), size=12),
                                    ft.Container(expand=True),
                                    ft.Text(str(dt), size=12),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            )
                        )
                    except Exception:
                        pass
            else:
                xml_controls.append(
                    ft.Text(
                        "(Nenhum XML importado)", size=12, color=COLORS["text_muted"]
                    )
                )

            # --- Cálculo do Risco Operacional (campo derivado, não editável) ---
            # Critérios considerados (expostos ao usuário no tooltip):
            # - Atrasos recorrentes de entrega (prazo médio real)
            # - Frequência de problemas com XMLs (erros/rejeições)
            # - Falta de entregas recentes (compras recentes)
            # - Histórico negativo nas observações internas
            # Se não houver dados suficientes, exibimos: "Não avaliado"

            try:
                # Pontuação simples por critérios (maior = maior risco)
                risk_score = 0
                data_points = 0

                # 1) Atrasos (prazo_real já calculado acima)
                try:
                    if prazo_real is not None:
                        data_points += 1
                        if prazo_real > 14:
                            risk_score += 2
                        elif prazo_real > 7:
                            risk_score += 1
                except Exception:
                    pass

                # 2) Problemas em XMLs importados (contagem de registros com status/erro)
                try:
                    xmls_total = len(xmls) if xmls else 0
                    xml_errors = 0
                    if xmls_total > 0:
                        for xx in xmls:
                            st = str(xx.get("status", "") or "").lower()
                            if any(
                                k in st
                                for k in (
                                    "erro",
                                    "rejei",
                                    "rejeição",
                                    "rejeitado",
                                    "rejected",
                                )
                            ):
                                xml_errors += 1
                            # alguns registros usam chave 'erro' ou 'rejeicao'
                            if xx.get("erro") or xx.get("rejeicao"):
                                xml_errors += 1
                        data_points += 1
                        ratio = xml_errors / float(xmls_total) if xmls_total else 0
                        if ratio > 0.3:
                            risk_score += 2
                        elif ratio > 0:
                            risk_score += 1
                except Exception:
                    pass

                # 3) Falta de entregas recentes (compras nos últimos 90 dias)
                try:
                    import datetime as _dt

                    recent_purchases = 0
                    cutoff = _dt.datetime.now() - _dt.timedelta(days=90)
                    for p in purchases:
                        dt = p.get("data") or p.get("date") or p.get("created_at")
                        if isinstance(dt, str):
                            try:
                                dt = _dt.datetime.fromisoformat(dt)
                            except Exception:
                                try:
                                    dt = _dt.datetime.strptime(
                                        dt.split(" ")[0], "%Y-%m-%d"
                                    )
                                except Exception:
                                    dt = None
                        if isinstance(dt, _dt.datetime) and dt >= cutoff:
                            recent_purchases += 1
                    data_points += 1
                    if recent_purchases == 0:
                        risk_score += 1
                except Exception:
                    pass

                # 4) Histórico negativo nas observações internas (palavras-chave)
                try:
                    if obs_val:
                        data_points += 1
                        txt = str(obs_val).lower()
                        negative_keywords = [
                            "atraso",
                            "reclama",
                            "problema",
                            "inadimpl",
                            "rejei",
                            "erro",
                            "falha",
                        ]
                        neg_count = sum(1 for kw in negative_keywords if kw in txt)
                        if neg_count >= 2:
                            risk_score += 2
                        elif neg_count == 1:
                            risk_score += 1
                except Exception:
                    pass

                if data_points == 0:
                    risco_text = "Não avaliado"
                    risco_color = COLORS["text_muted"]
                    risco_icon = None
                else:
                    if risk_score >= 4:
                        risco_text = "Alto"
                        risco_color = COLORS["red"]
                        risco_icon = ft.icons.WARNING
                    elif risk_score >= 2:
                        risco_text = "Médio"
                        risco_color = COLORS.get("orange", "#FFB300")
                        risco_icon = ft.icons.WARNING
                    else:
                        risco_text = "Baixo"
                        risco_color = COLORS.get("green", "#8FC74F")
                        risco_icon = ft.icons.CHECK_CIRCLE_ROUNDED
            except Exception:
                risco_text = "Não avaliado"
                risco_color = COLORS["text_muted"]
                risco_icon = None

            # Avaliação interna (procura por vários nomes possíveis no objeto)
            avaliacao_attr_names = [
                "avaliacao_interna",
                "avaliacao",
                "rating",
                "score",
            ]
            avaliacao_val = None
            for n in avaliacao_attr_names:
                if hasattr(fornecedor, n):
                    try:
                        avaliacao_val = getattr(fornecedor, n)
                        break
                    except Exception:
                        continue

            # Converter avaliação numérica para int (0-5)
            def _int_from_value(v):
                try:
                    return max(0, min(5, int(round(float(v)))))
                except Exception:
                    return 0

            aval_int = (
                _int_from_value(avaliacao_val) if avaliacao_val is not None else 0
            )

            # Observações internas (procurar por nomes comuns)
            obs_names = [
                "observacoes_internas",
                "observacoes",
                "notas",
                "notas_internas",
                "observacao",
            ]
            obs_val = None
            for n in obs_names:
                if hasattr(fornecedor, n):
                    try:
                        obs_val = getattr(fornecedor, n) or None
                        break
                    except Exception:
                        continue

            obs_display = obs_val if obs_val else "—"

            # Função para salvar avaliação clicada
            def _salvar_avaliacao(n):
                try:
                    dados_upd = {
                        "nome_razao_social": getattr(
                            fornecedor,
                            "nome_razao_social",
                            getattr(fornecedor, "nome", ""),
                        ),
                        "cnpj_cpf": getattr(fornecedor, "cnpj_cpf", None),
                        "contato": getattr(fornecedor, "contato", None),
                        "condicao_pagamento": getattr(
                            fornecedor, "condicao_pagamento", None
                        ),
                        "prazo_entrega_medio": getattr(
                            fornecedor, "prazo_entrega_medio", None
                        ),
                        "categoria": (
                            getattr(fornecedor, "categoria", None)
                            if hasattr(fornecedor, "categoria")
                            else None
                        ),
                        "status": getattr(fornecedor, "status", "ativo"),
                        "avaliacao_interna": int(n),
                        "observacoes_internas": getattr(
                            fornecedor, "observacoes_internas", None
                        ),
                    }
                    ok, msg = pdv_core.cadastrar_ou_atualizar_fornecedor(
                        dados_upd, getattr(fornecedor, "id", None)
                    )
                    if ok:
                        try:
                            # atualizar objeto local e re-renderizar
                            fornecedor.avaliacao_interna = int(n)
                        except Exception:
                            pass
                        try:
                            if detalhes_container_ref.current:
                                detalhes_container_ref.current.content = (
                                    create_detalhes_fornecedor(fornecedor)
                                )
                                detalhes_container_ref.current.update()
                        except Exception:
                            pass
                        show_snackbar(page, "Avaliação salva.", COLORS["green"])
                    else:
                        show_snackbar(page, f"Erro ao salvar: {msg}", COLORS["red"])
                except Exception as e:
                    logger.exception("Erro ao salvar avaliação: %s", e)
                    show_snackbar(page, f"Erro ao salvar avaliação: {e}", COLORS["red"])

            def _on_obs_blur(e: ft.ControlEvent):
                try:
                    new_val = None
                    try:
                        new_val = e.control.value
                    except Exception:
                        try:
                            new_val = (
                                obs_text_ref.current.value
                                if obs_text_ref.current
                                else None
                            )
                        except Exception:
                            new_val = None

                    if new_val is None:
                        return

                    # evitar salvar se não mudou
                    existing = getattr(fornecedor, "observacoes_internas", None) or ""
                    if str(existing) == str(new_val or ""):
                        return

                    dados_upd = {
                        "nome_razao_social": getattr(
                            fornecedor,
                            "nome_razao_social",
                            getattr(fornecedor, "nome", ""),
                        ),
                        "cnpj_cpf": getattr(fornecedor, "cnpj_cpf", None),
                        "contato": getattr(fornecedor, "contato", None),
                        "condicao_pagamento": getattr(
                            fornecedor, "condicao_pagamento", None
                        ),
                        "prazo_entrega_medio": getattr(
                            fornecedor, "prazo_entrega_medio", None
                        ),
                        "categoria": (
                            getattr(fornecedor, "categoria", None)
                            if hasattr(fornecedor, "categoria")
                            else None
                        ),
                        "status": getattr(fornecedor, "status", "ativo"),
                        "observacoes_internas": str(new_val).strip(),
                        "avaliacao_interna": (
                            getattr(fornecedor, "avaliacao_interna", None)
                            if getattr(fornecedor, "avaliacao_interna", None)
                            is not None
                            else None
                        ),
                    }
                    ok, msg = pdv_core.cadastrar_ou_atualizar_fornecedor(
                        dados_upd, getattr(fornecedor, "id", None)
                    )
                    if ok:
                        try:
                            fornecedor.observacoes_internas = str(new_val).strip()
                        except Exception:
                            pass
                        try:
                            if detalhes_container_ref.current:
                                detalhes_container_ref.current.content = (
                                    create_detalhes_fornecedor(fornecedor)
                                )
                                detalhes_container_ref.current.update()
                        except Exception:
                            pass
                        show_snackbar(page, "Observações salvas.", COLORS["green"])
                    else:
                        show_snackbar(
                            page, f"Erro ao salvar observações: {msg}", COLORS["red"]
                        )
                except Exception as ex:
                    logger.exception("Erro ao salvar observações: %s", ex)
                    show_snackbar(
                        page, f"Erro ao salvar observações: {ex}", COLORS["red"]
                    )

            def _enter_obs_edit(e: ft.ControlEvent):
                try:
                    if detalhes_container_ref.current:
                        detalhes_container_ref.current.content = (
                            create_detalhes_fornecedor(fornecedor, obs_editing=True)
                        )
                        detalhes_container_ref.current.update()
                except Exception:
                    pass

            def _save_obs_and_exit(e: ft.ControlEvent):
                try:
                    # Construir evento com valor atual do TextField e delegar ao handler existente
                    class _Evt:
                        pass

                    ev = _Evt()
                    ev.control = type("C", (), {})()
                    try:
                        ev.control.value = (
                            obs_text_ref.current.value if obs_text_ref.current else None
                        )
                    except Exception:
                        ev.control.value = None
                    _on_obs_blur(ev)
                    if detalhes_container_ref.current:
                        detalhes_container_ref.current.content = (
                            create_detalhes_fornecedor(fornecedor, obs_editing=False)
                        )
                        detalhes_container_ref.current.update()
                except Exception:
                    pass

            # Renderiza estrelas clicáveis
            def _render_rating(current: int):
                stars = []
                for i in range(1, 6):
                    filled = i <= current
                    icon_color = ft.Colors.AMBER_700 if filled else ft.Colors.GREY_400
                    stars.append(
                        ft.IconButton(
                            icon=ft.icons.STAR,
                            icon_color=icon_color,
                            tooltip=f"{i} estrela(s)",
                            on_click=(lambda e, v=i: _salvar_avaliacao(v)),
                        )
                    )
                return ft.Row(stars, spacing=0)

            rating_component = _render_rating(aval_int)

            painel = ft.Column(
                [
                    title,
                    ft.Divider(),
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(
                                        "📦 Últimas compras", weight=ft.FontWeight.BOLD
                                    ),
                                    ft.Column(compras_controls, spacing=6),
                                ],
                                expand=True,
                            ),
                            ft.Container(width=18),
                            ft.Column(
                                [
                                    ft.Text(
                                        "📄 Últimos XMLs importados",
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.Column(xml_controls, spacing=6),
                                ],
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Divider(),
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(
                                                "Risco Operacional",
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Container(width=8),
                                            # Ícone de informação com tooltip explicando critérios
                                            ft.IconButton(
                                                icon=ft.Icons.INFO_OUTLINE,
                                                tooltip=(
                                                    "Critérios: atrasos médios de entrega; frequência de problemas em XMLs (erros/rejeições); falta de entregas recentes; histórico negativo em observações internas. "
                                                    "Se não houver dados suficientes, exibimos 'Não avaliado'."
                                                ),
                                                on_click=None,
                                                icon_color=COLORS["primary"],
                                            ),
                                        ],
                                        spacing=4,
                                    ),
                                    ft.Row(
                                        [
                                            (
                                                ft.Icon(risco_icon, color=risco_color)
                                                if risco_icon
                                                else ft.Container()
                                            ),
                                            ft.Container(width=6),
                                            ft.Text(
                                                risco_text, size=12, color=risco_color
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.START,
                                    ),
                                ],
                                expand=True,
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        "Avaliação interna", weight=ft.FontWeight.BOLD
                                    ),
                                    rating_component,
                                ],
                                expand=True,
                            ),
                            ft.Column(
                                [
                                    # Cabeçalho com título e botão de edição/confirmar
                                    ft.Row(
                                        [
                                            ft.Text(
                                                "Observações internas",
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Container(expand=True),
                                            # Ícone muda conforme o modo: lápis para entrar, check para confirmar
                                            (
                                                ft.IconButton(
                                                    icon=ft.icons.CHECK,
                                                    tooltip="Salvar",
                                                    on_click=_save_obs_and_exit,
                                                )
                                                if obs_editing
                                                else ft.IconButton(
                                                    icon=ft.icons.EDIT,
                                                    tooltip="Editar observações",
                                                    on_click=_enter_obs_edit,
                                                )
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.START,
                                    ),
                                    # Corpo: texto em modo visualização, TextField em modo edição
                                    ft.Column(
                                        [
                                            (
                                                ft.Column(
                                                    [
                                                        ft.Text(
                                                            obs_display
                                                            if obs_display
                                                            and obs_display != "—"
                                                            else "Nenhuma observação interna registrada."
                                                        )
                                                    ]
                                                )
                                                if not obs_editing
                                                else ft.TextField(
                                                    ref=obs_text_ref,
                                                    value=obs_val or "",
                                                    hint_text="Digite observações internas sobre este fornecedor...",
                                                    filled=True,
                                                    min_lines=3,
                                                    max_lines=5,
                                                    counter_text="",
                                                    content_padding=8,
                                                    border=ft.InputBorder.NONE,
                                                    prefix_text=None,
                                                    prefix_icon=None,
                                                    suffix_icon=None,
                                                    bgcolor="#F6F6F6",
                                                    expand=True,
                                                    autofocus=True,
                                                    on_blur=_on_obs_blur,
                                                )
                                            )
                                        ],
                                        expand=True,
                                    ),
                                ],
                                expand=True,
                            ),
                        ],
                        spacing=12,
                    ),
                ],
                spacing=10,
                expand=True,
            )

            return ft.Container(
                content=painel, padding=12, bgcolor="white", border_radius=8
            )
        except Exception as ex:
            logger.exception("Erro em create_detalhes_fornecedor: %s", ex)
            return ft.Column(
                [
                    ft.Text(
                        "Selecione um fornecedor para editar",
                        italic=True,
                        color=COLORS["text_muted"],
                        size=16,
                        text_align=ft.TextAlign.CENTER,
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )

    def on_cnpj_change(e: ft.ControlEvent):
        value = e.control.value
        e.control.value = formatar_cnpj_cpf(value)
        page.update()

    def filtrar_fornecedores(e: ft.ControlEvent):
        try:
            termo = search_ref.current.value.lower() if search_ref.current else ""
            logger.info(f"filtrar_fornecedores chamado com termo: '{termo}'")
            load_fornecedores_table(termo)
        except Exception as ex:
            logger.error(f"Erro em filtrar_fornecedores: {ex}", exc_info=True)

    def start_refresh_animation(e: ft.ControlEvent):
        try:
            # Mostrar indicador e desabilitar botão
            if refresh_pr_ref.current:
                refresh_pr_ref.current.visible = True
            if refresh_btn_ref.current:
                refresh_btn_ref.current.disabled = True
            page.update()
        except Exception:
            pass

        try:
            import asyncio

            async def _run():
                try:
                    # Executa o refresh (sincrono) e aguarda um pequeno intervalo
                    handle_refresh(e)
                    await asyncio.sleep(0.15)
                except Exception:
                    pass
                try:
                    if refresh_pr_ref.current:
                        refresh_pr_ref.current.visible = False
                    if refresh_btn_ref.current:
                        refresh_btn_ref.current.disabled = False
                    page.update()
                except Exception:
                    pass

            page.run_task(_run)
        except Exception:
            # Fallback síncrono
            try:
                handle_refresh(e)
                if refresh_pr_ref.current:
                    refresh_pr_ref.current.visible = False
                if refresh_btn_ref.current:
                    refresh_btn_ref.current.disabled = False
                page.update()
            except Exception:
                pass

    def handle_refresh(e: ft.ControlEvent):
        logger.info("Botão de atualização clicado - limpando busca e recarregando")
        if search_ref.current:
            search_ref.current.value = ""
        load_fornecedores_table("")
        show_snackbar(page, "Lista atualizada!", COLORS["green"])

    def export_fornecedores(export_type: str):
        """Exporta fornecedores para CSV ou PDF"""
        try:
            page.app_data["pdv_core"] = pdv_core
            pdv_core_local = page.app_data.get("pdv_core")
            if not pdv_core_local:
                raise RuntimeError("Sistema não iniciado")

            # Buscar fornecedores do banco de dados
            fornecedores = pdv_core_local.session.query(Fornecedor).all()
            if not fornecedores:
                show_snackbar(page, "Nenhum fornecedor para exportar", COLORS["orange"])
                return

            headers = [
                "ID",
                "Razão Social",
                "CNPJ/CPF",
                "Contato",
                "Categoria",
                "Prazo Entrega",
                "Status",
            ]
            data = []

            for f in fornecedores:
                nome = getattr(f, "nome_razao_social", "")
                cnpj_cpf = getattr(f, "cnpj_cpf", "")
                contato = getattr(f, "contato", "")
                categoria = getattr(f, "categoria", "")
                prazo = getattr(f, "prazo_entrega_medio", "")
                status = getattr(f, "status", "")

                data.append(
                    [
                        getattr(f, "id", ""),
                        nome,
                        cnpj_cpf,
                        contato,
                        categoria,
                        prazo,
                        status,
                    ]
                )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            caminho = (
                generate_csv_file(headers, data, f"fornecedores_{timestamp}")
                if export_type == "csv"
                else generate_pdf_file(
                    headers,
                    data,
                    f"fornecedores_{timestamp}",
                    "Relatório de Fornecedores",
                    # Dar mais espaço ao 'Contato' e ajustar demais colunas
                    col_widths=[5, 28, 18, 26, 12, 6, 5],
                )
            )

            print(f"[DEBUG] Arquivo exportado: {caminho}")
            show_snackbar(page, f"✅ Exportado: {Path(caminho).name}", COLORS["green"])

            # Abrir arquivo automaticamente
            try:
                caminho_absoluto = os.path.abspath(caminho)
                print(f"[DEBUG] Abrindo arquivo: {caminho_absoluto}")
                if platform.system() == "Windows":
                    os.startfile(caminho_absoluto)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", caminho_absoluto])
                else:
                    subprocess.Popen(["xdg-open", caminho_absoluto])
            except Exception as open_ex:
                print(f"[DEBUG] Erro ao abrir arquivo: {str(open_ex)}")
                logger.warning(f"Erro ao abrir arquivo: {str(open_ex)}")

        except Exception as ex:
            print(f"[DEBUG] Erro na exportação: {str(ex)}")
            logger.error(f"Erro na exportação: {str(ex)}", exc_info=True)
            show_snackbar(page, f"Erro ao exportar: {str(ex)}", COLORS["red"])

    # --- Builders para componentes da view (extraídos para legibilidade) ---
    def _make_app_bar() -> ft.AppBar:
        def _local_back(e: ft.ControlEvent):
            try:
                # Se houver repositório global de XMLs aberto, fecha-lo
                try:
                    stored = page.app_data.get("fornecedores_global_xml_repo")
                    if stored and stored in getattr(page, "overlay", []):
                        fechar_xml_overlay(e, stored)
                        try:
                            e.handled = True
                        except Exception:
                            pass
                        return
                except Exception:
                    pass

                # Se o painel inferior estiver visível (XML detalhado), ocultá-lo
                try:
                    if getattr(
                        bottom_panel_ref, "current", None
                    ) is not None and getattr(
                        bottom_panel_ref.current, "visible", False
                    ):
                        fechar_xml_overlay(e, None)
                        try:
                            e.handled = True
                        except Exception:
                            pass
                        return
                except Exception:
                    pass

                # Fechar page.dialog padrão se aberto
                try:
                    if getattr(page, "dialog", None) is not None and getattr(
                        page.dialog, "open", False
                    ):
                        page.dialog.open = False
                        page.update()
                        try:
                            e.handled = True
                        except Exception:
                            pass
                        return
                except Exception:
                    pass

                # Nada fechado: delegar para o callback original
                try:
                    handle_back(e)
                except Exception:
                    try:
                        handle_back(None)
                    except Exception:
                        pass
            except Exception:
                pass

        return ft.AppBar(
            ref=appbar_ref,
            leading=ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                on_click=_local_back,
                tooltip="Voltar ao Painel Gerencial",
                icon_color=ft.Colors.WHITE,
            ),
            title=appbar_main_title,
            center_title=True,
            bgcolor=COLORS["primary"],
        )

    def _make_search_row() -> tuple[ft.TextField, ft.Row]:
        search_field_local = ft.TextField(
            ref=search_ref,
            label="Buscar fornecedor...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=filtrar_fornecedores,
            on_submit=filtrar_fornecedores,
            border_color=COLORS["primary"],
            disabled=False,
            autofocus=False,
            expand=True,
        )

        row = ft.Row(
            [
                search_field_local,
                ft.Row(
                    [
                        ft.IconButton(
                            ref=refresh_btn_ref,
                            icon=ft.Icons.REFRESH,
                            tooltip="Atualizar lista",
                            on_click=start_refresh_animation,
                            icon_color=COLORS["primary"],
                        ),
                        ft.Container(
                            content=ft.ProgressRing(
                                ref=refresh_pr_ref, visible=False, width=18, height=18
                            ),
                            padding=ft.padding.only(left=6),
                            alignment=ft.alignment.center,
                        ),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.IconButton(
                    icon=ft.Icons.UPLOAD_FILE,
                    tooltip="Importar CSV/Excel",
                    on_click=importar_fornecedores_csv,
                    icon_color=COLORS["primary"],
                ),
                ft.IconButton(
                    icon=ft.Icons.FILE_OPEN,
                    tooltip="Repositório de NF-e (XML) — visualizar todas as notas",
                    on_click=abrir_repositorio_global_xmls,
                    icon_color=COLORS["primary"],
                ),
                ft.IconButton(
                    icon=ft.Icons.DOWNLOAD,
                    tooltip="Exportar CSV",
                    on_click=lambda e: export_fornecedores("csv"),
                    icon_color=COLORS["green"],
                ),
                ft.IconButton(
                    icon=ft.Icons.PICTURE_AS_PDF,
                    tooltip="Exportar PDF",
                    on_click=lambda e: export_fornecedores("pdf"),
                    icon_color=COLORS["red"],
                ),
            ],
            spacing=5,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return search_field_local, row

    def _make_lista_fornecedores(search_row_control: ft.Row) -> ft.Card:
        # calcular altura disponível para a lista (fallback se não disponível)
        try:
            win_h = page.window_height or 800
        except Exception:
            win_h = 800

        # espaço reservado para título, search e paddings (~220px) — ajustar se necessário
        list_h = max(300, int(win_h - 220))

        return ft.Card(
            elevation=4,
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    "Lista de Fornecedores",
                                    style=ft.TextThemeStyle.TITLE_LARGE,
                                    weight=ft.FontWeight.BOLD,
                                    color=COLORS["text"],
                                ),
                                ft.ProgressRing(
                                    ref=loading_ref, visible=False, width=20, height=20
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        search_row_control,
                        ft.Container(
                            content=ft.Column(
                                ref=fornecedores_list_ref,
                                controls=[],
                                scroll=ft.ScrollMode.ADAPTIVE,
                                expand=True,
                            ),
                            expand=True,
                            height=list_h,
                        ),
                    ],
                    expand=True,
                    spacing=10,
                ),
                padding=15,
                expand=True,
            ),
            expand=True,
        )

    def _make_form_fornecedor() -> tuple[ft.Row, ft.Card]:
        checkboxes_group_local = ft.Row(
            [
                ft.Checkbox(
                    label=meio,
                    ref=checkboxes_ref[meio],
                    fill_color=COLORS["primary"],
                    check_color=ft.Colors.WHITE,
                )
                for meio in MEIOS_PAGAMENTO
            ],
            wrap=True,
        )

        form_card = ft.Card(
            elevation=4,
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            ref=form_title_ref,
                            value="Cadastrar Novo Fornecedor",
                            style=ft.TextThemeStyle.TITLE_MEDIUM,
                            weight=ft.FontWeight.BOLD,
                            color=COLORS["text"],
                        ),
                        ft.TextField(ref=selected_id_ref, visible=False),
                        ft.TextField(
                            ref=nome_ref,
                            label="Nome / Razão Social *",
                            hint_text="Obrigatório",
                            border_color=COLORS["primary"],
                        ),
                        ft.Row(
                            [
                                ft.TextField(
                                    ref=cnpj_cpf_ref,
                                    label="CNPJ / CPF",
                                    expand=True,
                                    border_color=COLORS["primary"],
                                    on_change=on_cnpj_change,
                                ),
                                ft.TextField(
                                    ref=contato_ref,
                                    label="Contato (Telefone/Email)",
                                    expand=True,
                                    border_color=COLORS["primary"],
                                    label_style=ft.TextStyle(size=16),
                                    text_size=14,
                                ),
                            ]
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(
                                        "Condição de Pagamento (Meios Aceitos)",
                                        weight=ft.FontWeight.BOLD,
                                        size=14,
                                        color=COLORS["text"],
                                    ),
                                    checkboxes_group_local,
                                ],
                                spacing=5,
                            ),
                            padding=ft.padding.only(top=10, bottom=10),
                        ),
                        ft.TextField(
                            ref=prazo_entrega_ref,
                            label="Prazo Médio Entrega (Ex: 7 dias úteis)",
                            border_color=COLORS["primary"],
                        ),
                        ft.Dropdown(
                            ref=categoria_ref,
                            label="Categoria",
                            hint_text="Selecione uma categoria",
                            options=[
                                ft.dropdown.Option(value, label)
                                for value, label in CATEGORIA_OPCOES
                            ],
                            border_color=COLORS["primary"],
                        ),
                        ft.Dropdown(
                            ref=status_ref,
                            label="Status",
                            value="ativo",
                            options=[
                                ft.dropdown.Option(value, label)
                                for value, label in STATUS_OPCOES
                            ],
                            border_color=COLORS["primary"],
                        ),
                        ft.Row(
                            [
                                ft.FilledButton(
                                    "Salvar",
                                    icon=ft.Icons.SAVE,
                                    on_click=salvar_fornecedor,
                                    style=ft.ButtonStyle(
                                        bgcolor=COLORS["green"], color=ft.Colors.WHITE
                                    ),
                                ),
                                ft.OutlinedButton(
                                    "Novo / Limpar",
                                    icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                                    on_click=limpar_formulario,
                                    style=ft.ButtonStyle(color=COLORS["primary"]),
                                ),
                            ]
                        ),
                    ],
                    spacing=15,
                ),
                padding=15,
            ),
        )
        return checkboxes_group_local, form_card

    def _make_detalhes_container() -> ft.Container:
        return ft.Container(
            ref=detalhes_container_ref,
            content=create_detalhes_fornecedor(None),
            padding=ft.padding.only(top=10),
        )

    # Construção da view usando os builders
    app_bar = _make_app_bar()
    search_field, search_row = _make_search_row()
    lista_fornecedores = _make_lista_fornecedores(search_row)
    checkboxes_group, form_fornecedor = _make_form_fornecedor()
    detalhes_container = _make_detalhes_container()

    view = ft.View(
        "/gerente/fornecedores",
        [
            app_bar,
            ft.Container(
                content=ft.ResponsiveRow(
                    [
                        ft.Column(
                            [lista_fornecedores], col={"md": 12, "lg": 5}, expand=True
                        ),
                        ft.Column(
                            [form_fornecedor, detalhes_container],
                            col={"md": 12, "lg": 7},
                            scroll=ft.ScrollMode.ALWAYS,
                        ),
                    ],
                    expand=True,
                    run_spacing=20,
                ),
                padding=ft.padding.all(15),
                expand=True,
            ),
            ft.Container(
                ref=bottom_bar_ref,
                visible=False,
                bgcolor=ft.Colors.GREEN_600,
                padding=10,
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.INFO, color=ft.Colors.WHITE),
                        ft.Text(
                            "",
                            ref=bottom_bar_text_ref,
                            color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
            ft.Container(
                ref=bottom_panel_ref,
                visible=False,
                bgcolor=COLORS.get("card", "white"),
                padding=12,
                border=ft.border.only(top=ft.BorderSide(1, ft.Colors.GREY_300)),
                content=None,
            ),
        ],
        padding=0,
    )

    try:

        def _fornecedores_on_key(e):
            try:
                key = (str(e.key) or "").upper()
                if key in ("ESCAPE", "ESC"):
                    page.go("/gerente")
            except Exception:
                pass

        view.on_keyboard_event = _fornecedores_on_key
    except Exception:
        pass

    # Ao criar a view, se houver dados de XML persistidos, anexar o painel inferior fixo
    try:
        xml_data = None
        try:
            xml_data = page.session.get("xml_data")
        except Exception:
            xml_data = None

        if xml_data and getattr(bottom_panel_ref, "current", None) is not None:
            try:
                panel = _build_panel_from_xml(xml_data)
                bottom_panel_ref.current.content = panel
                bottom_panel_ref.current.visible = True
                try:
                    bottom_panel_ref.current.update()
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass

    def on_view_did_mount():
        logger.info("View de fornecedores montada (on_view_did_mount)")
        page.bgcolor = COLORS["background"]

        async def _load_on_mount():
            # tentar aguardar refs serem vinculados, com retries
            max_tries = 8
            for i in range(max_tries):
                try:
                    if fornecedores_list_ref.current:
                        break
                except Exception:
                    pass
                try:
                    await page.sleep(0.08)
                except Exception:
                    # ambiente sem awaitable sleep
                    break
            try:
                # garantir update antes de popular
                try:
                    page.update()
                except Exception:
                    pass
                load_fornecedores_table("")
            except Exception as ex:
                logger.exception(f"Erro no carregamento inicial: {ex}")
            try:
                limpar_formulario()
            except Exception:
                pass

        try:
            page.run_task(_load_on_mount)
            logger.info("Disparada task de carregamento inicial de fornecedores")
        except Exception:
            # fallback síncrono se run_task não estiver disponível
            try:
                load_fornecedores_table("")
                limpar_formulario()
            except Exception:
                pass

        # Configurar Floating Action Button específico desta view
        try:
            # salvar FAB anterior para restaurar ao sair da view
            page.app_data["prev_fab_fornecedores"] = getattr(
                page, "floating_action_button", None
            )
            page.floating_action_button = ft.FloatingActionButton(
                icon=ft.icons.ADD,
                tooltip="Novo fornecedor",
                on_click=lambda e: limpar_formulario(),
            )
        except Exception:
            pass

        # Restaurar o FAB anterior ao desmontar a view
        try:

            def _restore_fab():
                try:
                    prev = page.app_data.get("prev_fab_fornecedores")
                    page.floating_action_button = prev
                except Exception:
                    try:
                        page.floating_action_button = None
                    except Exception:
                        pass

            view.on_view_will_unmount = lambda: _restore_fab()
        except Exception:
            pass

    view.on_view_did_mount = on_view_did_mount

    # Expor função de recarga na view para permitir disparo externo
    try:
        setattr(view, "load_fornecedores_table", load_fornecedores_table)
        setattr(view, "limpar_formulario", limpar_formulario)
    except Exception:
        pass

    return view


__all__ = [
    "FornecedorData",
    "COLORS",
    "MEIOS_PAGAMENTO",
    "STATUS_OPCOES",
    "show_snackbar",
    "validar_cnpj_cpf",
    "formatar_cnpj_cpf",
    "create_fornecedores_view",
]
