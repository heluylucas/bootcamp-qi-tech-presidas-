from tests.utils import DbUtils, PayloadGenerator, RequestGenerator
from tests.utils.random_generator import RandomGenerator


class TestMember:
    """O leitor: quem pode levar um livro emprestado."""

    def test_creates_member(self):
        payload = PayloadGenerator.create_member_payload()

        status, response = RequestGenerator.POST_member(payload)
        assert status == 201

        _key = response["member_key"]

        status, response = RequestGenerator.GET_member(_key)
        assert status == 200
        assert response == {
            "member_key": _key,
            "name": "Capitu Pádua",
            "email": payload["email"],
            "document_number": payload["document_number"],
        }

    def test_not_found(self):
        status, response = RequestGenerator.GET_member("00000000-0000-0000-0000-000000000000")
        assert status == 404
        assert response["code"] == "QIT001021"

    def test_refuses_duplicated_email(self):
        """Dois leitores não dividem o mesmo e-mail: o segundo cadastro é 409."""
        first_payload = PayloadGenerator.create_member_payload()
        status, _response = RequestGenerator.POST_member(first_payload)
        assert status == 201

        second_payload = PayloadGenerator.create_member_payload(name="Bento Santiago", email=first_payload["email"])

        status, response = RequestGenerator.POST_member(second_payload)
        assert status == 409
        assert response["code"] == "QIT001022"

    def test_schema_refuses_malformed_email(self):
        payload = PayloadGenerator.create_member_payload(email="capitu.example.com")

        status, response = RequestGenerator.POST_member(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_schema_refuses_missing_document_number(self):
        payload = PayloadGenerator.create_member_payload()
        del payload["document_number"]

        status, response = RequestGenerator.POST_member(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_refuses_invalid_document_number(self):
        """Máscara certa e dígitos verificadores errados: 422, e a mensagem não repete o CPF."""
        document_number = "111.222.333-44"
        payload = PayloadGenerator.create_member_payload(document_number=document_number)

        status, response = RequestGenerator.POST_member(payload)
        assert status == 422
        assert response["code"] == "QIT001023"
        assert document_number not in response["description"]

    def test_schema_refuses_document_number_without_mask(self):
        payload = PayloadGenerator.create_member_payload(document_number="11122233344")

        status, response = RequestGenerator.POST_member(payload)
        assert status == 400
        assert response["code"] == "QIT000001"

    def test_refuses_duplicated_document_number(self):
        """Dois leitores não dividem o mesmo CPF: o segundo cadastro é 409, sem o número na mensagem."""
        document_number = RandomGenerator.generate_cpf()

        status, _response = RequestGenerator.POST_member(
            PayloadGenerator.create_member_payload(document_number=document_number)
        )
        assert status == 201

        status, response = RequestGenerator.POST_member(
            PayloadGenerator.create_member_payload(name="Bento Santiago", document_number=document_number)
        )
        assert status == 409
        assert response["code"] == "QIT001024"
        assert document_number not in response["description"]

    def test_same_document_number_in_author_and_member(self):
        """O CPF é único por tabela: a mesma pessoa pode ser autora e leitora."""
        document_number = RandomGenerator.generate_cpf()

        status, _response = RequestGenerator.POST_author(
            PayloadGenerator.create_author_payload(document_number=document_number)
        )
        assert status == 201

        status, response = RequestGenerator.POST_member(
            PayloadGenerator.create_member_payload(document_number=document_number)
        )
        assert status == 201

        status, response = RequestGenerator.GET_member(response["member_key"])
        assert status == 200
        assert response["document_number"] == document_number

    def test_get_pages(self):
        DbUtils.rollback()

        for _member in range(3):
            status, _response = RequestGenerator.POST_member(PayloadGenerator.create_member_payload())
            assert status == 201

        status, response = RequestGenerator.GET_members()
        assert status == 200
        assert len(response["data"]) == 3
        assert response["is_last_page"] is True

        status, response = RequestGenerator.GET_members({"limit": 2})
        assert status == 200
        assert len(response["data"]) == 2
        assert response["is_last_page"] is False

        status, response = RequestGenerator.GET_members({"limit": 2, "page": 1})
        assert status == 200
        assert len(response["data"]) == 1
        assert response["is_last_page"] is True
