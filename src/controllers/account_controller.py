from controllers.base_controller import BaseController
from dtos.account_dto import account_to_dict, status_event_to_dict
from errors import (
    AccountAlreadyExists,
    AccountNotEmpty,
    AccountNotFound,
    CustomerNotFound,
    InvalidStatusTransition,
    StatusReasonRequired,
)
from models import Account
from repositories import AccountRepository, CustomerRepository


# A tabela de transições do Módulo 2: de cada status, para onde se pode ir.
# CLOSED é final. Ir para o mesmo status também é proibido (409).
ALLOWED_TRANSITIONS = {
    "ACTIVE": {"BLOCKED", "CLOSED"},
    "BLOCKED": {"ACTIVE", "CLOSED"},
    "CLOSED": set(),
}

REASON_REQUIRED = {"BLOCKED", "CLOSED"}


class AccountController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def create(self, customer_key: str) -> dict:
        # A trava na linha do cliente enfileira aberturas simultâneas: a
        # segunda só conta depois que a primeira fez commit, e vê a conta nova.
        customer = CustomerRepository.get_by_key_for_update(self.context, customer_key)

        if customer is None:
            raise CustomerNotFound()

        if AccountRepository.count_not_closed(self.context, customer.id) > 0:
            raise AccountAlreadyExists()

        active = AccountRepository.get_status(self.context, "ACTIVE")
        account = AccountRepository.create(self.context, customer.id, active.id)
        AccountRepository.create_status_event(self.context, account.id, None, active.id, None)

        self.session.commit()
        return account_to_dict(account)

    def get(self, customer_key: str, account_key: str) -> dict:
        account = self.get_owned_account(customer_key, account_key)
        return account_to_dict(account)

    def change_status(self, customer_key: str, account_key: str, payload: dict) -> dict:
        # Travada: o status e o saldo lidos aqui decidem a mudança.
        account = self.get_owned_account(customer_key, account_key, for_update=True)
        current = account.status.enumerator
        target = payload["status"]
        # Motivo só com espaços conta como motivo nenhum.
        reason = payload.get("reason", "").strip() or None

        if target not in ALLOWED_TRANSITIONS[current]:
            raise InvalidStatusTransition()

        if target in REASON_REQUIRED and reason is None:
            raise StatusReasonRequired()

        # TODO(módulo 7): a RN-CON-08 também exige posição de investimento
        # zerada; conferir aqui quando a tabela position existir.
        if target == "CLOSED" and account.balance > 0:
            raise AccountNotEmpty()

        from_status_id = account.status_id
        to_status = AccountRepository.get_status(self.context, target)
        AccountRepository.update_status(self.context, account, to_status.id)
        AccountRepository.create_status_event(self.context, account.id, from_status_id, to_status.id, reason)

        self.session.commit()
        return account_to_dict(account)

    def list_status_events(self, customer_key: str, account_key: str) -> dict:
        account = self.get_owned_account(customer_key, account_key)
        events = AccountRepository.list_status_events(self.context, account.id)
        return {"items": [status_event_to_dict(event) for event in events]}

    def get_owned_account(self, customer_key: str, account_key: str, for_update: bool = False) -> Account:
        """Confere o dono antes de tudo (R8): conta de outro cliente dá o mesmo 404 da inexistente."""
        customer = CustomerRepository.get_by_key(self.context, customer_key)

        if customer is None:
            raise CustomerNotFound()

        if for_update:
            account = AccountRepository.get_by_key_for_update(self.context, customer.id, account_key)
        else:
            account = AccountRepository.get_by_key(self.context, customer.id, account_key)

        if account is None:
            raise AccountNotFound()

        return account
