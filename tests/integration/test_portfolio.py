import uuid

import pytest

from tests.utils import RequestGenerator
from tests.utils.helpers import (
    AGGRESSIVE,
    CDB,
    CONSERVATIVE,
    FUND,
    IPCA,
    LCI,
    MODERATE,
    PREFIXED,
    SELIC,
    answer_profile,
    create_customer,
)


def customer_with_profile(option: int) -> tuple:
    customer_key = create_customer()
    return customer_key, answer_profile(customer_key, option)


def suggest(customer_key: str, amount: int):
    return RequestGenerator.get_portfolio_suggestion(customer_key, {"amount": str(amount)})


def amounts_by_name(body: dict) -> dict:
    return {item["name"]: item["amount"] for item in body["items"]}


class TestPortfolioSuggestion:
    @pytest.mark.parametrize(
        "option, profile, amount, expected",
        [
            (CONSERVATIVE, "CONSERVATIVE", 1000000, {SELIC: 500000, CDB: 300000, LCI: 200000}),
            (MODERATE, "MODERATE", 1000000, {SELIC: 250000, CDB: 200000, PREFIXED: 200000, IPCA: 200000, FUND: 150000}),
            (MODERATE, "MODERATE", 100001, {SELIC: 25001, CDB: 20000, PREFIXED: 20000, IPCA: 20000, FUND: 15000}),
            (AGGRESSIVE, "AGGRESSIVE", 100003, {SELIC: 10000, PREFIXED: 20000, IPCA: 30000, FUND: 40003}),
        ],
        ids=["conservative_round", "moderate_round", "moderate_leftover", "aggressive_leftover"],
    )
    def test_distribution(self, option, profile, amount, expected):
        customer_key, _ = customer_with_profile(option)

        status, body = suggest(customer_key, amount)

        assert status == 200
        assert body["profile"] == profile
        assert body["amount"] == amount
        assert sum(item["weight_bps"] for item in body["items"]) == 10000
        assert sum(item["amount"] for item in body["items"]) == amount
        assert amounts_by_name(body) == expected

    def test_items_from_largest_weight(self):
        customer_key, _ = customer_with_profile(MODERATE)

        _, body = suggest(customer_key, 1000000)

        weights = [item["weight_bps"] for item in body["items"]]
        assert weights == sorted(weights, reverse=True)

    @pytest.mark.parametrize("option", [CONSERVATIVE, MODERATE, AGGRESSIVE])
    def test_every_product_fits_the_profile(self, option):
        customer_key, assessment = customer_with_profile(option)

        _, body = suggest(customer_key, 1000000)

        for item in body["items"]:
            _, product = RequestGenerator.get_product(item["product_key"])
            assert product["risk_level"] <= assessment["maximum_risk_level"]

    def test_response_format(self):
        customer_key, _ = customer_with_profile(MODERATE)

        _, body = suggest(customer_key, 1000000)

        assert set(body) == {"profile", "amount", "items"}
        for item in body["items"]:
            assert set(item) == {"product_key", "name", "weight_bps", "amount"}
            assert len(item["product_key"]) == 36

    def test_works_without_account_or_balance(self):
        customer_key, _ = customer_with_profile(AGGRESSIVE)

        status, _ = suggest(customer_key, 100000000)

        assert status == 200

    def test_suggestion_is_not_recorded(self):
        customer_key, _ = customer_with_profile(MODERATE)

        first_status, first = suggest(customer_key, 1000000)
        second_status, second = suggest(customer_key, 1000000)

        assert first_status == second_status == 200
        assert first == second

    def test_minimum_amount_is_accepted(self):
        customer_key, _ = customer_with_profile(MODERATE)

        status, _ = suggest(customer_key, 100000)

        assert status == 200


class TestPortfolioSuggestionRefusals:
    def test_without_profile(self):
        customer_key = create_customer()

        status, body = suggest(customer_key, 1000000)

        assert status == 409
        assert body["code"] == "PPP004005"

    def test_below_minimum_amount(self):
        customer_key, _ = customer_with_profile(MODERATE)

        status, body = suggest(customer_key, 99999)

        assert status == 422
        assert body["code"] == "PPP006001"

    def test_profile_is_checked_before_amount(self):
        customer_key = create_customer()

        status, body = suggest(customer_key, 99999)

        assert status == 409
        assert body["code"] == "PPP004005"

    def test_customer_not_found(self):
        status, body = suggest(str(uuid.uuid4()), 1000000)

        assert status == 404
        assert body["code"] == "PPP001001"

    @pytest.mark.parametrize(
        "query_params",
        [
            None,
            {"amount": "abc"},
            {"amount": "10.5"},
            {"amount": "-100"},
            {"amount": ""},
            {"amount": "1000000", "page": "1"},
        ],
        ids=["missing", "text", "decimal", "negative", "empty", "unknown_param"],
    )
    def test_invalid_amount(self, query_params):
        customer_key, _ = customer_with_profile(MODERATE)

        status, body = RequestGenerator.get_portfolio_suggestion(customer_key, query_params)

        assert status == 400
        assert body["code"] == "PPP000001"
