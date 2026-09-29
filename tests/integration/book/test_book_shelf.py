from tests.utils import ObjectGenerator, RequestGenerator
from tests.utils.mock_utils import Mock


class TestBookShelf:
    """O PUT /book/{key}/shelf e a regra de capacidade.

    Estes testes provam a regra por UMA requisição de cada vez. A parte
    da regra que só aparece com duas requisições ao mesmo tempo — a
    trava do `SELECT ... FOR UPDATE` — não tem teste aqui, e a
    explicação do porquê dela está no BookController._check_capacity.
    """

    def test_moves_to_shelf_with_room(self):
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        shelf_key = ObjectGenerator.create_shelf(capacity=2)["shelf_key"]
        book_key = ObjectGenerator.create_book(author_key)["book_key"]

        status, response = RequestGenerator.PUT_book_shelf(book_key, {"shelf_key": shelf_key})
        assert status == 200
        assert response == {"book_key": book_key, "status": "AVAILABLE"}

        status, response = RequestGenerator.GET_book(book_key)
        assert status == 200
        assert response["shelf_key"] == shelf_key

    def test_refuses_full_shelf(self):
        """Estante de capacidade 1 com um livro: o segundo leva 409, e fica onde estava."""
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        shelf_key = ObjectGenerator.create_shelf(capacity=1)["shelf_key"]

        ObjectGenerator.create_book(author_key, shelf_key=shelf_key)
        second_book_key = ObjectGenerator.create_book(author_key)["book_key"]

        status, response = RequestGenerator.PUT_book_shelf(second_book_key, {"shelf_key": shelf_key})
        assert status == 409
        assert response["code"] == "QIT001017"

        status, response = RequestGenerator.GET_book(second_book_key)
        assert status == 200
        assert response["shelf_key"] is None

    def test_refuses_moving_to_the_shelf_it_is_already_on(self):
        """Pedir a estante onde o livro já está é 409, e o livro fica onde estava."""
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        shelf_key = ObjectGenerator.create_shelf(capacity=2)["shelf_key"]
        book_key = ObjectGenerator.create_book(author_key, shelf_key=shelf_key)["book_key"]

        status, response = RequestGenerator.PUT_book_shelf(book_key, {"shelf_key": shelf_key})
        assert status == 409
        assert response["code"] == "QIT001025"

        status, response = RequestGenerator.GET_book(book_key)
        assert status == 200
        assert response["shelf_key"] == shelf_key

    def test_moving_to_its_own_full_shelf_is_not_reported_as_full(self):
        """Na estante cheia com o próprio livro, o 409 é o da mesma estante, e não o da lotação.

        A conferência da mesma estante vem antes da conta: se o livro
        entrasse na conta, a resposta sairia QIT001017 — o motivo errado.
        """
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        shelf_key = ObjectGenerator.create_shelf(capacity=1)["shelf_key"]
        book_key = ObjectGenerator.create_book(author_key, shelf_key=shelf_key)["book_key"]

        status, response = RequestGenerator.PUT_book_shelf(book_key, {"shelf_key": shelf_key})
        assert status == 409
        assert response["code"] == "QIT001025"

    def test_shelf_not_found(self):
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        book_key = ObjectGenerator.create_book(author_key)["book_key"]

        status, response = RequestGenerator.PUT_book_shelf(
            book_key, {"shelf_key": "00000000-0000-0000-0000-000000000000"}
        )
        assert status == 404
        assert response["code"] == "QIT001013"

    def test_book_not_found(self):
        shelf_key = ObjectGenerator.create_shelf()["shelf_key"]

        status, response = RequestGenerator.PUT_book_shelf(
            "00000000-0000-0000-0000-000000000000", {"shelf_key": shelf_key}
        )
        assert status == 404
        assert response["code"] == "QIT001015"
