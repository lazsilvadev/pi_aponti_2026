import base64
import io
import os
import re
import threading

import flet as ft

from caixa.logic import montar_payload_pix
from models.db_models import PaymentSettings, User
from utils.crypto import decrypt_str, encrypt_str


def create_pix_settings_view(page: ft.Page, handle_back):
    """View para gerenciamento das configurações Pix (somente gerente)."""
    # Segurança: apenas gerente pode acessar (rota /gerente/* já protege)

    session = None
    try:
        session = page.app_data.get("db_session")
    except Exception:
        session = None

    # campos com largura reduzida para modal mais compacto
    # campos mais fluidos: merchant e chave expandem para preencher a largura do modal
    merchant_field = ft.TextField(label="Merchant Name", expand=True)
    chave_field = ft.TextField(
        label="Chave PIX", password=True, can_reveal_password=True, expand=True
    )
    cpf_field = ft.TextField(label="CPF/CNPJ (opcional)", width=180)
    cidade_field = ft.TextField(label="Cidade", width=100)
    # (removido campo de taxa e adquirente para compatibilidade com versão anterior)
    tipo_dropdown = ft.Dropdown(
        label="Tipo PIX",
        options=[ft.dropdown.Option("dinamico"), ft.dropdown.Option("com_valor")],
        value="dinamico",
    )
    active_switch = ft.Switch(label="Ativo", value=True)

    # Estado local para QR enviado
    state = {"qr_image": None}

    # estado de preview sujo
    state.setdefault("dirty", False)

    # debounce timer para gerar pré-visualização
    _debounce = {"t": None}

    qr_preview = ft.Image(width=120, height=120)
    qr_container = ft.Container(
        content=qr_preview,
        width=120,
        height=120,
        scale=ft.Scale(0.92),
        opacity=0,
        animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        border_radius=ft.border_radius.all(6),
        bgcolor=ft.Colors.WHITE,
        padding=6,
    )
    file_picker = ft.FilePicker()
    page.overlay.append(file_picker)

    status_text = ft.Text("", visible=False)
    user_label = ft.Text("")
    last_edit_label = ft.Text("")

    def set_status(msg: str):
        try:
            status_text.value = msg
            status_text.visible = bool(msg)
            try:
                status_text.update()
            except AssertionError:
                # controle ainda não adicionado à view; ignore
                pass
        except Exception:
            pass

    def load_settings():
        try:
            cfg = None
            if session:
                cfg = session.query(PaymentSettings).filter_by(active=True).first()
            # mostrar usuário atual e informações de auditoria
            try:
                user_id = (
                    page.session.get("user_id") if hasattr(page, "session") else None
                )
                if session and user_id:
                    u = session.get(User, user_id)
                    if u:
                        user_label.value = f"Logado como: {u.username} ({u.role})"
            except Exception:
                pass
            if not cfg:
                merchant_field.value = "Mercadinho Ponto Certo"
                chave_field.value = ""
                cpf_field.value = ""
                cidade_field.value = "Recife"
                tipo_dropdown.value = "dinamico"
                active_switch.value = True
            else:
                merchant_field.value = cfg.merchant_name or ""
                # Mostrar campo de chave como vazio (segurança); usuário pode inserir nova
                chave_field.value = ""
                # manter o valor descriptografado em memória para gerar QR se necessário
                chave_field.data = decrypt_str(cfg.chave_pix or "")
                cpf_field.value = decrypt_str(cfg.cpf_cnpj or "")
                cidade_field.value = cfg.cidade or ""
                tipo_dropdown.value = cfg.tipo_pix or "dinamico"
                active_switch.value = bool(cfg.active)
                # QR image preview
                if cfg.qr_image_base64:
                    state["qr_image"] = cfg.qr_image_base64
                    qr_preview.src_base64 = cfg.qr_image_base64
                # mantendo compatibilidade: não exibir taxa/adquirente aqui
                try:
                    if getattr(cfg, "updated_by", None) or getattr(
                        cfg, "updated_at", None
                    ):
                        ub = getattr(cfg, "updated_by", "") or ""
                        ua = getattr(cfg, "updated_at", None)
                        last_edit_label.value = f"Última alteração: {ub} {ua.strftime('%Y-%m-%d %H:%M') if ua else ''}"
                except Exception:
                    pass
            page.update()
        except Exception as e:
            print(f"[PIX-UI] Erro ao carregar settings: {e}")

    def save_settings(e=None):
        try:
            if not session:
                set_status("DB session indisponível")
                return

            # Controle de acesso: somente gerente pode salvar
            user_id = page.session.get("user_id") if hasattr(page, "session") else None
            username = None
            if session and user_id:
                try:
                    u = session.get(User, user_id)
                    if u:
                        username = getattr(u, "username", None)
                        if getattr(u, "role", None) != "gerente":
                            set_status(
                                "Apenas usuários com papel 'gerente' podem alterar as configurações."
                            )
                            return
                except Exception:
                    pass

            # Validação básica
            if not (merchant_field.value or "").strip():
                set_status("Merchant name obrigatório.")
                return
            if active_switch.value and not (
                chave_field.value or getattr(chave_field, "data", None)
            ):
                set_status("Chave PIX vazia - preencha para ativar.")
                return
            cpf_raw = (cpf_field.value or "").strip()
            if cpf_raw:
                digits = re.sub(r"\D", "", cpf_raw)
                if len(digits) not in (11, 14):
                    set_status("CPF/CNPJ inválido (deve ter 11 ou 14 dígitos).")
                    return

            # Se ativar, desativar outros registros
            if active_switch.value:
                try:
                    session.query(PaymentSettings).update({"active": False})
                    session.commit()
                except Exception:
                    session.rollback()

            # Preferir valor recém-digitado; caso contrário usar valor existente em memória
            chave_plain = chave_field.value or getattr(chave_field, "data", "") or ""
            cpf_plain = cpf_field.value or ""
            # Não processar taxa de cartão/adquirente (removido)
            encrypted_chave = encrypt_str(chave_plain or "")
            encrypted_cpf = encrypt_str(cpf_plain or "")

            cfg = PaymentSettings(
                merchant_name=merchant_field.value or "Mercadinho Ponto Certo",
                chave_pix=encrypted_chave,
                cpf_cnpj=encrypted_cpf,
                cidade=cidade_field.value or "",
                tipo_pix=tipo_dropdown.value or "dinamico",
                active=bool(active_switch.value),
                updated_by=username,
                qr_image_base64=state.get("qr_image"),
                # sem campos de taxa/adquirente ao salvar
            )
            session.add(cfg)
            session.commit()
            # atualizar page.app_data
            try:
                page.app_data["pix_settings"] = {
                    "merchant_name": cfg.merchant_name,
                    "chave_pix": decrypt_str(cfg.chave_pix or ""),
                    "cpf_cnpj": decrypt_str(cfg.cpf_cnpj or ""),
                    "cidade": cfg.cidade,
                    "qr_image": cfg.qr_image_base64,
                    "tipo_pix": cfg.tipo_pix,
                }
            except Exception:
                pass

            set_status("📌 Configurações salvas com sucesso")
            # atualizar labels
            try:
                user_label.value = f"Logado como: {username or ''}"
                from datetime import datetime

                last_edit_label.value = f"Última alteração: {username or ''} {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            except Exception:
                pass
        except Exception as ex:
            try:
                session.rollback()
            except Exception:
                pass
            set_status(f"Erro ao salvar: {ex}")

    def gerar_qr(e=None):
        try:
            merchant = merchant_field.value or "Mercadinho Ponto Certo"
            chave = chave_field.value or getattr(chave_field, "data", None) or None
            cidade = cidade_field.value or "Recife"
            try:
                from payments.pix_generator import PixGenerator
            except Exception:
                set_status("Biblioteca de geração de PIX não disponível")
                return

            valor_teste = 1.23
            progress_ring.visible = True
            set_status("Gerando QR...")
            try:
                page.update()
            except Exception:
                pass

            def _work():
                try:
                    gen = PixGenerator(chave or "", merchant, cidade)
                    qr_base64 = gen.gerar_qr_base64(valor_teste)
                    payload = gen.gerar_payload(valor_teste)
                    print(f"[PIX-PAYLOAD] {payload}")
                    state["qr_image"] = qr_base64
                    qr_preview.src_base64 = qr_base64
                    # animar entrada (fade + scale)
                    qr_container.scale = ft.Scale(1.0)
                    qr_container.opacity = 1
                    state["dirty"] = False
                    set_status("QR gerado")
                    try:
                        dlg = ft.AlertDialog(
                            title=ft.Text("QR Preview"),
                            content=ft.Column(
                                [
                                    ft.Image(src_base64=qr_base64),
                                    ft.Text(payload, size=12),
                                ]
                            ),
                            actions=[
                                ft.ElevatedButton(
                                    "Fechar",
                                    on_click=lambda e: setattr(dlg, "open", False),
                                )
                            ],
                            modal=True,
                        )
                        page.dialog = dlg
                        dlg.open = True
                    except Exception:
                        pass
                except Exception as ex:
                    try:
                        set_status(f"Erro ao gerar QR: {ex}")
                    except Exception:
                        pass
                finally:
                    progress_ring.visible = False
                    try:
                        page.update()
                    except Exception:
                        pass

            threading.Thread(target=_work, daemon=True).start()
        except Exception as ex:
            set_status(f"Erro ao gerar QR: {ex}")

    # Avisar sobre criptografia ausente
    if not os.environ.get("PIX_FERNET_KEY"):
        set_status(
            "Atenção: PIX_FERNET_KEY ausente — chave será armazenada em texto claro."
        )

    def on_file_picker_result(e: ft.FilePickerResultEvent):
        try:
            if not e.files:
                return
            f = e.files[0]
            # ler arquivo local
            try:
                with open(f.path, "rb") as fh:
                    data = fh.read()
                b64 = base64.b64encode(data).decode("ascii")
                state["qr_image"] = b64
                qr_preview.src_base64 = b64
                qr_container.scale = ft.Scale(1.0)
                qr_container.opacity = 1
                page.update()
            except Exception as ex:
                set_status(f"Erro ao ler arquivo: {ex}")
        except Exception:
            pass

    file_picker.on_result = on_file_picker_result

    # comportamento ao alterar a chave: marcar preview como sujo e limpar imagem
    def on_chave_change(e=None):
        try:
            state["dirty"] = True
            state["qr_image"] = None
            qr_preview.src_base64 = None
            qr_container.opacity = 0
            qr_container.scale = ft.Scale(0.9)
            set_status("Preview desatualizado — clique 'Gerar QR' para atualizar")
            try:
                page.update()
            except Exception:
                pass
        except Exception:
            pass

    chave_field.on_change = on_chave_change

    load_settings()

    # progress indicator junto ao preview
    progress_ring = ft.ProgressRing(width=22, height=22, visible=False)

    upload_row = ft.Row(
        [
            ft.Column(
                [
                    ft.Row([qr_container, progress_ring], spacing=8),
                    ft.Text("QR Preview", size=12),
                ],
                spacing=6,
            ),
            ft.Column(
                [
                    ft.ElevatedButton(
                        "Upload QR (PNG/JPG)",
                        on_click=lambda e: file_picker.pick_files(allow_multiple=False),
                        style=ft.ButtonStyle(padding=6),
                    ),
                    ft.Text("Ou gere dinamicamente com 'Gerar QR'", size=11),
                ],
                spacing=6,
            ),
        ],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
    )

    save_button = ft.ElevatedButton(
        "Salvar",
        on_click=save_settings,
        style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=14, vertical=8)),
    )
    # desabilitar visualmente se não for gerente
    try:
        user_id = page.session.get("user_id") if hasattr(page, "session") else None
        if session and user_id:
            u = session.get(User, user_id)
            if u and getattr(u, "role", None) != "gerente":
                save_button.disabled = True
    except Exception:
        pass

    # container com borda arredondada e padding mais compacto
    content_col = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Configuração do Pix", size=14, weight=ft.FontWeight.BOLD),
                    user_label,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            last_edit_label,
            merchant_field,
            chave_field,
            ft.Row([cpf_field, cidade_field, tipo_dropdown], spacing=10),
            active_switch,
            upload_row,
            ft.Row(
                [
                    ft.Row(
                        [
                            save_button,
                            ft.ElevatedButton(
                                "Gerar QR",
                                on_click=gerar_qr,
                                style=ft.ButtonStyle(
                                    padding=ft.padding.symmetric(
                                        horizontal=12, vertical=8
                                    )
                                ),
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.ElevatedButton(
                        "Fechar",
                        on_click=lambda e: (
                            handle_back(e) if callable(handle_back) else None
                        ),
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
            status_text,
        ],
        spacing=6,
        scroll=ft.ScrollMode.AUTO,
    )

    return ft.View(
        "/gerente/pix_settings",
        appbar=ft.AppBar(
            title=ft.Text("Configurações Pix"),
            bgcolor=ft.Colors.WHITE,
            center_title=False,
        ),
        controls=[
            ft.Container(
                content=content_col,
                padding=ft.padding.only(top=8, left=12, right=12, bottom=6),
                width=440,
                height=320,
                alignment=ft.alignment.top_left,
                bgcolor=ft.Colors.WHITE,
                border_radius=ft.border_radius.all(8),
            )
        ],
    )


def create_pix_settings_modal_content(page: ft.Page, handle_back):
    """Retorna o `ft.Column` usado na view para permitir exibir em modal."""
    try:
        # Algumas rotinas internas podem chamar page.update() ao montar a view.
        # Para evitar erros ('Control must be added to the page first'),
        # temporariamente inibimos page.update() enquanto instanciamos a view.
        orig_update = getattr(page, "update", None)
        try:
            page.update = lambda *a, **k: None
            v = create_pix_settings_view(page, handle_back)
        finally:
            # restaurar
            if orig_update is not None:
                page.update = orig_update

        if v and getattr(v, "controls", None):
            container = v.controls[0]
            # container is ft.Container with .content = ft.Column
            return container.content
    except Exception as ex:
        print(f"[PIX] Erro ao criar conteúdo do modal: {ex}")
    return ft.Column([ft.Text("Erro ao montar o conteúdo do PIX")])
