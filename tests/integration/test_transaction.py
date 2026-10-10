import uuid
from datetime import timedelta

import pytest

from tests.utils import RequestGenerator
from tests.utils.helpers import (
    TRANSFER_FEE,
    balance_of,
    business_date,
    close_day,
    create_customer,
    deposit,
    open_account,
    send,
)


# Limites por operação (RN-MOV-02), em centavos.
DEPOSIT_LIMIT = 100_000_000
WITHDRAWAL_LIMIT = 500_000
TRANSFER_LIMIT = 5_000_000


def withdraw(customer_key: str, account_key: str, amount: int):
    return send(customer_key, account_key, {"type": "WITHDRAWAL", "amount": amount})


def transfer(customer_key: str, account_key: str, destination_account_key: str, amount: int):
    payload = {"type": "TRANSFER", "amount": amount, "destination_account_key": destination_account_key}
    return send(customer_key, account_key, payload)


class TestDeposit:
    def test_deposit_increases_balance(self):
        customer_key, account_key = open_account()

        status, body = deposit(customer_key, account_key, 10000)

        assert status == 201
        assert len(body["transaction_key"]) == 36
        assert "id" not in body
        assert body["type"] == "DEPOSIT"
        assert body["amount"] == 10000
        assert body["fee_amount"] == 0
        assert body["balance"] == 10000
        assert "created_at" in body
        assert balance_of(customer_key, account_key) == 10000

    def test_deposit_at_limit(self):
        customer_key, account_key = open_account()

        status, body = deposit(customer_key, account_key, DEPOSIT_LIMIT)

        assert status == 201
        assert body["balance"] == DEPOSIT_LIMIT


class TestWithdrawal:
    def test_withdrawal_decreases_balance(self):
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, 10000)

        status, body = withdraw(customer_key, account_key, 3000)

        assert status == 201
        assert body["type"] == "WITHDRAWAL"
        assert body["fee_amount"] == 0
        assert body["balance"] == 7000
        assert balance_of(customer_key, account_key) == 7000

    def test_insufficient_balance_changes_nothing(self):
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, 10000)

        status, body = withdraw(customer_key, account_key, 10001)

        assert status == 409
        assert body["code"] == "PPP003003"
        assert balance_of(customer_key, account_key) == 10000


class TestTransfer:
    def test_transfer_charges_fee_only_from_origin(self):
        """Exemplo do doc: A com R$ 1.000 e B com R$ 500; A transfere R$ 200."""
        origin_customer, origin_account = open_account()
        destination_customer, destination_account = open_account()
        deposit(origin_customer, origin_account, 100000)
        deposit(destination_customer, destination_account, 50000)

        status, body = transfer(origin_customer, origin_account, destination_account, 20000)

        assert status == 201
        assert body["type"] == "TRANSFER"
        assert body["amount"] == 20000
        assert body["fee_amount"] == TRANSFER_FEE
        assert body["balance"] == 79800
        assert balance_of(origin_customer, origin_account) == 79800
        assert balance_of(destination_customer, destination_account) == 70000

    def test_transfer_of_whole_balance_with_fee(self):
        """O saque passa pela mesma conta de saldo (com tarifa zero): este limite vale pelos dois."""
        origin_customer, origin_account = open_account()
        _, destination_account = open_account()
        deposit(origin_customer, origin_account, 10000 + TRANSFER_FEE)

        status, body = transfer(origin_customer, origin_account, destination_account, 10000)

        assert status == 201
        assert body["balance"] == 0

    def test_insufficient_balance_for_fee_changes_nothing(self):
        """Tem o valor, mas não o valor mais a tarifa (RN-MOV-04)."""
        origin_customer, origin_account = open_account()
        destination_customer, destination_account = open_account()
        deposit(origin_customer, origin_account, 10000)

        status, body = transfer(origin_customer, origin_account, destination_account, 10000)

        assert status == 409
        assert body["code"] == "PPP003003"
        assert balance_of(origin_customer, origin_account) == 10000
        assert balance_of(destination_customer, destination_account) == 0

    def test_same_account_transfer(self):
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, 10000)

        status, body = transfer(customer_key, account_key, account_key, 1000)

        assert status == 422
        assert body["code"] == "PPP003006"
        assert balance_of(customer_key, account_key) == 10000

    def test_destination_not_found(self):
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, 10000)

        status, body = transfer(customer_key, account_key, str(uuid.uuid4()), 1000)

        assert status == 404
        assert body["code"] == "PPP003002"
        assert balance_of(customer_key, account_key) == 10000

    @pytest.mark.parametrize("target_status", ["BLOCKED", "CLOSED"])
    def test_destination_not_active(self, target_status):
        origin_customer, origin_account = open_account()
        destination_customer, destination_account = open_account()
        deposit(origin_customer, origin_account, 10000)
        RequestGenerator.patch_internal_account_status(destination_account, {"status": target_status, "reason": "teste"})

        status, body = transfer(origin_customer, origin_account, destination_account, 1000)

        assert status == 409
        assert body["code"] == "PPP003007"
        assert balance_of(origin_customer, origin_account) == 10000

    def test_origin_not_active(self):
        origin_customer, origin_account = open_account()
        _, destination_account = open_account()
        deposit(origin_customer, origin_account, 10000)
        RequestGenerator.patch_internal_account_status(origin_account, {"status": "BLOCKED", "reason": "teste"})

        status, body = transfer(origin_customer, origin_account, destination_account, 1000)

        assert status == 409
        assert body["code"] == "PPP002005"
        assert balance_of(origin_customer, origin_account) == 10000

    def test_transfer_at_limit(self):
        origin_customer, origin_account = open_account()
        destination_customer, destination_account = open_account()
        deposit(origin_customer, origin_account, TRANSFER_LIMIT + TRANSFER_FEE)

        status, _ = transfer(origin_customer, origin_account, destination_account, TRANSFER_LIMIT)

        assert status == 201
        assert balance_of(destination_customer, destination_account) == TRANSFER_LIMIT

    def test_destination_of_other_customer_cannot_be_used_as_origin(self):
        """R8: pagar alguém pode; mover dinheiro da conta de outro cliente, não."""
        _, victim_account = open_account()
        attacker_customer, attacker_account = open_account()

        status, body = transfer(attacker_customer, victim_account, attacker_account, 1000)

        assert status == 404
        assert body["code"] == "PPP002001"


class TestIdempotency:
    """RN-GER-08 e RN-MOV-09: repetir o mesmo pedido não repete o efeito."""

    def test_repeated_transfer_moves_money_once(self):
        origin_customer, origin_account = open_account()
        destination_customer, destination_account = open_account()
        deposit(origin_customer, origin_account, 100000)
        key = str(uuid.uuid4())
        payload = {"type": "TRANSFER", "amount": 20000, "destination_account_key": destination_account}

        RequestGenerator.post_transaction(origin_customer, origin_account, payload, key)
        status, body = RequestGenerator.post_transaction(origin_customer, origin_account, payload, key)

        assert status == 200
        assert body["balance"] == 79800
        assert balance_of(origin_customer, origin_account) == 79800
        assert balance_of(destination_customer, destination_account) == 20000

    def test_repetition_returns_balance_of_that_moment(self):
        """A resposta repetida é a original, mesmo que a conta tenha mexido depois."""
        customer_key, account_key = open_account()
        key = str(uuid.uuid4())
        payload = {"type": "DEPOSIT", "amount": 10000}
        RequestGenerator.post_transaction(customer_key, account_key, payload, key)
        deposit(customer_key, account_key, 5000)

        status, body = RequestGenerator.post_transaction(customer_key, account_key, payload, key)

        assert status == 200
        assert body["balance"] == 10000
        assert balance_of(customer_key, account_key) == 15000

    def test_key_used_by_another_account_is_refused(self):
        """A chave é única no banco inteiro; a de outra conta dá 409 sem mostrar nada dela."""
        first_customer, first_account = open_account()
        second_customer, second_account = open_account()
        key = str(uuid.uuid4())
        payload = {"type": "DEPOSIT", "amount": 10000}
        RequestGenerator.post_transaction(first_customer, first_account, payload, key)

        status, body = RequestGenerator.post_transaction(second_customer, second_account, payload, key)

        assert status == 409
        assert body["code"] == "PPP000004"
        assert "transaction_key" not in body
        assert balance_of(second_customer, second_account) == 0

    @pytest.mark.parametrize(
        "second_request",
        [
            lambda destination, other: {"type": "TRANSFER", "amount": 30000, "destination_account_key": destination},
            lambda destination, other: {"type": "TRANSFER", "amount": 20000, "destination_account_key": other},
            lambda destination, other: {"type": "WITHDRAWAL", "amount": 20000},
        ],
        ids=["other_amount", "other_destination", "other_type"],
    )
    def test_same_key_with_another_request(self, second_request):
        """Repetição é o MESMO pedido: mesma chave com outro valor, destino ou tipo é outro pedido (409)."""
        origin_customer, origin_account = open_account()
        _, destination = open_account()
        _, other_destination = open_account()
        deposit(origin_customer, origin_account, 100000)
        key = str(uuid.uuid4())
        first = {"type": "TRANSFER", "amount": 20000, "destination_account_key": destination}
        RequestGenerator.post_transaction(origin_customer, origin_account, first, key)

        status, body = RequestGenerator.post_transaction(
            origin_customer, origin_account, second_request(destination, other_destination), key
        )

        assert status == 409
        assert body["code"] == "PPP000004"
        assert balance_of(origin_customer, origin_account) == 100000 - 20000 - TRANSFER_FEE

    def test_field_order_does_not_matter(self):
        customer_key, account_key = open_account()
        key = str(uuid.uuid4())
        RequestGenerator.post_transaction(customer_key, account_key, {"type": "DEPOSIT", "amount": 10000}, key)

        status, _ = RequestGenerator.post_transaction(
            customer_key, account_key, {"amount": 10000, "type": "DEPOSIT"}, key
        )

        assert status == 200
        assert balance_of(customer_key, account_key) == 10000

    def test_refused_request_does_not_use_up_the_key(self):
        """Recusa não grava nada; a mesma chave pode ser usada depois que der para executar."""
        customer_key, account_key = open_account()
        key = str(uuid.uuid4())
        payload = {"type": "WITHDRAWAL", "amount": 3000}

        refused_status, _ = RequestGenerator.post_transaction(customer_key, account_key, payload, key)
        deposit(customer_key, account_key, 10000)
        status, body = RequestGenerator.post_transaction(customer_key, account_key, payload, key)

        assert refused_status == 409
        assert status == 201
        assert body["balance"] == 7000

    def test_repetition_after_account_was_blocked(self):
        """A repetição é conferida antes do status: devolve a original em vez de 409 (rfc_fluxos)."""
        customer_key, account_key = open_account()
        key = str(uuid.uuid4())
        payload = {"type": "DEPOSIT", "amount": 10000}
        _, first = RequestGenerator.post_transaction(customer_key, account_key, payload, key)
        RequestGenerator.patch_internal_account_status(account_key, {"status": "BLOCKED", "reason": "teste"})

        status, body = RequestGenerator.post_transaction(customer_key, account_key, payload, key)

        assert status == 200
        assert body == first

    @pytest.mark.parametrize("key", ["", "nao-e-um-uuid"])
    def test_invalid_idempotency_key(self, key):
        customer_key, account_key = open_account()

        status, body = RequestGenerator.post_transaction(
            customer_key, account_key, {"type": "DEPOSIT", "amount": 1000}, key
        )

        assert status == 400
        assert body["code"] == "PPP000003"
        assert balance_of(customer_key, account_key) == 0


class TestTransactionRefusals:
    @pytest.mark.parametrize("amount", [0, -100])
    def test_invalid_amount(self, amount):
        customer_key, account_key = open_account()

        status, body = deposit(customer_key, account_key, amount)

        assert status == 422
        assert body["code"] == "PPP003004"

    @pytest.mark.parametrize(
        "transaction_type, limit",
        [("DEPOSIT", DEPOSIT_LIMIT), ("WITHDRAWAL", WITHDRAWAL_LIMIT), ("TRANSFER", TRANSFER_LIMIT)],
    )
    def test_above_limit_changes_nothing(self, transaction_type, limit):
        customer_key, account_key = open_account()
        _, destination_account = open_account()
        deposit(customer_key, account_key, TRANSFER_LIMIT * 2)
        payload = {"type": transaction_type, "amount": limit + 1}
        if transaction_type == "TRANSFER":
            payload["destination_account_key"] = destination_account

        status, body = send(customer_key, account_key, payload)

        assert status == 422
        assert body["code"] == "PPP003005"
        assert balance_of(customer_key, account_key) == TRANSFER_LIMIT * 2

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"amount": 1000},
            {"type": "DEPOSIT"},
            {"type": "INVESTMENT_APPLY", "amount": 1000},
            {"type": "INVESTMENT_REDEEM", "amount": 1000},
            {"type": "deposit", "amount": 1000},
            {"type": "DEPOSIT", "amount": 10.5},
            {"type": "DEPOSIT", "amount": "1000"},
            {"type": "DEPOSIT", "amount": 1000, "description": "A" * 141},
            {"type": "DEPOSIT", "amount": 1000, "extra": "campo fora do contrato"},
        ],
    )
    def test_malformed_payload(self, payload):
        customer_key, account_key = open_account()

        status, body = send(customer_key, account_key, payload)

        assert status == 400
        assert body["code"] == "PPP000001"

    def test_missing_idempotency_key(self):
        customer_key, account_key = open_account()

        status, body = RequestGenerator.post_transaction(
            customer_key, account_key, {"type": "DEPOSIT", "amount": 1000}, None
        )

        assert status == 400
        assert body["code"] == "PPP000003"
        assert balance_of(customer_key, account_key) == 0

    @pytest.mark.parametrize("transaction_type, target_status", [("DEPOSIT", "BLOCKED"), ("WITHDRAWAL", "CLOSED")])
    def test_account_not_active(self, transaction_type, target_status):
        customer_key, account_key = open_account()
        RequestGenerator.patch_internal_account_status(account_key, {"status": target_status, "reason": "teste"})

        status, body = send(customer_key, account_key, {"type": transaction_type, "amount": 1000})

        assert status == 409
        assert body["code"] == "PPP002005"

    def test_account_of_another_customer(self):
        """R8: a conta existe, mas não é deste cliente. Resposta igual à de inexistente."""
        _, account_key = open_account()
        other_customer_key = create_customer()

        status, body = deposit(other_customer_key, account_key, 1000)

        assert status == 404
        assert body["code"] == "PPP002001"

    def test_account_not_found(self):
        customer_key = create_customer()

        status, body = deposit(customer_key, str(uuid.uuid4()), 1000)

        assert status == 404
        assert body["code"] == "PPP002001"

    def test_customer_not_found(self):
        status, body = deposit(str(uuid.uuid4()), str(uuid.uuid4()), 1000)

        assert status == 404
        assert body["code"] == "PPP001001"


def statement(customer_key: str, account_key: str, **query_params) -> list:
    status, body = RequestGenerator.get_transactions(customer_key, account_key, {"limit": "100", **query_params})
    assert status == 200
    return body["items"]


class TestStatement:
    """RN-MOV-12: o extrato lista os lançamentos da conta, do mais novo para o mais antigo."""

    def test_statement_rebuilds_balance(self):
        """O invariante: saldo = soma dos créditos - soma dos débitos do extrato."""
        customer_key, account_key = open_account()
        other_customer, other_account = open_account()
        deposit(customer_key, account_key, 100000)
        deposit(other_customer, other_account, 10000)
        withdraw(customer_key, account_key, 3000)
        transfer(customer_key, account_key, other_account, 20000)
        transfer(other_customer, other_account, account_key, 5000)

        items = statement(customer_key, account_key)

        credits = sum(item["amount"] for item in items if item["direction"] == "CREDIT")
        debits = sum(item["amount"] for item in items if item["direction"] == "DEBIT")
        balance = balance_of(customer_key, account_key)
        assert balance == 100000 - 3000 - 20000 - TRANSFER_FEE + 5000
        assert credits - debits == balance
        assert items[0]["balance_after"] == balance

    def test_transfer_shows_on_both_sides(self):
        origin_customer, origin_account = open_account()
        destination_customer, destination_account = open_account()
        deposit(origin_customer, origin_account, 100000)
        _, transfer_body = transfer(origin_customer, origin_account, destination_account, 20000)

        origin_items = statement(origin_customer, origin_account, type="TRANSFER")
        destination_items = statement(destination_customer, destination_account)

        assert [(item["direction"], item["category"], item["amount"]) for item in origin_items] == [
            ("DEBIT", "FEE", TRANSFER_FEE),
            ("DEBIT", "PRINCIPAL", 20000),
        ]
        assert [item["balance_after"] for item in origin_items] == [79800, 80000]
        assert all(item["counterparty_account_key"] == destination_account for item in origin_items)
        assert len(destination_items) == 1
        assert destination_items[0]["direction"] == "CREDIT"
        assert destination_items[0]["amount"] == 20000
        assert destination_items[0]["counterparty_account_key"] == origin_account
        transaction_keys = {item["transaction_key"] for item in origin_items + destination_items}
        assert transaction_keys == {transfer_body["transaction_key"]}

    def test_entry_fields(self):
        customer_key, account_key = open_account()
        send(customer_key, account_key, {"type": "DEPOSIT", "amount": 10000, "description": "salário"})

        items = statement(customer_key, account_key)

        assert len(items) == 1
        entry = items[0]
        assert "id" not in entry
        assert len(entry["transaction_key"]) == 36
        assert entry["type"] == "DEPOSIT"
        assert entry["direction"] == "CREDIT"
        assert entry["category"] == "PRINCIPAL"
        assert entry["amount"] == 10000
        assert entry["balance_after"] == 10000
        assert entry["description"] == "salário"
        assert entry["counterparty_account_key"] is None
        assert "created_at" in entry

    def test_pagination_newest_first(self):
        customer_key, account_key = open_account()
        for amount in [1000, 2000, 3000, 4000, 5000]:
            deposit(customer_key, account_key, amount)

        pages = []
        for page in ["1", "2", "3", "4"]:
            status, body = RequestGenerator.get_transactions(customer_key, account_key, {"page": page, "limit": "2"})
            assert status == 200
            assert (body["page"], body["limit"], body["total"]) == (int(page), 2, 5)
            pages.append([item["amount"] for item in body["items"]])

        assert pages == [[5000, 4000], [3000, 2000], [1000], []]

    def test_default_paging(self):
        customer_key, account_key = open_account()
        for _ in range(21):
            deposit(customer_key, account_key, 100)

        status, body = RequestGenerator.get_transactions(customer_key, account_key)

        assert status == 200
        assert (body["page"], body["limit"], body["total"]) == (1, 20, 21)
        assert len(body["items"]) == 20

    @pytest.mark.parametrize(
        "query_params",
        [
            {"page": "0"},
            {"page": "abc"},
            {"limit": "0"},
            {"limit": "101"},
            {"type": "deposit"},
            {"from": "01/10/2026"},
            {"to": "2026-02-30"},
            {"status": "ACTIVE"},
        ],
    )
    def test_invalid_query(self, query_params):
        customer_key, account_key = open_account()

        status, body = RequestGenerator.get_transactions(customer_key, account_key, query_params)

        assert status == 400
        assert body["code"] == "PPP000001"

    def test_from_after_to(self):
        customer_key, account_key = open_account()

        status, body = RequestGenerator.get_transactions(
            customer_key, account_key, {"from": "2026-10-10", "to": "2026-10-01"}
        )

        assert status == 400
        assert body["code"] == "PPP000005"

    def test_filter_by_type(self):
        customer_key, account_key = open_account()
        _, other_account = open_account()
        deposit(customer_key, account_key, 100000)
        withdraw(customer_key, account_key, 1000)
        transfer(customer_key, account_key, other_account, 1000)

        items = statement(customer_key, account_key, type="WITHDRAWAL")

        assert [(item["type"], item["amount"]) for item in items] == [("WITHDRAWAL", 1000)]

    def test_filter_by_date(self):
        """Datas de movimento (o calendário do banco), com as duas pontas inclusas."""
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, 1000)
        today = business_date()
        tomorrow = (today + timedelta(days=1)).isoformat()
        yesterday = (today - timedelta(days=1)).isoformat()

        items = statement(customer_key, account_key, **{"from": today.isoformat(), "to": today.isoformat()})
        assert [item["business_date"] for item in items] == [today.isoformat()]
        assert statement(customer_key, account_key, **{"from": tomorrow}) == []
        assert statement(customer_key, account_key, to=yesterday) == []

    def test_statement_follows_the_business_day(self):
        """O lançamento fica no dia de movimento em que aconteceu, mesmo depois do fechamento."""
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, 1000)
        first_day = business_date()
        close_day()
        second_day = business_date()
        deposit(customer_key, account_key, 2000)

        first = statement(customer_key, account_key, **{"from": first_day.isoformat(), "to": first_day.isoformat()})
        second = statement(customer_key, account_key, **{"from": second_day.isoformat()})
        assert [(item["amount"], item["business_date"]) for item in first] == [(1000, first_day.isoformat())]
        assert [(item["amount"], item["business_date"]) for item in second] == [(2000, second_day.isoformat())]

    def test_blocked_account_still_sees_statement(self):
        """RN-CON-09: conta bloqueada não movimenta, mas consulta."""
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, 1000)
        RequestGenerator.patch_internal_account_status(account_key, {"status": "BLOCKED", "reason": "teste"})

        assert len(statement(customer_key, account_key)) == 1

    def test_account_of_another_customer(self):
        _, account_key = open_account()
        other_customer_key = create_customer()

        status, body = RequestGenerator.get_transactions(other_customer_key, account_key)

        assert status == 404
        assert body["code"] == "PPP002001"


class TestReceipt:
    """RN-MOV-13: o comprovante só aparece para as contas que participaram da transação."""

    def test_origin_and_destination_see_the_receipt(self):
        origin_customer, origin_account = open_account()
        destination_customer, destination_account = open_account()
        deposit(origin_customer, origin_account, 100000)
        payload = {
            "type": "TRANSFER", "amount": 20000, "destination_account_key": destination_account, "description": "aluguel"
        }
        _, created = send(origin_customer, origin_account, payload)
        transaction_key = created["transaction_key"]

        origin_status, origin_receipt = RequestGenerator.get_transaction(
            origin_customer, origin_account, transaction_key
        )
        destination_status, destination_receipt = RequestGenerator.get_transaction(
            destination_customer, destination_account, transaction_key
        )

        assert (origin_status, destination_status) == (200, 200)
        assert origin_receipt == destination_receipt
        assert origin_receipt == {
            "transaction_key": transaction_key,
            "type": "TRANSFER",
            "amount": 20000,
            "fee_amount": TRANSFER_FEE,
            "description": "aluguel",
            "origin_account_key": origin_account,
            "destination_account_key": destination_account,
            "business_date": business_date().isoformat(),
            "created_at": created["created_at"],
        }

    def test_deposit_receipt(self):
        customer_key, account_key = open_account()
        _, created = deposit(customer_key, account_key, 1000)

        status, receipt = RequestGenerator.get_transaction(customer_key, account_key, created["transaction_key"])

        assert status == 200
        assert receipt["origin_account_key"] is None
        assert receipt["destination_account_key"] == account_key

    def test_account_not_involved(self):
        """R8: a transação existe, mas não envolve esta conta. Resposta igual à de inexistente."""
        customer_key, account_key = open_account()
        _, created = deposit(customer_key, account_key, 1000)
        other_customer, other_account = open_account()

        status, body = RequestGenerator.get_transaction(other_customer, other_account, created["transaction_key"])

        assert status == 404
        assert body["code"] == "PPP003001"

    def test_transaction_not_found(self):
        customer_key, account_key = open_account()

        status, body = RequestGenerator.get_transaction(customer_key, account_key, str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP003001"

    def test_account_of_another_customer(self):
        customer_key, account_key = open_account()
        _, created = deposit(customer_key, account_key, 1000)
        other_customer_key = create_customer()

        status, body = RequestGenerator.get_transaction(other_customer_key, account_key, created["transaction_key"])

        assert status == 404
        assert body["code"] == "PPP002001"
