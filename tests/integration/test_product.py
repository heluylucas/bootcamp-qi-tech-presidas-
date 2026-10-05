import uuid
from datetime import date, timedelta

import pytest

from tests.utils import RequestGenerator


PRODUCT_TYPES = {"PUBLIC_BOND", "PRIVATE_BOND", "FUND"}


def business_date() -> date:
    _, body = RequestGenerator.get_business_date()
    return date.fromisoformat(body["business_date"])


def product_named(name: str) -> dict:
    _, body = RequestGenerator.get_products()
    return next(product for product in body["items"] if product["name"] == name)


class TestListProducts:
    def test_list_catalog(self):
        status, body = RequestGenerator.get_products()

        assert status == 200
        assert len(body["items"]) == 6
        for product in body["items"]:
            assert len(product["product_key"]) == 36
            assert "id" not in product
            assert product["type"] in PRODUCT_TYPES

    def test_filter_by_max_risk(self):
        status, body = RequestGenerator.get_products({"max_risk": "2"})

        assert status == 200
        assert len(body["items"]) == 4
        assert all(product["risk_level"] <= 2 for product in body["items"])

    def test_filter_by_type(self):
        status, body = RequestGenerator.get_products({"type": "FUND"})

        assert status == 200
        assert [product["name"] for product in body["items"]] == ["FGV Quant Capital FIM"]

    @pytest.mark.parametrize(
        "query_params",
        [{"max_risk": "0"}, {"max_risk": "abc"}, {"type": "STOCK"}, {"color": "blue"}],
    )
    def test_invalid_filter(self, query_params):
        status, body = RequestGenerator.get_products(query_params)

        assert status == 400
        assert body["code"] == "BNK000001"


class TestGetProduct:
    def test_get_product_with_price_of_the_day(self):
        product = product_named("Tesouro Selic 2031")

        status, body = RequestGenerator.get_product(product["product_key"])

        assert status == 200
        assert body["name"] == "Tesouro Selic 2031"
        # O preço do dia é o da data de movimento (RN-PRO-04), em texto (R6).
        assert body["price"]["reference_date"] == business_date().isoformat()
        assert float(body["price"]["unit_price"]) > 0
        assert len(body["price"]["unit_price"].split(".")[1]) == 8

    def test_own_issue_letter_is_an_offer_with_term(self):
        # Emissão própria: cada aplicação vence em data da aplicação + prazo (RN-PRO-09).
        product = product_named("LCI Quant Bank 12 meses")

        status, body = RequestGenerator.get_product(product["product_key"])

        assert status == 200
        assert body["term_months"] == 12
        assert body["maturity_date"] is None
        assert body["tax_exempt"] is True

    def test_public_bond_has_fixed_maturity(self):
        product = product_named("Tesouro Selic 2031")

        status, body = RequestGenerator.get_product(product["product_key"])

        assert status == 200
        assert body["term_months"] is None
        assert body["maturity_date"] == "2031-03-01"
        assert body["tax_exempt"] is False

    def test_product_not_found(self):
        status, body = RequestGenerator.get_product(str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "BNK005001"


class TestProductPrices:
    def test_price_history_in_period(self):
        product = product_named("FGV Quant Capital FIM")
        to_date = business_date()
        from_date = to_date - timedelta(days=6)

        status, body = RequestGenerator.get_product_prices(
            product["product_key"], {"from": from_date.isoformat(), "to": to_date.isoformat()}
        )

        assert status == 200
        dates = [price["reference_date"] for price in body["items"]]
        assert dates == sorted(dates)
        assert all(from_date.isoformat() <= day <= to_date.isoformat() for day in dates)
        # Sempre existe o preço da data de movimento (seed ou fechamento do dia).
        assert dates[-1] == to_date.isoformat()

    def test_price_history_product_not_found(self):
        status, body = RequestGenerator.get_product_prices(str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "BNK005001"

    @pytest.mark.parametrize("query_params", [{"from": "01/10/2026"}, {"to": "2026-02-30"}, {"page": "1"}])
    def test_invalid_period(self, query_params):
        product = product_named("FGV Quant Capital FIM")

        status, body = RequestGenerator.get_product_prices(product["product_key"], query_params)

        assert status == 400
        assert body["code"] == "BNK000001"
