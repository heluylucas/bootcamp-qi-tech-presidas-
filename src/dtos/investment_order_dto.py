from decimal import Decimal

from models import InvestmentOrder, Position


def order_to_dict(order: InvestmentOrder) -> dict:
    """Quantidade e preço saem como texto: um decimal no JSON costuma ser lido como float (R6)."""
    response = {
        "order_key": order.order_key,
        "product_key": order.product.product_key,
        "side": order.side,
        "source": order.source,
        "amount": order.amount,
        "unit_price": f"{order.unit_price:.8f}",
        "quantity": f"{order.quantity:.8f}",
        "maturity_date": order.maturity_date.isoformat() if order.maturity_date else None,
        "status": order.status,
        "transaction_key": order.transaction.transaction_key,
    }

    if order.side == "REDEEM":
        # RN-ORD-16: tudo vem do custo gravado na ordem, então a repetição devolve os mesmos números.
        response["cost_amount"] = order.cost_amount
        response.update(result_to_dict(order.amount, order.cost_amount))

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


def total_to_dict(items: list) -> dict:
    current_amount = sum(item["current_amount"] for item in items)
    invested_amount = sum(item["invested_amount"] for item in items)
    return {
        "current_amount": current_amount,
        "invested_amount": invested_amount,
        **result_to_dict(current_amount, invested_amount),
    }


def result_to_dict(amount: int, cost_amount: int) -> dict:
    """Resultado (pode ser negativo) e rentabilidade em pontos-base; 0 se o custo for 0."""
    result_amount = amount - cost_amount
    # Decimal // trunca em direção ao zero, como a regra pede para resultado negativo.
    return_bps = int(Decimal(result_amount * 10000) // cost_amount) if cost_amount else 0
    return {"result_amount": result_amount, "return_bps": return_bps}
