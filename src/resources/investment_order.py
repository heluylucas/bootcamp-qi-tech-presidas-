from typing import Optional

from fastapi import Header, Request, status
from fastapi.responses import JSONResponse

from controllers.investment_order_controller import InvestmentOrderController
from utils.schema_handler import SchemaHandler


class InvestmentOrderResource:
    @SchemaHandler.validate("post_investment_order.json")
    def on_post(
        self,
        customer_key: str,
        account_key: str,
        payload: dict,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        order, created = InvestmentOrderController().create(customer_key, account_key, payload, idempotency_key)
        return JSONResponse(content=order, status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def on_get(self, customer_key: str, account_key: str, order_key: str) -> JSONResponse:
        order = InvestmentOrderController().get(customer_key, account_key, order_key)
        return JSONResponse(content=order, status_code=status.HTTP_200_OK)

    @SchemaHandler.validate_query_params("get_investment_orders.json")
    def on_get_list(self, customer_key: str, account_key: str, request: Request) -> JSONResponse:
        orders = InvestmentOrderController().list_orders(customer_key, account_key, dict(request.query_params))
        return JSONResponse(content=orders, status_code=status.HTTP_200_OK)

    @SchemaHandler.validate_query_params("get_positions.json")
    def on_get_positions(self, customer_key: str, account_key: str, request: Request) -> JSONResponse:
        include_closed = request.query_params.get("include_closed") == "true"
        positions = InvestmentOrderController().list_positions(customer_key, account_key, include_closed)
        return JSONResponse(content=positions, status_code=status.HTTP_200_OK)
