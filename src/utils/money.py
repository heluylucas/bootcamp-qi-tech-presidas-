from decimal import ROUND_DOWN, Decimal


# Cotas e preço unitário têm 8 casas decimais: NUMERIC(24,8) e NUMERIC(20,8).
EIGHT_PLACES = Decimal("0.00000001")


def quantity_for(amount: int, unit_price: Decimal) -> Decimal:
    """Quantas cotas o valor (em centavos) compra: reais / preço, truncado em 8 casas (RN-ORD-06)."""
    return (Decimal(amount) / 100 / unit_price).quantize(EIGHT_PLACES, ROUND_DOWN)


def amount_for(quantity: Decimal, unit_price: Decimal) -> int:
    """Quanto as cotas valem ao preço, em centavos inteiros, para baixo (RN-POS-01)."""
    return int(quantity * unit_price * 100)
