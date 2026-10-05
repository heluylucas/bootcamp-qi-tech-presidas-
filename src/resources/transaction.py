from typing import Optional

from fastapi import Header, status
from fastapi.responses import JSONResponse

from controllers.transaction_controller import TransactionController
from utils.schema_handler import SchemaHandler


class TransactionResource:
    @SchemaHandler.validate("post_transaction.json")
    def on_post(
        self,
        customer_key: str,
        account_key: str,
        payload: dict,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    ) -> JSONResponse:
        transaction = TransactionController().create(customer_key, account_key, payload, idempotency_key)
        return JSONResponse(content=transaction, status_code=status.HTTP_201_CREATED)
