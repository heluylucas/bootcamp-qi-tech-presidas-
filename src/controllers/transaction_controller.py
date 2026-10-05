import hashlib
import json
from typing import Optional

from controllers.base_controller import BaseController
from dtos.transaction_dto import transaction_to_dict
from errors import (
    AccountNotActive,
    AccountNotFound,
    AmountAboveLimit,
    CustomerNotFound,
    DestinationAccountNotActive,
    DestinationAccountNotFound,
    InsufficientBalance,
    InvalidAmount,
    MissingIdempotencyKey,
    SameAccountTransfer,
)
from models import Account
from repositories import AccountRepository, CustomerRepository, TransactionRepository


# Limite por operação, em centavos (RN-MOV-02).
AMOUNT_LIMITS = {
    "DEPOSIT": 100_000_000,
    "WITHDRAWAL": 500_000,
    "TRANSFER": 5_000_000,
}

# Tarifa fixa da transferência, em centavos (RN-MOV-10). O valor cobrado fica
# gravado em transaction.fee_amount: se mudar aqui, o histórico não muda.
TRANSFER_FEE = 200


class TransactionController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def create(self, customer_key: str, account_key: str, payload: dict, idempotency_key: Optional[str]) -> dict:
        if idempotency_key is None:
            raise MissingIdempotencyKey()

        transaction_type = payload["type"]
        amount = payload["amount"]

        if amount <= 0:
            raise InvalidAmount()

        if amount > AMOUNT_LIMITS[transaction_type]:
            raise AmountAboveLimit()

        customer = CustomerRepository.get_by_key(self.context, customer_key)

        if customer is None:
            raise CustomerNotFound()

        origin = AccountRepository.get_by_key(self.context, customer.id, account_key)

        if origin is None:
            raise AccountNotFound()

        destination = None
        if transaction_type == "TRANSFER":
            destination = AccountRepository.get_by_key_any_owner(self.context, payload["destination_account_key"])

            if destination is None:
                raise DestinationAccountNotFound()

            if destination.id == origin.id:
                raise SameAccountTransfer()

        # Daqui em diante, status e saldo são lidos com as contas travadas (RN-MOV-08).
        origin, destination = self.lock_accounts(origin, destination)

        # TODO(módulo 3): idempotência (Passo 4) — com as contas já travadas, procurar a
        # transação desta (conta, chave) e devolver a original em vez de gravar outra.

        if origin.status.enumerator != "ACTIVE":
            raise AccountNotActive()

        if destination is not None and destination.status.enumerator != "ACTIVE":
            raise DestinationAccountNotActive()

        fee = TRANSFER_FEE if transaction_type == "TRANSFER" else 0

        if transaction_type != "DEPOSIT" and origin.balance < amount + fee:
            raise InsufficientBalance()

        if transaction_type == "DEPOSIT":
            transaction, balance = self.deposit(origin, amount, payload, idempotency_key)
        elif transaction_type == "WITHDRAWAL":
            transaction, balance = self.withdraw(origin, amount, payload, idempotency_key)
        else:
            transaction, balance = self.transfer(origin, destination, amount, payload, idempotency_key)

        self.session.commit()
        return transaction_to_dict(transaction, balance)

    def lock_accounts(self, origin: Account, destination: Optional[Account]) -> tuple:
        """Trava as contas sempre em ordem crescente de id.

        Se A -> B e B -> A chegassem juntas e cada uma travasse primeiro a
        própria origem, cada uma seguraria uma conta esperando a outra para
        sempre (deadlock). Na mesma ordem, as duas disputam a mesma primeira trava.
        """
        accounts = [origin] if destination is None else sorted([origin, destination], key=lambda account: account.id)
        locked = {}
        for account in accounts:
            locked[account.id] = AccountRepository.get_by_id_for_update(self.context, account.id)

        if destination is None:
            return locked[origin.id], None

        return locked[origin.id], locked[destination.id]

    def deposit(self, account: Account, amount: int, payload: dict, idempotency_key: str) -> tuple:
        new_balance = account.balance + amount
        transaction = self.create_transaction("DEPOSIT", account, None, account, amount, 0, payload, idempotency_key)
        self.add_entry(transaction, account, "CREDIT", "PRINCIPAL", amount, new_balance)
        return transaction, new_balance

    def withdraw(self, account: Account, amount: int, payload: dict, idempotency_key: str) -> tuple:
        new_balance = account.balance - amount
        transaction = self.create_transaction("WITHDRAWAL", account, account, None, amount, 0, payload, idempotency_key)
        self.add_entry(transaction, account, "DEBIT", "PRINCIPAL", amount, new_balance)
        return transaction, new_balance

    def transfer(
        self, origin: Account, destination: Account, amount: int, payload: dict, idempotency_key: str
    ) -> tuple:
        """Um pedido, três lançamentos: principal e tarifa saem da origem, só o principal entra no destino."""
        transaction = self.create_transaction(
            "TRANSFER", origin, origin, destination, amount, TRANSFER_FEE, payload, idempotency_key
        )
        after_principal = origin.balance - amount
        after_fee = after_principal - TRANSFER_FEE
        destination_balance = destination.balance + amount

        self.add_entry(transaction, origin, "DEBIT", "PRINCIPAL", amount, after_principal)
        self.add_entry(transaction, origin, "DEBIT", "FEE", TRANSFER_FEE, after_fee)
        self.add_entry(transaction, destination, "CREDIT", "PRINCIPAL", amount, destination_balance)
        return transaction, after_fee

    def create_transaction(
        self,
        transaction_type: str,
        requester: Account,
        origin: Optional[Account],
        destination: Optional[Account],
        amount: int,
        fee: int,
        payload: dict,
        idempotency_key: str,
    ):
        type_row = TransactionRepository.get_type(self.context, transaction_type)
        return TransactionRepository.create(
            self.context,
            type_id=type_row.id,
            requester_account_id=requester.id,
            origin_account_id=origin.id if origin else None,
            destination_account_id=destination.id if destination else None,
            amount=amount,
            fee_amount=fee,
            description=payload.get("description"),
            idempotency_key=idempotency_key,
            request_hash=hash_request(payload),
        )

    def add_entry(self, transaction, account: Account, direction: str, category: str, amount: int, balance_after: int):
        """Grava o lançamento e leva o saldo da conta junto: os dois nunca se separam."""
        TransactionRepository.create_ledger_entry(
            self.context, transaction.id, account.id, direction, category, amount, balance_after
        )
        AccountRepository.update_balance(self.context, account, balance_after)


def hash_request(payload: dict) -> str:
    """A "impressão digital" do corpo: mesmo conteúdo, mesmo hash, em qualquer ordem de campos."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
