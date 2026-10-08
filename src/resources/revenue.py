from fastapi import Request, status
from fastapi.responses import JSONResponse

from controllers.revenue_controller import RevenueController
from utils.schema_handler import SchemaHandler


class RevenueResource:
    @SchemaHandler.validate_query_params("get_revenue.json")
    def on_get(self, request: Request) -> JSONResponse:
        revenue = RevenueController().get(dict(request.query_params))
        return JSONResponse(content=revenue, status_code=status.HTTP_200_OK)
