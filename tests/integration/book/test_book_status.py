from tests.utils import ObjectGenerator, RequestGenerator
from tests.utils.mock_utils import Mock


class TestBookStatus:
    """Emprestar e devolver: AVAILABLE → BORROWED → AVAILABLE, e só.

    Emprestar agora diz PARA QUEM: o corpo leva o `member_key`, e o livro
    passa a devolver esse leitor até voltar. A parte da regra que só
    aparece com dois empréstimos ao mesmo tempo — a trava do
    `SELECT ... FOR UPDATE` na linha do livro — não tem teste aqui; o
    porquê dela está no BookController._get_locked_book.
    """

    def test_borrows_and_returns(self):
        """Emprestar grava o leitor; devolver limpa. O GET confirma os dois."""
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        book_key = ObjectGenerator.create_book(author_key)["book_key"]
        member_key = ObjectGenerator.create_member()["member_key"]

        status, response = RequestGenerator.PUT_book_borrow(book_key, {"member_key": member_key})
        assert status == 200
        assert response == {"book_key": book_key, "status": "BORROWED"}

        status, response = RequestGenerator.GET_book(book_key)
        assert status == 200
        assert response["status"] == "BORROWED"
        assert response["member_key"] == member_key

        status, response = RequestGenerator.PUT_book_return(book_key)
        assert status == 200
        assert response == {"book_key": book_key, "status": "AVAILABLE"}

        status, response = RequestGenerator.GET_book(book_key)
        assert status == 200
        assert response["status"] == "AVAILABLE"
        assert response["member_key"] is None

    def test_refuses_borrowing_twice(self):
        """Emprestar o que já está emprestado é 409, e o leitor não é trocado.

        O segundo pedido vem de OUTRO leitor. Se ele passasse, o livro
        ficaria no nome de quem não está com ele.
        """
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        book_key = ObjectGenerator.create_book(author_key)["book_key"]
        first_member_key = ObjectGenerator.create_member()["member_key"]
        second_member_key = ObjectGenerator.create_member()["member_key"]

        status, _response = RequestGenerator.PUT_book_borrow(book_key, {"member_key": first_member_key})
        assert status == 200

        status, response = RequestGenerator.PUT_book_borrow(book_key, {"member_key": second_member_key})
        assert status == 409
        assert response["code"] == "QIT001020"

        status, response = RequestGenerator.GET_book(book_key)
        assert response["status"] == "BORROWED"
        assert response["member_key"] == first_member_key

    def test_refuses_returning_available_book(self):
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        book_key = ObjectGenerator.create_book(author_key)["book_key"]

        status, response = RequestGenerator.PUT_book_return(book_key)
        assert status == 409
        assert response["code"] == "QIT001020"

    def test_book_not_found(self):
        member_key = ObjectGenerator.create_member()["member_key"]

        status, response = RequestGenerator.PUT_book_borrow(
            "00000000-0000-0000-0000-000000000000", {"member_key": member_key}
        )
        assert status == 404
        assert response["code"] == "QIT001015"

    def test_borrow_with_unknown_member(self):
        """Leitor que não existe é 404, e o livro continua disponível e sem leitor."""
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        book_key = ObjectGenerator.create_book(author_key)["book_key"]

        status, response = RequestGenerator.PUT_book_borrow(
            book_key, {"member_key": "00000000-0000-0000-0000-000000000000"}
        )
        assert status == 404
        assert response["code"] == "QIT001021"

        status, response = RequestGenerator.GET_book(book_key)
        assert status == 200
        assert response["status"] == "AVAILABLE"
        assert response["member_key"] is None

    def test_schema_refuses_borrow_without_member(self):
        """Emprestar sem dizer para quem é recusado pelo schema, antes do controller."""
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        book_key = ObjectGenerator.create_book(author_key)["book_key"]

        status, response = RequestGenerator.PUT_book_borrow(book_key, {})
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_creating_a_book_records_the_first_status_event(self):
        """O cadastro já deixa a primeira linha do histórico: AVAILABLE.

        A forma inteira do GET /book/{book_key}, com o `status_events`,
        é conferida no test_book_create; aqui fica só a trilha.
        """
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        book_key = ObjectGenerator.create_book(author_key)["book_key"]

        status, response = RequestGenerator.GET_book(book_key)
        assert status == 200
        assert extract_trail(response) == ["AVAILABLE"]

    def test_borrow_and_return_record_one_event_each_in_order(self):
        """Emprestar e devolver acrescentam um evento cada, e a trilha sai na ordem."""
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        book_key = ObjectGenerator.create_book(author_key)["book_key"]
        member_key = ObjectGenerator.create_member()["member_key"]

        status, _response = RequestGenerator.PUT_book_borrow(book_key, {"member_key": member_key})
        assert status == 200

        status, response = RequestGenerator.GET_book(book_key)
        assert status == 200
        assert response["status"] == "BORROWED"
        assert extract_trail(response) == ["AVAILABLE", "BORROWED"]

        status, _response = RequestGenerator.PUT_book_return(book_key)
        assert status == 200

        status, response = RequestGenerator.GET_book(book_key)
        assert status == 200
        assert response["status"] == "AVAILABLE"
        assert extract_trail(response) == ["AVAILABLE", "BORROWED", "AVAILABLE"]

        event_datetimes = extract_event_datetimes(response)
        assert event_datetimes == sorted(event_datetimes)

    def test_refused_transition_records_no_event(self):
        """Transição recusada com 409 não deixa linha no histórico.

        São as duas recusas da regra: devolver o que está disponível e
        emprestar o que já está emprestado. Depois de cada uma, a trilha
        é a mesma de antes do pedido.
        """
        Mock().clear()

        author_key = ObjectGenerator.create_author()["author_key"]
        book_key = ObjectGenerator.create_book(author_key)["book_key"]
        first_member_key = ObjectGenerator.create_member()["member_key"]
        second_member_key = ObjectGenerator.create_member()["member_key"]

        status, response = RequestGenerator.PUT_book_return(book_key)
        assert status == 409
        assert response["code"] == "QIT001020"

        status, response = RequestGenerator.GET_book(book_key)
        assert status == 200
        assert extract_trail(response) == ["AVAILABLE"]

        status, _response = RequestGenerator.PUT_book_borrow(book_key, {"member_key": first_member_key})
        assert status == 200

        status, response = RequestGenerator.PUT_book_borrow(book_key, {"member_key": second_member_key})
        assert status == 409
        assert response["code"] == "QIT001020"

        status, response = RequestGenerator.GET_book(book_key)
        assert status == 200
        assert extract_trail(response) == ["AVAILABLE", "BORROWED"]


def extract_trail(book_response: dict) -> list:
    trail = []
    for status_event in book_response["status_events"]:
        trail.append(status_event["status"])

    return trail


def extract_event_datetimes(book_response: dict) -> list:
    event_datetimes = []
    for status_event in book_response["status_events"]:
        event_datetimes.append(status_event["event_datetime"])

    return event_datetimes
