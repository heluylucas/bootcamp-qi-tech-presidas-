import uuid
from datetime import timedelta

import pytest

from tests.utils import RequestGenerator
from tests.utils.helpers import FUND, LCI, SELIC, business_date, product_key


PRODUCT_TYPES = {"PUBLIC_BOND", "PRIVATE_BOND", "FUND"}


class TestListProducts:
    def test_list_catalog(self):
        status, body = RequestGenerator.get_products()

        assert status == 200
        assert len(body["items"]) == 6
        for product in body["items"]:
            assert len(product["product_key"]) == 36
            assert product["type"] in PRODUCT_TYPES

    def test_filter_by_maximum_risk_level(self):
        status, body = RequestGenerator.get_products({"maximum_risk_level": "2"})

        assert status == 200
        assert len(body["items"]) == 4
        assert all(product["risk_level"] <= 2 for product in body["items"])

    def test_filter_by_type(self):
        status, body = RequestGenerator.get_products({"type": "FUND"})

        assert status == 200
        assert [product["name"] for product in body["items"]] == [FUND]

    @pytest.mark.parametrize(
        "query_params",
        [{"maximum_risk_level": "0"}, {"maximum_risk_level": "abc"}, {"type": "STOCK"}, {"color": "blue"}],
    )
    def test_invalid_filter(self, query_params):
        status, body = RequestGenerator.get_products(query_params)

        assert status == 400
        assert body["code"] == "PPP000001"


class TestGetProduct:
    def test_get_product_with_price_of_the_day(self):
        status, body = RequestGenerator.get_product(product_key(SELIC))

        assert status == 200
        assert body["name"] == SELIC
        # Aplicação mínima em centavos: R$ 50,00.
        assert body["minimum_application_amount"] == 5000
        # O preço do dia é o da data de movimento (RN-PRO-04), em texto (R6).
        assert body["price"]["price_date"] == business_date().isoformat()
        assert float(body["price"]["unit_price"]) > 0
        assert len(body["price"]["unit_price"].split(".")[1]) == 8

    def test_own_issue_letter_is_an_offer_with_term(self):
        # Emissão própria: cada aplicação vence em data da aplicação + prazo (RN-PRO-09).
        status, body = RequestGenerator.get_product(product_key(LCI))

        assert status == 200
        assert body["term_months"] == 12
        # O prazo diz tudo: com prazo, só resgata no vencimento. Não há liquidez nem data fixa à parte.
        assert "liquidity" not in body
        assert "maturity_date" not in body
        # Imposto de renda está fora do escopo: o produto não diz se é isento.
        assert "tax_exempt" not in body

    def test_public_bond_has_no_term(self):
        # Sem prazo: o resgate pode ser a qualquer dia.
        status, body = RequestGenerator.get_product(product_key(SELIC))

        assert status == 200
        assert body["term_months"] is None

    def test_product_not_found(self):
        status, body = RequestGenerator.get_product(str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP005001"


class TestProductPrices:
    def test_price_history_in_period(self):
        to_date = business_date()
        from_date = to_date - timedelta(days=6)

        status, body = RequestGenerator.get_product_prices(
            product_key(FUND), {"from": from_date.isoformat(), "to": to_date.isoformat()}
        )

        assert status == 200
        dates = [price["price_date"] for price in body["items"]]
        assert dates == sorted(dates)
        assert all(from_date.isoformat() <= day <= to_date.isoformat() for day in dates)
        # Sempre existe o preço da data de movimento (seed ou fechamento do dia).
        assert dates[-1] == to_date.isoformat()

    def test_price_history_product_not_found(self):
        status, body = RequestGenerator.get_product_prices(str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP005001"

    @pytest.mark.parametrize("query_params", [{"from": "01/10/2026"}, {"to": "2026-02-30"}, {"page": "1"}])
    def test_invalid_period(self, query_params):
        status, body = RequestGenerator.get_product_prices(product_key(FUND), query_params)

        assert status == 400
        assert body["code"] == "PPP000001"
