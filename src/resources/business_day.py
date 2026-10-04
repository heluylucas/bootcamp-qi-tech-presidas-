from fastapi import status
from fastapi.responses import JSONResponse

from controllers.business_day_controller import BusinessDayController
from utils.schema_handler import SchemaHandler


class BusinessDayResource:
    def on_get(self) -> JSONResponse:
        business_date = BusinessDayController().get()
        return JSONResponse(content=business_date, status_code=status.HTTP_200_OK)

    @SchemaHandler.validate("post_day_close.json")
    def on_post_close(self, payload: dict) -> JSONResponse:
        closed = BusinessDayController().close(payload)
        return JSONResponse(content=closed, status_code=status.HTTP_201_CREATED)
