import calendar
import uuid
from datetime import date
from decimal import ROUND_DOWN, Decimal

import pytest

from tests.utils import RequestGenerator
from tests.utils.helpers import (
    CDB,
    CONSERVATIVE,
    FUND,
    LCI,
    MODERATE,
    answer_profile,
    apply,
    balance_of,
    business_date,
    close_day,
    create_customer,
    investor,
    product,
    product_key,
)


EIGHT_PLACES = Decimal("0.00000001")


def unit_price(name: str) -> Decimal:
    return Decimal(product(name)["price"]["unit_price"])


def redeem(customer_key: str, account_key: str, name: str, amount: int = None, idempotency_key: str = None):
    payload = {"product_key": product_key(name), "side": "REDEEM"}
    payload.update({"amount": amount} if amount is not None else {"redeem_all": True})
    return RequestGenerator.post_investment_order(customer_key, account_key, payload, idempotency_key or str(uuid.uuid4()))


def closed_account() -> tuple:
    customer_key = create_customer()
    answer_profile(customer_key, MODERATE)
    _, account = RequestGenerator.post_account(customer_key)
    closing = {"status": "CLOSED", "reason": "Pedido do cliente"}
    RequestGenerator.patch_account(customer_key, account["account_key"], closing)
    return customer_key, account["account_key"]


def plus_months(day: date, months: int) -> date:
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


class TestApply:
    def test_apply_debits_account_and_returns_order(self):
        customer_key, account_key = investor()
        price = unit_price(CDB)

        status, body = apply(customer_key, account_key, CDB, 10000)

        assert status == 201
        assert len(body["investment_order_key"]) == 36
        assert len(body["transaction_key"]) == 36
        assert body["product_key"] == product_key(CDB)
        assert body["side"] == "APPLY"
        assert body["amount"] == 10000
        assert body["status"] == "EXECUTED"
        assert body["source"] == "CUSTOMER"
        assert body["unit_price"] == f"{price:.8f}"
        assert body["quantity"] == f"{(Decimal(100) / price).quantize(EIGHT_PLACES, ROUND_DOWN):.8f}"
        assert body["maturity_date"] is None
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000

    def test_lci_records_maturity_date(self):
        customer_key, account_key = investor(CONSERVATIVE)

        status, body = apply(customer_key, account_key, LCI, 10000)

        assert status == 201
        assert body["maturity_date"] == plus_months(business_date(), 12).isoformat()

    def test_minimum_application_is_accepted(self):
        customer_key, account_key = investor()

        status, _ = apply(customer_key, account_key, CDB, 5000)

        assert status == 201

    def test_whole_balance_can_be_applied(self):
        customer_key, account_key = investor(balance=10000)

        status, _ = apply(customer_key, account_key, CDB, 10000)

        assert status == 201
        assert balance_of(customer_key, account_key) == 0

    def test_product_at_profile_risk_limit_is_accepted(self):
        customer_key, account_key = investor(MODERATE)

        status, _ = apply(customer_key, account_key, FUND, 10000)

        assert status == 201


class TestApplyIdempotency:
    def test_same_key_and_body_returns_original_without_debiting_again(self):
        customer_key, account_key = investor()
        key = str(uuid.uuid4())

        first_status, first = apply(customer_key, account_key, CDB, 10000, key)
        second_status, second = apply(customer_key, account_key, CDB, 10000, key)

        assert first_status == 201
        assert second_status == 200
        assert first == second
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000

    def test_same_key_with_different_body(self):
        customer_key, account_key = investor()
        key = str(uuid.uuid4())
        apply(customer_key, account_key, CDB, 10000, key)

        status, body = apply(customer_key, account_key, CDB, 20000, key)

        assert status == 409
        assert body["code"] == "PPP000004"
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000

    def test_same_key_with_another_product(self):
        customer_key, account_key = investor()
        key = str(uuid.uuid4())
        apply(customer_key, account_key, CDB, 10000, key)

        status, body = apply(customer_key, account_key, FUND, 10000, key)

        assert status == 409
        assert body["code"] == "PPP000004"
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000

    def test_key_already_used_in_a_deposit_is_refused(self):
        customer_key, account_key = investor()
        key = str(uuid.uuid4())
        RequestGenerator.post_transaction(customer_key, account_key, {"type": "DEPOSIT", "amount": 5000}, key)

        status, body = apply(customer_key, account_key, CDB, 10000, key)

        assert status == 409
        assert body["code"] == "PPP000004"
        assert balance_of(customer_key, account_key) == 1_000_000 + 5000

    def test_key_of_an_order_is_refused_in_the_transaction_route(self):
        customer_key, account_key = investor()
        key = str(uuid.uuid4())
        apply(customer_key, account_key, CDB, 10000, key)

        status, body = RequestGenerator.post_transaction(
            customer_key, account_key, {"type": "DEPOSIT", "amount": 5000}, key
        )

        assert status == 409
        assert body["code"] == "PPP000004"
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000

    def test_key_of_an_application_is_refused_in_a_redemption(self):
        customer_key, account_key = investor()
        key = str(uuid.uuid4())
        apply(customer_key, account_key, CDB, 10000, key)

        status, body = redeem(customer_key, account_key, CDB, 4000, key)

        assert status == 409
        assert body["code"] == "PPP000004"
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000

    def test_key_used_by_another_customer_is_refused(self):
        first_customer, first_account = investor()
        second_customer, second_account = investor()
        key = str(uuid.uuid4())
        apply(first_customer, first_account, CDB, 10000, key)

        status, body = apply(second_customer, second_account, CDB, 10000, key)

        assert status == 409
        assert body["code"] == "PPP000004"
        assert "investment_order_key" not in body
        assert balance_of(second_customer, second_account) == 1_000_000

    def test_invalid_idempotency_key(self):
        customer_key, account_key = investor()
        payload = {"product_key": product_key(CDB), "side": "APPLY", "amount": 10000}

        status, body = RequestGenerator.post_investment_order(customer_key, account_key, payload, "nao-e-um-uuid")

        assert status == 400
        assert body["code"] == "PPP000003"

    def test_missing_idempotency_key(self):
        customer_key, account_key = investor()
        payload = {"product_key": product_key(CDB), "side": "APPLY", "amount": 10000}

        status, body = RequestGenerator.post_investment_order(customer_key, account_key, payload, None)

        assert status == 400
        assert body["code"] == "PPP000003"


class TestApplyRefusals:
    def test_customer_not_found(self):
        status, body = apply(str(uuid.uuid4()), str(uuid.uuid4()), CDB, 10000)

        assert status == 404
        assert body["code"] == "PPP001001"

    def test_account_not_found(self):
        customer_key = create_customer()
        answer_profile(customer_key, MODERATE)

        status, body = apply(customer_key, str(uuid.uuid4()), CDB, 10000)

        assert status == 404
        assert body["code"] == "PPP002001"

    def test_account_of_another_customer(self):
        owner, owner_account = investor()
        stranger, _ = investor()

        status, body = apply(stranger, owner_account, CDB, 10000)

        assert status == 404
        assert body["code"] == "PPP002001"
        assert balance_of(owner, owner_account) == 1_000_000

    def test_closed_account(self):
        customer_key, account_key = closed_account()

        status, body = apply(customer_key, account_key, CDB, 10000)

        assert status == 409
        assert body["code"] == "PPP002005"

    def test_blocked_account(self):
        customer_key, account_key = investor()
        RequestGenerator.patch_internal_account_status(account_key, {"status": "BLOCKED", "reason": "Suspeita de fraude"})

        status, body = apply(customer_key, account_key, CDB, 10000)

        assert status == 409
        assert body["code"] == "PPP002005"
        assert balance_of(customer_key, account_key) == 1_000_000

    def test_without_profile(self):
        customer_key = create_customer()
        _, account = RequestGenerator.post_account(customer_key)
        account_key = account["account_key"]

        status, body = apply(customer_key, account_key, CDB, 10000)

        assert status == 409
        assert body["code"] == "PPP004005"

    def test_product_not_found(self):
        customer_key, account_key = investor()
        payload = {"product_key": str(uuid.uuid4()), "side": "APPLY", "amount": 10000}

        status, body = RequestGenerator.post_investment_order(customer_key, account_key, payload, str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP005001"

    def test_product_above_profile_risk(self):
        customer_key, account_key = investor(CONSERVATIVE)

        status, body = apply(customer_key, account_key, FUND, 10000)

        assert status == 422
        assert body["code"] == "PPP007003"
        assert balance_of(customer_key, account_key) == 1_000_000

    def test_below_minimum_application(self):
        customer_key, account_key = investor()

        status, body = apply(customer_key, account_key, CDB, 4999)

        assert status == 422
        assert body["code"] == "PPP007002"

    def test_insufficient_balance(self):
        customer_key, account_key = investor(balance=9999)

        status, body = apply(customer_key, account_key, CDB, 10000)

        assert status == 409
        assert body["code"] == "PPP003003"
        assert balance_of(customer_key, account_key) == 9999

    @pytest.mark.parametrize("amount", [0, -100])
    def test_invalid_amount(self, amount):
        customer_key, account_key = investor()

        status, body = apply(customer_key, account_key, CDB, amount)

        assert status == 422
        assert body["code"] == "PPP003004"

    @pytest.mark.parametrize(
        "payload",
        [
            {"side": "APPLY", "amount": 10000},
            {"product_key": "x", "amount": 10000},
            {"product_key": "x", "side": "BUY", "amount": 10000},
            {"product_key": "x", "side": "APPLY"},
            {"product_key": "x", "side": "APPLY", "amount": "10000"},
            {"product_key": "x", "side": "APPLY", "amount": 100.5},
            {"product_key": "x", "side": "APPLY", "redeem_all": True},
            {"product_key": "x", "side": "APPLY", "amount": 10000, "redeem_all": True},
            {"product_key": "x", "side": "APPLY", "amount": 10000, "extra": 1},
            {"product_key": "x", "side": "REDEEM"},
            {"product_key": "x", "side": "REDEEM", "amount": 10000, "redeem_all": True},
            {"product_key": "x", "side": "REDEEM", "redeem_all": False},
        ],
        ids=[
            "no_product",
            "no_side",
            "unknown_side",
            "no_amount",
            "amount_text",
            "amount_decimal",
            "apply_redeem_all",
            "apply_both",
            "unknown_field",
            "redeem_nothing",
            "redeem_both",
            "redeem_all_false",
        ],
    )
    def test_malformed_payload(self, payload):
        customer_key, account_key = investor()

        status, body = RequestGenerator.post_investment_order(customer_key, account_key, payload, str(uuid.uuid4()))

        assert status == 400
        assert body["code"] == "PPP000001"


def investor_with_fund_quote_up() -> tuple:
    assert close_day(fund="1.23456789")[0] == 201
    customer_key, account_key = investor(MODERATE, balance=150000)
    status, applied = apply(customer_key, account_key, FUND, 150000)
    assert status == 201
    assert applied["quantity"] == "1215.00001105"
    assert close_day(fund="1.24")[0] == 201
    return customer_key, account_key


class TestRedeem:
    def test_partial_redeem_credits_account_at_average_cost(self):
        customer_key, account_key = investor_with_fund_quote_up()

        status, body = redeem(customer_key, account_key, FUND, 50000)

        assert status == 201
        assert body["side"] == "REDEEM"
        assert body["source"] == "CUSTOMER"
        assert body["amount"] == 50000
        assert body["unit_price"] == "1.24000000"
        assert body["quantity"] == "403.22580645"
        assert body["acquisition_cost_amount"] == 49780
        assert body["result_amount"] == 220
        assert body["return_bps"] == 44
        assert body["maturity_date"] is None
        assert balance_of(customer_key, account_key) == 50000

    def test_redeem_all_zeroes_position(self):
        customer_key, account_key = investor_with_fund_quote_up()
        redeem(customer_key, account_key, FUND, 50000)

        status, body = redeem(customer_key, account_key, FUND)

        assert status == 201
        assert body["quantity"] == "811.77420460"
        assert body["amount"] == 100660
        assert body["acquisition_cost_amount"] == 100220
        assert body["result_amount"] == 440
        assert body["return_bps"] == 43
        assert balance_of(customer_key, account_key) == 50000 + 100660

        status, body = redeem(customer_key, account_key, FUND)
        assert status == 409
        assert body["code"] == "PPP007004"


class TestRedeemIdempotency:
    def test_same_key_and_body_returns_original_without_crediting_again(self):
        customer_key, account_key = investor()
        apply(customer_key, account_key, CDB, 10000)
        key = str(uuid.uuid4())

        first_status, first = redeem(customer_key, account_key, CDB, 4000, key)
        second_status, second = redeem(customer_key, account_key, CDB, 4000, key)

        assert first_status == 201
        assert second_status == 200
        assert first == second
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000 + 4000

    def test_same_key_with_different_body(self):
        customer_key, account_key = investor()
        apply(customer_key, account_key, CDB, 10000)
        key = str(uuid.uuid4())
        redeem(customer_key, account_key, CDB, 4000, key)

        status, body = redeem(customer_key, account_key, CDB, 5000, key)

        assert status == 409
        assert body["code"] == "PPP000004"
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000 + 4000

    def test_partial_redeem_key_reused_in_redeem_all(self):
        customer_key, account_key = investor()
        apply(customer_key, account_key, CDB, 10000)
        key = str(uuid.uuid4())
        redeem(customer_key, account_key, CDB, 4000, key)

        status, body = redeem(customer_key, account_key, CDB, None, key)

        assert status == 409
        assert body["code"] == "PPP000004"
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000 + 4000

    def test_repeated_redeem_all_returns_original(self):
        customer_key, account_key = investor()
        apply(customer_key, account_key, CDB, 10000)
        key = str(uuid.uuid4())
        _, first = redeem(customer_key, account_key, CDB, None, key)

        status, body = redeem(customer_key, account_key, CDB, None, key)

        assert status == 200
        assert body == first


class TestRedeemRefusals:
    def test_customer_not_found(self):
        status, body = redeem(str(uuid.uuid4()), str(uuid.uuid4()), CDB, 4000)

        assert status == 404
        assert body["code"] == "PPP001001"

    def test_account_of_another_customer(self):
        owner, owner_account = investor()
        apply(owner, owner_account, CDB, 10000)
        stranger, _ = investor()

        status, body = redeem(stranger, owner_account, CDB, 4000)

        assert status == 404
        assert body["code"] == "PPP002001"
        assert balance_of(owner, owner_account) == 1_000_000 - 10000

    def test_closed_account(self):
        customer_key, account_key = closed_account()

        status, body = redeem(customer_key, account_key, CDB, 4000)

        assert status == 409
        assert body["code"] == "PPP002005"

    def test_blocked_account(self):
        customer_key, account_key = investor()
        apply(customer_key, account_key, CDB, 10000)
        RequestGenerator.patch_internal_account_status(account_key, {"status": "BLOCKED", "reason": "Suspeita de fraude"})

        status, body = redeem(customer_key, account_key, CDB, 4000)

        assert status == 409
        assert body["code"] == "PPP002005"
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000

    def test_product_not_found(self):
        customer_key, account_key = investor()
        payload = {"product_key": str(uuid.uuid4()), "side": "REDEEM", "amount": 4000}

        status, body = RequestGenerator.post_investment_order(customer_key, account_key, payload, str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP005001"

    @pytest.mark.parametrize("amount", [4000, None], ids=["by_amount", "redeem_all"])
    def test_without_position(self, amount):
        customer_key, account_key = investor()

        status, body = redeem(customer_key, account_key, CDB, amount)

        assert status == 409
        assert body["code"] == "PPP007004"

    def test_more_than_position(self):
        customer_key, account_key = investor()
        apply(customer_key, account_key, CDB, 10000)

        status, body = redeem(customer_key, account_key, CDB, 10001)

        assert status == 409
        assert body["code"] == "PPP007004"
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000

    @pytest.mark.parametrize("amount", [5000, None], ids=["by_amount", "redeem_all"])
    def test_lci_before_maturity(self, amount):
        customer_key, account_key = investor(CONSERVATIVE)
        apply(customer_key, account_key, LCI, 10000)

        status, body = redeem(customer_key, account_key, LCI, amount)

        assert status == 422
        assert body["code"] == "PPP007005"
        assert balance_of(customer_key, account_key) == 1_000_000 - 10000

    @pytest.mark.parametrize("amount", [0, -100])
    def test_invalid_amount(self, amount):
        customer_key, account_key = investor()
        apply(customer_key, account_key, CDB, 10000)

        status, body = redeem(customer_key, account_key, CDB, amount)

        assert status == 422
        assert body["code"] == "PPP003004"


class TestGetOrder:
    def test_returns_the_same_as_creation(self):
        customer_key, account_key = investor()
        _, applied = apply(customer_key, account_key, CDB, 10000)
        _, redeemed = redeem(customer_key, account_key, CDB, 4000)

        apply_status, apply_body = RequestGenerator.get_investment_order(customer_key, account_key, applied["investment_order_key"])
        redeem_status, redeem_body = RequestGenerator.get_investment_order(customer_key, account_key, redeemed["investment_order_key"])

        assert (apply_status, apply_body) == (200, applied)
        assert (redeem_status, redeem_body) == (200, redeemed)

    def test_order_not_found(self):
        customer_key, account_key = investor()

        status, body = RequestGenerator.get_investment_order(customer_key, account_key, str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP007001"

    def test_order_of_another_customer(self):
        owner, owner_account = investor()
        _, order = apply(owner, owner_account, CDB, 10000)
        stranger, stranger_account = investor()

        status, body = RequestGenerator.get_investment_order(stranger, stranger_account, order["investment_order_key"])

        assert status == 404
        assert body["code"] == "PPP007001"

    def test_account_of_another_customer(self):
        owner, owner_account = investor()
        _, order = apply(owner, owner_account, CDB, 10000)
        stranger, _ = investor()

        status, body = RequestGenerator.get_investment_order(stranger, owner_account, order["investment_order_key"])

        assert status == 404
        assert body["code"] == "PPP002001"

    def test_customer_not_found(self):
        status, body = RequestGenerator.get_investment_order(str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP001001"


class TestListOrders:
    def test_newest_first_in_pages(self):
        customer_key, account_key = investor()
        for amount in (5000, 6000, 7000):
            apply(customer_key, account_key, CDB, amount)

        status, first = RequestGenerator.get_investment_orders(customer_key, account_key, {"limit": "2"})
        _, second = RequestGenerator.get_investment_orders(customer_key, account_key, {"limit": "2", "page": "2"})

        assert status == 200
        assert [order["amount"] for order in first["items"]] == [7000, 6000]
        assert (first["page"], first["limit"], first["total"]) == (1, 2, 3)
        assert [order["amount"] for order in second["items"]] == [5000]
        assert (second["page"], second["total"]) == (2, 3)

    def test_default_page_and_limit(self):
        customer_key, account_key = investor()
        _, order = apply(customer_key, account_key, CDB, 10000)

        status, body = RequestGenerator.get_investment_orders(customer_key, account_key)

        assert status == 200
        assert body == {"items": [order], "page": 1, "limit": 20, "total": 1}

    def test_filter_by_product(self):
        customer_key, account_key = investor()
        apply(customer_key, account_key, CDB, 10000)
        _, fund_order = apply(customer_key, account_key, FUND, 10000)

        status, body = RequestGenerator.get_investment_orders(customer_key, account_key, {"product_key": product_key(FUND)})

        assert status == 200
        assert body["items"] == [fund_order]
        assert body["total"] == 1

    def test_unknown_product_lists_nothing(self):
        customer_key, account_key = investor()
        apply(customer_key, account_key, CDB, 10000)

        status, body = RequestGenerator.get_investment_orders(customer_key, account_key, {"product_key": str(uuid.uuid4())})

        assert status == 200
        assert (body["items"], body["total"]) == ([], 0)

    def test_account_of_another_customer(self):
        owner, owner_account = investor()
        apply(owner, owner_account, CDB, 10000)
        stranger, _ = investor()

        status, body = RequestGenerator.get_investment_orders(stranger, owner_account)

        assert status == 404
        assert body["code"] == "PPP002001"

    def test_customer_not_found(self):
        status, body = RequestGenerator.get_investment_orders(str(uuid.uuid4()), str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP001001"

    @pytest.mark.parametrize(
        "query_params",
        [{"page": "0"}, {"page": "abc"}, {"limit": "0"}, {"limit": "101"}, {"limit": "1.5"}, {"color": "blue"}],
        ids=["page_zero", "page_text", "limit_zero", "limit_above_max", "limit_decimal", "unknown_param"],
    )
    def test_invalid_query(self, query_params):
        customer_key, account_key = investor()

        status, body = RequestGenerator.get_investment_orders(customer_key, account_key, query_params)

        assert status == 400
        assert body["code"] == "PPP000001"


class TestPositions:
    def test_current_value_and_return(self):
        customer_key, account_key = investor_with_fund_quote_up()

        status, body = RequestGenerator.get_positions(customer_key, account_key)

        assert status == 200
        assert body["items"] == [
            {
                "product_key": product_key(FUND),
                "quantity": "1215.00001105",
                "unit_price": "1.24000000",
                "current_amount": 150660,
                "acquisition_cost_amount": 150000,
                "result_amount": 660,
                "return_bps": 44,
            }
        ]
        assert body["total"] == {
            "investments_amount": 150660,
            "acquisition_cost_amount": 150000,
            "result_amount": 660,
            "return_bps": 44,
            "cash_amount": 0,
            "net_worth_amount": 150660,
            "cash_bps": 0,
            "investments_bps": 10000,
        }

    def test_total_adds_up_every_product(self):
        customer_key, account_key = investor()
        apply(customer_key, account_key, CDB, 10000)
        apply(customer_key, account_key, FUND, 20000)

        status, body = RequestGenerator.get_positions(customer_key, account_key)

        assert status == 200
        assert len(body["items"]) == 2
        total = body["total"]
        assert total["investments_amount"] == sum(item["current_amount"] for item in body["items"])
        assert total["acquisition_cost_amount"] == 30000
        assert total["result_amount"] == total["investments_amount"] - 30000

    def test_closed_position_only_when_asked(self):
        customer_key, account_key = investor()
        apply(customer_key, account_key, CDB, 10000)
        redeem(customer_key, account_key, CDB)

        _, default = RequestGenerator.get_positions(customer_key, account_key)
        status, with_closed = RequestGenerator.get_positions(customer_key, account_key, {"include_closed": "true"})

        assert default["items"] == []
        assert status == 200
        assert len(with_closed["items"]) == 1
        closed = with_closed["items"][0]
        assert (closed["quantity"], closed["current_amount"], closed["acquisition_cost_amount"]) == ("0.00000000", 0, 0)
        assert closed["return_bps"] == 0

    def test_capital_split_between_cash_and_investments(self):
        customer_key, account_key = investor(balance=1_000_000)
        apply(customer_key, account_key, CDB, 250000)

        status, body = RequestGenerator.get_positions(customer_key, account_key)

        total = body["total"]
        cash = balance_of(customer_key, account_key)
        net_worth = cash + total["investments_amount"]
        assert status == 200
        assert total["cash_amount"] == cash == 750000
        assert total["net_worth_amount"] == net_worth
        assert total["cash_bps"] == cash * 10000 // net_worth
        assert total["cash_bps"] + total["investments_bps"] == 10000

    def test_account_shows_the_same_capital(self):
        customer_key, account_key = investor(balance=1_000_000)
        apply(customer_key, account_key, CDB, 250000)

        _, positions = RequestGenerator.get_positions(customer_key, account_key)
        status, account = RequestGenerator.get_account(customer_key, account_key)

        assert status == 200
        assert account["balance"] == 750000
        assert account["investments_amount"] == positions["total"]["investments_amount"]
        assert account["net_worth_amount"] == account["balance"] + account["investments_amount"]
        assert account["net_worth_amount"] == positions["total"]["net_worth_amount"]

    def test_only_cash(self):
        customer_key, account_key = investor(balance=50000)

        _, body = RequestGenerator.get_positions(customer_key, account_key)

        assert body["total"]["cash_amount"] == 50000
        assert body["total"]["net_worth_amount"] == 50000
        assert (body["total"]["cash_bps"], body["total"]["investments_bps"]) == (10000, 0)

    def test_empty_account_has_nothing(self):
        customer_key = create_customer()
        _, account = RequestGenerator.post_account(customer_key)

        status, body = RequestGenerator.get_positions(customer_key, account["account_key"])

        assert status == 200
        assert body["items"] == []
        total = body["total"]
        assert (total["cash_amount"], total["net_worth_amount"]) == (0, 0)
        assert (total["cash_bps"], total["investments_bps"]) == (0, 0)

    def test_account_of_another_customer(self):
        owner, owner_account = investor()
        apply(owner, owner_account, CDB, 10000)
        stranger, _ = investor()

        status, body = RequestGenerator.get_positions(stranger, owner_account)

        assert status == 404
        assert body["code"] == "PPP002001"

    def test_customer_not_found(self):
        status, body = RequestGenerator.get_positions(str(uuid.uuid4()), str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP001001"

    @pytest.mark.parametrize("query_params", [{"include_closed": "yes"}, {"page": "1"}], ids=["not_boolean", "unknown_param"])
    def test_invalid_query(self, query_params):
        customer_key, account_key = investor()

        status, body = RequestGenerator.get_positions(customer_key, account_key, query_params)

        assert status == 400
        assert body["code"] == "PPP000001"


class TestCloseAccountWithPosition:
    def test_open_position_blocks_closing(self):
        customer_key, account_key = investor(balance=10000)
        apply(customer_key, account_key, CDB, 10000)

        status, body = RequestGenerator.patch_account(customer_key, account_key, {"status": "CLOSED", "reason": "Pedido do cliente"})

        assert status == 409
        assert body["code"] == "PPP002004"
        _, account = RequestGenerator.get_account(customer_key, account_key)
        assert account["status"] == "ACTIVE"

    def test_closes_after_redeeming_and_withdrawing_everything(self):
        customer_key, account_key = investor(balance=10000)
        apply(customer_key, account_key, CDB, 10000)
        redeem(customer_key, account_key, CDB)
        withdrawal = {"type": "WITHDRAWAL", "amount": balance_of(customer_key, account_key)}
        RequestGenerator.post_transaction(customer_key, account_key, withdrawal, str(uuid.uuid4()))

        status, body = RequestGenerator.patch_account(customer_key, account_key, {"status": "CLOSED", "reason": "Pedido do cliente"})

        assert status == 200
        assert body["status"] == "CLOSED"
