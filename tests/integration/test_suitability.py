import uuid
from datetime import date

import pytest

from tests.utils import RandomGenerator, RequestGenerator


QUESTION_CODES = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]


def create_customer() -> str:
    payload = {"name": "Ana Silva", "document_number": RandomGenerator.generate_cpf(), "birth_date": "1990-05-17"}
    _, body = RequestGenerator.post_customer(payload)
    return body["customer_key"]


def answers(default: int, **overrides) -> dict:
    """As sete respostas com a mesma opção, trocando só as que vierem em overrides (ex.: Q3=1)."""
    items = []
    for code in QUESTION_CODES:
        items.append({"question_code": code, "option_code": overrides.get(code, default)})
    return {"answers": items}


def add_two_years(day: date) -> date:
    # 29/02 + 24 meses cai num ano sem 29/02: vira 28/02.
    try:
        return day.replace(year=day.year + 2)
    except ValueError:
        return day.replace(year=day.year + 2, day=28)


class TestListQuestions:
    def test_list_questions(self):
        status, body = RequestGenerator.get_suitability_questions()

        assert status == 200
        assert [question["code"] for question in body["items"]] == QUESTION_CODES

        for question in body["items"]:
            assert question["text"]
            assert question["dimension"]
            assert [option["code"] for option in question["options"]] == [1, 2, 3, 4]
            assert "id" not in question

    def test_points_are_not_exposed(self):
        """Se os pontos aparecessem, o cliente escolheria o perfil em vez de responder."""
        _, body = RequestGenerator.get_suitability_questions()

        for question in body["items"]:
            for option in question["options"]:
                assert "points" not in option
                assert "id" not in option


class TestSubmitSuitability:
    @pytest.mark.parametrize(
        "option, expected_score, expected_profile",
        [
            (1, 7, "CONSERVATIVE"),
            (2, 14, "MODERATE"),
            (3, 21, "AGGRESSIVE"),
            (4, 28, "AGGRESSIVE"),
        ],
    )
    def test_profile_by_score(self, option, expected_score, expected_profile):
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, answers(option))

        assert status == 201
        assert body["score"] == expected_score
        assert body["profile"] == expected_profile
        assert body["forced_by_rule"] is False

    def test_upper_limit_of_conservative(self):
        # Q1 = 1 e o resto 2: 13 pontos, ainda Conservador (sem a trava, que é só Q3/Q5).
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, answers(2, Q1=1))

        assert status == 201
        assert body["score"] == 13
        assert body["profile"] == "CONSERVATIVE"

    def test_upper_limit_of_moderate(self):
        # Seis respostas 3 e a Q7 = 2: 20 pontos, ainda Moderado.
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, answers(3, Q7=2))

        assert status == 201
        assert body["score"] == 20
        assert body["profile"] == "MODERATE"

    @pytest.mark.parametrize("question_code", ["Q3", "Q5"])
    def test_safety_lock_forces_conservative(self, question_code):
        """RN-SUI-04: 'resgataria tudo' (Q3) ou 'preciso a qualquer momento' (Q5) vira Conservador."""
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, answers(4, **{question_code: 1}))

        assert status == 201
        assert body["score"] == 25
        assert body["profile"] == "CONSERVATIVE"
        assert body["forced_by_rule"] is True

    def test_response_format(self):
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, answers(2))

        assert status == 201
        assert len(body["assessment_key"]) == 36
        assert "id" not in body
        assert "created_at" in body
        assert body["answers"] == answers(2)["answers"]

    def test_valid_for_24_months(self):
        # TODO(módulo 4): quando a data de movimento entrar, comparar com ela
        # (GET /internal/business_date) em vez da data do created_at.
        customer_key = create_customer()

        _, body = RequestGenerator.post_suitability(customer_key, answers(2))

        answered_on = date.fromisoformat(body["created_at"][:10])
        assert body["valid_until"] == add_two_years(answered_on).isoformat()

    @pytest.mark.parametrize(
        "payload",
        [
            {"answers": answers(2)["answers"][:6]},
            {"answers": answers(2)["answers"] + [{"question_code": "Q1", "option_code": 3}]},
            {"answers": answers(2)["answers"] + [{"question_code": "Q9", "option_code": 1}]},
            {"answers": answers(2)["answers"][:6] + [{"question_code": "Q9", "option_code": 1}]},
            {"answers": []},
        ],
        ids=["missing_question", "repeated_question", "unknown_question", "unknown_instead_of_q7", "empty"],
    )
    def test_incomplete_answers(self, payload):
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, payload)

        assert status == 422
        assert body["code"] == "PPP004002"

    @pytest.mark.parametrize("option", [0, 5])
    def test_invalid_option(self, option):
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, answers(2, Q4=option))

        assert status == 422
        assert body["code"] == "PPP004003"

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"answers": "Q1"},
            {"answers": answers(2)["answers"], "extra": "campo fora do contrato"},
            {"answers": [{"question_code": "Q1"}]},
            {"answers": [{"question_code": "Q1", "option_code": 1, "points": 4}]},
            {"answers": [{"question_code": "Q1", "option_code": "1"}]},
            {"answers": [{"question_code": 1, "option_code": 1}]},
            {"answers": [{"question_code": "Q1", "option_code": 1.5}]},
        ],
    )
    def test_malformed_payload(self, payload):
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, payload)

        assert status == 400
        assert body["code"] == "PPP000001"

    def test_customer_not_found(self):
        status, body = RequestGenerator.post_suitability(str(uuid.uuid4()), answers(2))

        assert status == 404
        assert body["code"] == "PPP001001"

    def test_refused_answers_record_nothing(self):
        customer_key = create_customer()
        RequestGenerator.post_suitability(customer_key, answers(2, Q4=5))

        status, body = RequestGenerator.get_suitability(customer_key)

        assert status == 404
        assert body["code"] == "PPP004001"


class TestCurrentSuitability:
    def test_get_current(self):
        customer_key = create_customer()
        _, created = RequestGenerator.post_suitability(customer_key, answers(3))

        status, body = RequestGenerator.get_suitability(customer_key)

        assert status == 200
        assert body == created

    def test_never_answered(self):
        customer_key = create_customer()

        status, body = RequestGenerator.get_suitability(customer_key)

        assert status == 404
        assert body["code"] == "PPP004001"

    def test_customer_not_found(self):
        status, body = RequestGenerator.get_suitability(str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP001001"

    def test_retake_changes_current_profile(self):
        customer_key = create_customer()
        RequestGenerator.post_suitability(customer_key, answers(1))
        _, retaken = RequestGenerator.post_suitability(customer_key, answers(4))

        status, body = RequestGenerator.get_suitability(customer_key)

        assert status == 200
        assert body["assessment_key"] == retaken["assessment_key"]
        assert body["profile"] == "AGGRESSIVE"


class TestSuitabilityHistory:
    def test_retake_keeps_history(self):
        """RN-SUI-06: refazer cria uma avaliação nova e a antiga continua guardada (R4)."""
        customer_key = create_customer()
        _, first = RequestGenerator.post_suitability(customer_key, answers(1))
        _, second = RequestGenerator.post_suitability(customer_key, answers(4))

        status, body = RequestGenerator.get_suitabilities(customer_key)

        assert status == 200
        assert [item["assessment_key"] for item in body["items"]] == [
            second["assessment_key"],
            first["assessment_key"],
        ]
        assert [item["profile"] for item in body["items"]] == ["AGGRESSIVE", "CONSERVATIVE"]

    def test_empty_history(self):
        customer_key = create_customer()

        status, body = RequestGenerator.get_suitabilities(customer_key)

        assert status == 200
        assert body == {"items": []}

    def test_customer_not_found(self):
        status, body = RequestGenerator.get_suitabilities(str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP001001"
