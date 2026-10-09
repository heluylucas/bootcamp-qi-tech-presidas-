import calendar
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tests.integration.test_investment_order import CDB, FUND, apply, investor
from tests.utils import INTERNAL_TOKEN, RandomGenerator, RequestGenerator
from tests.utils.requisition import ClientRequisition


# Tarifa de transferência (RN-MOV-10), em centavos.
TRANSFER_FEE = 200


def today() -> str:
    # O período filtra pela hora real do lançamento, em UTC (RN-REC-09).
    return datetime.now(timezone.utc).date().isoformat()


def fee_revenue_today() -> int:
    _, body = RequestGenerator.get_revenue({"from": today(), "to": today()})
    return body["realized"]["fee_amount"]


def open_account() -> tuple:
    payload = {"name": "Ana Silva", "document_number": RandomGenerator.generate_cpf(), "birth_date": "1990-05-17"}
    _, customer = RequestGenerator.post_customer(payload)
    _, account = RequestGenerator.post_account(customer["customer_key"])
    return customer["customer_key"], account["account_key"]


def send(customer_key: str, account_key: str, payload: dict):
    return RequestGenerator.post_transaction(customer_key, account_key, payload, str(uuid.uuid4()))


def balance_of(customer_key: str, account_key: str) -> int:
    _, account = RequestGenerator.get_account(customer_key, account_key)
    return account["balance"]


class TestFeeRevenue:
    def test_transfer_fee_goes_to_the_bank(self):
        """A tarifa sai da origem e entra na conta do banco: nenhum centavo some (RN-REC-03)."""
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

    def test_repeated_transfer_charges_the_fee_once(self):
        origin_customer, origin_account = open_account()
        _, destination_account = open_account()
        send(origin_customer, origin_account, {"type": "DEPOSIT", "amount": 100000})
        before = fee_revenue_today()
        key = str(uuid.uuid4())
        payload = {"type": "TRANSFER", "amount": 20000, "destination_account_key": destination_account}

        RequestGenerator.post_transaction(origin_customer, origin_account, payload, key)
        RequestGenerator.post_transaction(origin_customer, origin_account, payload, key)

        assert fee_revenue_today() == before + TRANSFER_FEE


def day_offset(days: int) -> str:
    """Hoje (UTC) mais `days` dias, em AAAA-MM-DD."""
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def estimated(period: dict = None) -> dict:
    """As estimativas do período; sem período, só o dia de hoje."""
    _, body = RequestGenerator.get_revenue(period or {"from": today(), "to": today()})
    return body["estimated"]


def base_today(name: str) -> int:
    return estimated()[name]["daily"][0]["base_amount"]


def by_formula(day: dict) -> int:
    """RN-REC-05 e 07: base do dia × taxa anual do dia / 365, em centavos para baixo.

    Dia anterior à primeira taxa publicada (o banco ainda não existia) vale 0.
    """
    if day["annual_rate_bps"] is None:
        return 0
    return int(Decimal(day["base_amount"]) * day["annual_rate_bps"] / (10000 * 365))


class TestEstimatedRevenue:
    def test_each_estimate_is_the_sum_of_its_days(self):
        status, body = RequestGenerator.get_revenue({"from": day_offset(-6), "to": today()})

        assert status == 200
        assert body["days"] == 7
        for name, estimate in body["estimated"].items():
            assert [day["date"] for day in estimate["daily"]] == [day_offset(offset) for offset in range(-6, 1)]
            assert estimate["amount"] == sum(day["amount"] for day in estimate["daily"]), name
        for name in ("fund_administration_fee", "float"):
            for day in body["estimated"][name]["daily"]:
                assert day["amount"] == by_formula(day), name
        assert body["total_amount"] == body["realized"]["fee_amount"] + sum(
            estimate["amount"] for estimate in body["estimated"].values()
        )

    def test_deposit_today_does_not_change_a_past_period(self):
        """Cada dia usa a base daquele dia: o dinheiro de hoje não entra na receita de ontem."""
        customer_key, account_key = open_account()
        yesterday = {"from": day_offset(-1), "to": day_offset(-1)}
        before = estimated(yesterday)

        send(customer_key, account_key, {"type": "DEPOSIT", "amount": 10000})

        assert estimated(yesterday) == before

    def test_days_after_today_are_not_counted(self):
        status, body = RequestGenerator.get_revenue({"from": today(), "to": day_offset(10)})

        assert status == 200
        assert body["days"] == 1
        assert all(len(estimate["daily"]) == 1 for estimate in body["estimated"].values())

    def test_period_in_the_future_has_no_estimate(self):
        status, body = RequestGenerator.get_revenue({"from": day_offset(1), "to": day_offset(5)})

        assert status == 200
        assert body["days"] == 0
        for estimate in body["estimated"].values():
            assert estimate == {"amount": 0, "daily": []}

    def test_deposit_raises_the_float_base(self):
        customer_key, account_key = open_account()
        before = base_today("float")

        send(customer_key, account_key, {"type": "DEPOSIT", "amount": 10000})

        assert base_today("float") == before + 10000

    def test_transfer_fee_leaves_the_float(self):
        """A tarifa vai para a conta do banco, que não entra no float (RN-REC-07)."""
        origin_customer, origin_account = open_account()
        _, destination_account = open_account()
        send(origin_customer, origin_account, {"type": "DEPOSIT", "amount": 100000})
        before = base_today("float")

        send(
            origin_customer,
            origin_account,
            {"type": "TRANSFER", "amount": 20000, "destination_account_key": destination_account},
        )

        assert base_today("float") == before - TRANSFER_FEE

    def test_own_issue_application_raises_the_spread_base(self):
        customer_key, account_key = investor()
        spread_before, float_before = base_today("own_issue_spread"), base_today("float")

        apply(customer_key, account_key, CDB, 50000)

        assert base_today("own_issue_spread") == spread_before + 50000
        assert base_today("float") == float_before - 50000

    def test_fund_application_raises_the_fund_base(self):
        customer_key, account_key = investor()
        before = base_today("fund_administration_fee")

        apply(customer_key, account_key, FUND, 50000)

        # As cotas são truncadas em 8 casas: o patrimônio ao preço do dia pode ficar 1 centavo abaixo.
        assert before + 49999 <= base_today("fund_administration_fee") <= before + 50000

    def test_report_does_not_move_money(self):
        customer_key, account_key = open_account()
        send(customer_key, account_key, {"type": "DEPOSIT", "amount": 10000})

        estimated()

        assert balance_of(customer_key, account_key) == 10000


class TestRevenuePeriod:
    def test_default_period_is_the_current_month(self):
        status, body = RequestGenerator.get_revenue()

        now = datetime.now(timezone.utc).date()
        last_day = calendar.monthrange(now.year, now.month)[1]
        assert status == 200
        assert body["from"] == now.replace(day=1).isoformat()
        assert body["to"] == now.replace(day=last_day).isoformat()
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
