from datetime import date

from tests.utils import DbUtils, RequestGenerator
from tests.utils.helpers import (
    CONSERVATIVE,
    LCI,
    apply,
    balance_of,
    business_date,
    investor,
    open_account,
    product_key,
    send,
)


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

    def test_day_close_pays_back_lci_to_blocked_account(self):
        """RN-FEC-09: a conta bloqueada recebe o vencimento, mas o cliente continua sem sacar nem transferir."""
        DbUtils.rollback()
        try:
            customer_key, account_key = investor(CONSERVATIVE)
            _, applied = apply(customer_key, account_key, LCI, 10000)
            # Bloqueia depois de aplicar: conta bloqueada não aplica (PPP002005).
            RequestGenerator.patch_internal_account_status(
                account_key, {"status": "BLOCKED", "reason": "Suspeita de fraude"}
            )

            close_days_until(date.fromisoformat(applied["maturity_date"]))

            # O dinheiro voltou mesmo com a conta bloqueada: o banco devolver não é o cliente movimentar.
            balance = balance_of(customer_key, account_key)
            assert balance > 1_000_000
            settlement, _ = lci_orders(customer_key, account_key)
            assert (settlement["side"], settlement["source"]) == ("REDEEM", "MATURITY")

            # Continua bloqueada, e o dinheiro que entrou também está preso: não saca nem transfere.
            _, account = RequestGenerator.get_account(customer_key, account_key)
            assert account["status"] == "BLOCKED"
            _, destination_key = open_account()
            withdrawal_status, withdrawal = send(customer_key, account_key, {"type": "WITHDRAWAL", "amount": 1000})
            transfer_status, transfer = send(
                customer_key,
                account_key,
                {"type": "TRANSFER", "amount": 1000, "destination_account_key": destination_key},
            )
            assert (withdrawal_status, withdrawal["code"]) == (409, "PPP002005")
            assert (transfer_status, transfer["code"]) == (409, "PPP002005")
            assert balance_of(customer_key, account_key) == balance
        finally:
            DbUtils.rollback()
