from fastapi import Request, status
from fastapi.responses import JSONResponse

from controllers.product_controller import ProductController
from utils.schema_handler import SchemaHandler


class ProductResource:
    @SchemaHandler.validate_query_params("get_products.json")
    def on_get_list(self, request: Request) -> JSONResponse:
        products = ProductController().list(dict(request.query_params))
        return JSONResponse(content=products, status_code=status.HTTP_200_OK)

    def on_get(self, product_key: str) -> JSONResponse:
        product = ProductController().get(product_key)
        return JSONResponse(content=product, status_code=status.HTTP_200_OK)

    @SchemaHandler.validate_query_params("get_product_prices.json")
    def on_get_prices(self, product_key: str, request: Request) -> JSONResponse:
        prices = ProductController().list_prices(product_key, dict(request.query_params))
        return JSONResponse(content=prices, status_code=status.HTTP_200_OK)
