import uuid
from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos.transaction_dto import entry_to_dict, receipt_to_dict, transaction_to_dict
from errors import (
    AccountNotActive,
    AmountAboveLimit,
    DestinationAccountNotActive,
    DestinationAccountNotFound,
    IdempotencyKeyReused,
    InsufficientBalance,
    InvalidAmount,
    InvalidParameter,
    MissingIdempotencyKey,
    SameAccountTransfer,
    TransactionNotFound,
)
from models import Account, Transaction
from repositories import AccountRepository, BusinessDayRepository, TransactionRepository
from utils.dates import parse_date


AMOUNT_LIMITS = {
    "DEPOSIT": 100_000_000,
    "WITHDRAWAL": 500_000,
    "TRANSFER": 5_000_000,
}

TRANSFER_FEE = 200

DEFAULT_PAGE = 1
DEFAULT_LIMIT = 20


class TransactionController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def create(self, customer_key: str, account_key: str, payload: dict, idempotency_key: Optional[str]) -> Tuple[dict, bool]:
        idempotency_key = parse_idempotency_key(idempotency_key)
        transaction_type = payload["type"]
        amount = payload["amount"]

        if amount <= 0:
            raise InvalidAmount()

        if amount > AMOUNT_LIMITS[transaction_type]:
            raise AmountAboveLimit()

        origin = self.get_owned_account(customer_key, account_key)

        destination = None
        bank = None
        if transaction_type == "TRANSFER":
            destination = AccountRepository.get_by_key_any_owner(self.context, payload["destination_account_key"])

            if destination is None:
                raise DestinationAccountNotFound()

            if destination.id == origin.id:
                raise SameAccountTransfer()

            bank = AccountRepository.get_bank(self.context)

        origin, destination, bank = self.lock_accounts(origin, destination, bank)

        # Depois da trava: um reenvio simultâneo espera o original e o encontra gravado.
        previous = self.find_repetition(idempotency_key, origin)

        if previous is not None:
            if not is_same_transaction(previous, payload, destination):
                raise IdempotencyKeyReused()

            balance = TransactionRepository.get_balance_after(self.context, previous.id, origin.id)
            return transaction_to_dict(previous, balance), False

        if origin.status != "ACTIVE":
            raise AccountNotActive()

        if destination is not None and destination.status != "ACTIVE":
            raise DestinationAccountNotActive()

        fee = TRANSFER_FEE if transaction_type == "TRANSFER" else 0

        if transaction_type != "DEPOSIT" and origin.balance < amount + fee:
            raise InsufficientBalance()

        description = payload.get("description")
        if transaction_type == "DEPOSIT":
            transaction, balance = self.deposit(origin, amount, description, idempotency_key)
        elif transaction_type == "WITHDRAWAL":
            transaction, balance = self.withdraw(origin, amount, description, idempotency_key)
        else:
            transaction, balance = self.transfer(origin, destination, bank, amount, description, idempotency_key)

        self.session.commit()
        return transaction_to_dict(transaction, balance), True

    def list_statement(self, customer_key: str, account_key: str, query_params: dict) -> dict:
        from_date = parse_date(query_params.get("from"), "from")
        to_date = parse_date(query_params.get("to"), "to")

        if from_date is not None and to_date is not None and from_date > to_date:
            raise InvalidParameter("from must not be after to")

        page = int(query_params.get("page", DEFAULT_PAGE))
        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        account = self.get_owned_account(customer_key, account_key)

        entries, total = TransactionRepository.list_entries(
            self.context, account.id, query_params.get("type"), from_date, to_date, (page - 1) * limit, limit
        )
        return {"items": [entry_to_dict(entry) for entry in entries], "page": page, "limit": limit, "total": total}

    def get_receipt(self, customer_key: str, account_key: str, transaction_key: str) -> dict:
        account = self.get_owned_account(customer_key, account_key)
        transaction = TransactionRepository.get_by_key_for_account(self.context, transaction_key, account.id)

        if transaction is None:
            raise TransactionNotFound()

        return receipt_to_dict(transaction)

    def lock_accounts(self, *accounts: Optional[Account]) -> List[Optional[Account]]:
        locked = {}
        for account in sorted((account for account in accounts if account), key=lambda account: account.id):
            locked[account.id] = AccountRepository.get_by_id_for_update(self.context, account.id)

        return [locked[account.id] if account else None for account in accounts]

    def deposit(self, account: Account, amount: int, description: Optional[str], idempotency_key: str) -> Tuple[Transaction, int]:
        new_balance = account.balance + amount
        transaction = self.create_transaction("DEPOSIT", account, None, amount, 0, description, idempotency_key)
        self.add_entry(transaction, account, "CREDIT", "PRINCIPAL", amount, new_balance)
        return transaction, new_balance

    def withdraw(self, account: Account, amount: int, description: Optional[str], idempotency_key: str) -> Tuple[Transaction, int]:
        new_balance = account.balance - amount
        transaction = self.create_transaction("WITHDRAWAL", account, None, amount, 0, description, idempotency_key)
        self.add_entry(transaction, account, "DEBIT", "PRINCIPAL", amount, new_balance)
        return transaction, new_balance

    def transfer(
        self,
        origin: Account,
        destination: Account,
        bank: Account,
        amount: int,
        description: Optional[str],
        idempotency_key: str,
    ) -> Tuple[Transaction, int]:
        transaction = self.create_transaction(
            "TRANSFER", origin, destination, amount, TRANSFER_FEE, description, idempotency_key
        )
        after_principal = origin.balance - amount
        after_fee = after_principal - TRANSFER_FEE

        self.add_entry(transaction, origin, "DEBIT", "PRINCIPAL", amount, after_principal)
        self.add_entry(transaction, origin, "DEBIT", "FEE", TRANSFER_FEE, after_fee)
        self.add_entry(transaction, destination, "CREDIT", "PRINCIPAL", amount, destination.balance + amount)
        self.add_entry(transaction, bank, "CREDIT", "FEE", TRANSFER_FEE, bank.balance + TRANSFER_FEE)
        return transaction, after_fee

    def find_repetition(self, idempotency_key: str, account: Account) -> Optional[Transaction]:
        previous = TransactionRepository.get_by_idempotency_key(self.context, idempotency_key)

        if previous is not None and previous.owner_account_id != account.id:
            raise IdempotencyKeyReused()

        return previous

    def create_transaction(
        self,
        transaction_type: str,
        account: Account,
        destination: Optional[Account],
        amount: int,
        fee: int,
        description: Optional[str],
        idempotency_key: Optional[str],
        business_date: Optional[date] = None,
    ) -> Transaction:
        if business_date is None:
            business_date = BusinessDayRepository.get_current(self.context).business_date

        try:
            return TransactionRepository.create(
                self.context,
                transaction_type=transaction_type,
                owner_account_id=account.id,
                destination_account_id=destination.id if destination else None,
                amount=amount,
                fee_amount=fee,
                description=description,
                idempotency_key=idempotency_key,
                business_date=business_date,
            )
        # Mesma chave em contas diferentes ao mesmo tempo: o UNIQUE barra a segunda.
        except IntegrityError:
            raise IdempotencyKeyReused()

    def add_entry(self, transaction: Transaction, account: Account, direction: str, category: str, amount: int, balance_after: int) -> None:
        TransactionRepository.create_ledger_entry(
            self.context, transaction.id, account.id, direction, category, amount, balance_after
        )
        AccountRepository.update_balance(self.context, account, balance_after)


def is_same_transaction(previous: Transaction, payload: dict, destination: Optional[Account]) -> bool:
    return (
        previous.type == payload["type"]
        and previous.amount == payload["amount"]
        and previous.destination_account_id == (destination.id if destination else None)
        and previous.description == payload.get("description")
    )


def parse_idempotency_key(idempotency_key: Optional[str]) -> str:
    try:
        return str(uuid.UUID(idempotency_key))
    except (TypeError, ValueError):
        raise MissingIdempotencyKey()
