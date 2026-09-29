from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import BookController
from utils.schema_handler import SchemaHandler

DEFAULT_LIMIT = 10
DEFAULT_PAGE = 0


class BookResource:
    """A porta de entrada HTTP do livro.

    Mesmo desenho do AuthorResource, com três rotas a mais: mover de
    estante, emprestar e devolver. As três respondem 200 com
    `{book_key, status}` — quem quiser o livro inteiro, com a trilha
    `status_events`, pede o GET /book/{book_key} depois.

    Os erros (404, 409, 502) não saem daqui. Erro já carrega o próprio
    status (veja src/errors/custom_errors.py), e quem o levanta é o
    controller.
    """

    @SchemaHandler.validate("post_book.json")
    def on_post(self, payload: dict) -> JSONResponse:
        controller = BookController()
        book = controller.create(payload)

        return JSONResponse(
            content=jsonable_encoder(book),
            status_code=http_status.HTTP_201_CREATED,
        )

    def on_get_by_key(self, book_key: str) -> JSONResponse:
        controller = BookController()
        book = controller.get_by_key(book_key)

        return JSONResponse(
            content=jsonable_encoder(book),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate_query_params("get_books.json")
    def on_get_list(self, request: Request) -> JSONResponse:
        controller = BookController()

        query_params = request.query_params

        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        page = int(query_params.get("page", DEFAULT_PAGE))
        shelf_key = query_params.get("shelf_key")

        offset = page * limit
        books_page = controller.get_list(limit, offset, shelf_key)

        page_envelope = {
            "data": books_page["books_list_dto"],
            "limit": limit,
            "page": page,
            "is_last_page": books_page["is_last_page"],
        }

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate("put_book_shelf.json")
    def on_put_shelf(self, book_key: str, payload: dict) -> JSONResponse:
        shelf_key = payload["shelf_key"]

        controller = BookController()
        book = controller.move_to_shelf(book_key, shelf_key)

        return JSONResponse(
            content=jsonable_encoder(book),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate("put_book_borrow.json")
    def on_put_borrow(self, book_key: str, payload: dict) -> JSONResponse:
        member_key = payload["member_key"]

        controller = BookController()
        book = controller.borrow(book_key, member_key)

        return JSONResponse(
            content=jsonable_encoder(book),
            status_code=http_status.HTTP_200_OK,
        )

    def on_put_return(self, book_key: str) -> JSONResponse:
        controller = BookController()
        book = controller.return_book(book_key)

        return JSONResponse(
            content=jsonable_encoder(book),
            status_code=http_status.HTTP_200_OK,
        )
