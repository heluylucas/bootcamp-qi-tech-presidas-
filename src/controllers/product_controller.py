from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos.product_dto import price_to_dict, product_to_dict, product_with_price_to_dict
from errors import InvalidPrice, InvalidSchema, PriceAlreadyPublished, ProductNotFound
from repositories import BusinessDayRepository, ProductRepository


class ProductController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def list(self, query_params: dict) -> dict:
        max_risk = query_params.get("max_risk")
        products = ProductRepository.list(
            self.context, query_params.get("type"), int(max_risk) if max_risk else None
        )
        return {"items": [product_to_dict(product) for product in products]}

    def get(self, product_key: str) -> dict:
        product = self._get_product(product_key)
        business_date = BusinessDayRepository.get_current(self.context).reference_date
        price = ProductRepository.get_price_on(self.context, product.id, business_date)

        return product_with_price_to_dict(product, price)

    def list_prices(self, product_key: str, query_params: dict) -> dict:
        from_date = parse_date(query_params.get("from"), "from")
        to_date = parse_date(query_params.get("to"), "to")
        product = self._get_product(product_key)

        prices = ProductRepository.list_prices(self.context, product.id, from_date, to_date)
        return {"items": [price_to_dict(price) for price in prices]}

    def publish_price(self, product_key: str, payload: dict) -> dict:
        reference_date = parse_date(payload["reference_date"], "reference_date")
        unit_price = Decimal(payload["unit_price"])
        product = self._get_product(product_key)
        business_date = BusinessDayRepository.get_current(self.context).reference_date

        if unit_price <= 0 or reference_date > business_date:
            raise InvalidPrice()

        if ProductRepository.get_price_by_date(self.context, product.id, reference_date) is not None:
            raise PriceAlreadyPublished()

        # Duas publicações da mesma data ao mesmo tempo passam as duas pela
        # busca acima; o UNIQUE(product_id, reference_date) recusa a segunda.
        try:
            price = ProductRepository.create_price(self.context, product.id, reference_date, unit_price)
        except IntegrityError:
            raise PriceAlreadyPublished()

        self.session.commit()
        return price_to_dict(price)

    def _get_product(self, product_key: str):
        product = ProductRepository.get_by_key(self.context, product_key)

        if product is None:
            raise ProductNotFound()

        return product


def parse_date(text: Optional[str], field: str) -> Optional[date]:
    """O schema só confere a cara AAAA-MM-DD; "2026-02-30" só cai aqui."""
    if text is None:
        return None

    try:
        return date.fromisoformat(text)
    except ValueError:
        raise InvalidSchema(f"{field} is not a valid date")
