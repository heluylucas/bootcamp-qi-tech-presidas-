from typing import Optional

from models import Product, ProductPrice


def product_to_dict(product: Product) -> dict:
    return {
        "product_key": product.product_key,
        "name": product.name,
        "type": product.type,
        "issuer": product.issuer,
        "indexer": product.indexer,
        "rate_description": product.rate_description,
        "risk_level": product.risk_level,
        "term_months": product.term_months,
        "minimum_application_amount": product.minimum_application_amount,
    }


def product_with_price_to_dict(product: Product, price: Optional[ProductPrice]) -> dict:
    # Sem nenhum preço até a data de movimento, "price" sai nulo (RN-PRO-04).
    return {**product_to_dict(product), "price": price_to_dict(price) if price else None}


def price_to_dict(price: ProductPrice) -> dict:
    return {
        "price_date": price.price_date.isoformat(),
        # Texto com 8 casas, para quem recebe não ler como float (R6).
        "unit_price": f"{price.unit_price:.8f}",
    }
