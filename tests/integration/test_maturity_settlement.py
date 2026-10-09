from datetime import date

from tests.integration.test_investment_order import (
    CONSERVATIVE,
    LCI,
    apply,
    balance_of,
    business_date,
    investor,
    product_key,
)
from tests.utils import DbUtils, RequestGenerator


def close_days_until(day: date) -> None:
    """Fecha um dia útil atrás do outro até a data de movimento chegar ao dia.

    Sem ensinar nada ao mock: os preços vêm do cenário que o mock-init ensina ao subir.
    """
    while business_date() < day:
        status, body = RequestGenerator.post_day_close({"close_date": business_date().isoformat()})
        assert status == 201, body


def lci_orders(customer_key: str, account_key: str) -> list:
    _, body = RequestGenerator.get_investment_orders(customer_key, account_key, {"product_key": product_key(LCI)})
    return body["items"]


class TestMaturitySettlement:
    def test_day_close_pays_back_lci_at_maturity(self):
        """RN-FEC-09: no vencimento, o fechamento do dia resgata a LCI sozinho e o dinheiro volta à conta."""
        # A data de movimento volta a hoje, para o ano inteiro caber nos dias que o mock conhece.
        DbUtils.rollback()
        try:
            customer_key, account_key = investor(CONSERVATIVE)
            _, applied = apply(customer_key, account_key, LCI, 10000)
            assert balance_of(customer_key, account_key) == 1_000_000 - 10000

            close_days_until(date.fromisoformat(applied["maturity_date"]))

            # O dinheiro voltou com o rendimento do ano.
            balance = balance_of(customer_key, account_key)
            assert balance > 1_000_000

            settlement, original = lci_orders(customer_key, account_key)
            assert original["order_key"] == applied["order_key"]
            assert settlement["side"] == "REDEEM"
            assert settlement["source"] == "MATURITY"
            assert settlement["quantity"] == applied["quantity"]
            assert settlement["acquisition_cost_amount"] == 10000
            assert settlement["amount"] == balance - (1_000_000 - 10000)
            assert settlement["result_amount"] > 0

            # A posição zerou, mas continua existindo (RN-ORD-14).
            _, positions = RequestGenerator.get_positions(customer_key, account_key)
            assert positions["items"] == []
            _, with_closed = RequestGenerator.get_positions(customer_key, account_key, {"include_closed": "true"})
            assert [item["quantity"] for item in with_closed["items"]] == ["0.00000000"]

            # Um fechamento a mais não paga de novo.
            status, _ = RequestGenerator.post_day_close({"close_date": business_date().isoformat()})
            assert status == 201
            assert balance_of(customer_key, account_key) == balance
            assert len(lci_orders(customer_key, account_key)) == 2
        finally:
            # Não deixa o banco um ano à frente para os outros testes.
            DbUtils.rollback()
