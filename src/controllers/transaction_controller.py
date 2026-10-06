import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from controllers.base_controller import BaseController
from dtos.transaction_dto import entry_to_dict, receipt_to_dict, transaction_to_dict
from errors import (
    AccountNotActive,
    AccountNotFound,
    AmountAboveLimit,
    CustomerNotFound,
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
from models import Account
from repositories import AccountRepository, CustomerRepository, TransactionRepository
from utils.dates import parse_date


# Limite por operação, em centavos (RN-MOV-02).
AMOUNT_LIMITS = {
    "DEPOSIT": 100_000_000,
    "WITHDRAWAL": 500_000,
    "TRANSFER": 5_000_000,
}

# Tarifa fixa da transferência, em centavos (RN-MOV-10). O valor cobrado fica
# gravado em transaction.fee_amount: se mudar aqui, o histórico não muda.
TRANSFER_FEE = 200

# Tamanho da coluna transaction.idempotency_key (CHAR(36), o tamanho de um UUID).
IDEMPOTENCY_KEY_MAX_LENGTH = 36

# Paginação do extrato (RN-GER-11). O máximo de 100 fica no schema.
DEFAULT_PAGE = 1
DEFAULT_LIMIT = 20


class TransactionController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def create(self, customer_key: str, account_key: str, payload: dict, idempotency_key: Optional[str]) -> tuple:
        """Devolve (resposta, criada). criada=False é a repetição de um pedido já feito."""
        # Vazia conta como ausente; maior que a coluna CHAR(36) viraria 500 no banco.
        if not idempotency_key or len(idempotency_key) > IDEMPOTENCY_KEY_MAX_LENGTH:
            raise MissingIdempotencyKey()

        transaction_type = payload["type"]
        amount = payload["amount"]

        if amount <= 0:
            raise InvalidAmount()

        if amount > AMOUNT_LIMITS[transaction_type]:
            raise AmountAboveLimit()

        origin = self.get_owned_account(customer_key, account_key)

        destination = None
        if transaction_type == "TRANSFER":
            destination = AccountRepository.get_by_key_any_owner(self.context, payload["destination_account_key"])

            if destination is None:
                raise DestinationAccountNotFound()

            if destination.id == origin.id:
                raise SameAccountTransfer()

        # Daqui em diante, status e saldo são lidos com as contas travadas (RN-MOV-08).
        origin, destination = self.lock_accounts(origin, destination)

        # Idempotência DEPOIS da trava (rfc_fluxos): um reenvio que chega enquanto o
        # original roda espera a trava e encontra a transação já gravada, em vez de
        # ver o saldo debitado e levar um falso "saldo insuficiente".
        request_hash = hash_request(payload)
        previous = TransactionRepository.get_by_idempotency_key(self.context, origin.id, idempotency_key)

        if previous is not None:
            if previous.request_hash != request_hash:
                raise IdempotencyKeyReused()

            balance = TransactionRepository.get_balance_after(self.context, previous.id, origin.id)
            return transaction_to_dict(previous, balance), False

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
        return transaction_to_dict(transaction, balance), True

    def list_statement(self, customer_key: str, account_key: str, query_params: dict) -> dict:
        """Extrato (RN-MOV-12). Conta bloqueada ou encerrada continua consultando (RN-CON-09)."""
        from_date = parse_date(query_params.get("from"), "from")
        to_date = parse_date(query_params.get("to"), "to")

        if from_date is not None and to_date is not None and from_date > to_date:
            raise InvalidParameter("from must not be after to")

        page = int(query_params.get("page", DEFAULT_PAGE))
        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        account = self.get_owned_account(customer_key, account_key)

        # Datas reais do lançamento, em UTC, com as duas pontas inclusas: o dia
        # inteiro de `to` cabe porque o fim é o começo do dia seguinte.
        start = start_of_day(from_date) if from_date else None
        end = start_of_day(to_date + timedelta(days=1)) if to_date else None

        entries, total = TransactionRepository.list_entries(
            self.context, account.id, query_params.get("type"), start, end, (page - 1) * limit, limit
        )
        return {"items": [entry_to_dict(entry) for entry in entries], "page": page, "limit": limit, "total": total}

    def get_receipt(self, customer_key: str, account_key: str, transaction_key: str) -> dict:
        """Comprovante (RN-MOV-13): só para a origem ou o destino da transação."""
        account = self.get_owned_account(customer_key, account_key)
        transaction = TransactionRepository.get_by_key_for_account(self.context, transaction_key, account.id)

        if transaction is None:
            raise TransactionNotFound()

        return receipt_to_dict(transaction)

    def get_owned_account(self, customer_key: str, account_key: str) -> Account:
        """Confere o dono antes de tudo (R8): conta de outro cliente dá o mesmo 404 da inexistente."""
        customer = CustomerRepository.get_by_key(self.context, customer_key)

        if customer is None:
            raise CustomerNotFound()

        account = AccountRepository.get_by_key(self.context, customer.id, account_key)

        if account is None:
            raise AccountNotFound()

        return account

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


def start_of_day(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def hash_request(payload: dict) -> str:
    """A "impressão digital" do corpo: mesmo conteúdo, mesmo hash, em qualquer ordem de campos."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
