from controllers.base_controller import BaseController
from dtos import ShelfDTO
from errors import DuplicatedShelfCode, NotFoundShelf
from repositories import ShelfRepository


class ShelfController(BaseController):
    """As regras de negócio da estante.

    A estante tem uma regra própria — o `code` não se repete — e uma
    que não é dela: a lotação. Quem conta os livros de uma estante é o
    BookController, porque a pergunta "cabe mais um?" só aparece quando
    alguém tenta pôr um LIVRO lá.
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.shelf_repository = ShelfRepository(self.context)

    def create(self, shelf_data: dict) -> dict:
        self.logger.debug("Criando uma nova estante")

        code = shelf_data["code"]

        if self.shelf_repository.get_by_code(code) is not None:
            raise DuplicatedShelfCode(code)

        shelf = self.shelf_repository.create(shelf_data)

        shelf_dto = ShelfDTO.only_obj_key(shelf)
        self.session.commit()

        return shelf_dto

    def get_by_key(self, shelf_key: str) -> dict:
        shelf = self.shelf_repository.get_by_key(shelf_key)

        if shelf is None:
            raise NotFoundShelf(shelf_key)

        return ShelfDTO.obj_to_dict(shelf)

    def get_list(self, limit: int, offset: int) -> dict:
        shelves_list = self.shelf_repository.list_page(limit, offset)

        is_last_page = True
        if len(shelves_list) > limit:
            is_last_page = False
            shelves_list = shelves_list[:-1]

        return {
            "shelves_list_dto": ShelfDTO.list_obj_to_list_dict(shelves_list),
            "is_last_page": is_last_page,
        }
