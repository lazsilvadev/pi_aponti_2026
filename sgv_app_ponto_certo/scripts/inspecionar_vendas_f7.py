from datetime import datetime, time

from models.db_models import ItemVenda, Produto, Venda, get_session, init_db


def main():
    engine = init_db()
    session = get_session(engine)

    hoje = datetime.now().date()
    inicio = datetime.combine(hoje, time.min)
    fim = datetime.combine(hoje, time.max)

    print(f"Inspecionando vendas de hoje: {hoje}\n")

    vendas = (
        session.query(Venda)
        .filter(Venda.data_venda >= inicio, Venda.data_venda <= fim)
        .order_by(Venda.data_venda.desc())
        .all()
    )

    if not vendas:
        print("Nenhuma venda encontrada para hoje.")
        return

    for v in vendas:
        print(f"Venda #{v.id} - {v.data_venda} - total={v.total}")
        for it in v.itens:
            prod = (
                session.query(Produto).filter_by(id=it.produto_id).first()
                if it.produto_id
                else None
            )
            cod = getattr(prod, "codigo_barras", None)
            nome = getattr(prod, "nome", None)
            print(
                f"  Item id={it.id} produto_id={it.produto_id} codigo={cod} nome={nome} "
                f"qtd={it.quantidade} preco_unitario={it.preco_unitario}"
            )
        print("-")


if __name__ == "__main__":
    main()
