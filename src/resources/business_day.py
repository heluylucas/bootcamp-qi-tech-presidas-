from fastapi import status
from fastapi.responses import JSONResponse

from controllers.business_day_controller import BusinessDayController


class BusinessDayResource:
    def on_get(self) -> JSONResponse:
        business_date = BusinessDayController().get()
        return JSONResponse(content=business_date, status_code=status.HTTP_200_OK)
