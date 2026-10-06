from typing import Optional

from fastapi import Header, Request, status
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
        transaction, created = TransactionController().create(customer_key, account_key, payload, idempotency_key)
        # Repetição idempotente: a resposta original, com 200 em vez de 201 (nada foi criado agora).
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return JSONResponse(content=transaction, status_code=status_code)

    @SchemaHandler.validate_query_params("get_transactions.json")
    def on_get_list(self, customer_key: str, account_key: str, request: Request) -> JSONResponse:
        statement = TransactionController().list_statement(customer_key, account_key, dict(request.query_params))
        return JSONResponse(content=statement, status_code=status.HTTP_200_OK)

    def on_get(self, customer_key: str, account_key: str, transaction_key: str) -> JSONResponse:
        receipt = TransactionController().get_receipt(customer_key, account_key, transaction_key)
        return JSONResponse(content=receipt, status_code=status.HTTP_200_OK)
