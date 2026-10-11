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
    return {**product_to_dict(product), "price": price_to_dict(price) if price else None}


def price_to_dict(price: ProductPrice) -> dict:
    return {
        "price_date": price.price_date.isoformat(),
        "unit_price": f"{price.unit_price:.8f}",
    }
