# View de Estoque: tela responsável por cadastro, edição,
# importação e visualização de produtos de estoque.

import unicodedata
from datetime import datetime
from pathlib import Path

import flet as ft

from estoque import alerts as est_alerts
from estoque import dialogs as dialogs
from estoque import handlers as est_handlers
from estoque import imports as import_utils
from estoque import repository as repo
from estoque.components import criar_linha_tabela as criar_linha_tabela_ext

# (removido import não utilizado) from alertas.alertas_init import atualizar_badge_alertas_no_gerente
from models.db_models import Produto
from utils.export_utils import generate_csv_file, generate_pdf_file

try:
    from utils.barcode_reader import BarcodeReader
except Exception:
    BarcodeReader = None
import os

from estoque.formatters import converter_texto_para_data as fmt_converter_data
from estoque.formatters import converter_texto_para_preco as fmt_converter_preco

# Paleta de cores usada na tela de estoque (cores da logo Mercadinho Ponto Certo)
COLORS = {
    "primary": "#034986",  # Azul da logo
    "accent": "#FFB347",  # Laranja suave da logo
    "background": "#F0F4F8",  # Cinza suave
    "text": "#2D3748",  # Texto escuro
    "green": "#8FC74F",  # Verde da logo
}
# Cores customizadas para botões na tela de Estoque
NAVY = "#012a4a"  # azul marinho
BTN_TEXT_GRAY = ft.Colors.WHITE  # agora texto em branco para melhor contraste
CATEGORIAS = [
    "Hortifrúti",
    "Carnes (açougue)",
    "Frios e laticínios",
    "Mercearia",
    "Padaria",
    "Bebidas",
    "Higiene e Limpeza",
    "Utensílios Domésticos",
    "Pet Shop",
]

# Caminho base do projeto (um nível acima da pasta "estoque")
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
# Arquivo JSON onde os produtos de estoque são salvos/carregados
ARQUIVO_DADOS = os.path.join(BASE_DIR, "data", "produtos.json")


# Helpers de importação (disponíveis para testes)
def _converter_texto_para_data(texto):
    # Delegamos para o utilitário centralizado para manter consistência
    return fmt_converter_data(texto)


def _converter_texto_para_preco(texto):
    # Usa o conversor robusto (remove NBSP, caracteres estranhos e trata vírgula/ponto)
    return fmt_converter_preco(texto)


def _validar_produto_fields(nome, categoria, quantidade, validade_obj):
    if not (nome and categoria and quantidade):
        raise ValueError("Campos obrigatórios ausentes")
    if validade_obj is None:
        raise ValueError("Data inválida")
    try:
        qtd = int(quantidade)
        if qtd < 0:
            raise ValueError("Quantidade negativa")
        return qtd
    except Exception:
        raise ValueError("Quantidade inválida")


# Reexportar funções de I/O do módulo `repository` para compatibilidade
# (evita duplicação e mantém os testes/scripts que importam destas names).
read_products_from_file = repo.read_products_from_file


carregar_produtos = repo.carregar_produtos


salvar_produtos = repo.salvar_produtos


def create_estoque_view(page: ft.Page, voltar_callback, handle_logout=None):
    """Monta e retorna a View do módulo de Estoque.

    - `page`: instância principal do Flet.
    - `voltar_callback`: função chamada ao clicar no botão de voltar.
    - `handle_logout`: função para fazer logout (ESC).
    """
    # ✅ REGISTRAR HANDLER DE TECLADO IMEDIATAMENTE

    # Handler de teclado simples para ESC
    def estoque_keyboard_handler(e: ft.KeyboardEvent):
        """Handler de teclado para a view de Estoque.

        - Se algum overlay de diálogo customizado estiver visível, fecha-o e consome a tecla ESC.
        - Caso contrário, mantém o comportamento anterior (navegação/logout conforme role).
        """
        try:
            key_estoque = str(e.key).upper() if e.key else ""
            try:
                print(
                    f"[ESTOQUE-KEY] key={e.key!r} e.handled={getattr(e, 'handled', False)} dialog_visible={getattr(dialog_overlay, 'visible', False) if 'dialog_overlay' in globals() or 'dialog_overlay' in locals() else 'NA'} exclusao_visible={getattr(exclusao_overlay, 'visible', False) if 'exclusao_overlay' in globals() or 'exclusao_overlay' in locals() else 'NA'} page_dialog_open={getattr(getattr(page, 'dialog', None), 'open', False)} estoque_prevent={page.app_data.get('estoque_prevent_esc_nav')}"
                )
            except Exception:
                pass
            if e.key in ("Escape",) or key_estoque in ("ESCAPE", "ESC"):
                # Prioriza fechar diálogos/modais abertos nesta view.
                # Acessa as variáveis do escopo da view diretamente e ignora NameError.
                try:
                    if dialog_overlay is not None and getattr(
                        dialog_overlay, "visible", False
                    ):
                        fechar_dialog()
                        try:
                            e.handled = True
                        except Exception:
                            pass
                        return
                except Exception:
                    pass

                try:
                    if exclusao_overlay is not None and getattr(
                        exclusao_overlay, "visible", False
                    ):
                        fechar_exclusao()
                        try:
                            e.handled = True
                        except Exception:
                            pass
                        return
                except Exception:
                    pass

                # Compatibilidade com AlertDialog padrão (page.dialog)
                try:
                    if getattr(page, "dialog", None) is not None and getattr(
                        page.dialog, "open", False
                    ):
                        page.dialog.open = False
                        try:
                            import time

                            page.app_data["estoque_last_modal_closed_ts"] = time.time()
                        except Exception:
                            pass
                        try:
                            e.handled = True
                        except Exception:
                            pass
                        try:
                            page.app_data["estoque_prevent_esc_nav"] = True

                            async def _clear_flag3():
                                try:
                                    import asyncio

                                    await asyncio.sleep(0.15)
                                    page.app_data["estoque_prevent_esc_nav"] = False
                                except Exception:
                                    try:
                                        page.app_data["estoque_prevent_esc_nav"] = False
                                    except Exception:
                                        pass

                            try:
                                page.run_task(_clear_flag3)
                            except Exception:
                                try:
                                    page.app_data["estoque_prevent_esc_nav"] = False
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        page.update()
                        return
                except Exception:
                    pass

                # Se não havia diálogos abertos, segue com comportamento padrão
                role = page.session.get("role")
                if role == "gerente":
                    page.go("/gerente")
                else:
                    print("[LOGOUT] ESC pressionado no Estoque - fazendo logout")
                    page.session.set("_logout_flag", "true")
                    page.session.clear()
                    page.session.set("_logout_flag", "true")
                    page.update()
                    page.go("/login")
        except Exception:
            pass

    # Não sobrescrever o handler global da página; usaremos o handler na View

    page.locale = "pt-BR"

    # Leitor de código de barras via câmera (utils/barcode_reader)
    barcode_reader = BarcodeReader() if BarcodeReader else None

    # DatePicker "global" da página para reaproveitar em vários lugares
    page.overlay.append(
        ft.DatePicker(
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2050, 12, 31),
            confirm_text="Confirmar",
            cancel_text="Cancelar",
            help_text="Selecione a data",
            error_format_text="Formato inválido",
            error_invalid_text="Data fora do limite",
            field_label_text="Digite a data",
            field_hint_text="DD/MM/AAAA",
        )
    )

    # Lista em memória com todos os produtos exibidos/editados na tela
    produtos = repo.carregar_produtos()

    # Placeholder para o dialog - será definido posteriormente
    dialog = None

    # Função helper para atualizar o badge de alertas (sincroniza + badges)
    def atualizar_badge_alertas():
        pdv_core_local = page.app_data.get("pdv_core")
        if not pdv_core_local:
            print("[ESTOQUE] ❌ PDVCore não encontrado")
            return
        # sincroniza estoque com banco e atualiza badges (gerente + local)
        est_alerts.sincronizar_estoque(page, pdv_core_local, produtos, Produto)
        est_alerts.atualizar_badge_gerente(page, pdv_core_local)
        try:
            # Usa refs definidas mais abaixo na view
            est_alerts.atualizar_badge_local(
                page, alerta_numero_ref_est, alerta_container_ref_est
            )
        except Exception as ex:
            print(f"[ESTOQUE] ⚠️  Falha ao atualizar badge local: {ex}")

    # Calcula contadores dos cards (baixo estoque, total e vencidos)
    def atualizar_estatisticas():
        baixo = sum(1 for p in produtos if p["quantidade"] < 10)
        venc = sum(1 for p in produtos if p["validade"] < datetime.now())
        return baixo, len(produtos), venc

    # Converte texto dd/mm/aaaa em datetime ou None (utilitário centralizado)
    def converter_texto_para_data(texto):
        return fmt_converter_data(texto)

    # Converte texto de preço (com R$, vírgula/ponto) em float (utilitário centralizado)
    def converter_texto_para_preco(texto):
        return fmt_converter_preco(texto)

    # Valida campos básicos do produto e retorna quantidade como int
    def validar_produto(nome, categoria, quantidade, validade_obj):
        if not (nome and categoria and quantidade):
            raise ValueError("⚠️ Todos os campos são obrigatórios!")
        if validade_obj is None:
            raise ValueError("⚠️ Data inválida! Use o formato DD/MM/AAAA.")
        try:
            qtd = int(quantidade)
            if qtd < 0:
                raise ValueError()
            return qtd
        except Exception:
            raise ValueError("Quantidade deve ser um número inteiro positivo")

    # Atualiza os cards de resumo e recarrega as linhas da tabela
    # Se for passada uma lista filtrada, usa-a apenas para popular a tabela;
    # os cards continuam refletindo os valores totais do conjunto `produtos`.
    def atualizar_tabela(lista_filtrada=None):
        baixo, total, venc = atualizar_estatisticas()
        texto_baixo_estoque.value = str(baixo)
        texto_total_produtos.value = str(total)
        texto_vencidos.value = str(venc)
        data_table.rows.clear()
        fonte = lista_filtrada if lista_filtrada is not None else produtos
        for p in fonte:
            data_table.rows.append(
                criar_linha_tabela_ext(p, editar_produto, excluir_produto)
            )
        page.update()

    # Fecha o diálogo de cadastro/edição de produto
    def fechar_dialog():
        dialog.open = False
        dialog_overlay.visible = False
        try:
            import time

            page.app_data["estoque_last_modal_closed_ts"] = time.time()
        except Exception:
            pass
        try:
            page.app_data["estoque_prevent_esc_nav"] = True

            async def _clear_flag():
                try:
                    import asyncio

                    await asyncio.sleep(0.15)
                    page.app_data["estoque_prevent_esc_nav"] = False
                except Exception:
                    try:
                        page.app_data["estoque_prevent_esc_nav"] = False
                    except Exception:
                        pass

            try:
                page.run_task(_clear_flag)
            except Exception:
                # fallback: limpar sem aguardar
                try:
                    page.app_data["estoque_prevent_esc_nav"] = False
                except Exception:
                    pass
        except Exception:
            pass
        page.update()

    # Limpa todos os campos do formulário de produto
    def limpar_campos():
        nome_field.value = ""
        categoria_field.value = None
        quantidade_field.value = ""
        preco_custo_field.value = ""
        preco_field.value = ""
        codigo_barras_field.value = ""
        lote_field.value = ""
        codigo_barras_leitor_field.value = ""
        data_atual = datetime.now()
        validade_picker.value = data_atual
        data_validade_field.value = data_atual.strftime("%d/%m/%Y")

    # Abre o diálogo no modo "Adicionar Produto"
    def abrir_dialog(e):
        try:
            print("[INFO] Abrindo dialogo de adicionar produto...")
            limpar_campos()
            print("[DEBUG] Adicionando overlay...")
            if dialog_overlay not in page.overlay:
                page.overlay.append(dialog_overlay)
            dialog_overlay.visible = True
            print("[DEBUG] Chamando page.update()...")
            page.update()
            print("[OK] Dialogo aberto com sucesso!")
        except Exception as ex:
            print(f"[ERROR] Erro ao abrir dialogo: {ex}")
            import traceback

            traceback.print_exc()

    # Entra no modo edição preenchendo o diálogo com dados do produto
    def editar_produto(e, produto_id):
        try:
            print(f"[DEBUG] Editando produto ID: {produto_id}")
            produto = next((p for p in produtos if p["id"] == produto_id), None)
            if not produto:
                print(f"[ERROR] Produto {produto_id} nao encontrado")
                return

            # Carregar dados do produto nos campos
            nome_field.value = produto["nome"]
            categoria_field.value = produto["categoria"]
            quantidade_field.value = str(produto["quantidade"])
            codigo_barras_field.value = produto.get("codigo_barras", "")
            codigo_barras_leitor_field.value = produto.get("codigo_barras", "")
            validade_picker.value = produto["validade"]
            data_validade_field.value = produto["validade"].strftime("%d/%m/%Y")
            preco_field.value = f"{produto.get('preco_venda', 0.0):.2f}".replace(
                ".", ","
            )
            preco_custo_field.value = (
                f"{float(produto.get('preco_custo', 0.0)):.2f}".replace(".", ",")
            )
            lote_field.value = produto.get("lote", "")

            def salvar_edicao(_):
                try:
                    print("[DEBUG] Salvando edicao do produto...")
                    nova_validade = converter_texto_para_data(data_validade_field.value)
                    qtd = validar_produto(
                        nome_field.value,
                        categoria_field.value,
                        quantidade_field.value,
                        nova_validade,
                    )
                    produto["nome"] = nome_field.value
                    produto["categoria"] = categoria_field.value
                    produto["validade"] = nova_validade
                    produto["quantidade"] = qtd
                    produto["codigo_barras"] = codigo_barras_field.value
                    produto["preco_venda"] = converter_texto_para_preco(
                        preco_field.value
                    )
                    produto["preco_custo"] = converter_texto_para_preco(
                        preco_custo_field.value
                    )
                    produto["lote"] = lote_field.value
                    repo.salvar_produtos(produtos)
                    atualizar_tabela()
                    fechar_dialog()
                    limpar_campos()
                    atualizar_badge_alertas()
                    page.snack_bar = ft.SnackBar(
                        ft.Text("Produto editado com sucesso!", color="white"),
                        bgcolor=ft.Colors.GREEN_600,
                    )
                    page.snack_bar.open = True
                    page.update()
                    print("[OK] Produto editado com sucesso")
                except ValueError as err:
                    print(f"[ERROR] Erro ao salvar: {err}")
                    page.snack_bar = ft.SnackBar(
                        ft.Text(str(err), color="white"), bgcolor=ft.Colors.RED_600
                    )
                    page.snack_bar.open = True
                    page.update()

            # Atualizar titulo do dialog
            # Encontrar o botão "Salvar" no overlay e atualizar seu callback
            # O botão está em dialog_content > Row do fundo > ElevatedButton
            for control in dialog_content.content.controls:
                if isinstance(control, ft.Row):
                    for row_control in control.controls:
                        if isinstance(row_control, ft.ElevatedButton) and "Salvar" in (
                            row_control.text or ""
                        ):
                            row_control.text = "Salvar Alteracoes"
                            row_control.bgcolor = NAVY
                            try:
                                row_control.color = BTN_TEXT_GRAY
                            except Exception:
                                pass
                            row_control.on_click = salvar_edicao
                            break

            # Abrir o overlay customizado
            if dialog_overlay not in page.overlay:
                page.overlay.append(dialog_overlay)
            dialog_overlay.visible = True
            page.update()
            print("[OK] Produto carregado para edicao")
        except Exception as ex:
            print(f"[ERROR] Erro ao editar produto: {ex}")
            import traceback

            traceback.print_exc()

    produto_id_para_excluir = None
    produto_em_exclusao = None

    # Abre o diálogo de confirmação de exclusão
    def excluir_produto(e, produto_id):
        nonlocal produto_id_para_excluir, produto_em_exclusao
        try:
            print(f"[DEBUG] Abrindo dialogo de exclusao para produto {produto_id}")
            produto_id_para_excluir = produto_id
            # Guarda referência ao produto para sincronizar com o banco (zerar estoque)
            produto_em_exclusao = next(
                (p for p in produtos if p["id"] == produto_id), None
            )
            # Abrir o overlay de exclusão
            if exclusao_overlay not in page.overlay:
                page.overlay.append(exclusao_overlay)
            exclusao_overlay.visible = True
            page.update()
            print("[OK] Dialogo de exclusao aberto")
        except Exception as ex:
            print(f"[ERROR] Erro ao abrir dialogo de exclusao: {ex}")
            import traceback

            traceback.print_exc()

    # Confirma a exclusão e remove o produto da lista/arquivo
    def confirmar_exclusao(e):
        nonlocal produto_id_para_excluir, produto_em_exclusao
        if produto_id_para_excluir is not None:
            # Tenta zerar o estoque no banco para não aparecer em relatórios
            try:
                pdv_core_local = page.app_data.get("pdv_core")
                if pdv_core_local and produto_em_exclusao:
                    cod = (produto_em_exclusao or {}).get("codigo_barras") or ""
                    if cod:
                        prod_db = (
                            pdv_core_local.session.query(Produto)
                            .filter_by(codigo_barras=cod)
                            .first()
                        )
                        if prod_db:
                            prod_db.estoque_atual = 0
                            pdv_core_local.session.commit()
                            print(f"[ESTOQUE] DB atualizado: estoque zerado para {cod}")
                    # Sem código de barras, não altera DB para evitar afetar item errado
            except Exception as sx:
                print(f"[ESTOQUE] Aviso ao zerar estoque no DB: {sx}")

            produtos[:] = [p for p in produtos if p["id"] != produto_id_para_excluir]
            repo.salvar_produtos(produtos)
            atualizar_tabela()
            # Atualiza badges/contadores gerais
            try:
                atualizar_badge_alertas()
            except Exception:
                pass
            page.snack_bar = ft.SnackBar(
                ft.Text("✅ Produto excluído!", color="white"),
                bgcolor=ft.Colors.GREEN_600,
            )
            page.snack_bar.open = True
        produto_id_para_excluir = None
        produto_em_exclusao = None
        exclusao_overlay.visible = False
        page.update()

    # Cancela a exclusão em andamento
    def cancelar_exclusao(e):
        nonlocal produto_id_para_excluir, produto_em_exclusao
        produto_id_para_excluir = None
        produto_em_exclusao = None
        exclusao_overlay.visible = False
        page.update()

    # Diálogo de confirmação de exclusão de produto
    # Removido AlertDialog não utilizado (confirmar_exclusao_dialog)

    # Cria um novo produto a partir do formulário e salva
    def adicionar_produto(e):
        try:
            data_val = converter_texto_para_data(data_validade_field.value)
            qtd = validar_produto(
                nome_field.value,
                categoria_field.value,
                quantidade_field.value,
                data_val,
            )
            preco_val = converter_texto_para_preco(preco_field.value)
            preco_custo_val = converter_texto_para_preco(preco_custo_field.value)
            novo = {
                "id": max([p["id"] for p in produtos], default=0) + 1,
                "nome": nome_field.value,
                "categoria": categoria_field.value,
                "validade": data_val,
                "quantidade": qtd,
                "lote": lote_field.value,
                "preco_venda": preco_val,
                "preco_custo": preco_custo_val,
                "codigo_barras": codigo_barras_field.value,
            }
            produtos.append(novo)
            repo.salvar_produtos(produtos)
            atualizar_tabela()
            fechar_dialog()
            limpar_campos()
            atualizar_badge_alertas()
            page.snack_bar = ft.SnackBar(
                ft.Text("✅ Produto adicionado!", color="white"),
                bgcolor=ft.Colors.GREEN_600,
            )
            page.snack_bar.open = True
            page.update()
        except Exception as err:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"{err}", color="white"), bgcolor=ft.Colors.RED_600
            )
            page.snack_bar.open = True
            page.update()

    # Gera um CSV do estoque atual usando utilitário de exportação
    def exportar_csv(e):
        try:
            headers = [
                "ID",
                "Nome",
                "Categoria",
                "Validade",
                "Lote",
                "Quant.",
                "Custo",
                "Preço",
            ]
            data = [
                [
                    p["id"],
                    p["nome"],
                    p["categoria"],
                    p["validade"].strftime("%d/%m/%Y"),
                    p.get("lote", ""),
                    p["quantidade"],
                    f"{float(p.get('preco_custo', 0.0)):.2f}".replace(".", ","),
                    f"{float(p.get('preco_venda', p.get('preco', 0.0))):.2f}".replace(
                        ".", ","
                    ),
                ]
                for p in produtos
            ]
            caminho = generate_csv_file(headers, data, nome_base="estoque")
            os.startfile(caminho)
            page.snack_bar = ft.SnackBar(
                ft.Text(f"✅ CSV exportado: {Path(caminho).name}"),
                bgcolor=ft.Colors.GREEN_600,
            )
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"❌ Erro ao exportar: {str(ex)}"), bgcolor=ft.Colors.RED_600
            )
            page.snack_bar.open = True
            page.update()

    # Gera um PDF do estoque atual usando utilitário de exportação
    def exportar_pdf(e):
        try:
            headers = [
                "ID",
                "Nome",
                "Categoria",
                "Validade",
                "Lote",
                "Quant.",
                "Custo",
                "Preço",
            ]
            data = [
                [
                    p["id"],
                    p["nome"],
                    p["categoria"],
                    p["validade"].strftime("%d/%m/%Y"),
                    p.get("lote", ""),
                    p["quantidade"],
                    f"{float(p.get('preco_custo', 0.0)):.2f}".replace(".", ","),
                    f"{float(p.get('preco_venda', p.get('preco', 0.0))):.2f}".replace(
                        ".",
                        ",",
                    ),
                ]
                for p in produtos
            ]
            pesos = [6, 34, 16, 12, 12, 8, 8, 8]
            caminho = generate_pdf_file(
                headers,
                data,
                nome_base="estoque",
                title="Relatório de Estoque",
                col_widths=pesos,
            )
            os.startfile(caminho)
            page.snack_bar = ft.SnackBar(
                ft.Text(f"✅ PDF exportado: {Path(caminho).name}"),
                bgcolor=ft.Colors.GREEN_600,
            )
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"❌ Erro ao gerar PDF: {str(ex)}"), bgcolor=ft.Colors.RED_600
            )
            page.snack_bar.open = True
            page.update()

    # Handler chamado após o usuário escolher um arquivo CSV
    def on_file_selected(ev):
        file_path = (
            file_picker.result.files[0].path if file_picker.result.files else None
        )
        if not file_path:
            return

        importados, duplicados, err = import_utils.process_import(
            file_path,
            produtos,
            converter_texto_para_data,
            converter_texto_para_preco,
            validar_produto,
        )

        if err:
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Erro ao importar arquivo: {err}", color="white"),
                bgcolor=ft.Colors.RED_600,
            )
            page.snack_bar.open = True
            page.update()
            return

        if importados:
            base_id = max([p["id"] for p in produtos], default=0)
            for idx, obj in enumerate(importados, start=1):
                obj["id"] = base_id + idx
            produtos.extend(importados)
            salvar_produtos(produtos)
            atualizar_tabela()
            page.snack_bar = ft.SnackBar(
                ft.Text(
                    f"✅ {len(importados)} produto(s) importado(s)!", color="white"
                ),
                bgcolor=ft.Colors.GREEN_600,
            )
            page.snack_bar.open = True

            if duplicados:
                try:
                    names_preview = ", ".join((duplicados[:3]))
                    extra = "" if len(duplicados) <= 3 else f" +{len(duplicados) - 3}"
                    show_appbar_alert(
                        f"Produtos já existentes ignorados: {len(duplicados)} (ex.: {names_preview}{extra})",
                        duration_ms=3500,
                    )
                except Exception:
                    pass
                try:
                    show_bottom_corner_message(
                        f"Produtos já foram adicionados: {len(duplicados)} ignorado(s)",
                        bgcolor=ft.Colors.ORANGE_600,
                        duration_ms=3500,
                    )
                except Exception:
                    pass
                try:
                    page.snack_bar = ft.SnackBar(
                        ft.Text(
                            f"Produtos já existentes ignorados: {len(duplicados)}",
                            color=ft.Colors.WHITE,
                        ),
                        bgcolor=ft.Colors.ORANGE_700,
                    )
                    page.snack_bar.open = True
                    page.update()
                except Exception:
                    pass
            else:
                page.update()
        else:
            # Nenhum novo produto - provavelmente apenas duplicados
            if duplicados:
                try:
                    names_preview = ", ".join((duplicados[:3]))
                    extra = "" if len(duplicados) <= 3 else f" +{len(duplicados) - 3}"
                    show_appbar_alert(
                        f"Produtos já existentes ignorados: {len(duplicados)} (ex.: {names_preview}{extra})",
                        duration_ms=3500,
                    )
                except Exception:
                    pass
                try:
                    show_bottom_corner_message(
                        f"Produtos já foram adicionados: {len(duplicados)} ignorado(s)",
                        bgcolor=ft.Colors.ORANGE_600,
                        duration_ms=3500,
                    )
                except Exception:
                    pass
                try:
                    preview = ", ".join(duplicados[:10])
                    detalhe = preview + (" ..." if len(duplicados) > 10 else "")
                    dialog_local = ft.AlertDialog(
                        title=ft.Text("Importação — Produtos Ignorados"),
                        content=ft.Column(
                            [
                                ft.Text(
                                    f"O arquivo não contém produtos novos. {len(duplicados)} produto(s) foram ignorados por já existirem."
                                ),
                                ft.Text(f"Exemplos: {detalhe}", size=12),
                            ],
                            tight=True,
                        ),
                        actions=[
                            ft.ElevatedButton(
                                "OK",
                                on_click=lambda e: (
                                    setattr(dialog_local, "open", False),
                                    page.update(),
                                ),
                                bgcolor=NAVY,
                                color=BTN_TEXT_GRAY,
                            )
                        ],
                        modal=True,
                    )
                    page.dialog = dialog_local
                    dialog_local.open = True
                    page.update()
                except Exception:
                    pass
            else:
                page.snack_bar = ft.SnackBar(
                    ft.Text(
                        "Nenhum produto válido encontrado no arquivo.", color="white"
                    ),
                    bgcolor=ft.Colors.RED_600,
                )
                page.snack_bar.open = True
                page.update()

    # FilePicker para importar produtos de um arquivo CSV/Excel
    file_picker = ft.FilePicker(on_result=on_file_selected)
    page.overlay.append(file_picker)

    # Abre o seletor de arquivo CSV de produtos
    def importar_csv(e):
        # permite CSV e planilhas Excel
        file_picker.pick_files(
            allow_multiple=False, allowed_extensions=["csv", "xls", "xlsx"]
        )

    # DatePicker usado especificamente para o campo de validade do produto
    validade_picker = ft.DatePicker(
        first_date=datetime(2020, 1, 1),
        last_date=datetime(2050, 12, 31),
        confirm_text="Confirmar",
        cancel_text="Cancelar",
        help_text="Selecione a data de validade",
        error_format_text="Formato inválido",
        error_invalid_text="Data fora do intervalo",
        field_label_text="Data de validade",
        field_hint_text="DD/MM/AAAA",
        on_change=lambda e: setattr(
            data_validade_field, "value", e.control.value.strftime("%d/%m/%Y")
        ),
    )
    page.overlay.append(validade_picker)

    # Abre o calendário já posicionado na data atual do campo
    def abrir_calendario(e):
        try:
            print("[DEBUG] Abrindo calendário...")
            dia, mes, ano = map(int, data_validade_field.value.split("/"))
            validade_picker.value = datetime(ano, mes, dia)
        except Exception as ex:
            print(f"[DEBUG] Erro ao parsear data: {ex}")
            validade_picker.value = datetime.now()

        # Garante que o picker está no overlay
        if validade_picker not in page.overlay:
            page.overlay.append(validade_picker)

        # Abre o DatePicker
        page.open(validade_picker)
        print("[DEBUG] Calendário aberto!")

    # Valores grandes escuros para contrastar com fundo claro dos cards
    texto_baixo_estoque = ft.Text(
        "0", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_900
    )
    texto_total_produtos = ft.Text(
        "0", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_900
    )
    texto_vencidos = ft.Text(
        "0", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_900
    )

    # --- Busca e Filtros (UI + estado) ---
    search_field = ft.TextField(
        hint_text="Buscar produto...",
        width=320,
        dense=True,
        on_change=lambda e: aplicar_filtros(),
        on_submit=lambda e: aplicar_filtros(),
    )

    # Estado dos filtros simples
    filtro_categoria = None
    filtro_max_qtd = None

    def _normalize(texto: str) -> str:
        """Remove acentos/diacríticos e normaliza para minúsculas."""
        if not texto:
            return ""
        nf = unicodedata.normalize("NFD", str(texto))
        return "".join(c for c in nf if unicodedata.category(c) != "Mn").lower()

    def aplicar_filtros():
        # Aplica busca + filtros sobre a lista `produtos` e atualiza a tabela
        termo_raw = (search_field.value or "").strip()
        termo = _normalize(termo_raw)
        resultado = []
        for p in produtos:
            nome = _normalize(p.get("nome") or "")
            categoria = p.get("categoria") or ""
            qtd = int(p.get("quantidade") or 0)

            # Buscar apenas por produtos cujo nome COMEÇA com o termo
            if termo and not nome.startswith(termo):
                continue
            if filtro_categoria and filtro_categoria != "Todas":
                if categoria != filtro_categoria:
                    continue
            if filtro_max_qtd is not None:
                try:
                    if qtd > filtro_max_qtd:
                        continue
                except Exception:
                    pass

            resultado.append(p)

        atualizar_tabela(resultado)

    # Diálogo simples de filtros
    categoria_dropdown = ft.Dropdown(
        label="Categoria",
        options=[ft.dropdown.Option("Todas")]
        + [ft.dropdown.Option(c) for c in CATEGORIAS],
        value="Todas",
        dense=True,
    )
    max_qtd_field = ft.TextField(label="Máx. Quantidade", dense=True)

    def abrir_filtros(e):
        # Preenche campos do diálogo com estado atual e abre o AlertDialog.
        # Primeiro, fechar/limpar outros diálogos para evitar que o AlertDialog
        # fique por baixo de overlays existentes.
        try:
            print(
                f"[ESTOQUE] abrir_filtros: overlays_count={len(page.overlay) if hasattr(page, 'overlay') else 'NA'}"
            )
        except Exception:
            pass

        try:
            # Preencher valores do diálogo
            categoria_dropdown.value = filtro_categoria or "Todas"
            max_qtd_field.value = (
                str(filtro_max_qtd) if filtro_max_qtd is not None else ""
            )

            # Fechar qualquer dialogo atual para evitar sobreposição
            try:
                if getattr(page, "dialog", None) is not None:
                    try:
                        page.dialog.open = False
                    except Exception:
                        pass
                    page.dialog = None
            except Exception:
                pass

            # Atribuir e abrir o dialog de filtros
            page.dialog = filtros_dialog
            filtros_dialog.open = True
            # Também tentar abrir explicitamente via page.open() como fallback
            try:
                page.open(filtros_dialog)
            except Exception:
                pass

            page.update()
            print("[ESTOQUE] abrir_filtros: diálogo aberto com sucesso")
        except Exception as ex:
            print(f"[ESTOQUE] abrir_filtros falhou: {ex}")
            try:
                page.snack_bar = ft.SnackBar(
                    ft.Text(f"Erro ao abrir filtros: {ex}"), bgcolor=ft.Colors.RED_600
                )
                page.snack_bar.open = True
                page.update()
            except Exception:
                pass

    def aplicar_filtros_dialog(e):
        nonlocal filtro_categoria, filtro_max_qtd
        filtro_categoria = (
            categoria_dropdown.value if categoria_dropdown.value != "Todas" else None
        )
        try:
            filtro_max_qtd = (
                int(max_qtd_field.value) if max_qtd_field.value.strip() != "" else None
            )
        except Exception:
            filtro_max_qtd = None
        filtros_dialog.open = False
        page.update()
        aplicar_filtros()

    def limpar_filtros(e):
        nonlocal filtro_categoria, filtro_max_qtd
        filtro_categoria = None
        filtro_max_qtd = None
        categoria_dropdown.value = "Todas"
        max_qtd_field.value = ""
        filtros_dialog.open = False
        page.update()
        aplicar_filtros()

    # Diálogo de filtros: manter fundo padrão do AlertDialog, aplicar
    # fundo azul apenas nos botões 'Limpar' e 'Cancelar' (texto em branco).
    filtros_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Filtros"),
        content=ft.Column([categoria_dropdown, max_qtd_field], tight=True),
        actions=[
            ft.ElevatedButton(
                "Limpar",
                on_click=limpar_filtros,
                bgcolor=NAVY,
                color=ft.Colors.WHITE,
            ),
            ft.ElevatedButton(
                "Cancelar",
                on_click=lambda e: (
                    setattr(filtros_dialog, "open", False),
                    page.update(),
                ),
                bgcolor=NAVY,
                color=ft.Colors.WHITE,
            ),
            ft.ElevatedButton(
                "Aplicar",
                on_click=aplicar_filtros_dialog,
                bgcolor=NAVY,
                color=ft.Colors.WHITE,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    # Novo card profissional: ícone em círculo, tipografia grande, fundo colorido,
    # bordas arredondadas e sombra sutil.
    def criar_card_profissional(
        titulo, texto_valor, icone=None, cor_icone=None, width=220, shadow=True
    ):
        try:
            icon_circle = ft.Container(
                content=ft.Icon(icone, color=ft.Colors.WHITE, size=26),
                width=52,
                height=52,
                alignment=ft.alignment.center,
                border_radius=12,
                bgcolor=cor_icone or ft.Colors.BLUE_600,
            )

            text_col = ft.Column(
                [
                    texto_valor,
                    ft.Text(titulo, size=12, color=ft.Colors.GREY_800),
                ],
                spacing=4,
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            )

            return ft.Container(
                content=ft.Row(
                    [icon_circle, ft.Container(width=12), text_col],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(vertical=12, horizontal=14),
                bgcolor="#F8FAFF",  # fundo claro azul suave
                border=ft.border.all(1, ft.Colors.GREY_200),
                border_radius=12,
                shadow=(
                    ft.BoxShadow(
                        blur_radius=8, spread_radius=1, color="rgba(0,0,0,0.06)"
                    )
                    if shadow
                    else None
                ),
                width=width,
                height=88,
            )
        except Exception:
            # Fallback simples
            return ft.Container(content=ft.Column([texto_valor, ft.Text(titulo)]))

    # Usar o novo card profissional com cores de ícone distintas
    card_baixo_estoque = criar_card_profissional(
        "Baixo Estoque",
        texto_baixo_estoque,
        ft.Icons.WARNING,
        ft.Colors.RED_600,
        shadow=False,
    )
    card_total_produtos = criar_card_profissional(
        "Total de Produtos",
        texto_total_produtos,
        ft.Icons.INVENTORY,
        ft.Colors.BLUE_600,
        shadow=False,
    )
    card_vencidos = criar_card_profissional(
        "Vencimentos Próximos",
        texto_vencidos,
        ft.Icons.EVENT_BUSY,
        ft.Colors.ORANGE_600,
        width=280,
        shadow=False,
    )

    nome_field = ft.TextField(label="Nome do Produto", dense=True, expand=True)
    categoria_field = ft.Dropdown(
        label="Categoria",
        options=[ft.dropdown.Option(c) for c in CATEGORIAS],
        dense=True,
        expand=True,
    )
    quantidade_field = ft.TextField(
        label="Quantidade",
        dense=True,
        expand=True,
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    codigo_barras_field = ft.TextField(
        label="Código de Barras", dense=True, expand=True
    )
    lote_field = ft.TextField(label="Lote", dense=True, expand=True, hint_text="Lote")
    preco_custo_field = ft.TextField(
        label="Preço de Custo",
        dense=True,
        expand=True,
        prefix="R$",
        keyboard_type=ft.KeyboardType.NUMBER,
        hint_text="Ex: 3,20",
    )
    preco_field = ft.TextField(
        label="Preço de Venda",
        dense=True,
        expand=True,
        prefix="R$",
        keyboard_type=ft.KeyboardType.NUMBER,
        hint_text="Ex: 4,99",
    )

    # Inicia leitura de código de barras via câmera
    def iniciar_leitura_camera(e):
        def on_barcode_detected(barcode_data):
            codigo_barras_field.value = barcode_data
            codigo_barras_leitor_field.value = barcode_data
            page.update()
            page.snack_bar = ft.SnackBar(
                ft.Text(f"✅ Código lido: {barcode_data}", color="white"),
                bgcolor=ft.Colors.GREEN_600,
            )
            page.snack_bar.open = True
            page.update()

        if not barcode_reader or not barcode_reader.is_camera_available():
            page.snack_bar = ft.SnackBar(
                ft.Text("❌ Câmera não disponível!", color="white"),
                bgcolor=ft.Colors.RED_600,
            )
            page.snack_bar.open = True
            page.update()
            return

        barcode_reader.start_camera(on_barcode_detected)
        page.snack_bar = ft.SnackBar(
            ft.Text(
                "📷 Câmera iniciada. Aponte para o código de barras...",
                color="white",
            ),
            bgcolor=ft.Colors.BLUE_600,
        )
        page.snack_bar.open = True
        page.update()

    # Ativa o modo para uso de leitor óptico (keyboard wedge)
    def ativar_leitor_optico(e):
        try:
            # Tenta focar o campo para que o leitor (que atua como teclado) insira o código
            codigo_barras_field.focus()
            page.snack_bar = ft.SnackBar(
                ft.Text(
                    "📡 Modo leitor óptico: aponte o leitor e escaneie. O código será inserido no campo.",
                    color="white",
                ),
                bgcolor=ft.Colors.BLUE_600,
            )
            page.snack_bar.open = True
            page.update()
        except Exception:
            page.snack_bar = ft.SnackBar(
                ft.Text("❌ Não foi possível ativar o leitor óptico.", color="white"),
                bgcolor=ft.Colors.RED_600,
            )
            page.snack_bar.open = True
            page.update()

    # adiciona botão suffix para ativar leitor óptico (keyboard wedge)
    try:
        codigo_barras_field.suffix = ft.IconButton(
            icon=ft.Icons.KEYBOARD,
            on_click=ativar_leitor_optico,
            tooltip="Ler com leitor óptico",
        )
    except Exception:
        pass

    codigo_barras_leitor_field = ft.TextField(
        label="Scanner de Código de Barras",
        dense=True,
        expand=True,
        keyboard_type=ft.KeyboardType.TEXT,
        hint_text="Escaneie o código aqui ou digite manualmente",
        on_change=lambda e: setattr(codigo_barras_field, "value", e.control.value),
        # O campo terá dois botões no suffix: câmera (leitura por câmera) e teclado (leitor óptico)
        suffix=ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.CAMERA_ALT,
                    on_click=iniciar_leitura_camera,
                    tooltip="Ler código via câmera",
                ),
                ft.IconButton(
                    icon=ft.Icons.KEYBOARD,
                    on_click=lambda e: ativar_leitor_optico_leitor(e),
                    tooltip="Ler com leitor óptico",
                ),
            ],
            spacing=2,
        ),
    )

    # Foca o campo `codigo_barras_leitor_field` para uso com leitor óptico (keyboard wedge)
    def ativar_leitor_optico_leitor(e):
        try:
            codigo_barras_leitor_field.focus()
            page.snack_bar = ft.SnackBar(
                ft.Text(
                    "📡 Modo leitor óptico: escaneie com o leitor. O código será inserido no campo.",
                    color="white",
                ),
                bgcolor=ft.Colors.BLUE_600,
            )
            page.snack_bar.open = True
            page.update()
        except Exception:
            page.snack_bar = ft.SnackBar(
                ft.Text("❌ Não foi possível ativar o leitor óptico.", color="white"),
                bgcolor=ft.Colors.RED_600,
            )
            page.snack_bar.open = True
            page.update()

    data_validade_field = ft.TextField(
        label="Data de Validade (DD/MM/YYYY)",
        value=datetime.now().strftime("%d/%m/%Y"),
        read_only=True,
        dense=True,
        expand=True,
        suffix=ft.IconButton(
            icon=ft.Icons.CALENDAR_MONTH,
            on_click=abrir_calendario,
            tooltip="Selecionar Data",
        ),
        keyboard_type=ft.KeyboardType.DATETIME,
    )

    # Tabela principal que lista os produtos de estoque
    data_table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("ID", size=14, weight=ft.FontWeight.BOLD, width=60)),
            ft.DataColumn(
                ft.Text(
                    "Nome do Produto", size=14, weight=ft.FontWeight.BOLD, expand=True
                )
            ),
            ft.DataColumn(
                ft.Text("Categoria", size=14, weight=ft.FontWeight.BOLD, expand=True)
            ),
            ft.DataColumn(
                ft.Text("Validade", size=14, weight=ft.FontWeight.BOLD, width=100)
            ),
            ft.DataColumn(
                ft.Text("Lote", size=14, weight=ft.FontWeight.BOLD, width=90)
            ),
            ft.DataColumn(
                ft.Text("Quantidade", size=14, weight=ft.FontWeight.BOLD, width=100)
            ),
            ft.DataColumn(
                ft.Text("Custo", size=14, weight=ft.FontWeight.BOLD, width=100)
            ),
            ft.DataColumn(
                ft.Text("Preço", size=14, weight=ft.FontWeight.BOLD, width=100)
            ),
            ft.DataColumn(
                ft.Text(
                    "Código de Barras", size=14, weight=ft.FontWeight.BOLD, width=120
                )
            ),
            ft.DataColumn(
                ft.Text("Ações", size=14, weight=ft.FontWeight.BOLD, width=120)
            ),
        ],
        rows=[],
        column_spacing=30,
        bgcolor="white",
        border=ft.border.all(1, ft.Colors.GREY_300),
        border_radius=5,
    )

    tabela_container = ft.Container(
        content=ft.ListView(
            controls=[data_table],
            expand=True,
            auto_scroll=False,
        ),
        expand=True,
        width=float("inf"),
        border=ft.border.all(1, ft.Colors.GREY_300),
        border_radius=8,
        bgcolor="white",
        padding=0,
        margin=ft.margin.only(top=15),
    )

    # Criar overlay customizado para o diálogo via módulo dialogs
    dialog_content = dialogs.create_dialog_content(
        nome_field,
        categoria_field,
        data_validade_field,
        quantidade_field,
        preco_custo_field,
        preco_field,
        codigo_barras_field,
        codigo_barras_leitor_field,
        lote_field,
        COLORS["accent"],
        on_salvar=lambda e: adicionar_produto(e),
        on_cancelar=lambda e: fechar_dialog(),
    )

    # Criar overlay customizado para confirmação de exclusão via módulo dialogs
    exclusao_content = dialogs.create_exclusao_content(
        on_confirmar=lambda e: confirmar_exclusao(e),
        on_cancelar=lambda e: fechar_exclusao(),
    )

    # Overlay para exclusão via módulo dialogs
    exclusao_overlay = dialogs.create_exclusao_overlay(exclusao_content)

    def fechar_exclusao():
        exclusao_overlay.visible = False
        try:
            import time

            page.app_data["estoque_last_modal_closed_ts"] = time.time()
        except Exception:
            pass
        try:
            page.app_data["estoque_prevent_esc_nav"] = True

            async def _clear_flag2():
                try:
                    import asyncio

                    await asyncio.sleep(0.15)
                    page.app_data["estoque_prevent_esc_nav"] = False
                except Exception:
                    try:
                        page.app_data["estoque_prevent_esc_nav"] = False
                    except Exception:
                        pass

            try:
                page.run_task(_clear_flag2)
            except Exception:
                try:
                    page.app_data["estoque_prevent_esc_nav"] = False
                except Exception:
                    pass
        except Exception:
            pass
        page.update()

    # Overlay dialog via módulo dialogs
    dialog_overlay = dialogs.create_dialog_overlay(dialog_content)

    # Agora que todos os campos foram criados, definir o dialog como AlertDialog original
    dialog = ft.AlertDialog(
        title=ft.Text("Adicionar Produto"),
        content=ft.Column(
            [
                ft.Row([nome_field, categoria_field], spacing=12),
                ft.Row(
                    [
                        data_validade_field,
                        lote_field,
                        quantidade_field,
                        preco_custo_field,
                        preco_field,
                    ],
                    spacing=12,
                ),
                ft.Row([codigo_barras_field, codigo_barras_leitor_field], spacing=12),
                # Pequena ajuda sobre modos de leitura: câmera vs leitor óptico
                ft.Row(
                    [
                        ft.Text(
                            "Modo de leitura: Câmera (ícone) — usa a câmera do dispositivo; Leitor óptico (ícone) — leitor USB que emula teclado.",
                            size=12,
                            color=ft.Colors.GREY_700,
                        )
                    ],
                    tight=True,
                ),
            ],
            tight=True,
            spacing=12,
        ),
        actions=[
            ft.Row(
                [
                    ft.ElevatedButton(
                        "Cancelar",
                        bgcolor=NAVY,
                        color=ft.Colors.WHITE,
                        on_click=lambda e: fechar_dialog(),
                    ),
                    ft.ElevatedButton(
                        "Salvar",
                        bgcolor=NAVY,
                        color=ft.Colors.WHITE,
                        on_click=lambda e: adicionar_produto(e),
                    ),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.END,
            )
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    # Linha com cards minimalistas — espaçamento moderado e centralizados
    cards_row = ft.Row(
        [card_baixo_estoque, card_total_produtos, card_vencidos],
        spacing=20,
        wrap=True,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    botoes_acao = ft.Row(
        [
            ft.ElevatedButton(
                "Adicionar Produto",
                icon=ft.Icons.ADD,
                bgcolor=NAVY,
                color=BTN_TEXT_GRAY,
                on_click=abrir_dialog,
            ),
            ft.ElevatedButton(
                "Importar CSV/Excel",
                icon=ft.Icons.UPLOAD_FILE,
                on_click=importar_csv,
                bgcolor=NAVY,
                color=BTN_TEXT_GRAY,
            ),
            ft.ElevatedButton(
                "Exportar CSV",
                icon=ft.Icons.FILE_PRESENT,
                on_click=exportar_csv,
                bgcolor=NAVY,
                color=BTN_TEXT_GRAY,
            ),
            ft.ElevatedButton(
                "Exportar PDF",
                icon=ft.Icons.PICTURE_AS_PDF,
                on_click=exportar_pdf,
                bgcolor=NAVY,
                color=BTN_TEXT_GRAY,
            ),
        ],
        spacing=12,
    )

    # View principal da rota "/estoque"
    # Ícone de notificações com badge (local da tela de Estoque)
    alerta_numero_ref_est = ft.Ref[ft.Text]()
    alerta_container_ref_est = ft.Ref[ft.Container]()

    # Removidos controles de notificações não usados (botão e badge) para limpar diagnósticos
    # Removido container com badge de notificações não utilizado

    # Função local para atualizar o badge nesta tela
    def atualizar_badge_alertas_local():
        # encaminha para módulo alerts com as refs locais
        est_alerts.atualizar_badge_local(
            page, alerta_numero_ref_est, alerta_container_ref_est
        )

    # Referência para AppBar para permitir alertas temporários
    appbar_ref = ft.Ref[ft.AppBar]()

    # Título principal reutilizável
    appbar_main_title = ft.Text(
        "Controle de Estoque", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
    )

    # Função para exibir um alerta temporário na AppBar
    def show_appbar_alert(message: str, duration_ms: int = 3000):
        try:
            print(
                f"[ESTOQUE] show_appbar_alert called; appbar_current is {'set' if appbar_ref.current is not None else 'None'}"
            )
            if appbar_ref.current is None:
                # Fallback: se AppBar não estiver disponível, mostra snack_bar
                print(
                    "[ESTOQUE] appbar_ref.current is None — showing snack_bar fallback"
                )
                page.snack_bar = ft.SnackBar(
                    ft.Text(message, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.ORANGE_700,
                )
                page.snack_bar.open = True
                page.update()
                return

            print("[ESTOQUE] Updating appbar title with alert message")
            appbar_ref.current.title = ft.Column(
                [
                    appbar_main_title,
                    ft.Text(message, size=12, color=ft.Colors.WHITE),
                ],
                alignment="center",
                horizontal_alignment="center",
            )
            prev_bg = appbar_ref.current.bgcolor
            appbar_ref.current.bgcolor = ft.Colors.ORANGE_700
            appbar_ref.current.update()

            # Também mostra snack_bar para garantir visibilidade em todos os contextos
            try:
                page.snack_bar = ft.SnackBar(
                    ft.Text(message, color=ft.Colors.WHITE),
                    bgcolor=ft.Colors.ORANGE_700,
                )
                page.snack_bar.open = True
                page.update()
            except Exception:
                pass

            # Reverte após o tempo configurado
            try:
                import asyncio

                async def _revert_appbar_async():
                    try:
                        await asyncio.sleep(duration_ms / 1000.0)
                        if appbar_ref.current is not None:
                            appbar_ref.current.title = appbar_main_title
                            appbar_ref.current.bgcolor = prev_bg
                            appbar_ref.current.update()
                    except Exception:
                        pass

                page.run_task(_revert_appbar_async)
            except Exception:
                pass
        except Exception:
            pass

    # Mensagem no canto inferior direito (overlay temporário)
    def show_bottom_corner_message(
        message: str, bgcolor: str = ft.Colors.ORANGE_700, duration_ms: int = 3000
    ):
        try:
            msg_text = ft.Text(
                message, size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
            )
            pill = ft.Container(
                content=msg_text,
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                bgcolor=bgcolor,
                border_radius=12,
            )
            overlay = ft.Container(
                content=ft.Column(
                    [
                        ft.Container(expand=True),
                        ft.Row([pill], alignment=ft.MainAxisAlignment.END),
                    ],
                    expand=True,
                ),
                expand=True,
                bgcolor="transparent",
                visible=True,
            )

            page.overlay.append(overlay)
            page.update()

            try:
                import asyncio

                async def _auto_hide_async():
                    try:
                        await asyncio.sleep(duration_ms / 1000.0)
                        if overlay in page.overlay:
                            page.overlay.remove(overlay)
                        page.update()
                    except Exception:
                        pass

                page.run_task(_auto_hide_async)
            except Exception:
                try:
                    import time

                    time.sleep(duration_ms / 1000.0)
                    if overlay in page.overlay:
                        page.overlay.remove(overlay)
                    page.update()
                except Exception:
                    pass
        except Exception:
            pass

    # Largura responsiva para a área de cards: não excede 980px e deixa margem
    max_cards_width = (
        min(980, page.window_width - 40) if getattr(page, "window_width", None) else 980
    )

    # Handler local para o botão de voltar: tenta fechar modais locais antes de navegar
    def _local_voltar(e):
        try:
            # Fecha dialog customizado se visível
            try:
                if (
                    "dialog_overlay" in locals()
                    and dialog_overlay is not None
                    and getattr(dialog_overlay, "visible", False)
                ):
                    fechar_dialog()
                    try:
                        e.handled = True
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            # Fecha overlay de exclusão se visível
            try:
                if (
                    "exclusao_overlay" in locals()
                    and exclusao_overlay is not None
                    and getattr(exclusao_overlay, "visible", False)
                ):
                    fechar_exclusao()
                    try:
                        e.handled = True
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            # Fecha qualquer AlertDialog padrão (page.dialog)
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

            # Nenhum modal aberto: delega para o callback original
            try:
                voltar_callback(e)
            except Exception:
                try:
                    voltar_callback(None)
                except Exception:
                    pass
        except Exception:
            pass

    view = ft.View(
        "/estoque",
        bgcolor=COLORS["background"],
        padding=ft.padding.all(20),
        appbar=ft.AppBar(
            ref=appbar_ref,
            title=appbar_main_title,
            bgcolor=COLORS["primary"],
            center_title=True,
            leading=ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                icon_color=ft.Colors.WHITE,
                on_click=_local_voltar,
            ),
            # Removido o sino de notificações do canto superior direito
            actions=[],
        ),
        controls=[
            ft.Container(
                content=ft.Column(
                    [
                        # Área superior direita: busca + filtros
                        ft.Container(
                            content=ft.Row(
                                [
                                    search_field,
                                    ft.IconButton(
                                        icon=ft.Icons.FILTER_LIST,
                                        on_click=abrir_filtros,
                                        tooltip="Filtros",
                                    ),
                                ],
                                spacing=8,
                                alignment=ft.MainAxisAlignment.END,
                            ),
                            alignment=ft.alignment.center_right,
                            padding=ft.padding.only(top=6),
                        ),
                        ft.Divider(height=2, thickness=2, color=ft.Colors.GREY_300),
                        ft.Row(
                            [
                                ft.Container(
                                    content=cards_row,
                                    margin=ft.margin.only(top=12),
                                    padding=ft.padding.symmetric(horizontal=20),
                                    width=max_cards_width,
                                    expand=False,
                                    alignment=ft.alignment.center,
                                )
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        ft.Divider(height=1, thickness=1, color=ft.Colors.GREY_300),
                        botoes_acao,
                        tabela_container,
                    ],
                    expand=True,
                    spacing=20,
                ),
                expand=True,
            )
        ],
    )

    # Atualiza o badge ao montar a view de Estoque
    def on_view_did_mount_estoque():
        try:
            # Sincroniza o arquivo local com o banco e atualiza badges (local e gerente)
            atualizar_badge_alertas()
        except Exception as e:
            print(f"[ALERTAS-ESTOQUE] ❌ Erro no mount: {e}")

    view.on_view_did_mount = on_view_did_mount_estoque
    # Registrar handler de teclado específico desta view (fecha modais com ESC)
    view.on_keyboard_event = estoque_keyboard_handler

    # Monta uma linha da tabela de produtos a partir de um dict `p`
    def criar_linha_tabela(p):
        cor_qtd = ft.Colors.RED_600 if p["quantidade"] < 10 else ft.Colors.GREEN_600
        btn_editar = ft.IconButton(
            icon=ft.Icons.EDIT_OUTLINED,
            tooltip="Editar",
            icon_color=ft.Colors.BLUE_600,
            on_click=lambda e: (
                print(f"[DEBUG] Clique em editar produto {p['id']}"),
                editar_produto(e, p["id"]),
            ),
        )
        btn_excluir = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            tooltip="Excluir",
            icon_color=ft.Colors.RED_600,
            on_click=lambda e: (
                print(f"[DEBUG] Clique em excluir produto {p['id']}"),
                excluir_produto(e, p["id"]),
            ),
        )

        return ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(str(p["id"]), size=14)),
                ft.DataCell(
                    ft.Container(
                        content=ft.Text(
                            p["nome"], size=14, max_lines=2, overflow="visible"
                        ),
                        width=180,
                        padding=ft.padding.only(right=4),
                    )
                ),
                ft.DataCell(ft.Text(p["categoria"], size=14)),
                ft.DataCell(ft.Text(p["validade"].strftime("%d/%m/%Y"), size=14)),
                ft.DataCell(
                    ft.Text(
                        str(p["quantidade"]),
                        size=14,
                        color=cor_qtd,
                        weight=ft.FontWeight.BOLD,
                    )
                ),
                ft.DataCell(
                    ft.Text(
                        f"R$ {float(p.get('preco_venda', p.get('preco', 0.0))):.2f}".replace(
                            ".",
                            ",",
                        ),
                        size=14,
                        color=ft.Colors.GREY_800,
                    )
                ),
                ft.DataCell(
                    ft.Text(
                        p.get("codigo_barras", "-"),
                        size=12,
                        color=ft.Colors.GREY_700,
                    )
                ),
                ft.DataCell(ft.Row([btn_editar, btn_excluir], spacing=5)),
            ]
        )

    atualizar_tabela()

    # Handler para atalhos de teclado (ESC para voltar ao login)
    # Removido: handle_keyboard_shortcuts não era utilizado e gerava aviso de código não acessado.

    # Registrar handler de teclado no escopo da View (não global)
    # Encadear handler local e garantir que ESC leve ao Painel Gerencial
    try:
        view.on_keyboard_event = est_handlers.create_estoque_key_handler(
            page, original=estoque_keyboard_handler
        )
    except Exception:
        pass

    # Atualizar badge de alertas quando a view aparecer
    def on_view_will_appear(e):
        """Verifica estoque e sincroniza com banco quando a view de estoque é aberta"""
        print("\n[ESTOQUE] 📂 Tela de estoque aberta - sincronizando estoque...")
        atualizar_badge_alertas()

    view.on_view_will_appear = on_view_will_appear

    return view


__all__ = [
    "COLORS",
    "CATEGORIAS",
    "ARQUIVO_DADOS",
    "carregar_produtos",
    "salvar_produtos",
    "create_estoque_view",
    "read_products_from_file",
]
