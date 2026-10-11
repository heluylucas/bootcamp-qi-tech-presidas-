import calendar
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.utils import INTERNAL_TOKEN, RequestGenerator
from tests.utils.helpers import (
    CDB,
    FUND,
    TRANSFER_FEE,
    apply,
    balance_of,
    business_date,
    close_day,
    investor,
    open_account,
    send,
)
from tests.utils.requisition import ClientRequisition


def revenue(from_date: date, to_date: date) -> dict:
    _, body = RequestGenerator.get_revenue({"from": from_date.isoformat(), "to": to_date.isoformat()})
    return body


def fee_revenue_today() -> int:
    today = business_date()
    return revenue(today, today)["realized"]["fee_amount"]


class TestFeeRevenue:
    def test_transfer_fee_goes_to_the_bank(self):
        origin_customer, origin_account = open_account()
        destination_customer, destination_account = open_account()
        send(origin_customer, origin_account, {"type": "DEPOSIT", "amount": 100000})
        before = fee_revenue_today()

        send(
            origin_customer,
            origin_account,
            {"type": "TRANSFER", "amount": 20000, "destination_account_key": destination_account},
        )

        assert fee_revenue_today() == before + TRANSFER_FEE
        assert balance_of(origin_customer, origin_account) == 100000 - 20000 - TRANSFER_FEE
        assert balance_of(destination_customer, destination_account) == 20000

    def test_deposit_and_withdrawal_are_not_revenue(self):
        customer_key, account_key = open_account()
        before = fee_revenue_today()

        send(customer_key, account_key, {"type": "DEPOSIT", "amount": 10000})
        send(customer_key, account_key, {"type": "WITHDRAWAL", "amount": 3000})

        assert fee_revenue_today() == before

    def test_fee_belongs_to_the_business_day_of_the_transfer(self):
        origin_customer, origin_account = open_account()
        _, destination_account = open_account()
        send(origin_customer, origin_account, {"type": "DEPOSIT", "amount": 100000})
        day = business_date()
        send(
            origin_customer,
            origin_account,
            {"type": "TRANSFER", "amount": 20000, "destination_account_key": destination_account},
        )
        fee_of_day = revenue(day, day)["realized"]["fee_amount"]

        close_day()

        assert revenue(day, day)["realized"]["fee_amount"] == fee_of_day
        assert fee_revenue_today() == 0


def accrual_of(day: date) -> dict:
    return revenue(day, day)["estimated"]


def close_and_accrual() -> dict:
    day = business_date()
    close_day()
    return accrual_of(day)


def base_of(accrual: dict, name: str) -> int:
    return accrual[name]["daily"][0]["base_amount"]


def by_formula(day: dict) -> int:
    return int(Decimal(day["base_amount"]) * day["annual_rate_bps"] * day["calendar_days"] / (10000 * 365))


class TestEstimatedRevenue:
    def test_open_day_has_no_accrual(self):
        today = business_date()

        body = revenue(today, today)

        assert body["days"] == 0
        for estimate in body["estimated"].values():
            assert estimate == {"amount": 0, "daily": []}

    def test_closing_a_day_records_its_accrual(self):
        day = business_date()

        close_day()

        next_day = business_date()
        body = revenue(day, day)
        assert body["days"] == 1
        for name, estimate in body["estimated"].items():
            assert len(estimate["daily"]) == 1, name
            assert estimate["daily"][0]["date"] == day.isoformat()
            assert estimate["daily"][0]["calendar_days"] == (next_day - day).days
            assert estimate["amount"] == estimate["daily"][0]["amount"]
        for name in ("fund_administration_fee", "float"):
            assert body["estimated"][name]["daily"][0]["amount"] == by_formula(body["estimated"][name]["daily"][0])
        assert body["estimated"]["fund_administration_fee"]["daily"][0]["annual_rate_bps"] == 100
        assert body["total_amount"] == body["realized"]["fee_amount"] + sum(
            estimate["amount"] for estimate in body["estimated"].values()
        )

    def test_friday_accrual_covers_the_weekend(self):
        while business_date().weekday() != 4:
            close_day()

        accrual = close_and_accrual()

        assert accrual["float"]["daily"][0]["calendar_days"] == 3

    def test_closed_day_never_changes(self):
        customer_key, account_key = open_account()
        day = business_date()
        close_day()
        before = accrual_of(day)

        send(customer_key, account_key, {"type": "DEPOSIT", "amount": 10000})

        assert accrual_of(day) == before

    def test_deposit_raises_the_float_base(self):
        customer_key, account_key = open_account()
        before = close_and_accrual()

        send(customer_key, account_key, {"type": "DEPOSIT", "amount": 10000})

        assert base_of(close_and_accrual(), "float") == base_of(before, "float") + 10000

    def test_transfer_fee_leaves_the_float(self):
        origin_customer, origin_account = open_account()
        _, destination_account = open_account()
        send(origin_customer, origin_account, {"type": "DEPOSIT", "amount": 100000})
        before = close_and_accrual()

        send(
            origin_customer,
            origin_account,
            {"type": "TRANSFER", "amount": 20000, "destination_account_key": destination_account},
        )

        assert base_of(close_and_accrual(), "float") == base_of(before, "float") - TRANSFER_FEE

    def test_own_issue_application_raises_the_spread_base(self):
        customer_key, account_key = investor()
        before = close_and_accrual()

        apply(customer_key, account_key, CDB, 50000)

        after = close_and_accrual()
        assert base_of(after, "own_issue_spread") == base_of(before, "own_issue_spread") + 50000
        assert base_of(after, "float") == base_of(before, "float") - 50000

    def test_fund_application_raises_the_fund_base(self):
        customer_key, account_key = investor()
        close_day()
        before = close_and_accrual()

        apply(customer_key, account_key, FUND, 50000)

        after = base_of(close_and_accrual(), "fund_administration_fee")
        assert base_of(before, "fund_administration_fee") + 49999 <= after
        assert after <= base_of(before, "fund_administration_fee") + 50000

    def test_report_does_not_move_money(self):
        customer_key, account_key = open_account()
        send(customer_key, account_key, {"type": "DEPOSIT", "amount": 10000})
        today = business_date()

        revenue(today - timedelta(days=30), today)

        assert balance_of(customer_key, account_key) == 10000


class TestRevenuePeriod:
    def test_default_period_is_the_current_business_month(self):
        status, body = RequestGenerator.get_revenue()

        today = business_date()
        last_day = calendar.monthrange(today.year, today.month)[1]
        assert status == 200
        assert body["from"] == today.replace(day=1).isoformat()
        assert body["to"] == today.replace(day=last_day).isoformat()
        assert isinstance(body["realized"]["fee_amount"], int)

    def test_from_after_to(self):
        status, body = RequestGenerator.get_revenue({"from": "2026-10-10", "to": "2026-10-01"})

        assert status == 400
        assert body["code"] == "PPP000005"

    def test_period_longer_than_366_days(self):
        status, body = RequestGenerator.get_revenue({"from": "2025-01-01", "to": "2026-01-03"})

        assert status == 400
        assert body["code"] == "PPP000005"

    @pytest.mark.parametrize(
        "query_params",
        [{"from": "01/10/2026"}, {"to": "2026-13-01"}, {"extra": "x"}],
    )
    def test_invalid_query(self, query_params):
        status, body = RequestGenerator.get_revenue(query_params)

        assert status == 400
        assert body["code"] == "PPP000001"

    def test_without_operator_token(self):
        response = ClientRequisition.send("GET", "/internal/revenue", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN})

        assert response.response_status == 403
        assert response.response_json["code"] == "PPP000007"
