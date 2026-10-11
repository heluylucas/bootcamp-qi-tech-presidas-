from controllers.base_controller import BaseController
from controllers.investment_order_controller import InvestmentOrderController
from dtos.account_dto import account_to_dict, status_event_to_dict
from errors import (
    AccountAlreadyExists,
    AccountNotEmpty,
    AccountNotFound,
    CustomerNotFound,
    InvalidStatusTransition,
    StatusChangeReservedToBank,
    StatusReasonRequired,
)
from models import Account
from repositories import AccountRepository, CustomerRepository, PositionRepository
from utils.money import amount_for


ALLOWED_TRANSITIONS = {
    "ACTIVE": {"BLOCKED", "CLOSED"},
    "BLOCKED": {"ACTIVE", "CLOSED"},
    "CLOSED": set(),
}

REASON_REQUIRED = {"BLOCKED", "CLOSED"}

CUSTOMER_ALLOWED_TARGETS = {"CLOSED"}

ACTOR_CUSTOMER = "CUSTOMER"
ACTOR_BANK = "BANK"


class AccountController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def create(self, customer_key: str) -> dict:
        customer = CustomerRepository.get_by_key_for_update(self.context, customer_key)

        if customer is None:
            raise CustomerNotFound()

        if AccountRepository.count_not_closed(self.context, customer.id) > 0:
            raise AccountAlreadyExists()

        account = AccountRepository.create(self.context, customer.id, "ACTIVE")
        AccountRepository.create_status_event(self.context, account.id, None, "ACTIVE", None, ACTOR_CUSTOMER)

        self.session.commit()
        return self.account_response(account)

    def get(self, customer_key: str, account_key: str) -> dict:
        account = self.get_owned_account(customer_key, account_key)
        return self.account_response(account)

    def change_status(self, customer_key: str, account_key: str, payload: dict) -> dict:
        account = self.get_owned_account(customer_key, account_key, for_update=True)

        if payload["status"] not in CUSTOMER_ALLOWED_TARGETS:
            raise StatusChangeReservedToBank()

        return self.apply_status_change(account, payload, ACTOR_CUSTOMER)

    def change_status_by_bank(self, account_key: str, payload: dict) -> dict:
        account = AccountRepository.get_by_key_any_owner_for_update(self.context, account_key)

        if account is None:
            raise AccountNotFound()

        return self.apply_status_change(account, payload, ACTOR_BANK)

    def apply_status_change(self, account: Account, payload: dict, actor: str) -> dict:
        current = account.status
        target = payload["status"]
        reason = payload.get("reason", "").strip() or None

        if target not in ALLOWED_TRANSITIONS[current]:
            raise InvalidStatusTransition()

        if target in REASON_REQUIRED and reason is None:
            raise StatusReasonRequired()

        if target == "CLOSED" and (
            account.balance > 0 or PositionRepository.has_open_position(self.context, account.id)
        ):
            raise AccountNotEmpty()

        AccountRepository.update_status(self.context, account, target)
        AccountRepository.create_status_event(self.context, account.id, current, target, reason, actor)

        self.session.commit()
        return self.account_response(account)

    def account_response(self, account: Account) -> dict:
        priced = InvestmentOrderController().priced_positions(PositionRepository.list_by_account(self.context, account.id))
        investments_amount = sum(amount_for(position.quantity, unit_price) for position, unit_price in priced)
        return account_to_dict(account, investments_amount)

    def list_status_events(self, customer_key: str, account_key: str) -> dict:
        account = self.get_owned_account(customer_key, account_key)
        events = AccountRepository.list_status_events(self.context, account.id)
        return {"items": [status_event_to_dict(event) for event in events]}
