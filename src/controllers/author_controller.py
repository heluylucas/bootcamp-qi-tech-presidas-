from controllers.base_controller import BaseController
from dtos import AuthorDTO
from errors import DuplicatedDocumentNumber, InvalidDocumentNumber, NotFoundAuthor
from repositories import AuthorRepository
from utils.document_number import is_valid_cpf


class AuthorController(BaseController):
    """As regras de negócio do autor. Aqui mora o "pode" e o "não pode".

    O autor é uma entidade simples: buscar, criar, listar. A única regra
    é a do CPF, que é obrigatório, precisa existir e não pode se
    repetir (veja o `create`). As regras mais cheias estão no
    BookController, e é pra lá que vale ir depois deste.
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.author_repository = AuthorRepository(self.context)

    def create(self, author_data: dict) -> dict:
        """Cadastra o autor, conferindo o CPF.

        O schema já cobrou que o CPF veio, no formato 000.000.000-00
        (sem ele, 400). Aqui se confere o resto, em duas perguntas: o CPF
        existe (a conta dos dígitos verificadores, 422)? e já há outro
        autor com ele, pelo `get_by_document_number` (409)?

        O CPF é único dentro desta tabela, e só nela: a mesma pessoa pode
        ser autora e leitora.
        """
        self.logger.debug("Criando um novo autor")

        document_number = author_data["document_number"]

        if not is_valid_cpf(document_number):
            raise InvalidDocumentNumber()

        if self.author_repository.get_by_document_number(document_number) is not None:
            raise DuplicatedDocumentNumber()

        author = self.author_repository.create(author_data)

        # O DTO é montado ANTES do commit: depois dele, o SQLAlchemy
        # esquece os valores do objeto e iria ao banco de novo só pra
        # ler a chave que acabou de gravar.
        author_dto = AuthorDTO.only_obj_key(author)

        self.session.commit()

        return author_dto

    def get_by_key(self, author_key: str) -> dict:
        author = self.author_repository.get_by_key(author_key)

        if author is None:
            raise NotFoundAuthor(author_key)

        return AuthorDTO.obj_to_dict(author)

    def get_list(self, limit: int, offset: int) -> dict:
        authors_list = self.author_repository.list_page(limit, offset)

        # Pedimos um a mais que o limite só pra saber se existe próxima
        # página. Se veio o extra, ele não entra na resposta.
        is_last_page = True
        if len(authors_list) > limit:
            is_last_page = False
            authors_list = authors_list[:-1]

        return {
            "authors_list_dto": AuthorDTO.list_obj_to_list_dict(authors_list),
            "is_last_page": is_last_page,
        }
