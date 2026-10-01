from fastapi import status
from fastapi.responses import JSONResponse

from controllers.customer_controller import CustomerController
from utils.schema_handler import SchemaHandler


class CustomerResource:
    @SchemaHandler.validate("post_customer.json")
    def on_post(self, payload: dict) -> JSONResponse:
        customer = CustomerController().create(payload)
        return JSONResponse(content=customer, status_code=status.HTTP_201_CREATED)

    def on_get(self, customer_key: str) -> JSONResponse:
        customer = CustomerController().get(customer_key)
        return JSONResponse(content=customer, status_code=status.HTTP_200_OK)
