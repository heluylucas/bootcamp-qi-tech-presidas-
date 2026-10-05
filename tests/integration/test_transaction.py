import uuid

import pytest

from tests.utils import RandomGenerator, RequestGenerator


# Limites por operação (RN-MOV-02), em centavos.
DEPOSIT_LIMIT = 100_000_000
WITHDRAWAL_LIMIT = 500_000
TRANSFER_LIMIT = 5_000_000

# Tarifa de transferência (RN-MOV-10), em centavos.
TRANSFER_FEE = 200


def create_customer() -> str:
    payload = {"name": "Ana Silva", "document_number": RandomGenerator.generate_cpf(), "birth_date": "1990-05-17"}
    _, body = RequestGenerator.post_customer(payload)
    return body["customer_key"]


def open_account() -> tuple:
    customer_key = create_customer()
    _, account = RequestGenerator.post_account(customer_key)
    return customer_key, account["account_key"]


def send(customer_key: str, account_key: str, payload: dict):
    """Cada chamada usa uma Idempotency-Key nova: é um pedido novo, não uma repetição."""
    return RequestGenerator.post_transaction(customer_key, account_key, payload, str(uuid.uuid4()))


def deposit(customer_key: str, account_key: str, amount: int):
    return send(customer_key, account_key, {"type": "DEPOSIT", "amount": amount})


def withdraw(customer_key: str, account_key: str, amount: int):
    return send(customer_key, account_key, {"type": "WITHDRAWAL", "amount": amount})


def transfer(customer_key: str, account_key: str, destination_account_key: str, amount: int):
    payload = {"type": "TRANSFER", "amount": amount, "destination_account_key": destination_account_key}
    return send(customer_key, account_key, payload)


def balance_of(customer_key: str, account_key: str) -> int:
    _, account = RequestGenerator.get_account(customer_key, account_key)
    return account["balance"]


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

    def test_deposit_above_limit(self):
        customer_key, account_key = open_account()

        status, body = deposit(customer_key, account_key, DEPOSIT_LIMIT + 1)

        assert status == 422
        assert body["code"] == "PPP003005"
        assert balance_of(customer_key, account_key) == 0


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

    def test_withdrawal_of_whole_balance(self):
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, 10000)

        status, body = withdraw(customer_key, account_key, 10000)

        assert status == 201
        assert body["balance"] == 0

    def test_insufficient_balance_changes_nothing(self):
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, 10000)

        status, body = withdraw(customer_key, account_key, 10001)

        assert status == 409
        assert body["code"] == "PPP003003"
        assert balance_of(customer_key, account_key) == 10000

    def test_withdrawal_above_limit(self):
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, WITHDRAWAL_LIMIT * 2)

        status, body = withdraw(customer_key, account_key, WITHDRAWAL_LIMIT + 1)

        assert status == 422
        assert body["code"] == "PPP003005"
        assert balance_of(customer_key, account_key) == WITHDRAWAL_LIMIT * 2


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
        RequestGenerator.patch_account(
            destination_customer, destination_account, {"status": target_status, "reason": "teste"}
        )

        status, body = transfer(origin_customer, origin_account, destination_account, 1000)

        assert status == 409
        assert body["code"] == "PPP003007"
        assert balance_of(origin_customer, origin_account) == 10000

    def test_origin_not_active(self):
        origin_customer, origin_account = open_account()
        _, destination_account = open_account()
        deposit(origin_customer, origin_account, 10000)
        RequestGenerator.patch_account(origin_customer, origin_account, {"status": "BLOCKED", "reason": "teste"})

        status, body = transfer(origin_customer, origin_account, destination_account, 1000)

        assert status == 409
        assert body["code"] == "PPP002005"
        assert balance_of(origin_customer, origin_account) == 10000

    def test_transfer_above_limit(self):
        origin_customer, origin_account = open_account()
        _, destination_account = open_account()
        deposit(origin_customer, origin_account, TRANSFER_LIMIT * 2)

        status, body = transfer(origin_customer, origin_account, destination_account, TRANSFER_LIMIT + 1)

        assert status == 422
        assert body["code"] == "PPP003005"
        assert balance_of(origin_customer, origin_account) == TRANSFER_LIMIT * 2

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

    def test_repeated_deposit_returns_original(self):
        customer_key, account_key = open_account()
        key = str(uuid.uuid4())
        payload = {"type": "DEPOSIT", "amount": 10000}

        first_status, first = RequestGenerator.post_transaction(customer_key, account_key, payload, key)
        second_status, second = RequestGenerator.post_transaction(customer_key, account_key, payload, key)

        assert first_status == 201
        assert second_status == 200
        assert second == first
        assert balance_of(customer_key, account_key) == 10000

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

    def test_field_order_does_not_matter(self):
        customer_key, account_key = open_account()
        key = str(uuid.uuid4())
        RequestGenerator.post_transaction(customer_key, account_key, {"type": "DEPOSIT", "amount": 10000}, key)

        status, _ = RequestGenerator.post_transaction(
            customer_key, account_key, {"amount": 10000, "type": "DEPOSIT"}, key
        )

        assert status == 200
        assert balance_of(customer_key, account_key) == 10000

    def test_same_key_with_different_body(self):
        customer_key, account_key = open_account()
        key = str(uuid.uuid4())
        RequestGenerator.post_transaction(customer_key, account_key, {"type": "DEPOSIT", "amount": 10000}, key)

        status, body = RequestGenerator.post_transaction(
            customer_key, account_key, {"type": "DEPOSIT", "amount": 20000}, key
        )

        assert status == 409
        assert body["code"] == "PPP000004"
        assert balance_of(customer_key, account_key) == 10000

    def test_same_key_in_another_account_is_a_new_request(self):
        """A chave vale por conta: UNIQUE(requester_account_id, idempotency_key)."""
        first_customer, first_account = open_account()
        second_customer, second_account = open_account()
        key = str(uuid.uuid4())
        payload = {"type": "DEPOSIT", "amount": 10000}

        first_status, first = RequestGenerator.post_transaction(first_customer, first_account, payload, key)
        second_status, second = RequestGenerator.post_transaction(second_customer, second_account, payload, key)

        assert (first_status, second_status) == (201, 201)
        assert first["transaction_key"] != second["transaction_key"]
        assert balance_of(second_customer, second_account) == 10000

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
        RequestGenerator.patch_account(customer_key, account_key, {"status": "BLOCKED", "reason": "teste"})

        status, body = RequestGenerator.post_transaction(customer_key, account_key, payload, key)

        assert status == 200
        assert body == first

    @pytest.mark.parametrize("key", ["", "a" * 37])
    def test_invalid_idempotency_key(self, key):
        customer_key, account_key = open_account()

        status, body = RequestGenerator.post_transaction(
            customer_key, account_key, {"type": "DEPOSIT", "amount": 1000}, key
        )

        assert status == 400
        assert body["code"] == "PPP000003"
        assert balance_of(customer_key, account_key) == 0


class TestTransactionRefusals:
    @pytest.mark.parametrize("transaction_type", ["DEPOSIT", "WITHDRAWAL"])
    @pytest.mark.parametrize("amount", [0, -100])
    def test_invalid_amount(self, transaction_type, amount):
        customer_key, account_key = open_account()

        status, body = send(customer_key, account_key, {"type": transaction_type, "amount": amount})

        assert status == 422
        assert body["code"] == "PPP003004"

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

    @pytest.mark.parametrize("transaction_type", ["DEPOSIT", "WITHDRAWAL"])
    @pytest.mark.parametrize("target_status", ["BLOCKED", "CLOSED"])
    def test_account_not_active(self, transaction_type, target_status):
        customer_key, account_key = open_account()
        RequestGenerator.patch_account(customer_key, account_key, {"status": target_status, "reason": "teste"})

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
