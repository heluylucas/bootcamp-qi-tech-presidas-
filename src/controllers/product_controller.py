from controllers.base_controller import BaseController
from dtos.product_dto import price_to_dict, product_to_dict, product_with_price_to_dict
from errors import ProductNotFound
from repositories import BusinessDayRepository, ProductRepository
from utils.dates import parse_date


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

    def _get_product(self, product_key: str):
        product = ProductRepository.get_by_key(self.context, product_key)

        if product is None:
            raise ProductNotFound()

        return product
