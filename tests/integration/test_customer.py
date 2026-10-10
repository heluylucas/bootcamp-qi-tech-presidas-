import uuid
from datetime import date

import pytest

from tests.utils import RandomGenerator, RequestGenerator


def customer_payload(**overrides) -> dict:
    payload = {
        "name": "Ana Silva",
        "document_number": RandomGenerator.generate_cpf(),
        "birth_date": "1990-05-17",
    }
    payload.update(overrides)
    return payload


def masked(cpf: str) -> str:
    """'123.456.789-09' vira '***.456.789-**' (RN-GER-10)."""
    return f"***{cpf[3:11]}-**"


def without_punctuation(cpf: str) -> str:
    return cpf.replace(".", "").replace("-", "")


def with_wrong_check_digit(cpf: str) -> str:
    last_digit = (int(cpf[-1]) + 1) % 10
    return f"{cpf[:-1]}{last_digit}"


class TestCreateCustomer:
    def test_create_customer(self):
        payload = customer_payload()

        status, body = RequestGenerator.post_customer(payload)

        assert status == 201
        assert len(body["customer_key"]) == 36
        assert body["name"] == payload["name"]
        assert body["document_number"] == masked(payload["document_number"])
        assert body["birth_date"] == payload["birth_date"]
        assert "created_at" in body

    def test_create_customer_without_punctuation(self):
        cpf = RandomGenerator.generate_cpf()

        status, body = RequestGenerator.post_customer(customer_payload(document_number=without_punctuation(cpf)))

        assert status == 201
        assert body["document_number"] == masked(cpf)

    def test_invalid_check_digit(self):
        cpf = with_wrong_check_digit(RandomGenerator.generate_cpf())

        status, body = RequestGenerator.post_customer(customer_payload(document_number=cpf))

        assert status == 422
        assert body["code"] == "PPP001003"

    def test_all_digits_equal(self):
        status, body = RequestGenerator.post_customer(customer_payload(document_number="111.111.111-11"))

        assert status == 422
        assert body["code"] == "PPP001003"

    def test_duplicate_document_number(self):
        payload = customer_payload()
        RequestGenerator.post_customer(payload)

        status, body = RequestGenerator.post_customer(customer_payload(document_number=payload["document_number"]))

        assert status == 409
        assert body["code"] == "PPP001002"

    def test_duplicate_document_number_with_different_punctuation(self):
        cpf = RandomGenerator.generate_cpf()
        RequestGenerator.post_customer(customer_payload(document_number=cpf))

        status, body = RequestGenerator.post_customer(customer_payload(document_number=without_punctuation(cpf)))

        assert status == 409
        assert body["code"] == "PPP001002"

    def test_underage(self):
        # Dia 1 do mês, 17 anos atrás: menor de idade em qualquer dia do ano,
        # e sem o risco de cair num 29 de fevereiro que não existe.
        birth_date = date.today().replace(year=date.today().year - 17, day=1)

        status, body = RequestGenerator.post_customer(customer_payload(birth_date=birth_date.isoformat()))

        assert status == 422
        assert body["code"] == "PPP001004"

    def test_birth_date_in_future(self):
        birth_date = date(date.today().year + 1, 1, 1)

        status, body = RequestGenerator.post_customer(customer_payload(birth_date=birth_date.isoformat()))

        assert status == 422
        assert body["code"] == "PPP001004"

    @pytest.mark.parametrize("field", ["name", "document_number", "birth_date"])
    def test_missing_field(self, field):
        payload = customer_payload()
        del payload[field]

        status, body = RequestGenerator.post_customer(payload)

        assert status == 400
        assert body["code"] == "PPP000001"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"extra": "campo fora do contrato"},
            {"name": 123},
            {"name": "Al"},
            {"name": "A" * 121},
            {"name": "  Ana Silva  "},
            {"document_number": "123.456.78909"},
            {"document_number": "1234567890"},
            {"birth_date": 19900517},
            {"birth_date": "17/05/1990"},
            {"birth_date": "2000-02-30"},
        ],
    )
    def test_malformed_payload(self, overrides):
        status, body = RequestGenerator.post_customer(customer_payload(**overrides))

        assert status == 400
        assert body["code"] == "PPP000001"


class TestGetCustomer:
    def test_get_customer(self):
        payload = customer_payload()
        _, created = RequestGenerator.post_customer(payload)

        status, body = RequestGenerator.get_customer(created["customer_key"])

        assert status == 200
        assert body == created
        assert body["document_number"] == masked(payload["document_number"])

    def test_customer_not_found(self):
        status, body = RequestGenerator.get_customer(str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP001001"
