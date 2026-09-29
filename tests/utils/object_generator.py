from tests.utils.mock_generator import CatalogMock
from tests.utils.payload_generator import PayloadGenerator
from tests.utils.random_generator import RandomGenerator
from tests.utils.request_generator import RequestGenerator


class ObjectGenerator:
    """Cria pela API o que o teste precisa ter pronto antes de começar.

    Tudo nasce por POST, como um cliente faria. O teste recebe de volta
    só o que a API respondeu — a chave —, e é por ela que ele segue.
    """

    @staticmethod
    def create_author() -> dict:
        author_payload = PayloadGenerator.create_author_payload()

        status, response = RequestGenerator.POST_author(author_payload)
        assert status == 201

        return response

    @staticmethod
    def create_shelf(capacity: int = None) -> dict:
        shelf_payload = PayloadGenerator.create_shelf_payload(capacity=capacity)

        status, response = RequestGenerator.POST_shelf(shelf_payload)
        assert status == 201

        return response

    @staticmethod
    def create_member() -> dict:
        member_payload = PayloadGenerator.create_member_payload()

        status, response = RequestGenerator.POST_member(member_payload)
        assert status == 201

        return response

    @staticmethod
    def create_book(author_key: str, shelf_key: str = None) -> dict:
        """Um livro cadastrado — o que exige ensinar o catálogo antes.

        O POST /book atravessa a fronteira, então este atalho ensina ao
        mock a resposta do ISBN que ele mesmo sorteou. Ele NÃO limpa o
        mock: quem chama `Mock().clear()` é o teste, na primeira linha.
        """
        isbn = RandomGenerator.generate_isbn()
        CatalogMock.GET_isbn(isbn=isbn)

        book_payload = PayloadGenerator.create_book_payload(author_key, isbn=isbn, shelf_key=shelf_key)

        status, response = RequestGenerator.POST_book(book_payload)
        assert status == 201

        return response
