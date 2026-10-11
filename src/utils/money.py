from decimal import ROUND_DOWN, Decimal


EIGHT_PLACES = Decimal("0.00000001")


def quantity_for(amount: int, unit_price: Decimal) -> Decimal:
    return (Decimal(amount) / 100 / unit_price).quantize(EIGHT_PLACES, ROUND_DOWN)


def amount_for(quantity: Decimal, unit_price: Decimal) -> int:
    return int(quantity * unit_price * 100)
