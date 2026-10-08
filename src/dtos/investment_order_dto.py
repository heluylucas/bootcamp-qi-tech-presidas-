from decimal import Decimal

from models import InvestmentOrder, Position


def order_to_dict(order: InvestmentOrder) -> dict:
    """Quantidade e preço saem como texto: um decimal no JSON costuma ser lido como float (R6).

    Lado e valor vêm da transação da ordem, que é o pedido de dinheiro.
    """
    transaction = order.transaction
    side = "APPLY" if transaction.type == "INVESTMENT_APPLY" else "REDEEM"
    response = {
        "order_key": order.order_key,
        "product_key": order.product.product_key,
        "side": side,
        # Só a liquidação do vencimento (fechamento do dia) aponta para a aplicação que devolveu.
        "source": "CUSTOMER" if order.settled_order_id is None else "MATURITY",
        "amount": transaction.amount,
        "unit_price": f"{order.unit_price:.8f}",
        "quantity": f"{order.quantity:.8f}",
        "maturity_date": order.maturity_date.isoformat() if order.maturity_date else None,
        # Toda ordem é executada na hora: não há fila nem cotização com prazo.
        "status": "EXECUTED",
        "transaction_key": transaction.transaction_key,
    }

    if side == "REDEEM":
        # RN-ORD-16: tudo vem do custo gravado na ordem, então a repetição devolve os mesmos números.
        response["cost_amount"] = order.cost_amount
        response.update(result_to_dict(transaction.amount, order.cost_amount))

    return response


def position_to_dict(position: Position, unit_price: Decimal) -> dict:
    """RN-POS-01: o valor atual é a quantidade ao preço do dia, em centavos inteiros (para baixo)."""
    current_amount = int(position.quantity * unit_price * 100)
    return {
        "product_key": position.product.product_key,
        "quantity": f"{position.quantity:.8f}",
        "unit_price": f"{unit_price:.8f}",
        "current_amount": current_amount,
        "invested_amount": position.invested_amount,
        **result_to_dict(current_amount, position.invested_amount),
    }


def total_to_dict(items: list, cash_amount: int) -> dict:
    """Os investimentos somados e o capital total no banco: caixa + investimentos ao preço do dia."""
    current_amount = sum(item["current_amount"] for item in items)
    invested_amount = sum(item["invested_amount"] for item in items)
    net_worth_amount = cash_amount + current_amount
    # Pontos-base inteiros (10.000 = 100%), sem float. O caixa arredonda para baixo e os
    # investimentos completam, para a soma fechar sempre em 100%. Sem capital, os dois são 0.
    cash_bps = cash_amount * 10000 // net_worth_amount if net_worth_amount else 0
    return {
        "current_amount": current_amount,
        "invested_amount": invested_amount,
        **result_to_dict(current_amount, invested_amount),
        "cash_amount": cash_amount,
        "net_worth_amount": net_worth_amount,
        "cash_bps": cash_bps,
        "investments_bps": 10000 - cash_bps if net_worth_amount else 0,
    }


def result_to_dict(amount: int, cost_amount: int) -> dict:
    """Resultado (pode ser negativo) e rentabilidade em pontos-base; 0 se o custo for 0."""
    result_amount = amount - cost_amount
    # Decimal // trunca em direção ao zero, como a regra pede para resultado negativo.
    return_bps = int(Decimal(result_amount * 10000) // cost_amount) if cost_amount else 0
    return {"result_amount": result_amount, "return_bps": return_bps}
