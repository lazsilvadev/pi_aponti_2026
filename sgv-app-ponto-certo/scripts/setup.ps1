#requires -Version 5.1
param(
    [string]$ProjectPath = (Get-Location).Path,
    [string]$Python = "python",
    [switch]$SkipRun,
    [switch]$UseUv
)

Write-Host "==> Configurando projeto em" $ProjectPath -ForegroundColor Cyan
Push-Location $ProjectPath

# 1) Criar venv
if (-not (Test-Path ".\.venv")) {
    Write-Host "-> Criando ambiente virtual (.venv)" -ForegroundColor Cyan
    & $Python -m venv .venv
}
else {
    Write-Host "-> Ambiente virtual já existe" -ForegroundColor DarkGray
}

# 2) Ativar venv
Write-Host "-> Ativando venv" -ForegroundColor Cyan
. " .\.venv\Scripts\Activate.ps1"

# Determinar o executável Python do venv para operações subsequentes
$venvPython = Join-Path $ProjectPath ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $PythonExe = $venvPython
}
else {
    $found = Get-Command $Python -ErrorAction SilentlyContinue
    if ($found) { $PythonExe = $found.Source } else { $PythonExe = $Python }
}

Write-Host "-> Atualizando pip (usando o Python do venv)" -ForegroundColor Cyan
& $PythonExe -m pip install -U pip
Write-Host "-> Instalando gerenciador UV" -ForegroundColor Cyan
try { pip install uv } catch { Write-Host "(Aviso) Falha ao instalar uv: $_" -ForegroundColor Yellow }
Write-Host "-> Instalando deps com uv (requirements.txt)" -ForegroundColor Cyan
try { uv pip install -r requirements.txt } catch { Write-Host "(Aviso) uv não conseguiu instalar: $_" -ForegroundColor Yellow }

else {
    # 3) Atualizar pip
    Write-Host "-> Atualizando pip (usando o Python selecionado)" -ForegroundColor Cyan
    & $Python -m pip install -U pip

    # 4) Instalar dependências do projeto usando o mesmo Python
    Write-Host "-> Instalando dependências a partir de requirements.txt" -ForegroundColor Cyan
    if (Test-Path ".\requirements.txt") {
        & $PythonExe -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Falha ao instalar dependências (pip retornou código $LASTEXITCODE)." -ForegroundColor Red
            Write-Host "Provável causa: conflitos de versões (ex: numpy vs opencv-python). Ajuste requirements.txt e tente novamente." -ForegroundColor Yellow
            Exit $LASTEXITCODE
        }
    }
    else {
        Write-Host "(Aviso) requirements.txt não encontrado; instalando conjunto mínimo" -ForegroundColor Yellow
        $packages = @(
            "flet==0.28.3",
            "sqlalchemy",
            "alembic",
            "python-dotenv"
        )
        & $PythonExe -m pip install $packages
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Falha ao instalar dependências mínimas (pip retornou código $LASTEXITCODE)." -ForegroundColor Red
            Exit $LASTEXITCODE
        }
    }
    # Garantir a versão específica do Flet (instala novamente caso requirements tenha outra versão)
    try {
        & $Python -m pip install "flet==0.28.3"
    }
    catch {
        Write-Host "(Aviso) Falha ao fixar versão do flet: $_" -ForegroundColor Yellow
    }
}

# 5) Criar pastas necessárias
Write-Host "-> Garantindo pastas: assets, data, exports" -ForegroundColor Cyan
New-Item -ItemType Directory -Path .\assets -Force | Out-Null
New-Item -ItemType Directory -Path .\data -Force | Out-Null
New-Item -ItemType Directory -Path .\exports -Force | Out-Null

# 5.1) Criar banco embutido `mercadinho.db` se não existir
if (-not (Test-Path ".\mercadinho.db")) {
    Write-Host "-> Arquivo mercadinho.db não encontrado. Gerando banco de dados padrão..." -ForegroundColor Cyan
    try {
        & $PythonExe -c "from models.db_models import init_db; init_db()"
        Write-Host "-> mercadinho.db criado com sucesso." -ForegroundColor Green
    }
    catch {
        Write-Host "(Aviso) Falha ao criar mercadinho.db: $_" -ForegroundColor Yellow
    }
}
else {
    Write-Host "-> mercadinho.db já existe" -ForegroundColor DarkGray
}

# 6) Criar .env se não existir
if (-not (Test-Path ".\.env")) {
    Write-Host "-> Criando .env" -ForegroundColor Cyan
    @(
        "DATABASE_URL=sqlite:///mercadinho.db"
    ) | Set-Content -Path .\.env -Encoding UTF8
}
else {
    Write-Host "-> .env já existe" -ForegroundColor DarkGray
}

# 7) Remover caches (__pycache__ e .pyc)
Write-Host "-> Limpando __pycache__ e arquivos .pyc" -ForegroundColor Cyan
try {
    Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -LiteralPath ($_.FullName) -Recurse -Force -ErrorAction SilentlyContinue }
    Get-ChildItem -Path . -Recurse -File -Include "*.pyc" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -LiteralPath ($_.FullName) -Force -ErrorAction SilentlyContinue }
}
catch {
    Write-Host "(Aviso) Falha ao limpar caches: $_" -ForegroundColor Yellow
}

# 8) Rodar migrações Alembic (opcional)
if (Test-Path ".\alembic.ini") {
    Write-Host "-> Aplicando migrações Alembic (opcional) usando o Python do venv" -ForegroundColor Cyan
    try { & $PythonExe -m alembic upgrade head } catch { Write-Host "(Aviso) Alembic não executou: $_" -ForegroundColor Yellow }
}

if (-not $SkipRun) {
    # 9) Executar aplicação
    Write-Host "-> Iniciando aplicação" -ForegroundColor Cyan
    Write-Host "Usando Python:" $PythonExe -ForegroundColor DarkGray

    try {
        & $PythonExe .\app.py
    }
    catch {
        Write-Host "Falha ao iniciar a aplicação: $_" -ForegroundColor Red
    }
}
else {
    Write-Host "-> SkipRun habilitado: não executando a aplicação" -ForegroundColor Yellow
}

Pop-Location
