# Script para empacotar o app em um único executável (Windows)
Write-Host "Iniciando build do executável PontoCerto..."

# Tentar ativar a virtualenv local se existir
$activatePath = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $activatePath) {
    Write-Host "Ativando virtualenv .venv..."
    & $activatePath
}
else {
    Write-Host "Aviso: virtualenv não encontrada em .venv. Usando Python do sistema." -ForegroundColor Yellow
}

Write-Host "Atualizando pip e instalando PyInstaller..."
pip install --upgrade pip
pip install pyinstaller

Write-Host "Rodando PyInstaller..."
# --onefile: gera um único .exe
# --windowed: remove console (útil para apps GUI)
# --icon: usa o ícone do mercadinho
# --add-data: inclui pastas/arquivos adicionais no executável (formato Windows: SOURCE;DEST)
# Incluir `data` para garantir `data/produtos.json` e `mercadinho.db` se presente.
pyinstaller --noconfirm --clean --onefile --windowed --name "PontoCerto" --icon "assets/Mercadinho_Ponto_Certo.ico" --add-data "assets;assets" --add-data "data;data" --add-data "mercadinho.db;." app.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build concluído com sucesso. Executável gerado em: dist\PontoCerto.exe" -ForegroundColor Green
}
else {
    Write-Host "Build falhou (código $LASTEXITCODE). Verifique a saída do PyInstaller acima." -ForegroundColor Red
}

Write-Host "Fim do script build_exe.ps1"
