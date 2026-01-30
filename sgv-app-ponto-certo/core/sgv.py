"""Módulo principal de regras de negócio do sistema (PDV / SGV).

Aqui fica a classe `PDVCore`, responsável por concentrar o acesso
ao banco via SQLAlchemy e implementar a lógica de negócio usada
pelas telas (login, caixa, estoque, fornecedores, financeiro, etc.).
"""

import json
import os
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.db_models import (
    CaixaSchedule,
    CaixaSession,
    Expense,
    Fornecedor,
    ItemVenda,
    MovimentoFinanceiro,
    Produto,
    Receivable,
    User,
    Venda,
)

# Hash de senha com passlib: priorizar pbkdf2_sha256 (mais portátil),
# usar bcrypt apenas se backend estiver funcional.
try:
    from passlib.hash import bcrypt
except Exception:
    bcrypt = None

try:
    from passlib.hash import pbkdf2_sha256
except Exception:
    pbkdf2_sha256 = None


def _hash_password_prefer_portable(password: str) -> str:
    """Gera hash de senha preferindo pbkdf2_sha256 para máxima portabilidade.

    Se pbkdf2 não estiver disponível, tenta bcrypt apenas se o backend
    estiver funcional; caso contrário, retorna texto plano (último recurso).
    """
    # Preferir pbkdf2_sha256
    if pbkdf2_sha256:
        try:
            return pbkdf2_sha256.hash(password)
        except Exception:
            pass

    # Tentar bcrypt somente se importado e funcional
    if bcrypt:
        try:
            # Verificar backend realizando um ciclo hash/verify simples
            test_hash = bcrypt.hash("__test__")
            if bcrypt.verify("__test__", test_hash):
                return bcrypt.hash(password)
        except Exception:
            pass

    # Fallback extremo
    return password


class PDVCore:
    """Classe principal de lógica de negócios para o SGV.

    Responsabilidades principais:
    - Autenticação e gerenciamento de usuários
    - Registro de vendas (PDV) e atualização de estoque
    - Relatórios de vendas e produtos
    - Controle financeiro (despesas/receitas) e sessões de caixa
    - Cadastros e operações com fornecedores
    """

    def __init__(self, session: Session):
        self.session = session
        # Caminho para arquivo simples de configurações persistentes
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self._config_dir = os.path.join(base_dir, "data")
        self._config_file = os.path.join(self._config_dir, "app_config.json")

    # ====================================================================
    # CONFIGURAÇÕES (IMPRESSORA)
    # ====================================================================
    def _read_app_config(self) -> dict:
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception:
            pass
        return {}

    def _write_app_config(self, data: dict) -> None:
        os.makedirs(self._config_dir, exist_ok=True)
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_printer_config(self, printer_name: str, paper_size: str):
        """Persiste nome da impressora e tamanho de papel em arquivo JSON.

        Retorna (True, msg) em sucesso ou (False, msg) em erro.
        """
        try:
            cfg = self._read_app_config()
            cfg.setdefault("printer", {})
            cfg["printer"]["printer_name"] = printer_name
            cfg["printer"]["paper_size"] = paper_size or "80mm"
            self._write_app_config(cfg)
            return True, "Configurações de impressora salvas."
        except Exception as e:
            return False, f"Erro ao salvar configurações: {e}"

    def get_printer_config(self) -> dict:
        """Retorna dict com 'printer_name' e 'paper_size' (com defaults)."""
        cfg = self._read_app_config()
        printer = cfg.get("printer", {})
        return {
            "printer_name": printer.get("printer_name", ""),
            "paper_size": printer.get("paper_size", "80mm"),
        }

    # ====================================================================
    # MÉTODOS DE USUÁRIO
    # ====================================================================

    def authenticate_user(self, username, password):
        """Autentica um usuário a partir de username e senha.

        Suporta hashes gerados com bcrypt, pbkdf2_sha256 e, como
        fallback, senhas em texto plano (para legado). Se encontrar
        senha em texto plano válida, tenta regravar já com hash.
        """
        # Busca usuário pelo username e verifica hash da senha
        user = self.session.query(User).filter_by(username=username).first()
        if not user:
            return None

        stored = getattr(user, "password", "") or ""
        try:
            dbg_prefix = stored[:20]
            print(f"[AUTH] user='{username}' stored_prefix='{dbg_prefix}'")
        except Exception:
            pass
        try:
            # Verifica com bcrypt
            if stored.startswith("$2"):
                try:
                    from passlib.hash import bcrypt as _bcrypt

                    ok = _bcrypt.verify(password, stored)
                    print(f"[AUTH] bcrypt.verify -> {ok}")
                    if ok:
                        return user
                    return None
                except Exception:
                    print("[AUTH] bcrypt verify error; fallback")
                    # Se não conseguir verificar com bcrypt, continuar para outras tentativas
                    pass

            # Verifica com pbkdf2_sha256
            if stored.startswith("$pbkdf2-sha256$"):
                try:
                    from passlib.hash import pbkdf2_sha256 as _pbkdf2

                    ok = _pbkdf2.verify(password, stored)
                    print(f"[AUTH] pbkdf2.verify -> {ok}")
                    if ok:
                        return user
                    return None
                except Exception:
                    print("[AUTH] pbkdf2 verify error; fallback")
                    # Se não conseguir verificar com pbkdf2, continuar para fallback
                    pass

            # Fallback: senha em texto plano (legado)
            if password == stored:
                print("[AUTH] plain text match -> rehash")
                # Re-hash a senha para segurança usando o melhor disponível
                try:
                    user.password = _hash_password_prefer_portable(password)
                    self.session.commit()
                except Exception:
                    self.session.rollback()
                return user
            return None
        except Exception:
            return None

    def get_user_by_id(self, user_id):
        return self.session.query(User).filter_by(id=user_id).first()

    def get_user_by_username(self, username: str):
        """Retorna usuário por username ou None."""
        try:
            return self.session.query(User).filter_by(username=username).first()
        except Exception:
            return None

    def get_all_users(self):
        """Retorna todos os usuários, ordenados por username."""
        self.session.expire_all()
        return self.session.query(User).order_by(User.username).all()

    def update_user_settings(self, user_id, full_name, new_password):
        """Atualiza nome completo e/ou senha de um usuário existente."""
        try:
            user = self.session.query(User).filter_by(id=user_id).first()
            if not user:
                return False, "Usuário não encontrado."

            user.full_name = full_name
            if new_password:
                # Armazenar senha com hash preferindo formato portátil
                user.password = _hash_password_prefer_portable(new_password)

            self.session.commit()
            return True, "Configurações atualizadas com sucesso!"
        except Exception as e:
            self.session.rollback()
            return False, f"Erro ao atualizar: {e}"

    def create_user(
        self, username: str, password: str, role: str, full_name: str = None
    ):
        """Cria um novo usuário no banco.

        Retorna (True, user_obj) em sucesso ou (False, mensagem) em erro.
        Faz validações simples (campos obrigatórios, unicidade) e
        grava a senha com hash, se possível.
        """
        try:
            # Permitir senha vazia para perfis como 'caixa' (auto-login)
            # Exigir apenas username e role
            if not username or not role:
                return False, "Username e role são obrigatórios."

            # Verifica unicidade
            existing = self.session.query(User).filter_by(username=username).first()
            if existing:
                return False, "Nome de usuário já existe."

            # Hash da senha com preferência por formato portátil quando informada.
            # Se senha vazia, armazenar vazio (auto-login para 'user_caixa').
            if password:
                stored_password = _hash_password_prefer_portable(password)
            else:
                stored_password = ""

            user = User(
                username=username,
                password=stored_password,
                role=role,
                full_name=full_name,
            )
            self.session.add(user)
            self.session.commit()
            return True, user
        except Exception as e:
            self.session.rollback()
            return False, f"Erro ao criar usuário: {e}"

    def delete_user(self, user_id: int):
        """Remove um usuário do banco.

        Faz uma proteção extra para não remover o último gerente.
        Retorna (True, mensagem) ou (False, mensagem).
        """
        try:
            user = self.session.query(User).filter_by(id=user_id).first()
            if not user:
                return False, "Usuário não encontrado."

            # Proteção simples: não permitir remover último gerente
            if user.role == "gerente":
                total_gerentes = (
                    self.session.query(User).filter_by(role="gerente").count()
                )
                if total_gerentes <= 1:
                    return False, "Não é permitido remover o último gerente."

            self.session.delete(user)
            self.session.commit()
            return True, "Usuário removido com sucesso."
        except Exception as e:
            self.session.rollback()
            return False, f"Erro ao remover usuário: {e}"

    # ====================================================================
    # MÉTODOS DE VENDA (PDV)
    # ====================================================================

    def buscar_produto(self, codigo_barras):
        """Busca um produto pelo código de barras no banco."""
        return (
            self.session.query(Produto).filter_by(codigo_barras=codigo_barras).first()
        )

    def finalizar_venda(
        self,
        carrinho,
        forma_pagamento,
        valor_pago,
        usuario_id,
        transaction_id=None,
        payment_status=None,
    ):
        """Finaliza uma venda a partir do carrinho usado no PDV.

        - Verifica se o caixa do dia não está fechado
        - Cria registro de `Venda` e seus `ItemVenda`
        - Atualiza estoque de cada produto
        - Calcula troco com base em `valor_pago`
        """
        # Bloquear novas vendas somente se houve fechamento hoje
        # E não existir nenhuma sessão de caixa aberta atualmente.
        try:
            fechado_hoje = self.verificar_status_caixa_hoje()
        except Exception:
            fechado_hoje = False
        try:
            sessao_aberta = self.get_current_open_session(
                usuario_id
            ) or self.get_current_open_session(None)
        except Exception:
            sessao_aberta = None
        if fechado_hoje and not sessao_aberta:
            return (
                False,
                "O caixa já foi FECHADO hoje e não há sessão aberta.",
                0.0,
            )

        total_venda = 0.0
        try:
            # trata caso usuario_id venha None ou usuário não seja encontrado
            usuario = self.get_user_by_id(usuario_id) if usuario_id else None
            usuario_responsavel = usuario.username if usuario is not None else "caixa"

            venda = Venda(
                total=0.0,
                usuario_responsavel=usuario_responsavel,
                forma_pagamento=forma_pagamento,
                valor_pago=valor_pago,
                status="CONCLUIDA",
                transaction_id=transaction_id,
                payment_status=payment_status,
            )
            self.session.add(venda)
            self.session.flush()

            for item in carrinho:
                # Usa first() em vez de one() para não explodir se não existir no banco
                produto = (
                    self.session.query(Produto)
                    .filter_by(codigo_barras=item["cod"])
                    .first()
                )
                qtd = int(item.get("qtd", 0) or 0)
                preco_ui = float(item.get("preco", 0.0) or 0.0)

                if not produto:
                    # Se o produto não existir no banco, criar um registro mínimo
                    try:
                        produto = Produto(
                            codigo_barras=item["cod"],
                            nome=item.get("nome", f"Produto {item['cod']}")
                            or f"Produto {item['cod']}",
                            preco_custo=preco_ui,
                            preco_venda=preco_ui,
                            estoque_atual=0,
                        )
                        self.session.add(produto)
                        self.session.flush()  # obter produto.id
                    except Exception:
                        produto = None

                # Registrar item usando preço do carrinho; se produto foi criado, vincular o id
                item_venda = ItemVenda(
                    venda_id=venda.id,
                    produto_id=(produto.id if produto else None),
                    quantidade=qtd,
                    preco_unitario=preco_ui,
                )
                self.session.add(item_venda)
                total_venda += preco_ui * qtd
                # Se produto criado acima, não atualizamos estoque (mantém 0)
                continue

                if (produto.estoque_atual or 0) < qtd:
                    raise Exception(f"Estoque insuficiente para {produto.nome}")
                produto.estoque_atual = (produto.estoque_atual or 0) - qtd

                item_venda = ItemVenda(
                    venda_id=venda.id,
                    produto_id=produto.id,
                    quantidade=qtd,
                    preco_unitario=produto.preco_venda,
                )
                self.session.add(item_venda)
                total_venda += float(produto.preco_venda) * qtd

            venda.total = total_venda
            self.session.commit()
            troco = max(0.0, valor_pago - total_venda)
            return True, total_venda, troco
        except Exception as e:
            self.session.rollback()
            print(f"[ERRO FINALIZAR_VENDA] {e}")
            return False, str(e), 0.0

    # ====================================================================
    # MÉTODOS DE INVENTÁRIO/PRODUTO
    # ====================================================================

    def cadastrar_ou_atualizar_produto(self, dados_produto):
        """Cadastra um novo produto ou registra entrada de estoque.

        Se o código de barras já existir, atualiza campos e soma quantidade
        ao estoque atual. Caso contrário, cria um novo registro.
        """
        cod = dados_produto["codigo_barras"]
        produto = self.session.query(Produto).filter_by(codigo_barras=cod).first()
        try:
            if produto:
                produto.nome = dados_produto["nome"]
                produto.preco_custo = dados_produto["preco_custo"]
                produto.preco_venda = dados_produto["preco_venda"]
                produto.validade = dados_produto["validade"]
                produto.estoque_atual += dados_produto["quantidade"]
                acao = "atualizado (Entrada de estoque)"
            else:
                produto = Produto(
                    codigo_barras=cod,
                    nome=dados_produto["nome"],
                    preco_custo=dados_produto["preco_custo"],
                    preco_venda=dados_produto["preco_venda"],
                    estoque_atual=dados_produto["quantidade"],
                    validade=dados_produto["validade"],
                )
                self.session.add(produto)
                acao = "cadastrado"

            self.session.commit()
            return True, f"Produto '{produto.nome}' {acao} com sucesso!"
        except Exception as e:
            self.session.rollback()
            if "UNIQUE constraint failed: produtos.codigo_barras" in str(e):
                return False, "Erro: Código de Barras já cadastrado."
            return False, f"Erro ao {acao}: {e}"

    def get_produtos_list(self):
        """Retorna lista de produtos ordenada pelo nome."""
        # Garantir dados frescos antes de consultar
        try:
            self.session.expire_all()
        except Exception:
            pass
        return self.session.query(Produto).order_by(Produto.nome).all()

    def gerar_relatorio_produtos(self):
        """Gera lista com dados resumidos dos produtos.

        Cada item contém estoque, preços e margem de lucro estimada.
        """
        self.session.expire_all()
        produtos = self.session.query(Produto).all()
        relatorio = []
        for p in produtos:
            margem_lucro = p.preco_venda - p.preco_custo if p.preco_custo > 0 else 0
            relatorio.append(
                {
                    "id": p.id,
                    "codigo_barras": p.codigo_barras,
                    "nome": p.nome,
                    "estoque": p.estoque_atual,
                    "custo": p.preco_custo,
                    "venda": p.preco_venda,
                    "margem": margem_lucro,
                }
            )
        return relatorio

    def buscar_vendas_detalhadas(self):
        """Retorna vendas com informações resumidas para relatórios.

        Inclui data formatada, usuário responsável, total, forma de
        pagamento e uma descrição breve (primeiro item).
        """
        self.session.expire_all()
        vendas = self.session.query(Venda).order_by(Venda.data_venda.desc()).all()
        relatorio = []
        for v in vendas:
            if v.itens and v.itens[0].produto:
                primeiro_item_nome = v.itens[0].produto.nome
            else:
                primeiro_item_nome = "Venda Vazia/Não Finalizada"

            usuario_nome = (
                self.session.query(User)
                .filter_by(username=v.usuario_responsavel)
                .first()
            )
            usuario_str = (
                usuario_nome.full_name if usuario_nome else v.usuario_responsavel
            )

            relatorio.append(
                {
                    "id": v.id,
                    "data": v.data_venda.strftime("%d/%m/%Y %H:%M"),
                    "usuario": usuario_str,
                    "total": v.total,
                    "pagamento": v.forma_pagamento,
                    "status": v.status,
                    "descricao_breve": f"Venda {v.id}: {primeiro_item_nome}...",
                }
            )

        return relatorio

    def buscar_vendas_por_intervalo(self, start_dt: datetime, end_dt: datetime):
        """Retorna vendas cujo `data_venda` esteja entre `start_dt` e `end_dt` (inclusive).

        Cada venda retorna um dicionário com chave `itens` contendo lista de itens:
        [{"produto": nome, "quantidade": qtd, "preco_unitario": preco}, ...]
        """
        try:
            self.session.expire_all()
            vendas = (
                self.session.query(Venda)
                .filter(Venda.data_venda >= start_dt, Venda.data_venda <= end_dt)
                .order_by(Venda.data_venda.desc())
                .all()
            )
            relatorio = []
            for v in vendas:
                itens_list = []
                for it in v.itens:
                    produto_obj = getattr(it, "produto", None)
                    nome = getattr(produto_obj, "nome", "<produto>")
                    codigo = getattr(produto_obj, "codigo_barras", None)
                    produto_id = getattr(produto_obj, "id", None)
                    itens_list.append(
                        {
                            "produto": nome,
                            "produto_id": produto_id,
                            "codigo_barras": codigo,
                            "quantidade": it.quantidade,
                            "preco_unitario": it.preco_unitario,
                        }
                    )

                usuario_nome = (
                    self.session.query(User)
                    .filter_by(username=v.usuario_responsavel)
                    .first()
                )
                usuario_str = (
                    usuario_nome.full_name if usuario_nome else v.usuario_responsavel
                )

                relatorio.append(
                    {
                        "id": v.id,
                        "data": v.data_venda.strftime("%d/%m/%Y %H:%M"),
                        "usuario": usuario_str,
                        "total": v.total,
                        "pagamento": v.forma_pagamento,
                        "status": v.status,
                        "descricao_breve": f"Venda {v.id}",
                        "itens": itens_list,
                    }
                )

            print(
                f"[DEBUG] buscar_vendas_por_intervalo retornou {len(relatorio)} vendas para {start_dt} -> {end_dt}"
            )
            return relatorio
        except Exception as ex:
            print(f"Erro em buscar_vendas_por_intervalo: {ex}")
            return []

    def atualizar_preco_produto(
        self, produto_id: int, novo_custo: float, novo_venda: float
    ):
        """Atualiza apenas os preços de um produto existente.

        Compatível com chamadas da tela de Relatório de Produtos.
        Retorna (True, msg) em sucesso, (False, msg) em erro.
        """
        try:
            produto = self.session.query(Produto).filter_by(id=produto_id).first()
            if not produto:
                return False, "Produto não encontrado"
            produto.preco_custo = float(novo_custo or 0)
            produto.preco_venda = float(novo_venda or 0)
            self.session.commit()
            return True, f"Produto '{produto.nome}' atualizado"
        except Exception as e:
            self.session.rollback()
            return False, f"Erro ao atualizar preço: {e}"

    def criar_produto(
        self,
        nome: str,
        codigo_barras: str,
        preco_custo: float,
        preco_venda: float,
        estoque: int = 0,
    ):
        """Cria um novo produto com os campos essenciais.

        Compatível com importação em Relatório de Produtos.
        Retorna (True, Produto) em sucesso, (False, msg) em erro.
        """
        try:
            produto = Produto(
                nome=nome.strip(),
                codigo_barras=codigo_barras.strip() if codigo_barras else None,
                preco_custo=float(preco_custo or 0),
                preco_venda=float(preco_venda or 0),
                estoque_atual=int(estoque or 0),
            )
            self.session.add(produto)
            self.session.commit()
            return True, produto
        except Exception as e:
            self.session.rollback()
            return False, f"Erro ao criar produto: {e}"

    def estornar_venda(self, venda_id: int, usuario: str = None):
        """Marca uma venda como ESTORNADA e repõe o estoque dos produtos.

        Retorna (True, mensagem) em sucesso ou (False, mensagem) em erro.
        """
        try:
            venda = self.session.query(Venda).filter_by(id=venda_id).first()
            if not venda:
                return False, "Venda não encontrada."
            if venda.status == "ESTORNADA":
                return False, "Venda já estornada."

            # repor estoque
            for it in venda.itens:
                try:
                    produto = (
                        self.session.query(Produto).filter_by(id=it.produto_id).first()
                    )
                    if produto:
                        produto.estoque_atual = (produto.estoque_atual or 0) + (
                            it.quantidade or 0
                        )
                except Exception:
                    # continua mesmo que um item falhe
                    pass

            venda.status = "ESTORNADA"
            self.session.commit()

            # Registrar devoluções em JSON para exibição na tela de Devoluções
            try:
                from estoque.devolucoes import registrar_devolucoes_por_venda

                ok_reg = registrar_devolucoes_por_venda(
                    self, venda.id, motivo=f"Estorno da venda #{venda.id}"
                )
                if not ok_reg:
                    print(
                        f"[CORE] Aviso: estorno #{venda.id} registrado no banco, mas falhou ao salvar em devolucoes.json"
                    )
            except Exception as ex_reg:
                print(f"[CORE] Erro ao registrar devoluções JSON: {ex_reg}")

            return True, "Venda estornada com sucesso."
        except Exception as ex:
            self.session.rollback()
            print(f"Erro em estornar_venda: {ex}")
            return False, str(ex)

    def estornar_item(self, venda_id: int, item_id: int, usuario: str = None):
        """Estorna um item específico de uma venda: repõe estoque, atualiza total e registra devolução.

        Retorna (True, mensagem) ou (False, mensagem).
        """
        try:
            venda = self.session.query(Venda).filter_by(id=venda_id).first()
            if not venda:
                return False, "Venda não encontrada."
            if venda.status == "ESTORNADA":
                return False, "Venda já estornada."

            # Tentar localizar item por ItemVenda.id primeiro; se não, por produto_id dentro da venda
            item = (
                self.session.query(ItemVenda)
                .filter_by(id=item_id, venda_id=venda_id)
                .first()
            )
            if not item:
                # procurar por produto_id (caso o item_id passado seja produto_id)
                try:
                    item = (
                        self.session.query(ItemVenda)
                        .filter_by(venda_id=venda_id, produto_id=item_id)
                        .order_by(ItemVenda.id.asc())
                        .first()
                    )
                except Exception:
                    item = None

            if not item:
                return False, "Item não encontrado na venda."

            # Registrar devolução do item em JSON antes de remover a linha do banco
            try:
                from estoque.devolucoes import registrar_devolucao_item

                registrado = registrar_devolucao_item(
                    self,
                    venda_id,
                    int(item.id),
                    motivo=f"Estorno parcial da venda #{venda_id}",
                )
                if not registrado:
                    print(
                        f"[CORE] Aviso: estorno parcial #{venda_id}/{item.id} registrado no banco, mas falhou ao salvar em devolucoes.json"
                    )
            except Exception as ex_reg:
                print(f"[CORE] Erro ao registrar estorno parcial em JSON: {ex_reg}")

            # atualizar estoque
            try:
                produto = (
                    self.session.query(Produto).filter_by(id=item.produto_id).first()
                )
                if produto:
                    produto.estoque_atual = (produto.estoque_atual or 0) + (
                        item.quantidade or 0
                    )
            except Exception:
                pass

            # ajustar total da venda e remover o item
            try:
                deduz = (item.preco_unitario or 0.0) * (item.quantidade or 0)
                venda.total = float((venda.total or 0.0) - deduz)
                # remover o item
                self.session.delete(item)
            except Exception as ex_calc:
                print(f"Erro ao ajustar venda/item: {ex_calc}")

            # se após remoção não houver itens, marcar venda como ESTORNADA
            remaining = list(getattr(venda, "itens", []) or [])
            if len(remaining) == 0:
                venda.status = "ESTORNADA"

            self.session.commit()

            return True, "Item estornado com sucesso."
        except Exception as ex:
            try:
                self.session.rollback()
            except Exception:
                pass
            print(f"Erro em estornar_item: {ex}")
            return False, str(ex)

    # ====================================================================
    # MÉTODOS FINANCEIROS/CAIXA (EXISTENTES + CORRIGIDOS)
    # ====================================================================

    def verificar_status_caixa_hoje(self):
        """Retorna True se já existir um fechamento de caixa no dia atual."""
        hoje = date.today()
        fechamento_existente = (
            self.session.query(MovimentoFinanceiro)
            .filter(
                func.date(MovimentoFinanceiro.data) == hoje,
                MovimentoFinanceiro.tipo == "FECHAMENTO_CAIXA",
            )
            .first()
        )
        return fechamento_existente is not None

    def registrar_despesa(self, user, descricao, valor):
        """Registra despesa rápida (uso interno, não é a tela Financeiro)."""
        if valor <= 0:
            return False, "O valor da despesa deve ser positivo."
        try:
            despesa = MovimentoFinanceiro(
                descricao=descricao,
                valor=valor,
                tipo="DESPESA",
                usuario_responsavel=user,
            )
            self.session.add(despesa)
            self.session.commit()
            return True, f"Despesa de R$ {valor:.2f} registrada: {descricao}"
        except Exception as e:
            self.session.rollback()
            return False, f"Erro ao registrar despesa: {e}"

    # ====================================================================
    # MÉTODOS DE CAIXASESSION (EXISTENTES - OK)
    # ====================================================================

    def get_current_open_session(self, user_id: int = None):
        """Obtém a sessão de caixa aberta para o usuário (se houver)."""
        query = self.session.query(CaixaSession).filter(CaixaSession.status == "Open")
        if user_id:
            query = query.filter(CaixaSession.user_id == user_id)
        return query.first()

    def get_all_closed_sessions(self):
        """Retorna todas as sessões de caixa já fechadas."""
        return (
            self.session.query(CaixaSession)
            .filter(CaixaSession.status == "Closed")
            .order_by(CaixaSession.closing_time.desc())
            .all()
        )

    # ====================================================================
    # NOVOS MÉTODOS FINANCEIROS PARA A TELA FINANCEIRO
    # ====================================================================

    def open_new_caixa(self, user_id: int, opening_balance: float):
        """Abre um novo caixa para o usuário informado."""
        try:
            new_session = CaixaSession(
                user_id=user_id,
                opening_balance=opening_balance,
                opening_time=datetime.now(),
                status="Open",
            )
            self.session.add(new_session)
            self.session.commit()
            print(f"✅ CaixaSession criado: ID={new_session.id}, User={user_id}")
            return new_session
        except Exception as e:
            self.session.rollback()
            print(f"❌ ERRO ao abrir caixa: {str(e)}")
            raise e

    def close_caixa_session(
        self,
        session_id: int,
        closing_balance_system: float,
        closing_balance_actual: float,
        notes: str = None,
    ):
        """Fecha e audita uma sessão de caixa existente."""
        try:
            session_to_close = self.session.query(CaixaSession).get(session_id)
            if not session_to_close or session_to_close.status == "Closed":
                return None

            session_to_close.closing_time = datetime.now()
            session_to_close.closing_balance_system = closing_balance_system
            session_to_close.closing_balance_actual = closing_balance_actual
            session_to_close.status = "Closed"
            session_to_close.notes = notes

            self.session.commit()
            print(f"✅ CaixaSession fechado: ID={session_id}")
            return session_to_close
        except Exception as e:
            self.session.rollback()
            print(f"❌ ERRO ao fechar caixa: {str(e)}")
            raise e

    def create_expense(
        self, descricao: str, valor: float, vencimento: str, categoria: str
    ):
        """Cria uma despesa para ser exibida na tela Financeiro."""
        try:
            expense = Expense(
                descricao=descricao,
                valor=valor,
                vencimento=vencimento,
                categoria=categoria,
                status="Pendente",
                data_cadastro=datetime.now(),
            )
            self.session.add(expense)
            self.session.commit()
            print(f"✅ Expense criado: ID={expense.id}")
            return True, "Despesa criada com sucesso!"
        except Exception as e:
            self.session.rollback()
            print(f"❌ ERRO ao criar despesa: {str(e)}")
            return False, f"Erro: {str(e)}"

    def create_receivable(
        self, descricao: str, valor: float, vencimento: str, origem: str
    ):
        """Cria uma receita (recebível) para a tela Financeiro."""
        try:
            receivable = Receivable(
                descricao=descricao,
                valor=valor,
                vencimento=vencimento,
                origem=origem,
                status="Pendente",
                data_cadastro=datetime.now(),
            )
            self.session.add(receivable)
            self.session.commit()
            print(f"✅ Receivable criado: ID={receivable.id}")
            return True, "Receita criada com sucesso!"
        except Exception as e:
            self.session.rollback()
            print(f"❌ ERRO ao criar receita: {str(e)}")
            return False, f"Erro: {str(e)}"

    def mark_expense_as_paid(self, expense_id: int):
        """Marca uma despesa como paga e registra data de pagamento."""
        try:
            expense = self.session.query(Expense).get(expense_id)
            if expense:
                expense.status = "Pago"
                expense.data_pagamento = datetime.now()
                self.session.commit()
                print(f"✅ Expense marcado como pago: ID={expense_id}")
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"❌ ERRO ao marcar despesa: {str(e)}")
            return False

    def mark_expense_as_unpaid(self, expense_id: int):
        """Desmarca uma despesa como paga (volta para Pendente)."""
        try:
            expense = self.session.query(Expense).get(expense_id)
            if expense:
                expense.status = "Pendente"
                expense.data_pagamento = None
                self.session.commit()
                print(f"✅ Expense desmarcado como pago: ID={expense_id}")
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"❌ ERRO ao desmarcar despesa: {str(e)}")
            return False

    def mark_receivable_as_paid(self, receivable_id: int):
        """Marca um recebível como recebido e registra data de recebimento."""
        try:
            receivable = self.session.query(Receivable).get(receivable_id)
            if receivable:
                receivable.status = "Recebido"
                receivable.data_recebimento = datetime.now()
                self.session.commit()
                print(f"✅ Receivable marcado como recebido: ID={receivable_id}")
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"❌ ERRO ao marcar recebível: {str(e)}")
            return False

    def mark_receivable_as_unpaid(self, receivable_id: int):
        """Desmarca um recebível como recebido (volta para Pendente)."""
        try:
            receivable = self.session.query(Receivable).get(receivable_id)
            if receivable:
                receivable.status = "Pendente"
                receivable.data_recebimento = None
                self.session.commit()
                print(f"✅ Receivable desmarcado como recebido: ID={receivable_id}")
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"❌ ERRO ao desmarcar recebível: {str(e)}")
            return False

    def get_pending_expenses(self):
        """Busca todas as despesas com status "Pendente"."""
        try:
            return (
                self.session.query(Expense)
                .filter_by(status="Pendente")
                .order_by(Expense.vencimento)
                .all()
            )
        except Exception as e:
            print(f"❌ ERRO ao buscar despesas: {str(e)}")
            return []

    def get_pending_receivables(self):
        """Busca todos os recebíveis com status "Pendente"."""
        try:
            return (
                self.session.query(Receivable)
                .filter_by(status="Pendente")
                .order_by(Receivable.vencimento)
                .all()
            )
        except Exception as e:
            print(f"❌ ERRO ao buscar recebíveis: {str(e)}")
            return []

    def get_expenses_by_status(self, status_filter: str):
        """Busca despesas filtradas por status. 'Atrasado' busca vencidas e não pagas."""
        try:
            today = datetime.now().date()

            if status_filter == "Todos":
                return self.session.query(Expense).order_by(Expense.vencimento).all()
            elif status_filter == "Atrasado":
                # Atrasado = vencimento no passado E status != Pago
                return (
                    self.session.query(Expense)
                    .filter(Expense.vencimento < today, Expense.status != "Pago")
                    .order_by(Expense.vencimento)
                    .all()
                )
            else:
                # Pago, Pendente, etc
                return (
                    self.session.query(Expense)
                    .filter_by(status=status_filter)
                    .order_by(Expense.vencimento)
                    .all()
                )
        except Exception as e:
            print(f"❌ ERRO ao filtrar despesas: {str(e)}")
            return []

    def get_receivables_by_status(self, status_filter: str):
        """Busca recebíveis filtrados por status. 'Atrasado' busca vencidos e não recebidos."""
        try:
            today = datetime.now().date()

            if status_filter == "Todos":
                return (
                    self.session.query(Receivable).order_by(Receivable.vencimento).all()
                )
            elif status_filter == "Atrasado":
                # Atrasado = vencimento no passado E status != Recebido
                return (
                    self.session.query(Receivable)
                    .filter(
                        Receivable.vencimento < today, Receivable.status != "Recebido"
                    )
                    .order_by(Receivable.vencimento)
                    .all()
                )
            else:
                # Recebido, Pendente, etc
                return (
                    self.session.query(Receivable)
                    .filter_by(status=status_filter)
                    .order_by(Receivable.vencimento)
                    .all()
                )
        except Exception as e:
            print(f"❌ ERRO ao filtrar recebíveis: {str(e)}")
            return []

    # ====================================================================
    # MÉTODO DASHBOARD FINANCEIRO
    # ====================================================================

    def get_dashboard_data(self):
        """Busca dados reais do dashboard do banco de dados"""
        try:
            # Saldo atual: considerar receitas recebidas + vendas concluídas - despesas pagas
            # (o objetivo é que o 'Saldo Atual' reflita os itens vendidos)
            total_receitas = (
                self.session.query(func.sum(Receivable.valor))
                .filter(Receivable.status == "Recebido")
                .scalar()
                or 0
            )
            total_despesas = (
                self.session.query(func.sum(Expense.valor))
                .filter(Expense.status == "Pago")
                .scalar()
                or 0
            )
            # Soma total de vendas concluídas (considera o campo Venda.total)
            total_vendas = (
                self.session.query(func.sum(Venda.total))
                .filter(Venda.status == "CONCLUIDA")
                .scalar()
                or 0
            )

            saldo_atual = (
                (total_receitas or 0) + (total_vendas or 0) - (total_despesas or 0)
            )

            # Do mês atual
            mes_atual = datetime.now().month
            ano_atual = datetime.now().year

            receitas_mes = (
                self.session.query(func.sum(Receivable.valor))
                .filter(
                    Receivable.status == "Recebido",
                    func.extract("month", Receivable.data_recebimento) == mes_atual,
                    func.extract("year", Receivable.data_recebimento) == ano_atual,
                )
                .scalar()
                or 0
            )

            despesas_mes = (
                self.session.query(func.sum(Expense.valor))
                .filter(
                    Expense.status == "Pago",
                    func.extract("month", Expense.data_pagamento) == mes_atual,
                    func.extract("year", Expense.data_pagamento) == ano_atual,
                )
                .scalar()
                or 0
            )

            return {
                "saldo_atual": float(saldo_atual),
                "receitas_mes": float(receitas_mes),
                "despesas_mes": float(despesas_mes),
                "lucro_mes": float(receitas_mes - despesas_mes),
            }
        except Exception as ex:
            print(f"❌ Erro em get_dashboard_data: {ex}")
            # Retorna valores padrão se der erro
            return {
                "saldo_atual": 0.0,
                "receitas_mes": 0.0,
                "despesas_mes": 0.0,
                "lucro_mes": 0.0,
            }

    # ====================================================================
    # MÉTODOS DE FORNECEDOR
    # ====================================================================

    def get_all_fornecedores(self):
        try:
            self.session.expire_all()
            return (
                self.session.query(Fornecedor)
                .order_by(Fornecedor.nome_razao_social)
                .all()
            )
        except Exception as e:
            try:
                logger = getattr(self, "logger", None)
                if logger:
                    logger.exception("Erro em get_all_fornecedores: %s", e)
            except Exception:
                pass
            return []

    def get_fornecedor_by_id(self, fornecedor_id):
        try:
            return self.session.query(Fornecedor).filter_by(id=fornecedor_id).first()
        except Exception:
            return None

    def get_produtos_by_fornecedor(self, fornecedor_id):
        try:
            return (
                self.session.query(Produto)
                .filter_by(fornecedor_id=fornecedor_id)
                .order_by(Produto.nome)
                .all()
            )
        except Exception:
            return []

    def get_all_produtos(self):
        # compatibilidade com código que espera esse método
        return self.get_produtos_list()

    def get_historico_compras_fornecedor(self, fornecedor_id):
        """Retorna lista de objetos com atributos 'data' e 'valor_total' para o histórico."""
        from types import SimpleNamespace

        try:
            # Buscar vendas que possuam itens cujo produto pertence ao fornecedor
            vendas = (
                self.session.query(Venda)
                .join(ItemVenda, ItemVenda.venda_id == Venda.id)
                .join(Produto, Produto.id == ItemVenda.produto_id)
                .filter(Produto.fornecedor_id == fornecedor_id)
                .order_by(Venda.data_venda.desc())
                .all()
            )

            historico = []
            for v in vendas:
                valor_total = 0.0
                for it in v.itens:
                    # somente soma itens do fornecedor
                    if getattr(it.produto, "fornecedor_id", None) == fornecedor_id:
                        valor_total += it.quantidade * it.preco_unitario
                historico.append(
                    SimpleNamespace(data=v.data_venda, valor_total=valor_total)
                )

            return historico
        except Exception:
            return []

    def excluir_fornecedor(self, fornecedor_id):
        try:
            fornecedor = (
                self.session.query(Fornecedor).filter_by(id=fornecedor_id).first()
            )
            if not fornecedor:
                return False, "Fornecedor não encontrado."

            # Verifica produtos vinculados
            if fornecedor.produtos and len(fornecedor.produtos) > 0:
                return False, "FOREIGN KEY: fornecedor tem produtos vinculados"

            self.session.delete(fornecedor)
            self.session.commit()
            return (
                True,
                f"Fornecedor '{getattr(fornecedor, 'nome_razao_social', '')}' excluído com sucesso!",
            )
        except Exception as e:
            self.session.rollback()
            return False, str(e)

    def cadastrar_ou_atualizar_fornecedor(self, dados, fornecedor_id=None):
        try:
            if fornecedor_id:
                fornecedor = (
                    self.session.query(Fornecedor).filter_by(id=fornecedor_id).first()
                )
                if not fornecedor:
                    return False, "Fornecedor não encontrado."
                acao = "atualizado"
            else:
                fornecedor = Fornecedor()
                self.session.add(fornecedor)
                acao = "cadastrado"

            fornecedor.nome_razao_social = dados["nome_razao_social"]
            fornecedor.cnpj_cpf = dados["cnpj_cpf"]
            fornecedor.contato = dados["contato"]
            fornecedor.condicao_pagamento = dados["condicao_pagamento"]
            fornecedor.prazo_entrega_medio = dados["prazo_entrega_medio"]
            fornecedor.status = dados["status"]
            # Campos opcionais: avaliação e observações internas
            try:
                if "avaliacao_interna" in dados:
                    fornecedor.avaliacao_interna = dados.get("avaliacao_interna")
            except Exception:
                pass
            try:
                if "observacoes_internas" in dados:
                    fornecedor.observacoes_internas = dados.get("observacoes_internas")
            except Exception:
                pass

            self.session.commit()
            return (
                True,
                f"Fornecedor '{fornecedor.nome_razao_social}' {acao} com sucesso!",
            )
        except Exception as e:
            self.session.rollback()
            if "UNIQUE constraint failed: fornecedores.cnpj_cpf" in str(e):
                return False, "Erro: O CNPJ/CPF informado já está cadastrado."
            return False, f"Erro ao salvar fornecedor: {e}"

    def delete_expense(self, expense_id: int) -> bool:
        """Deleta uma despesa do banco de dados."""
        try:
            expense = self.session.get(Expense, expense_id)
            if not expense:
                return False
            self.session.delete(expense)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False

    def delete_receivable(self, receivable_id: int) -> bool:
        """Deleta uma receita do banco de dados."""
        try:
            receivable = self.session.get(Receivable, receivable_id)
            if not receivable:
                return False
            self.session.delete(receivable)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False

    def pay_expense_partial(self, expense_id: int, valor_pago: float) -> bool:
        """Registra um pagamento parcial de despesa. Se sobrar saldo, cria novo registro pendente."""
        try:
            expense = self.session.get(Expense, expense_id)
            if not expense:
                return False

            # Se pagou tudo, marca como pago
            if valor_pago >= expense.valor:
                expense.status = "Pago"
                expense.data_pagamento = datetime.now()
                self.session.commit()
                return True

            # Se pagou parcial
            if valor_pago > 0:
                # Marcar como pago
                expense.status = "Pago"
                expense.data_pagamento = datetime.now()

                # Criar novo registro com o saldo restante
                saldo = expense.valor - valor_pago
                new_expense = Expense(
                    descricao=f"{expense.descricao} (Saldo Restante)",
                    valor=saldo,
                    status="Pendente",
                    vencimento=expense.vencimento,
                    categoria=expense.categoria,
                )
                self.session.add(new_expense)
                self.session.commit()
                return True

            return False
        except Exception as e:
            self.session.rollback()
            print(f"Erro ao registrar pagamento parcial de despesa: {e}")
            return False

    def receive_receivable_partial(
        self, receivable_id: int, valor_recebido: float
    ) -> bool:
        """Registra um recebimento parcial. Se sobrar saldo, cria novo registro pendente."""
        try:
            receivable = self.session.get(Receivable, receivable_id)
            if not receivable:
                return False

            # Se recebeu tudo, marca como recebido
            if valor_recebido >= receivable.valor:
                receivable.status = "Recebido"
                receivable.data_recebimento = datetime.now()
                self.session.commit()
                return True

            # Se recebeu parcial
            if valor_recebido > 0:
                # Marcar como recebido
                receivable.status = "Recebido"
                receivable.data_recebimento = datetime.now()

                # Criar novo registro com o saldo restante
                saldo = receivable.valor - valor_recebido
                new_receivable = Receivable(
                    descricao=f"{receivable.descricao} (Saldo Restante)",
                    valor=saldo,
                    status="Pendente",
                    vencimento=receivable.vencimento,
                    origem=receivable.origem,
                )
                self.session.add(new_receivable)
                self.session.commit()
                return True

            return False
        except Exception as e:
            self.session.rollback()
            print(f"Erro ao registrar recebimento parcial: {e}")
            return False

    # ====================================================================
    # MÉTODOS DE AGENDAMENTO DE CAIXA
    # ====================================================================

    def schedule_caixa_closure(
        self,
        data_vigencia: str,
        hora_fechamento: str,
        hora_reabertura: str,
        usuario: str,
        notas: str = "",
    ) -> bool:
        """Cria um agendamento de fechamento/reabertura automática do caixa.

        Args:
            data_vigencia: formato 'dd/mm/aaaa'
            hora_fechamento: formato 'HH:MM' (ex: '20:30')
            hora_reabertura: formato 'HH:MM' (ex: '07:00')
            usuario: username do gerente que criou
            notas: observações opcionais

        Returns:
            True se agendamento foi criado/atualizado com sucesso
        """
        try:
            # Verifica se já existe agendamento para este dia
            existing = (
                self.session.query(CaixaSchedule)
                .filter_by(data_vigencia=data_vigencia)
                .first()
            )

            if existing:
                # Atualiza o existente
                existing.hora_fechamento = hora_fechamento
                existing.hora_reabertura = hora_reabertura
                existing.status = "Ativo"
                existing.criado_por = usuario
                existing.notas = notas
                existing.caixa_foi_fechado = False
                existing.caixa_foi_reaberto = False
            else:
                # Cria novo agendamento
                novo_agendamento = CaixaSchedule(
                    data_vigencia=data_vigencia,
                    hora_fechamento=hora_fechamento,
                    hora_reabertura=hora_reabertura,
                    status="Ativo",
                    criado_por=usuario,
                    notas=notas,
                    caixa_foi_fechado=False,
                    caixa_foi_reaberto=False,
                )
                self.session.add(novo_agendamento)

            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            print(f"Erro ao agendar fechamento de caixa: {e}")
            return False

    def get_caixa_schedule(self, data_vigencia: str = None) -> CaixaSchedule:
        """Retorna o agendamento de caixa para a data especificada (ou hoje).

        Args:
            data_vigencia: formato 'dd/mm/aaaa'. Se None, usa data de hoje

        Returns:
            CaixaSchedule object ou None se não existe
        """
        if data_vigencia is None:
            from datetime import datetime

            data_vigencia = datetime.now().strftime("%d/%m/%Y")

        try:
            return (
                self.session.query(CaixaSchedule)
                .filter_by(data_vigencia=data_vigencia)
                .first()
            )
        except Exception as e:
            print(f"Erro ao buscar agendamento: {e}")
            return None

    def get_caixa_schedule_by_id(self, schedule_id: int) -> CaixaSchedule:
        """Retorna o agendamento de caixa pelo ID.

        Args:
            schedule_id: ID do agendamento

        Returns:
            CaixaSchedule object ou None se não existe
        """
        try:
            return self.session.query(CaixaSchedule).get(schedule_id)
        except Exception as e:
            print(f"Erro ao buscar agendamento por ID: {e}")
            return None

    def override_caixa_schedule(self, schedule_id: int, novo_status: str) -> bool:
        """Permite ao gerente pausar, retomar ou cancelar um agendamento.

        Args:
            schedule_id: ID do agendamento
            novo_status: 'Ativo', 'Pausado' ou 'Cancelado'

        Returns:
            True se sucesso
        """
        try:
            schedule = self.session.query(CaixaSchedule).get(schedule_id)
            if not schedule:
                return False

            schedule.status = novo_status
            schedule.override_count += 1
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            print(f"Erro ao fazer override do agendamento: {e}")
            return False

    def check_and_apply_schedule(self) -> dict:
        """Verifica se é hora de fechar ou reabrir o caixa automaticamente.

        Deve ser chamado periodicamente (a cada minuto, por exemplo).

        Returns:
            dict com status da verificação:
            {
                'acao': 'nenhuma' | 'fechamento' | 'reabertura',
                'aplicado': True/False,
                'mensagem': str
            }
        """
        from datetime import datetime

        try:
            data_hoje = datetime.now().strftime("%d/%m/%Y")
            hora_agora = datetime.now().strftime("%H:%M")

            schedule = self.get_caixa_schedule(data_hoje)

            if not schedule or schedule.status != "Ativo":
                return {
                    "acao": "nenhuma",
                    "aplicado": False,
                    "mensagem": "Nenhum agendamento ativo para hoje",
                }

            # Verifica se é hora de fechar
            if (
                not schedule.caixa_foi_fechado
                and hora_agora >= schedule.hora_fechamento
            ):
                schedule.caixa_foi_fechado = True
                self.session.commit()
                return {
                    "acao": "fechamento",
                    "aplicado": True,
                    "mensagem": f"Caixa deve ser fechado às {schedule.hora_fechamento}",
                }

            # Verifica se é hora de reabrir
            if (
                not schedule.caixa_foi_reaberto
                and hora_agora >= schedule.hora_reabertura
            ):
                schedule.caixa_foi_reaberto = True
                self.session.commit()
                return {
                    "acao": "reabertura",
                    "aplicado": True,
                    "mensagem": f"Caixa deve ser reaberto às {schedule.hora_reabertura}",
                }

            return {
                "acao": "nenhuma",
                "aplicado": False,
                "mensagem": "Aguardando horários do agendamento",
            }
        except Exception as e:
            print(f"Erro ao verificar agendamento: {e}")
            return {
                "acao": "nenhuma",
                "aplicado": False,
                "mensagem": f"Erro: {str(e)}",
            }

    def get_proxima_fechamento_programado(self) -> dict:
        """Retorna informações do próximo fechamento programado.

        Returns:
            dict com id, data_vigencia, hora_fechamento, hora_reabertura, status
            ou dict vazio se nenhum agendamento
        """
        try:
            from datetime import datetime

            data_hoje = datetime.now().strftime("%d/%m/%Y")
            schedule = self.get_caixa_schedule(data_hoje)

            if schedule:
                return {
                    "id": schedule.id,
                    "data_vigencia": schedule.data_vigencia,
                    "hora_fechamento": schedule.hora_fechamento,
                    "hora_reabertura": schedule.hora_reabertura,
                    "status": schedule.status,
                    "caixa_foi_fechado": schedule.caixa_foi_fechado,
                    "caixa_foi_reaberto": schedule.caixa_foi_reaberto,
                }
            return {}
        except Exception as e:
            print(f"Erro ao buscar próximo fechamento: {e}")
            return {}
