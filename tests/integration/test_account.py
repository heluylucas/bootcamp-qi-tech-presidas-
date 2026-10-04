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


def change_status(customer_key: str, account_key: str, status: str, reason: str = "motivo de teste"):
    return RequestGenerator.patch_account(customer_key, account_key, {"status": status, "reason": reason})


class TestOpenAccount:
    def test_open_account(self):
        customer_key = create_customer()

        status, body = RequestGenerator.post_account(customer_key)

        assert status == 201
        assert len(body["account_key"]) == 36
        assert "id" not in body
        assert body["status"] == "ACTIVE"
        assert body["balance"] == 0
        assert "created_at" in body
        assert "updated_at" in body

    def test_customer_not_found(self):
        status, body = RequestGenerator.post_account(str(uuid.uuid4()))

        assert status == 404
        assert body["code"] == "BNK001001"

    def test_second_account_refused(self):
        customer_key, _ = open_account()

        status, body = RequestGenerator.post_account(customer_key)

        assert status == 409
        assert body["code"] == "BNK002002"

    def test_second_account_refused_while_blocked(self):
        customer_key, account_key = open_account()
        change_status(customer_key, account_key, "BLOCKED")

        status, body = RequestGenerator.post_account(customer_key)

        assert status == 409
        assert body["code"] == "BNK002002"

    def test_new_account_after_closing(self):
        customer_key, account_key = open_account()
        change_status(customer_key, account_key, "CLOSED")

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
        assert body["code"] == "BNK002001"

    def test_account_of_another_customer(self):
        """R8: a conta existe, mas não é deste cliente. Resposta igual à de inexistente."""
        _, account_key = open_account()
        other_customer_key = create_customer()

        get_status, get_body = RequestGenerator.get_account(other_customer_key, account_key)
        patch_status, patch_body = change_status(other_customer_key, account_key, "BLOCKED")
        events_status, events_body = RequestGenerator.get_account_status_events(other_customer_key, account_key)

        assert (get_status, get_body["code"]) == (404, "BNK002001")
        assert (patch_status, patch_body["code"]) == (404, "BNK002001")
        assert (events_status, events_body["code"]) == (404, "BNK002001")


class TestChangeAccountStatus:
    def test_block_and_unblock(self):
        customer_key, account_key = open_account()

        blocked_status, blocked = change_status(customer_key, account_key, "BLOCKED")
        active_status, active = RequestGenerator.patch_account(customer_key, account_key, {"status": "ACTIVE"})

        assert (blocked_status, blocked["status"]) == (200, "BLOCKED")
        assert (active_status, active["status"]) == (200, "ACTIVE")
        assert active["account_key"] == account_key

    @pytest.mark.parametrize("path", [["CLOSED"], ["BLOCKED", "CLOSED"]])
    def test_close_empty_account(self, path):
        customer_key, account_key = open_account()

        for target in path:
            status, body = change_status(customer_key, account_key, target)

        assert status == 200
        assert body["status"] == "CLOSED"

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
        customer_key, account_key = open_account()
        for step in path:
            change_status(customer_key, account_key, step)

        status, body = change_status(customer_key, account_key, target)

        assert status == 409
        assert body["code"] == "BNK002003"

    @pytest.mark.parametrize("target", ["BLOCKED", "CLOSED"])
    @pytest.mark.parametrize("payload_reason", [{}, {"reason": ""}, {"reason": "   "}])
    def test_reason_required(self, target, payload_reason):
        customer_key, account_key = open_account()

        status, body = RequestGenerator.patch_account(customer_key, account_key, {"status": target, **payload_reason})

        assert status == 422
        assert body["code"] == "BNK002006"

    def test_transition_checked_before_reason(self):
        """Conta CLOSED e sem motivo: a transição proibida é o erro que sai."""
        customer_key, account_key = open_account()
        change_status(customer_key, account_key, "CLOSED")

        status, body = RequestGenerator.patch_account(customer_key, account_key, {"status": "BLOCKED"})

        assert status == 409
        assert body["code"] == "BNK002003"

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
        customer_key, account_key = open_account()

        status, body = RequestGenerator.patch_account(customer_key, account_key, payload)

        assert status == 400
        assert body["code"] == "BNK000001"


class TestAccountStatusEvents:
    def test_history_records_every_transition(self):
        customer_key, account_key = open_account()
        change_status(customer_key, account_key, "BLOCKED", "suspeita de fraude")
        RequestGenerator.patch_account(customer_key, account_key, {"status": "ACTIVE"})
        change_status(customer_key, account_key, "CLOSED", "pedido do cliente")

        status, body = RequestGenerator.get_account_status_events(customer_key, account_key)

        assert status == 200
        transitions = [(event["from_status"], event["to_status"], event["reason"]) for event in body["items"]]
        assert transitions == [
            (None, "ACTIVE", None),
            ("ACTIVE", "BLOCKED", "suspeita de fraude"),
            ("BLOCKED", "ACTIVE", None),
            ("ACTIVE", "CLOSED", "pedido do cliente"),
        ]
        assert all("created_at" in event for event in body["items"])

    def test_refused_change_records_nothing(self):
        customer_key, account_key = open_account()
        change_status(customer_key, account_key, "CLOSED")
        change_status(customer_key, account_key, "ACTIVE")

        _, body = RequestGenerator.get_account_status_events(customer_key, account_key)

        assert [event["to_status"] for event in body["items"]] == ["ACTIVE", "CLOSED"]
