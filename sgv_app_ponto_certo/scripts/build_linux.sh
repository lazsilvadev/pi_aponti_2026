#!/usr/bin/env bash
# build_linux.sh
# Empacota o projeto Mercadinho em um único binário Linux usando PyInstaller.
# ATENÇÃO: este script deve ser executado em um sistema Linux (não faz cross-compile).

set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

PYTHON=${PYTHON:-python3}
VENV_DIR=".venv"

echo "==> Build Linux: usando projeto em $PROJECT_DIR"

# 1) criar/ativar venv
if [[ ! -d "$VENV_DIR" ]]; then
  echo "-> Criando venv"
  $PYTHON -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
PY="$PROJECT_DIR/$VENV_DIR/bin/python"
PIP="$PROJECT_DIR/$VENV_DIR/bin/pip"

echo "-> Python: $($PY -V)"

# 2) instalar dependências
echo "-> Instalando dependências"
$PIP install -U pip setuptools wheel
if [[ -f requirements.txt ]]; then
  $PIP install -r requirements.txt || true
else
  $PIP install flet sqlalchemy alembic python-dotenv || true
fi
# garantir pyinstaller
$PIP install pyinstaller

# 3) limpar builds anteriores
rm -rf build dist "${PROJECT_DIR%%/}/Mercadinho" *.spec || true

# 4) rodar pyinstaller
# Incluir assets e data como datas. Em Linux o formato é 'source:dest'
ADDITIONAL_DATA=("assets:assets" "data:data" "alembic:alembic")
DATA_ARGS=()
for d in "${ADDITIONAL_DATA[@]}"; do
  DATA_ARGS+=(--add-data "$d")
done

# nota: se precisar incluir hidden imports, adicione aqui
HIDDEN_IMPORTS=("fpdf")
HIDDEN_ARGS=()
for h in "${HIDDEN_IMPORTS[@]}"; do
  HIDDEN_ARGS+=(--hidden-import "$h")
done

echo "-> Executando PyInstaller (isso pode demorar)..."
# Use --onefile para empacotar tudo em um binário
# Não definimos ícone (opcional) para compatibilidade multiplataforma
eval "$PY -m pyinstaller --noconfirm --onefile --name 'mercadinho' ${DATA_ARGS[*]} ${HIDDEN_ARGS[*]} app.py"

if [[ -f dist/mercadinho ]]; then
  echo "Build completo: dist/mercadinho"
else
  echo "Build finalizado, mas dist/mercadinho não encontrado" >&2
  exit 1
fi

# 5) instruções finais
cat <<EOF

Build finalizado.
Arquivo gerado: dist/mercadinho
Copie este arquivo para o servidor Linux / máquina destino e execute:

  chmod +x dist/mercadinho
  ./dist/mercadinho

Lembre-se: o binário é estático em termos de Python, mas ainda pode depender de libs do sistema (GTK, libs do flet-desktop etc.). Teste no ambiente alvo.
EOF
