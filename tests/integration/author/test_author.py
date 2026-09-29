from tests.utils import DbUtils, PayloadGenerator, RequestGenerator
from tests.utils.random_generator import RandomGenerator


class TestAuthor:
    def test_creates_author(self):
        payload = PayloadGenerator.create_author_payload()

        status, response = RequestGenerator.POST_author(payload)
        assert status == 201

        _key = response["author_key"]

        status, response = RequestGenerator.GET_author(_key)
        assert status == 200
        assert response == {
            "author_key": _key,
            "name": "Machado de Assis",
            "nationality": "Brazilian",
            "document_number": payload["document_number"],
        }

    def test_schema_refuses_missing_document_number(self):
        payload = PayloadGenerator.create_author_payload()
        del payload["document_number"]

        status, response = RequestGenerator.POST_author(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_refuses_invalid_document_number(self):
        """Máscara certa e dígitos verificadores errados: 422, e a mensagem não repete o CPF."""
        document_number = "111.222.333-44"
        payload = PayloadGenerator.create_author_payload(document_number=document_number)

        status, response = RequestGenerator.POST_author(payload)
        assert status == 422
        assert response["code"] == "QIT001023"
        assert document_number not in response["description"]

    def test_schema_refuses_document_number_without_mask(self):
        payload = PayloadGenerator.create_author_payload(document_number="11122233344")

        status, response = RequestGenerator.POST_author(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_refuses_duplicated_document_number(self):
        """Dois autores não dividem o mesmo CPF: o segundo cadastro é 409, sem o número na mensagem."""
        document_number = RandomGenerator.generate_cpf()

        status, _response = RequestGenerator.POST_author(
            PayloadGenerator.create_author_payload(document_number=document_number)
        )
        assert status == 201

        status, response = RequestGenerator.POST_author(
            PayloadGenerator.create_author_payload(name="José de Alencar", document_number=document_number)
        )
        assert status == 409
        assert response["code"] == "QIT001024"
        assert document_number not in response["description"]

    def test_not_found(self):
        status, response = RequestGenerator.GET_author("00000000-0000-0000-0000-000000000000")
        assert status == 404
        assert response["code"] == "QIT001012"

    def test_refuses_empty_body(self):
        status, response = RequestGenerator.POST_author({})
        assert status == 400
        assert response["code"] == "QIT000001"

    # O DbUtils.rollback() abaixo não é enfeite e não é automático:
    # todos os testes dividem o MESMO banco, e nada limpa nada entre
    # eles. Qualquer teste cuja asserção dependa de QUANTAS linhas
    # existem — contar, listar, paginar — precisa chamá-lo na primeira
    # linha, ou herda o que os anteriores deixaram. A explicação
    # completa está em tests/utils/db_utils.py.
    def test_get_pages(self):
        DbUtils.rollback()

        for _author in range(3):
            status, _response = RequestGenerator.POST_author(PayloadGenerator.create_author_payload())
            assert status == 201

        status, response = RequestGenerator.GET_authors()
        assert status == 200
        assert len(response["data"]) == 3
        assert response["is_last_page"] is True

        status, response = RequestGenerator.GET_authors({"limit": 2})
        assert status == 200
        assert len(response["data"]) == 2
        assert response["is_last_page"] is False

        status, response = RequestGenerator.GET_authors({"limit": 2, "page": 1})
        assert status == 200
        assert len(response["data"]) == 1
        assert response["is_last_page"] is True
