from fastapi import status
from fastapi.responses import JSONResponse

from controllers.account_controller import AccountController
from utils.schema_handler import SchemaHandler


class AccountResource:
    def on_post(self, customer_key: str) -> JSONResponse:
        account = AccountController().create(customer_key)
        return JSONResponse(content=account, status_code=status.HTTP_201_CREATED)

    def on_get(self, customer_key: str, account_key: str) -> JSONResponse:
        account = AccountController().get(customer_key, account_key)
        return JSONResponse(content=account, status_code=status.HTTP_200_OK)

    @SchemaHandler.validate("patch_account.json")
    def on_patch(self, customer_key: str, account_key: str, payload: dict) -> JSONResponse:
        account = AccountController().change_status(customer_key, account_key, payload)
        return JSONResponse(content=account, status_code=status.HTTP_200_OK)

    @SchemaHandler.validate("patch_internal_account.json")
    def on_patch_internal(self, account_key: str, payload: dict) -> JSONResponse:
        account = AccountController().change_status_by_bank(account_key, payload)
        return JSONResponse(content=account, status_code=status.HTTP_200_OK)

    def on_get_status_events(self, customer_key: str, account_key: str) -> JSONResponse:
        events = AccountController().list_status_events(customer_key, account_key)
        return JSONResponse(content=events, status_code=status.HTTP_200_OK)
