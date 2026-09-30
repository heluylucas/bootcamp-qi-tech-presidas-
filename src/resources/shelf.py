from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import ShelfController
from utils.schema_handler import SchemaHandler

DEFAULT_LIMIT = 10
DEFAULT_PAGE = 0


class ShelfResource:
    """A porta de entrada HTTP da estante.

    Mesmo desenho do AuthorResource, e a explicação completa está lá:
    confere o corpo, chama o controller, devolve a resposta.
    """

    @SchemaHandler.validate("post_shelf.json")
    def on_post(self, payload: dict) -> JSONResponse:
        controller = ShelfController()
        shelf = controller.create(payload)

        return JSONResponse(
            content=jsonable_encoder(shelf),
            status_code=http_status.HTTP_201_CREATED,
        )

    def on_get_by_key(self, shelf_key: str) -> JSONResponse:
        controller = ShelfController()
        shelf = controller.get_by_key(shelf_key)

        return JSONResponse(
            content=jsonable_encoder(shelf),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate_query_params("get_shelves.json")
    def on_get_list(self, request: Request) -> JSONResponse:
        controller = ShelfController()

        query_params = request.query_params

        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        page = int(query_params.get("page", DEFAULT_PAGE))

        offset = page * limit
        shelves_page = controller.get_list(limit, offset)

        page_envelope = {
            "data": shelves_page["shelves_list_dto"],
            "limit": limit,
            "page": page,
            "is_last_page": shelves_page["is_last_page"],
        }

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
            status_code=http_status.HTTP_200_OK,
        )
