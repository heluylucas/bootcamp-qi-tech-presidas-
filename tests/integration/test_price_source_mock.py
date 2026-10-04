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


def business_days_ahead(day: date, count: int) -> date:
    for _ in range(count):
        day = next_business_day(day)
    return day


# O mock-init ensina 60 dias úteis a partir da data real em que o compose
# subiu. Os testes do fechamento apagam e fecham os primeiros dias dessa
# janela (PriceSourceMock.teach_day), então aqui se confere um dia lá na
# frente, que a suíte não alcança: 30 dias úteis depois de hoje.
FAR_DAY = business_days_ahead(date.today(), 30)


def fund_quote(day: date):
    return Mock().get(f"/fund-admin/funds/{FUND_CNPJ}/quotes", {"date": day.isoformat()})


class TestDemoScenario:
    """O que o mock-init deixou ensinado quando o compose subiu."""

    def test_fund_quote(self):
        response = fund_quote(FAR_DAY)

        assert response.status_code == 200
        body = response.json()
        assert body["DT_COMPTC"] == FAR_DAY.isoformat()
        assert float(body["VL_QUOTA"]) > 0

    def test_treasury_prices(self):
        response = Mock().get("/treasury/prices", {"date": FAR_DAY.isoformat()})

        assert response.status_code == 200
        body = response.json()
        assert body["date"] == FAR_DAY.isoformat()
        assert {bond["name"] for bond in body["bonds"]} == set(TREASURY_BONDS)

    def test_rates(self):
        cdi = Mock().get(f"/bcb/dados/serie/bcdata.sgs.{CDI_SERIES}/dados", bcb_query_flat(FAR_DAY))
        selic = Mock().get(f"/bcb/dados/serie/bcdata.sgs.{SELIC_SERIES}/dados", bcb_query_flat(FAR_DAY))

        assert cdi.json() == [{"data": FAR_DAY.strftime("%d/%m/%Y"), "valor": "14.90"}]
        assert selic.json() == [{"data": FAR_DAY.strftime("%d/%m/%Y"), "valor": "15.00"}]

    def test_weekend_is_not_taught(self):
        saturday = FAR_DAY + timedelta(days=(5 - FAR_DAY.weekday()) % 7)

        assert fund_quote(saturday).status_code == 404


class TestPriceSourceMock:
    def test_test_answer_wins_once_then_scenario_returns(self):
        PriceSourceMock.fund_quote(FAR_DAY, "102.00")

        first = fund_quote(FAR_DAY).json()["VL_QUOTA"]
        second = fund_quote(FAR_DAY).json()["VL_QUOTA"]

        assert first == "102.00"
        assert second != "102.00"


def bcb_query_flat(day: date) -> dict:
    return {name: values[0] for name, values in bcb_query(day).items()}
