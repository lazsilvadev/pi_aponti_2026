# TEF Adapter (simulado)

Este diretório contém um adaptador TEF simulável para permitir testes locais sem hardware.

- `TefAdapter(simulate=True)` — autorizações sempre aprovadas por padrão.
- Para testar rejeição, chame `authorize(..., options={'simulate_fail': True})`.

Como usar no projeto:

```py
from payments.tef_adapter import TefAdapter
adapter = TefAdapter(simulate=True)
resp = adapter.authorize(12.5, method='Crédito')
```

Substitua por um adaptador real do adquirente quando disponível.
