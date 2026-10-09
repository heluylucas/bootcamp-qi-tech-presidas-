import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from tests.integration.test_day_close import business_date, close_day
from tests.integration.test_investment_order import CDB, FUND, apply, investor
from tests.utils import INTERNAL_TOKEN, RandomGenerator, RequestGenerator
from tests.utils.requisition import ClientRequisition


# Tarifa de transferência (RN-MOV-10), em centavos.
TRANSFER_FEE = 200


def revenue(from_date: date, to_date: date) -> dict:
    """O relatório de um período em datas de movimento (RN-REC-09)."""
    _, body = RequestGenerator.get_revenue({"from": from_date.isoformat(), "to": to_date.isoformat()})
    return body


def fee_revenue_today() -> int:
    today = business_date()
    return revenue(today, today)["realized"]["fee_amount"]


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

    def test_fee_belongs_to_the_business_day_of_the_transfer(self):
        """A tarifa conta no dia de movimento em que a transferência aconteceu, não no dia seguinte."""
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
    """As estimativas de um único dia de movimento."""
    return revenue(day, day)["estimated"]


def close_and_accrual() -> dict:
    """Fecha o dia atual e devolve a provisão que o fechamento gravou para ele."""
    day = business_date()
    close_day()
    return accrual_of(day)


def base_of(accrual: dict, name: str) -> int:
    return accrual[name]["daily"][0]["base_amount"]


def by_formula(day: dict) -> int:
    """RN-REC-05 e 07: base × taxa anual × dias corridos / 365, em centavos para baixo."""
    return int(Decimal(day["base_amount"]) * day["annual_rate_bps"] * day["calendar_days"] / (10000 * 365))


class TestEstimatedRevenue:
    def test_open_day_has_no_accrual(self):
        """Só dia fechado tem provisão: o dia aberto ainda não tem a foto do fim do dia."""
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
        """O dinheiro parado no fim de semana continua aplicado: a provisão de sexta vale 3 dias."""
        while business_date().weekday() != 4:
            close_day()

        accrual = close_and_accrual()

        assert accrual["float"]["daily"][0]["calendar_days"] == 3

    def test_closed_day_never_changes(self):
        """A provisão é gravada no fechamento e nunca alterada (R4)."""
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
        """A tarifa vai para a conta do banco, que não entra no float (RN-REC-07)."""
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
        # Um fechamento antes: os dois dias comparados ficam com a mesma cota (a padrão do mock).
        close_day()
        before = close_and_accrual()

        apply(customer_key, account_key, FUND, 50000)

        after = base_of(close_and_accrual(), "fund_administration_fee")
        # As cotas são truncadas em 8 casas: o patrimônio ao preço do dia pode ficar 1 centavo abaixo.
        assert base_of(before, "fund_administration_fee") + 49999 <= after
        assert after <= base_of(before, "fund_administration_fee") + 50000

    def test_period_without_closed_day_has_no_estimate(self):
        later = business_date() + timedelta(days=10)

        body = revenue(later, later + timedelta(days=5))

        assert body["days"] == 0
        for estimate in body["estimated"].values():
            assert estimate == {"amount": 0, "daily": []}

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
