from decimal import Decimal

from models import InvestmentOrder, Position
from utils.money import amount_for


def order_to_dict(order: InvestmentOrder) -> dict:
    transaction = order.transaction
    side = "APPLY" if transaction.type == "INVESTMENT_APPLY" else "REDEEM"
    response = {
        "order_key": order.order_key,
        "product_key": order.product.product_key,
        "side": side,
        "source": "CUSTOMER" if order.matured_investment_order_id is None else "MATURITY",
        "amount": transaction.amount,
        "unit_price": f"{order.unit_price:.8f}",
        "quantity": f"{order.quantity:.8f}",
        "maturity_date": order.maturity_date.isoformat() if order.maturity_date else None,
        "status": "EXECUTED",
        "transaction_key": transaction.transaction_key,
    }

    if side == "REDEEM":
        response["acquisition_cost_amount"] = order.acquisition_cost_amount
        response.update(result_to_dict(transaction.amount, order.acquisition_cost_amount))

    return response


def position_to_dict(position: Position, unit_price: Decimal) -> dict:
    value = amount_for(position.quantity, unit_price)
    return {
        "product_key": position.product.product_key,
        "quantity": f"{position.quantity:.8f}",
        "unit_price": f"{unit_price:.8f}",
        "current_amount": value,
        "acquisition_cost_amount": position.acquisition_cost_amount,
        **result_to_dict(value, position.acquisition_cost_amount),
    }


def total_to_dict(items: list, cash_amount: int) -> dict:
    investments_amount = sum(item["current_amount"] for item in items)
    acquisition_cost_amount = sum(item["acquisition_cost_amount"] for item in items)
    net_worth_amount = cash_amount + investments_amount
    cash_bps = cash_amount * 10000 // net_worth_amount if net_worth_amount else 0
    return {
        "investments_amount": investments_amount,
        "acquisition_cost_amount": acquisition_cost_amount,
        **result_to_dict(investments_amount, acquisition_cost_amount),
        "cash_amount": cash_amount,
        "net_worth_amount": net_worth_amount,
        "cash_bps": cash_bps,
        "investments_bps": 10000 - cash_bps if net_worth_amount else 0,
    }


def result_to_dict(amount: int, acquisition_cost_amount: int) -> dict:
    result_amount = amount - acquisition_cost_amount
    return_bps = int(Decimal(result_amount * 10000) // acquisition_cost_amount) if acquisition_cost_amount else 0
    return {"result_amount": result_amount, "return_bps": return_bps}
