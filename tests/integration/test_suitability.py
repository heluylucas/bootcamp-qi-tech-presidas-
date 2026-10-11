import uuid
from datetime import datetime

import pytest

from tests.utils import RequestGenerator
from tests.utils.helpers import create_customer


QUESTION_CODES = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]


def answers(default: int, **overrides) -> dict:
    items = []
    for code in QUESTION_CODES:
        items.append({"question_code": code, "option_code": overrides.get(code, default)})
    return {"answers": items}


def add_two_years(moment: datetime) -> datetime:
    try:
        return moment.replace(year=moment.year + 2)
    except ValueError:
        return moment.replace(year=moment.year + 2, day=28)


def parse_utc(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


class TestListQuestions:
    def test_list_questions(self):
        status, body = RequestGenerator.get_suitability_questions()

        assert status == 200
        assert [question["code"] for question in body["items"]] == QUESTION_CODES

        for question in body["items"]:
            assert question["text"]
            assert question["dimension"]
            assert [option["code"] for option in question["options"]] == [1, 2, 3, 4]


class TestSubmitSuitability:
    @pytest.mark.parametrize(
        "option, expected_score, expected_profile, expected_maximum_risk",
        [
            (1, 7, "CONSERVATIVE", 2),
            (2, 14, "MODERATE", 3),
            (3, 21, "AGGRESSIVE", 5),
            (4, 28, "AGGRESSIVE", 5),
        ],
    )
    def test_profile_by_score(self, option, expected_score, expected_profile, expected_maximum_risk):
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, answers(option))

        assert status == 201
        assert body["score"] == expected_score
        assert body["profile"] == expected_profile
        assert body["maximum_risk_level"] == expected_maximum_risk
        assert body["forced_by_rule"] is False

    def test_upper_limit_of_conservative(self):
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, answers(2, Q1=1))

        assert status == 201
        assert body["score"] == 13
        assert body["profile"] == "CONSERVATIVE"

    def test_upper_limit_of_moderate(self):
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, answers(3, Q7=2))

        assert status == 201
        assert body["score"] == 20
        assert body["profile"] == "MODERATE"

    @pytest.mark.parametrize("question_code", ["Q3", "Q5"])
    def test_safety_lock_forces_conservative(self, question_code):
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, answers(4, **{question_code: 1}))

        assert status == 201
        assert body["score"] == 25
        assert body["profile"] == "CONSERVATIVE"
        assert body["maximum_risk_level"] == 2
        assert body["forced_by_rule"] is True

    def test_response_format(self):
        customer_key = create_customer()

        status, body = RequestGenerator.post_suitability(customer_key, answers(2))

        assert status == 201
        assert len(body["assessment_key"]) == 36
        assert "created_at" in body
        assert body["answers"] == answers(2)["answers"]

    def test_valid_for_24_months(self):
        customer_key = create_customer()

        _, body = RequestGenerator.post_suitability(customer_key, answers(2))

        valid_until = parse_utc(body["valid_until"])
        expected = add_two_years(parse_utc(body["created_at"]))
        assert abs((valid_until - expected).total_seconds()) <= 5

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
