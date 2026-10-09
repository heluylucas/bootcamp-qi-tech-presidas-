import uuid

import pytest

from tests.utils import RandomGenerator, RequestGenerator


def create_customer() -> str:
    payload = {"name": "Ana Silva", "document_number": RandomGenerator.generate_cpf(), "birth_date": "1990-05-17"}
    _, body = RequestGenerator.post_customer(payload)
    return body["customer_key"]


def open_account() -> tuple:
    customer_key = create_customer()
    _, account = RequestGenerator.post_account(customer_key)
    return customer_key, account["account_key"]


def customer_change(customer_key: str, account_key: str, status: str, reason: str = "motivo de teste"):
    """Rota do cliente: ele só pode encerrar (RN-CON-11)."""
    return RequestGenerator.patch_account(customer_key, account_key, {"status": status, "reason": reason})


def bank_change(account_key: str, status: str, reason: str = "motivo de teste"):
    """Rota do banco, com o token de operador: bloqueia, desbloqueia e encerra (RN-CON-11)."""
    return RequestGenerator.patch_internal_account_status(account_key, {"status": status, "reason": reason})


def deposit(customer_key: str, account_key: str, amount: int) -> None:
    payload = {"type": "DEPOSIT", "amount": amount}
    RequestGenerator.post_transaction(customer_key, account_key, payload, str(uuid.uuid4()))


def status_of(customer_key: str, account_key: str) -> str:
    _, account = RequestGenerator.get_account(customer_key, account_key)
    return account["status"]


class TestOpenAccount:
    def test_open_account(self):
        customer_key = create_customer()

        status, body = RequestGenerator.post_account(customer_key)

        assert status == 201
        assert len(body["account_key"]) == 36
        assert "id" not in body
        assert body["status"] == "ACTIVE"
        assert body["balance"] == 0
        # Conta nova: nada investido, o capital total é o próprio saldo.
        assert body["investments_amount"] == 0
        assert body["net_worth_amount"] == 0
        assert "created_at" in body
        assert "updated_at" in body

    def test_customer_not_found(self):
        status, body = RequestGenerator.post_account(str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP001001"

    def test_second_account_refused(self):
        customer_key, _ = open_account()

        status, body = RequestGenerator.post_account(customer_key)

        assert status == 409
        assert body["code"] == "PPP002002"

    def test_second_account_refused_while_blocked(self):
        customer_key, account_key = open_account()
        bank_change(account_key, "BLOCKED")

        status, body = RequestGenerator.post_account(customer_key)

        assert status == 409
        assert body["code"] == "PPP002002"

    def test_new_account_after_closing(self):
        customer_key, account_key = open_account()
        customer_change(customer_key, account_key, "CLOSED")

        status, body = RequestGenerator.post_account(customer_key)

        assert status == 201
        assert body["account_key"] != account_key


class TestGetAccount:
    def test_get_account(self):
        customer_key = create_customer()
        _, created = RequestGenerator.post_account(customer_key)

        status, body = RequestGenerator.get_account(customer_key, created["account_key"])

        assert status == 200
        assert body == created

    def test_account_not_found(self):
        customer_key = create_customer()

        status, body = RequestGenerator.get_account(customer_key, str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "PPP002001"

    def test_account_of_another_customer(self):
        """R8: a conta existe, mas não é deste cliente. Resposta igual à de inexistente.

        O PATCH pede BLOCKED (ação do banco) e mesmo assim sai 404: o dono é
        conferido antes de tudo (RN-CON-11), então nem o 403 vaza que a conta existe.
        """
        _, account_key = open_account()
        other_customer_key = create_customer()

        get_status, get_body = RequestGenerator.get_account(other_customer_key, account_key)
        patch_status, patch_body = customer_change(other_customer_key, account_key, "BLOCKED")
        events_status, events_body = RequestGenerator.get_account_status_events(other_customer_key, account_key)

        assert (get_status, get_body["code"]) == (404, "PPP002001")
        assert (patch_status, patch_body["code"]) == (404, "PPP002001")
        assert (events_status, events_body["code"]) == (404, "PPP002001")


class TestCustomerChangesStatus:
    """RN-CON-11: pela rota do cliente, só encerrar."""

    def test_customer_closes_empty_account(self):
        customer_key, account_key = open_account()

        status, body = customer_change(customer_key, account_key, "CLOSED")

        assert status == 200
        assert body["status"] == "CLOSED"

    def test_customer_closes_account_blocked_by_bank(self):
        customer_key, account_key = open_account()
        bank_change(account_key, "BLOCKED")

        status, body = customer_change(customer_key, account_key, "CLOSED")

        assert status == 200
        assert body["status"] == "CLOSED"

    def test_customer_cannot_block(self):
        customer_key, account_key = open_account()

        status, body = customer_change(customer_key, account_key, "BLOCKED")

        assert status == 403
        assert body["code"] == "PPP002007"
        assert status_of(customer_key, account_key) == "ACTIVE"

    def test_customer_cannot_unblock(self):
        """O problema que motivou a regra: quem foi bloqueado pelo banco não se desbloqueia sozinho."""
        customer_key, account_key = open_account()
        bank_change(account_key, "BLOCKED", "suspeita de fraude")

        status, body = customer_change(customer_key, account_key, "ACTIVE")

        assert status == 403
        assert body["code"] == "PPP002007"
        assert status_of(customer_key, account_key) == "BLOCKED"

    def test_reserved_action_checked_before_reason(self):
        """Pedir BLOCKED sem motivo: a ação reservada ao banco é o erro que sai, não a falta de motivo."""
        customer_key, account_key = open_account()

        status, body = RequestGenerator.patch_account(customer_key, account_key, {"status": "BLOCKED"})

        assert status == 403
        assert body["code"] == "PPP002007"

    @pytest.mark.parametrize("payload_reason", [{}, {"reason": ""}, {"reason": "   "}])
    def test_close_requires_reason(self, payload_reason):
        customer_key, account_key = open_account()

        status, body = RequestGenerator.patch_account(customer_key, account_key, {"status": "CLOSED", **payload_reason})

        assert status == 422
        assert body["code"] == "PPP002006"

    def test_cannot_close_twice(self):
        customer_key, account_key = open_account()
        customer_change(customer_key, account_key, "CLOSED")

        status, body = customer_change(customer_key, account_key, "CLOSED")

        assert status == 409
        assert body["code"] == "PPP002003"

    def test_cannot_close_with_balance(self):
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, 1000)

        status, body = customer_change(customer_key, account_key, "CLOSED")

        assert status == 409
        assert body["code"] == "PPP002004"

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"status": "FROZEN", "reason": "motivo"},
            {"status": "closed", "reason": "motivo"},
            {"status": "CLOSED", "reason": 123},
            {"status": "CLOSED", "reason": "A" * 256},
            {"status": "CLOSED", "reason": "motivo", "extra": "campo fora do contrato"},
        ],
    )
    def test_malformed_payload(self, payload):
        customer_key, account_key = open_account()

        status, body = RequestGenerator.patch_account(customer_key, account_key, payload)

        assert status == 400
        assert body["code"] == "PPP000001"


class TestBankChangesStatus:
    """RN-CON-11: a rota interna, com o token de operador, bloqueia, desbloqueia e encerra."""

    def test_block_and_unblock(self):
        _, account_key = open_account()

        blocked_status, blocked = bank_change(account_key, "BLOCKED")
        active_status, active = RequestGenerator.patch_internal_account_status(account_key, {"status": "ACTIVE"})

        assert (blocked_status, blocked["status"]) == (200, "BLOCKED")
        assert (active_status, active["status"]) == (200, "ACTIVE")
        assert active["account_key"] == account_key

    @pytest.mark.parametrize("path", [["CLOSED"], ["BLOCKED", "CLOSED"]])
    def test_close_empty_account(self, path):
        _, account_key = open_account()

        for target in path:
            status, body = bank_change(account_key, target)

        assert status == 200
        assert body["status"] == "CLOSED"

    def test_cannot_close_with_balance(self):
        customer_key, account_key = open_account()
        deposit(customer_key, account_key, 1000)

        status, body = bank_change(account_key, "CLOSED")

        assert status == 409
        assert body["code"] == "PPP002004"

    @pytest.mark.parametrize(
        "path, target",
        [
            ([], "ACTIVE"),
            (["BLOCKED"], "BLOCKED"),
            (["CLOSED"], "ACTIVE"),
            (["CLOSED"], "BLOCKED"),
            (["CLOSED"], "CLOSED"),
        ],
    )
    def test_invalid_transition(self, path, target):
        _, account_key = open_account()
        for step in path:
            bank_change(account_key, step)

        status, body = bank_change(account_key, target)

        assert status == 409
        assert body["code"] == "PPP002003"

    @pytest.mark.parametrize("target", ["BLOCKED", "CLOSED"])
    @pytest.mark.parametrize("payload_reason", [{}, {"reason": ""}, {"reason": "   "}])
    def test_reason_required(self, target, payload_reason):
        _, account_key = open_account()

        status, body = RequestGenerator.patch_internal_account_status(account_key, {"status": target, **payload_reason})

        assert status == 422
        assert body["code"] == "PPP002006"

    def test_transition_checked_before_reason(self):
        """Conta CLOSED e sem motivo: a transição proibida é o erro que sai."""
        _, account_key = open_account()
        bank_change(account_key, "CLOSED")

        status, body = RequestGenerator.patch_internal_account_status(account_key, {"status": "BLOCKED"})

        assert status == 409
        assert body["code"] == "PPP002003"

    def test_account_not_found(self):
        status, body = bank_change(str(uuid.uuid4()), "BLOCKED")

        assert status == 404
        assert body["code"] == "PPP002001"

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"status": "FROZEN", "reason": "motivo"},
            {"status": "blocked", "reason": "motivo"},
            {"status": "BLOCKED", "reason": 123},
            {"status": "BLOCKED", "reason": "A" * 256},
            {"status": "BLOCKED", "reason": "motivo", "extra": "campo fora do contrato"},
        ],
    )
    def test_malformed_payload(self, payload):
        _, account_key = open_account()

        status, body = RequestGenerator.patch_internal_account_status(account_key, payload)

        assert status == 400
        assert body["code"] == "PPP000001"

    @pytest.mark.parametrize("operator_token", [None, "token-errado"], ids=["missing", "wrong"])
    def test_requires_operator_token(self, operator_token):
        """RN-GER-14: sem o token de operador, quem tem só o INTERNAL-TOKEN (o cliente) não entra."""
        customer_key, account_key = open_account()
        RequestGenerator.patch_internal_account_status(account_key, {"status": "BLOCKED", "reason": "teste"})

        status, body = RequestGenerator.patch_internal_account_status(
            account_key, {"status": "ACTIVE"}, operator_token=operator_token
        )

        assert status == 403
        assert body["code"] == "PPP000007"
        assert status_of(customer_key, account_key) == "BLOCKED"


class TestAccountStatusEvents:
    def test_history_records_every_transition_and_who_did_it(self):
        customer_key, account_key = open_account()
        bank_change(account_key, "BLOCKED", "suspeita de fraude")
        RequestGenerator.patch_internal_account_status(account_key, {"status": "ACTIVE"})
        customer_change(customer_key, account_key, "CLOSED", "pedido do cliente")

        status, body = RequestGenerator.get_account_status_events(customer_key, account_key)

        assert status == 200
        transitions = [
            (event["from_status"], event["to_status"], event["reason"], event["actor"]) for event in body["items"]
        ]
        assert transitions == [
            (None, "ACTIVE", None, "CUSTOMER"),
            ("ACTIVE", "BLOCKED", "suspeita de fraude", "BANK"),
            ("BLOCKED", "ACTIVE", None, "BANK"),
            ("ACTIVE", "CLOSED", "pedido do cliente", "CUSTOMER"),
        ]
        assert all("created_at" in event for event in body["items"])

    def test_refused_change_records_nothing(self):
        customer_key, account_key = open_account()
        customer_change(customer_key, account_key, "BLOCKED")
        customer_change(customer_key, account_key, "CLOSED")
        bank_change(account_key, "ACTIVE")

        _, body = RequestGenerator.get_account_status_events(customer_key, account_key)

        assert [event["to_status"] for event in body["items"]] == ["ACTIVE", "CLOSED"]
