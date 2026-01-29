
# Mercadinho Ponto Certo (SGV em Flet)

Projeto Integrador desenvolvido no programa Bolsa Futuro Digital (Aponti), aplicado a um cenário real de mercadinho para gestão de vendas e estoque.

Aplicação de SGV construída com Flet e SQLite para operação de caixa, relatórios, devoluções/trocas e integração básica com impressoras térmicas.

## Pré-requisitos

- Windows 10/11 ou Linux (Debian/Ubuntu base)
- Python 3.12 ou 3.13
- Drivers de impressora instalados (Windows) ou CUPS/ESC/POS (Linux)

## Instalação

### Windows

1. Crie e ative um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

1. Instale as dependências principais:

```powershell
pip install -r requirements.txt
```

1. (Opcional) Recursos extras:

```powershell
# Excel e câmera
pip install pandas openpyxl opencv-python
```

# 🟢 Início Rápido (Windows)

Requisitos:

- Python 3.12/3.13 instalado (no PATH)
- Internet para instalar dependências
- Permissões do PowerShell para scripts

Como rodar:

1. Abra a pasta do projeto no VS Code
2. No terminal PowerShell, execute:

  ```powershell
  .\setup.ps1
  ```

- Para usar uv: `.\setup.ps1 -UseUv`

- Para não iniciar o app após instalar: `.\setup.ps1 -SkipRun`

O que o script faz (Windows: `setup.ps1` / Linux/macOS: `setup.sh`):

- Cria/ativa o ambiente virtual (`.venv`) e instala as dependências de `requirements.txt`.
- Garante pastas necessárias: `assets`, `data`, `exports`.
- Cria um arquivo `.env` com `DATABASE_URL=sqlite:///data/mercadinho.db` se não existir.
- Aplica migrações Alembic (`alembic upgrade head`) quando aplicável.
- Limpa caches (`__pycache__`, `.pyc`) e outros temporários.
- Inicia a aplicação `app.py` (a menos que seja usada a opção para não iniciar).

Observação sobre `setup.sh` (Linux/macOS): além das ações acima, o `setup.sh` também:

- Atualiza `pip`, `setuptools` e `wheel` no venv antes de instalar pacotes.
- Tenta inicializar o banco local chamando `models.db_models.init_db()` quando disponível.
- Aceita as opções `--skip-run` (preparar sem iniciar) e `--python /caminho/para/python`.

Verificação rápida após executar (`setup.sh` ou `setup.ps1`):

```bash
ls -la .venv data exports        # confirma criação de pastas/venv
.venv/bin/python -m pip show flet # confirma instalação de dependência principal
test -f data/mercadinho.db && echo "DB OK" || echo "DB ausente"
```

Bloqueios comuns: veja a seção "PowerShell: Política de execução e erros comuns" mais abaixo para instruções.

Observações:

- SmartScreen/antivírus podem alertar — permita a execução conforme orientações do README.
- Impressão e câmera exigem drivers/permissões; veja “Impressão” e “Dicas” no README.
- Em Linux, use as instruções específicas do README (setup.ps1 é apenas para Windows/PowerShell).


### Linux (Debian/Ubuntu)

1. Dependências de sistema (para câmera/USB/pyzbar):

```bash
sudo apt update
sudo apt install -y libzbar0 libusb-1.0-0 libgl1
```

1. Crie e ative o ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

1. Instale as dependências principais:

```bash
pip install -r requirements.txt
```

1. (Opcional) Recursos extras:

```bash
pip install pandas openpyxl opencv-python
```

## Como executar

- Execução direta pelo Python (Windows):

```powershell
python app.py
```

- Task integrada do VS Code: “Run App (Flet)” já está configurada para chamar [app.py](app.py).

- Execução direta pelo Python (Linux):

```bash
source .venv/bin/activate
python app.py
```

## Banco de dados e migrações

- Banco padrão: arquivo SQLite [mercadinho.db](mercadinho.db) na raiz.
- Migrações Alembic: estrutura em [alembic.ini](alembic.ini) e pasta [alembic/](alembic/).
- Para aplicar migrações:

```powershell
alembic upgrade head
```

## Login e perfis

- Caixa 1: acesso rápido no login (pode estar sem senha, conforme seed local).
- Gerente 2: senha padrão: root
- Estoque 3: senha padrão: estoque123
- Gerente: se necessário, use os scripts em [scripts/](scripts/) para restaurar ou configurar senha (ex.: `restore_gerente.py`).

## Atalhos e fluxo do Caixa

- Finalizar venda: F12 – exibe o cupom.
- ESC (comportamento por perfil): Gerente: volta ao Painel do Gerente.
- Na conta do Caixa sessão de login aberta:
 Consultar preço (F5): mostra quantidade real de estoque com fallback para dados do Estoque.
 Trocar (F7): Realiza a troca do produto por outro produto.
 Estornar (F6): Cancela uma venda já finalizada.

## Relatórios e exportação

- Relatórios de Produtos: lista unificada com base na tela de Estoque; exporta a mesma visão.
- Devoluções: exporta PDF/CSV; colunas ajustadas e caracteres ASCII para evitar erros de fonte.
- Diretório de exportação: [exports/](exports/) (automaticamente resolvido e aberto após exportações).

## Impressão

- Cupom fiscal simples via PDF (FPDF) ou comandos ESC/POS.
- Windows RAW printing: usa `win32print` (PyWin32). Certifique-se de que a impressora padrão está definida.
- Linux: utilize `python-escpos` (USB/Serial/Network) ou CUPS; `win32print` não está disponível.
- ESC/POS: suporte básico via `python-escpos` (USB/Serial/Network) e [utils/cupom.py](utils/cupom.py).

## Empacotar em executável (Windows)

Com o ambiente virtual ativo e ícone em [assets/Mercadinho_Ponto_Certo.ico](assets/Mercadinho_Ponto_Certo.ico):

```powershell
.\.venv\Scripts\flet.exe pack app.py `
 -n "Mercadinho Ponto Certo" `
 -i "assets\Mercadinho_Ponto_Certo.ico" `
 --add-data "assets;assets" `
 --add-data "data;data" `
 --add-data "alembic;alembic" `
 --hidden-import "fpdf"
```

- Saída: pasta `dist/` com o executável.

## Empacotar em executável (Linux)

Com o ambiente virtual ativo:

```bash
.venv/bin/flet pack app.py \
 -n "Mercadinho Ponto Certo" \
 -i assets/Mercadinho_Ponto_Certo.ico \
 --add-data "assets:assets" \
 --add-data "data:data" \
 --add-data "alembic:alembic" \
 --hidden-import fpdf
```

- Observação: em Linux/Mac, o formato de `--add-data` usa `src:dest` (dois pontos) e não `src;dest`.

## Dependências principais

- Ver [requirements.txt](requirements.txt) com comentários do uso de cada biblioteca.
- Extras úteis: [requirements.auto.txt](requirements.auto.txt) (gerado por análise de imports).

## Dicas e solução de problemas

- Excel: instale `pandas` e `openpyxl` para importar `.xlsx`.
- Câmera/leitor de códigos: `opencv-python` + `pyzbar`.
- Impressora térmica: para ESC/POS, confirme conexões USB/Serial e permissões.
- Caso o app não encontre dados de estoque, verifique arquivos em [data/](data/) e o banco [mercadinho.db](mercadinho.db).

### Windows: SmartScreen, Privacidade e Bloqueios

- SmartScreen (arquivo de editor desconhecido): ao abrir o `.exe`, se o Windows exibir o aviso do Defender SmartScreen, clique em "Mais informações" e selecione "Executar mesmo assim".
- Arquivo baixado da internet: clique com o botão direito no `.zip`/`.exe` → Propriedades → marque "Desbloquear" e aplique.
- Firewall do Windows: ao primeiro uso, permita o aplicativo em redes privadas quando solicitado. Se necessário, abra o Defender Firewall → "Permitir um app pelo firewall" e inclua o executável em `dist/`.
- Permissões de câmera/USB: Configurações → Privacidade e segurança → Câmera → permita o uso por aplicativos de desktop. Para USB/serial, mantenha drivers atualizados.
- Impressão RAW (win32print): defina a impressora padrão no Windows e garanta permissão de uso. Em alguns casos, executar como Administrador pode ser necessário.
- Antivírus de terceiros: adicione exceção para a pasta `dist/` e o executável se o antivírus bloquear a execução.
- Política de privacidade: o aplicativo roda localmente, não envia dados a terceiros e armazena informações apenas em `mercadinho.db` e `exports/`. Não há coleta de dados pessoais nem telemetria embutida.

### PowerShell: Política de execução e erros comuns

- Erro de permissão ao executar scripts no PowerShell:
  
 Execute na sessão do usuário atual para permitir scripts assinados/remotos:

 ```powershell
 Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
 ```

 Se aparecer prompt de confirmação, escolha "Sim". Não é necessário alterar a política do sistema inteiro.

- Erros ao instalar bibliotecas que exigem ferramentas de build:
  
 Windows (atualizar ferramentas do Python):

 ```powershell
 python -m pip install --upgrade setuptools wheel
 ```

 Linux (pacotes de build):

 ```bash
 sudo apt-get install build-essential python3-dev
 ```

 Observação: algumas bibliotecas com componentes nativos podem precisar desses pacotes. Este projeto usa dependências puras em Python por padrão; instale os pacotes de build apenas se o erro indicar necessidade.

## Testes

```powershell
python -m pytest
```

## Licença

Projeto interno do Mercadinho Ponto Certo.




