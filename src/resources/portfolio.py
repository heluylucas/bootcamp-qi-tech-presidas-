from fastapi import Request, status
from fastapi.responses import JSONResponse

from controllers.portfolio_controller import PortfolioController
from utils.schema_handler import SchemaHandler


class PortfolioResource:
    @SchemaHandler.validate_query_params("get_portfolio_suggestion.json")
    def on_get_suggestion(self, customer_key: str, request: Request) -> JSONResponse:
        # O schema já garantiu que "amount" existe e só tem dígitos.
        suggestion = PortfolioController().suggest(customer_key, int(request.query_params["amount"]))
        return JSONResponse(content=suggestion, status_code=status.HTTP_200_OK)
