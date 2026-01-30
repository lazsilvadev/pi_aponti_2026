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
. ".\.venv\Scripts\Activate.ps1"

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

# Instalar dependências do projeto usando o Python do venv
Write-Host "-> Instalando dependências a partir de requirements (se presente)" -ForegroundColor Cyan
$reqFile = $null
if (Test-Path ".\requirements.txt") { $reqFile = ".\requirements.txt" }
elseif (Test-Path ".\requirements") { $reqFile = ".\requirements" }

if ($reqFile) {
    Write-Host "-> Usando arquivo de requirements: $reqFile" -ForegroundColor DarkGray
    & $PythonExe -m pip install -r $reqFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Falha ao instalar dependências (pip retornou código $LASTEXITCODE)." -ForegroundColor Red
        Write-Host "Provável causa: conflitos de versões (ex: numpy vs opencv-python). Ajuste $reqFile e tente novamente." -ForegroundColor Yellow
        Exit $LASTEXITCODE
    }
}
else {
    Write-Host "(Aviso) Nenhum arquivo de requirements encontrado; instalando conjunto mínimo" -ForegroundColor Yellow
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
    & $PythonExe -m pip install "flet==0.28.3"
}
catch {
    Write-Host "(Aviso) Falha ao fixar versão do flet: $_" -ForegroundColor Yellow
}

# 5) Criar pastas necessárias
Write-Host "-> Garantindo pastas: assets, data, exports" -ForegroundColor Cyan
New-Item -ItemType Directory -Path .\assets -Force | Out-Null
New-Item -ItemType Directory -Path .\data -Force | Out-Null
New-Item -ItemType Directory -Path .\exports -Force | Out-Null

# 5.2) Garantir logo do Mercadinho para login/painel gerencial
Write-Host "-> Verificando logo em assets e atualizando data/app_config.json" -ForegroundColor Cyan
$assetLogoRel = "assets/Mercadinho_Ponto_Certo.png"
$assetLogoFs = Join-Path $ProjectPath "assets\Mercadinho_Ponto_Certo.png"
$cfgPath = Join-Path $ProjectPath "data\app_config.json"

if (Test-Path $assetLogoFs) {
    Write-Host "-> Logo encontrado: $assetLogoFs" -ForegroundColor DarkGray
} else {
    Write-Host "(Aviso) Logo não encontrado em assets: $assetLogoFs" -ForegroundColor Yellow
    Write-Host "         Coloque 'Mercadinho_Ponto_Certo.png' em .\assets para exibir no login/gerencial." -ForegroundColor Yellow
}

try {
    if (Test-Path $cfgPath) {
        $raw = Get-Content $cfgPath -Raw -ErrorAction Stop
        $json = $raw | ConvertFrom-Json
        $json.site_logo = $assetLogoRel
        $json | ConvertTo-Json -Depth 10 | Set-Content $cfgPath -Encoding UTF8
        Write-Host "-> Atualizado data/app_config.json (site_logo -> $assetLogoRel)" -ForegroundColor Green
    }
    else {
        $obj = @{
            printer = @{ printer_name = "MPT-II"; paper_size = "58mm" }
            site_logo = $assetLogoRel
            site_slogan = ""
            site_pdv_title = ""
            site_pdv_title_upper = $false
            icon_color = "#034986"
            login_button_bg = ""
            login_button_text_color = ""
        }
        $obj | ConvertTo-Json -Depth 10 | Set-Content $cfgPath -Encoding UTF8
        Write-Host "-> Criado data/app_config.json com site_logo = $assetLogoRel" -ForegroundColor Green
    }
}
catch {
    Write-Host "(Aviso) Falha ao atualizar/criar data/app_config.json: $_" -ForegroundColor Yellow
}

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
