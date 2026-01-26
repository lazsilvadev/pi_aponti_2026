import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PROD_PATH = BASE / "data" / "produtos.json"
BACKUP = (
    BASE / "data" / f"produtos_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Garantir que o diretório do projeto esteja no path para imports de pacote local
sys.path.insert(0, str(BASE))

print(f"Arquivo de produtos: {PROD_PATH}")
if not PROD_PATH.exists():
    print("Arquivo de produtos.json não encontrado. Abortando.")
    raise SystemExit(1)

with open(PROD_PATH, "r", encoding="utf-8") as f:
    produtos = json.load(f)

# Encontrar produto com quantidade positiva (preferir quantidade == 1)
idx = None
for i, p in enumerate(produtos):
    q = int(p.get("quantidade", 0) or 0)
    if q == 1:
        idx = i
        break
if idx is None:
    for i, p in enumerate(produtos):
        q = int(p.get("quantidade", 0) or 0)
        if q > 0:
            idx = i
            break

if idx is None:
    print("Nenhum produto com quantidade > 0 encontrado para simular venda.")
    raise SystemExit(0)

produto = produtos[idx]
print(
    f"Produto selecionado: id={produto.get('id')} nome={produto.get('nome')} quantidade={produto.get('quantidade')}"
)

# Backup
with open(BACKUP, "w", encoding="utf-8") as f:
    json.dump(produtos, f, ensure_ascii=False, indent=2)
print(f"Backup salvo em: {BACKUP}")

# Simular venda: reduzir para zero
produtos[idx]["quantidade"] = 0
with open(PROD_PATH, "w", encoding="utf-8") as f:
    json.dump(produtos, f, ensure_ascii=False, indent=2)
print(f"Atualizado {PROD_PATH}: produto id={produto.get('id')} agora com quantidade=0")

# Rodar verificação de alertas
try:
    from alertas.alertas_manager import AlertasManager

    am = AlertasManager()
    alertas = am.verificar_estoque_baixo(None)
    print("\n== Resultados da Verificação de Alertas ==")
    print(f"Total de alertas detectados: {len(alertas)}")
    for a in alertas:
        print(
            f" - {a['nome']} (id={a['id']}): estoque_atual={a['estoque_atual']} falta={a['falta']}"
        )
except Exception as e:
    print(f"Erro ao executar AlertasManager: {e}")
    raise

print("\nTeste concluído.")
