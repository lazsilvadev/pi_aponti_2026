#!/usr/bin/env bash
# setup.sh - configuração do projeto Mercadinho (Linux/macOS)
# Uso: ./setup.sh [--python /caminho/para/python] [--skip-run]
set -euo pipefail
PYTHON=${PYTHON:-}
SKIP_RUN=0

print_usage() {
  echo "Usage: $0 [--python /path/to/python] [--skip-run]"
}

# parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      PYTHON="$2"; shift 2;;
    --skip-run)
      SKIP_RUN=1; shift;;
    -h|--help)
      print_usage; exit 0;;
    *)
      echo "Unknown arg: $1"; print_usage; exit 1;;
  esac
done

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# detect python if not provided
if [[ -z "$PYTHON" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
  elif command -v python >/dev/null 2>&1; then
    PYTHON=python
  else
    echo "Python not found. Install Python 3 and retry." >&2
    exit 1
  fi
fi

echo "==> Configurando projeto em $PROJECT_DIR"

# 1) Criar venv
if [[ ! -d ".venv" ]]; then
  echo "-> Criando ambiente virtual (.venv)"
  $PYTHON -m venv .venv
else
  echo "-> Ambiente virtual já existe"
fi

# 2) Ativar venv
# shellcheck disable=SC1091
source ".venv/bin/activate"
VENV_PY="$PROJECT_DIR/.venv/bin/python"

echo "-> Usando Python do venv: $VENV_PY"

# 3) Atualizar pip
echo "-> Atualizando pip"
$VENV_PY -m pip install -U pip setuptools wheel

# 4) Instalar dependências
if [[ -f "requirements.txt" ]]; then
  echo "-> Instalando dependências de requirements.txt"
  $VENV_PY -m pip install -r requirements.txt || {
    echo "Falha ao instalar requirements.txt. Tentando instalar dependências mínimas." >&2
  }
else
  echo "-> requirements.txt não encontrado; instalando deps mínimas"
  $VENV_PY -m pip install flet sqlalchemy alembic python-dotenv || true
fi

# garantir versão do flet compatível (opcional)
# $VENV_PY -m pip install "flet==0.28.3" || true

# 5) Criar pastas necessárias
mkdir -p assets data exports

# 5.1) Criar banco mercadinho.db (se a aplicação usar esse nome localmente)
if [[ ! -f "data/mercadinho.db" && ! -f "mercadinho.db" ]]; then
  echo "-> Criando banco de dados padrão (invocando models.db_models.init_db())"
  # tentar inicializar via module
  if $VENV_PY -c "import importlib, sys; m=importlib.import_module('models.db_models'); getattr(m,'init_db', lambda: None)()"; then
    echo "-> Banco criado (se supported)"
  else
    echo "(Aviso) Não foi possível criar automaticamente o DB via models.db_models.init_db()"
  fi
else
  echo "-> Banco existente detectado"
fi

# 6) Criar .env se não existir
if [[ ! -f ".env" ]]; then
  echo "-> Criando .env"
  cat > .env <<EOF
DATABASE_URL=sqlite:///data/mercadinho.db
EOF
else
  echo "-> .env já existe"
fi

# 7) Limpar caches
echo "-> Limpando __pycache__ e .pyc"
find . -type d -name "__pycache__" -exec rm -rf {} + || true
find . -type f -name "*.pyc" -delete || true

# 8) Rodar migrações Alembic (se houver)
if [[ -f "alembic.ini" ]]; then
  echo "-> Aplicando migrações alembic"
  $VENV_PY -m alembic upgrade head || echo "(Aviso) Falha ao aplicar migrações"
fi

if [[ "$SKIP_RUN" -eq 0 ]]; then
  echo "-> Iniciando aplicação"
  echo "Usando: $VENV_PY"
  exec $VENV_PY ./app.py
else
  echo "-> Skip run habilitado; não executando a aplicação"
fi
