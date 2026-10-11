from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest

from tests.utils import RequestGenerator
from tests.utils.helpers import CDB, FUND, SELIC, business_date, close_day, next_business_day, product
from tests.utils.price_source_mock import DEFAULT_TREASURY_PRICES, PriceSourceMock, rate_body


class TestDayClose:
    def test_close_opens_next_business_day(self):
        today = business_date()

        status, body = close_day()

        assert status == 201
        assert body["business_date"] == next_business_day(today).isoformat()
        _, current = RequestGenerator.get_business_date()
        assert current["business_date"] == body["business_date"]

    def test_friday_closes_to_monday(self):
        while business_date().weekday() != 4:
            assert close_day()[0] == 201

        status, body = close_day()

        assert status == 201
        assert date.fromisoformat(body["business_date"]).weekday() == 0

    def test_records_one_price_per_product_and_both_rates(self):
        status, body = close_day(fund="102.00", cdi="12.00", selic="12.25")

        assert status == 201
        assert len(body["prices"]) == 6
        assert sorted(body["rates"], key=lambda rate: rate["code"]) == [
            {"code": "CDI", "annual_rate_bps": 1200},
            {"code": "SELIC", "annual_rate_bps": 1225},
        ]

    def test_product_shows_price_the_mock_answered(self):
        status, body = close_day(fund="102.00", treasury={**DEFAULT_TREASURY_PRICES, "TESOURO SELIC 2031": "123.45"})

        assert status == 201
        fund = product(FUND)
        selic = product(SELIC)
        assert fund["price"] == {"price_date": body["business_date"], "unit_price": "102.00000000"}
        assert selic["price"]["unit_price"] == "123.45000000"

    def test_own_issue_grows_by_cdi_of_the_closing_day(self):
        assert close_day(cdi="12.00")[0] == 201
        previous = Decimal(product(CDB)["price"]["unit_price"])

        status, _ = close_day(cdi="20.00")

        assert status == 201
        daily_cdi = (Decimal("1.12") ** (Decimal(1) / Decimal(252))) - 1
        expected = (previous * (1 + daily_cdi * Decimal("0.95"))).quantize(Decimal("0.00000001"), ROUND_HALF_UP)
        assert Decimal(product(CDB)["price"]["unit_price"]) == expected


class TestDayCloseRefused:
    def test_close_date_is_not_business_date(self):
        today = business_date()

        status, body = RequestGenerator.post_day_close({"close_date": (today - timedelta(days=1)).isoformat()})

        assert status == 409
        assert body["code"] == "PPP000006"
        assert business_date() == today

    def test_double_click_closes_one_day(self):
        today = business_date()
        assert close_day()[0] == 201

        status, body = RequestGenerator.post_day_close({"close_date": today.isoformat()})

        assert status == 409
        assert body["code"] == "PPP000006"
        assert business_date() == next_business_day(today)

    @pytest.mark.parametrize("payload", [{}, {"close_date": "05/10/2026"}, {"close_date": "2026-10-05", "x": 1}])
    def test_malformed_payload(self, payload):
        status, body = RequestGenerator.post_day_close(payload)

        assert status == 400
        assert body["code"] == "PPP000001"


class TestPriceSourceFailure:
    def assert_nothing_changed(self, today: date, fund_price: dict) -> None:
        assert business_date() == today
        assert product(FUND)["price"] == fund_price

    @pytest.mark.parametrize("service", ["fund", "treasury", "cdi", "selic"])
    def test_source_answers_error(self, service):
        today, fund_price = business_date(), product(FUND)["price"]
        new_day = next_business_day(today)
        PriceSourceMock.teach_day(new_day, skip=service)
        PriceSourceMock.server_error(service, new_day)

        status, body = RequestGenerator.post_day_close({"close_date": today.isoformat()})

        assert status == 502
        assert body["code"] == "PPP005006"
        self.assert_nothing_changed(today, fund_price)

    def test_connection_dropped(self):
        today, fund_price = business_date(), product(FUND)["price"]
        new_day = next_business_day(today)
        PriceSourceMock.teach_day(new_day, skip="treasury")
        PriceSourceMock.connection_dropped("treasury", new_day)

        status, body = RequestGenerator.post_day_close({"close_date": today.isoformat()})

        assert status == 502
        assert body["code"] == "PPP005006"
        self.assert_nothing_changed(today, fund_price)

    def test_fund_quote_zero(self):
        today, fund_price = business_date(), product(FUND)["price"]

        status, body = close_day(fund="0")

        assert status == 502
        assert body["code"] == "PPP005007"
        self.assert_nothing_changed(today, fund_price)

    def test_fund_quote_of_another_day(self):
        today, fund_price = business_date(), product(FUND)["price"]
        new_day = next_business_day(today)
        PriceSourceMock.teach_day(new_day, skip="fund")
        PriceSourceMock.fund_quote(new_day, "102.00", quote_date=today)

        status, body = RequestGenerator.post_day_close({"close_date": today.isoformat()})

        assert status == 502
        assert body["code"] == "PPP005007"
        self.assert_nothing_changed(today, fund_price)

    def test_treasury_bond_missing(self):
        today, fund_price = business_date(), product(FUND)["price"]
        without_ipca = {name: price for name, price in DEFAULT_TREASURY_PRICES.items() if "IPCA" not in name}

        status, body = close_day(treasury=without_ipca)

        assert status == 502
        assert body["code"] == "PPP005007"
        self.assert_nothing_changed(today, fund_price)

    @pytest.mark.parametrize("rate", [[], [{"data": "x", "valor": "abc"}]], ids=["empty", "not_a_number"])
    def test_rate_without_sense(self, rate):
        today, fund_price = business_date(), product(FUND)["price"]
        new_day = next_business_day(today)
        PriceSourceMock.teach_day(new_day, skip="cdi")
        PriceSourceMock.answer("cdi", new_day, rate)

        status, body = RequestGenerator.post_day_close({"close_date": today.isoformat()})

        assert status == 502
        assert body["code"] == "PPP005007"
        self.assert_nothing_changed(today, fund_price)

    def test_rate_of_another_day(self):
        today, fund_price = business_date(), product(FUND)["price"]
        new_day = next_business_day(today)
        PriceSourceMock.teach_day(new_day, skip="selic")
        PriceSourceMock.answer("selic", new_day, rate_body(today, "15.00"))

        status, body = RequestGenerator.post_day_close({"close_date": today.isoformat()})

        assert status == 502
        assert body["code"] == "PPP005007"
        self.assert_nothing_changed(today, fund_price)
