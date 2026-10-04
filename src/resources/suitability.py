from fastapi import status
from fastapi.responses import JSONResponse

from controllers.suitability_controller import SuitabilityController
from utils.schema_handler import SchemaHandler


class SuitabilityResource:
    def on_get_questions(self) -> JSONResponse:
        questions = SuitabilityController().list_questions()
        return JSONResponse(content=questions, status_code=status.HTTP_200_OK)

    @SchemaHandler.validate("post_suitability.json")
    def on_post(self, customer_key: str, payload: dict) -> JSONResponse:
        assessment = SuitabilityController().submit(customer_key, payload)
        return JSONResponse(content=assessment, status_code=status.HTTP_201_CREATED)

    def on_get(self, customer_key: str) -> JSONResponse:
        assessment = SuitabilityController().get_current(customer_key)
        return JSONResponse(content=assessment, status_code=status.HTTP_200_OK)

    def on_get_history(self, customer_key: str) -> JSONResponse:
        history = SuitabilityController().list_history(customer_key)
        return JSONResponse(content=history, status_code=status.HTTP_200_OK)
