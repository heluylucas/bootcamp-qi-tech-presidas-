from tests.utils import ObjectGenerator, RequestGenerator
from tests.utils.mock_utils import Mock


class TestBookGet:
    def test_not_found(self):
        status, response = RequestGenerator.GET_book("00000000-0000-0000-0000-000000000000")
        assert status == 404
        assert response["code"] == "QIT001015"

    def test_list_filters_by_shelf(self):
        """O filtro `shelf_key` traz só os livros daquela estante.

        Não precisa de DbUtils.rollback(): a estante nasce neste teste, e
        nenhum teste anterior pôs livro nela.
        """
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        shelf_key = ObjectGenerator.create_shelf()["shelf_key"]

        book_on_shelf = ObjectGenerator.create_book(author_key, shelf_key=shelf_key)
        ObjectGenerator.create_book(author_key)

        status, response = RequestGenerator.GET_books({"shelf_key": shelf_key})
        assert status == 200
        assert len(response["data"]) == 1
        assert response["data"][0]["book_key"] == book_on_shelf["book_key"]
        assert "status_events" not in response["data"][0]
        assert response["is_last_page"] is True

    def test_list_by_unknown_shelf(self):
        """Filtrar por estante que não existe é 404, e não uma lista vazia."""
        status, response = RequestGenerator.GET_books({"shelf_key": "00000000-0000-0000-0000-000000000000"})
        assert status == 404
        assert response["code"] == "QIT001013"
