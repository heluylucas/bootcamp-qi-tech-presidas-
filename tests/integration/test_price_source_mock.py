from datetime import date, timedelta

from tests.utils.mock_utils import Mock
from tests.utils.price_source_mock import (
    CDI_SERIES,
    FUND_CNPJ,
    SELIC_SERIES,
    TREASURY_BONDS,
    PriceSourceMock,
    bcb_query,
)


def next_business_day(day: date) -> date:
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


# O mock-init ensina a partir da data real em que o compose subiu, então
# aqui o "amanhã" é o do relógio, e não a data de movimento.
TOMORROW = next_business_day(date.today())


def fund_quote(day: date):
    return Mock().get(f"/fund-admin/funds/{FUND_CNPJ}/quotes", {"date": day.isoformat()})


class TestDemoScenario:
    """O que o mock-init deixou ensinado quando o compose subiu."""

    def test_fund_quote(self):
        response = fund_quote(TOMORROW)

        assert response.status_code == 200
        body = response.json()
        assert body["DT_COMPTC"] == TOMORROW.isoformat()
        assert float(body["VL_QUOTA"]) > 0

    def test_treasury_prices(self):
        response = Mock().get("/treasury/prices", {"date": TOMORROW.isoformat()})

        assert response.status_code == 200
        body = response.json()
        assert body["date"] == TOMORROW.isoformat()
        assert {bond["name"] for bond in body["bonds"]} == set(TREASURY_BONDS)

    def test_rates(self):
        cdi = Mock().get(f"/bcb/dados/serie/bcdata.sgs.{CDI_SERIES}/dados", bcb_query_flat(TOMORROW))
        selic = Mock().get(f"/bcb/dados/serie/bcdata.sgs.{SELIC_SERIES}/dados", bcb_query_flat(TOMORROW))

        assert cdi.json() == [{"data": TOMORROW.strftime("%d/%m/%Y"), "valor": "14.90"}]
        assert selic.json() == [{"data": TOMORROW.strftime("%d/%m/%Y"), "valor": "15.00"}]

    def test_weekend_is_not_taught(self):
        saturday = TOMORROW + timedelta(days=(5 - TOMORROW.weekday()) % 7)

        assert fund_quote(saturday).status_code == 404


class TestPriceSourceMock:
    def test_test_answer_wins_once_then_scenario_returns(self):
        PriceSourceMock.fund_quote(TOMORROW, "102.00")

        first = fund_quote(TOMORROW).json()["VL_QUOTA"]
        second = fund_quote(TOMORROW).json()["VL_QUOTA"]

        assert first == "102.00"
        assert second != "102.00"


def bcb_query_flat(day: date) -> dict:
    return {name: values[0] for name, values in bcb_query(day).items()}
