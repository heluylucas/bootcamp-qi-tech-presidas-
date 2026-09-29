from tests.utils import ObjectGenerator, PayloadGenerator, RandomGenerator, RequestGenerator
from tests.utils.mock_generator import CatalogMock
from tests.utils.mock_utils import Mock


class TestBookCreate:
    """O POST /book, a rota que atravessa a fronteira.

    Todo teste que toca o catálogo segue o ritual do
    tests/utils/mock_generator.py: limpa o mock, ensina a resposta, chama
    a API e, no fim, pergunta ao mock o que ele recebeu. A última parte é
    o que prova a fronteira — que a API chamou o catálogo, ou que NÃO
    chamou, quando a regra manda parar antes.
    """

    def test_creates_book_with_catalog_data(self):
        """O catálogo responde 200, e o livro nasce com o título, o ano e as páginas dele.

        O cliente mandou só o ISBN e o autor. Todo o resto do livro veio
        do corpo que o mock foi ensinado a devolver — e o retrieve no
        fim confere que houve exatamente UMA chamada, levando o
        INTERNAL-TOKEN: é o connector se apresentando a quem ele chama.
        """
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        isbn = RandomGenerator.generate_isbn()

        CatalogMock.GET_isbn(isbn=isbn)

        payload = PayloadGenerator.create_book_payload(author_key, isbn=isbn)
        status, response = RequestGenerator.POST_book(payload)
        assert status == 201

        _key = response["book_key"]
        assert response == {"book_key": _key, "status": "AVAILABLE"}

        status, response = RequestGenerator.GET_book(_key)
        assert status == 200

        event_datetime = response["status_events"][0]["event_datetime"]
        assert event_datetime is not None
        assert response == {
            "book_key": _key,
            "title": "Dom Casmurro",
            "isbn": isbn,
            "year": 1899,
            "pages": 256,
            "author_key": author_key,
            "shelf_key": None,
            "status": "AVAILABLE",
            "member_key": None,
            "status_events": [
                {"status": "AVAILABLE", "event_datetime": event_datetime},
            ],
        }

        received_requests = Mock().retrieve_requests("GET", f"/catalog/isbn/{isbn}")
        assert len(received_requests) == 1
        sent_token = received_requests[0]["headers"]["INTERNAL-TOKEN"]
        assert len(sent_token) == 1
        assert sent_token[0] != ""

    def test_duplicated_isbn_does_not_call_catalog(self):
        """ISBN que já está aqui para aqui, antes da fronteira.

        O primeiro cadastro passa pelo catálogo. Depois o mock é limpo e
        ensinado a responder 200 para qualquer ISBN — e mesmo assim não
        recebe nada: a API responde o QIT001016 sem incomodar o catálogo.
        """
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        isbn = RandomGenerator.generate_isbn()

        CatalogMock.GET_isbn(isbn=isbn)
        status, _response = RequestGenerator.POST_book(PayloadGenerator.create_book_payload(author_key, isbn=isbn))
        assert status == 201

        Mock().clear()
        CatalogMock.GET_isbn()

        status, response = RequestGenerator.POST_book(PayloadGenerator.create_book_payload(author_key, isbn=isbn))
        assert status == 409
        assert response["code"] == "QIT001016"

        received_requests = Mock().retrieve_requests("GET", f"/catalog/isbn/{isbn}")
        assert received_requests == []

    def test_author_not_found_does_not_call_catalog(self):
        Mock().clear()
        CatalogMock.GET_isbn()

        isbn = RandomGenerator.generate_isbn()
        payload = PayloadGenerator.create_book_payload("00000000-0000-0000-0000-000000000000", isbn=isbn)

        status, response = RequestGenerator.POST_book(payload)
        assert status == 404
        assert response["code"] == "QIT001012"

        received_requests = Mock().retrieve_requests("GET", f"/catalog/isbn/{isbn}")
        assert received_requests == []

    def test_isbn_not_found_in_catalog(self):
        """O catálogo diz 404, e a API diz 404 com o código DELA.

        O QIT001018, e não o QIT001015: quem não conhece o ISBN é o
        catálogo, e nenhum livro foi criado aqui.
        """
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        isbn = RandomGenerator.generate_isbn()

        CatalogMock.GET_isbn_not_found(isbn=isbn)

        status, response = RequestGenerator.POST_book(PayloadGenerator.create_book_payload(author_key, isbn=isbn))
        assert status == 404
        assert response["code"] == "QIT001018"

        verification = Mock().verify(f"/catalog/isbn/{isbn}", 1, 1)
        assert verification.status_code == 202

    def test_catalog_without_answer(self):
        """A conexão cai: 502 com o QIT001019, e não 500.

        O mock recebeu a chamada — o verify confere — e não respondeu.
        É o caso que prova o `except` do controller: sem ele, a exceção
        do `requests` virava o 500 genérico.
        """
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        isbn = RandomGenerator.generate_isbn()

        CatalogMock.GET_isbn_connection_dropped(isbn=isbn)

        status, response = RequestGenerator.POST_book(PayloadGenerator.create_book_payload(author_key, isbn=isbn))
        assert status == 502
        assert response["code"] == "QIT001019"

        verification = Mock().verify(f"/catalog/isbn/{isbn}", 1, 1)
        assert verification.status_code == 202

    def test_catalog_server_error(self):
        """O catálogo responde 500: também é 502, com o mesmo código.

        Diferente da conexão caída, aqui HOUVE resposta — só que não uma
        que dê pra usar. Para quem chama a API, os dois casos pedem a
        mesma coisa: tentar de novo depois.
        """
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        isbn = RandomGenerator.generate_isbn()

        CatalogMock.GET_isbn_server_error(isbn=isbn)

        status, response = RequestGenerator.POST_book(PayloadGenerator.create_book_payload(author_key, isbn=isbn))
        assert status == 502
        assert response["code"] == "QIT001019"

    def test_schema_refuses_malformed_isbn(self):
        """ISBN-13 são treze dígitos, e o `pattern` do schema cobra.

        O mock nem é ensinado: pedido torto morre no schema, antes de
        existir qualquer chance de chamar o catálogo.
        """
        for malformed_isbn in ["978000000000", "97800000000000", "978-85-000-0000", "978abcdefghij"]:
            payload = PayloadGenerator.create_book_payload("00000000-0000-0000-0000-000000000000", isbn=malformed_isbn)

            status, response = RequestGenerator.POST_book(payload)
            assert status == 400, f"ISBN '{malformed_isbn}' was accepted"
            assert response["code"] == "QIT000001"

    def test_refuses_creating_in_full_shelf(self):
        """A regra de lotação vale também no cadastro, não só na mudança de estante."""
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        shelf_key = ObjectGenerator.create_shelf(capacity=1)["shelf_key"]

        ObjectGenerator.create_book(author_key, shelf_key=shelf_key)

        isbn = RandomGenerator.generate_isbn()
        CatalogMock.GET_isbn(isbn=isbn)

        payload = PayloadGenerator.create_book_payload(author_key, isbn=isbn, shelf_key=shelf_key)
        status, response = RequestGenerator.POST_book(payload)
        assert status == 409
        assert response["code"] == "QIT001017"
