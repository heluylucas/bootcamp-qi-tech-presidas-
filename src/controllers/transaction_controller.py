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


# Limite por operação, em centavos (RN-MOV-02).
AMOUNT_LIMITS = {
    "DEPOSIT": 100_000_000,
    "WITHDRAWAL": 500_000,
    "TRANSFER": 5_000_000,
}

# Tarifa fixa da transferência, em centavos (RN-MOV-10). O valor cobrado fica
# gravado em transaction.fee_amount: se mudar aqui, o histórico não muda.
TRANSFER_FEE = 200

# Paginação do extrato (RN-GER-11). O máximo de 100 fica no schema.
DEFAULT_PAGE = 1
DEFAULT_LIMIT = 20


class TransactionController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def create(self, customer_key: str, account_key: str, payload: dict, idempotency_key: Optional[str]) -> Tuple[dict, bool]:
        """Devolve (resposta, criada). criada=False é a repetição de um pedido já feito."""
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

            # A tarifa entra na conta do banco, que também é escrita e por isso também é travada.
            bank = AccountRepository.get_bank(self.context)

        # Daqui em diante, status e saldo são lidos com as contas travadas (RN-MOV-08).
        origin, destination, bank = self.lock_accounts(origin, destination, bank)

        # Idempotência DEPOIS da trava (rfc_fluxos): um reenvio que chega enquanto o
        # original roda espera a trava e encontra a transação já gravada, em vez de
        # ver o saldo debitado e levar um falso "saldo insuficiente".
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
        """Extrato (RN-MOV-12). Conta bloqueada ou encerrada continua consultando (RN-CON-09)."""
        from_date = parse_date(query_params.get("from"), "from")
        to_date = parse_date(query_params.get("to"), "to")

        if from_date is not None and to_date is not None and from_date > to_date:
            raise InvalidParameter("from must not be after to")

        page = int(query_params.get("page", DEFAULT_PAGE))
        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        account = self.get_owned_account(customer_key, account_key)

        # Datas do calendário do banco (o dia de movimento de cada transação), com as duas pontas inclusas.
        entries, total = TransactionRepository.list_entries(
            self.context, account.id, query_params.get("type"), from_date, to_date, (page - 1) * limit, limit
        )
        return {"items": [entry_to_dict(entry) for entry in entries], "page": page, "limit": limit, "total": total}

    def get_receipt(self, customer_key: str, account_key: str, transaction_key: str) -> dict:
        """Comprovante (RN-MOV-13): só para a origem ou o destino da transação."""
        account = self.get_owned_account(customer_key, account_key)
        transaction = TransactionRepository.get_by_key_for_account(self.context, transaction_key, account.id)

        if transaction is None:
            raise TransactionNotFound()

        return receipt_to_dict(transaction)

    def lock_accounts(self, *accounts: Optional[Account]) -> List[Optional[Account]]:
        """Trava as contas sempre em ordem crescente de id e as devolve na ordem recebida (None fica None).

        Se A -> B e B -> A chegassem juntas e cada uma travasse primeiro a
        própria origem, cada uma seguraria uma conta esperando a outra para
        sempre (deadlock). Na mesma ordem, as duas disputam a mesma primeira trava.
        A conta do banco tem o menor id, então é sempre a primeira.
        """
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
        """Um pedido, quatro lançamentos: principal e tarifa saem da origem, o principal entra
        no destino e a tarifa entra na conta do banco. Cada débito tem o seu crédito."""
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
        """A transação já gravada com esta chave nesta conta; None se a chave é nova.

        A chave é única no banco inteiro. Achada em outra conta, é pedido de outro: 409, sem
        mostrar nada dele (R8). Quem chama ainda confere se o pedido é idêntico ao gravado.
        """
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
        # O dia da transação no calendário do banco: a data de movimento atual, salvo quando quem
        # chama já sabe o dia (a liquidação no fechamento grava no dia que está abrindo).
        if business_date is None:
            business_date = BusinessDayRepository.get_current(self.context).business_date

        # Dois pedidos com a mesma chave em contas diferentes, ao mesmo tempo, passam os dois
        # pelo find_repetition (cada um trava só a sua conta); o UNIQUE recusa o segundo aqui.
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
        except IntegrityError:
            raise IdempotencyKeyReused()

    def add_entry(self, transaction: Transaction, account: Account, direction: str, category: str, amount: int, balance_after: int) -> None:
        """Grava o lançamento e leva o saldo da conta junto: os dois nunca se separam."""
        TransactionRepository.create_ledger_entry(
            self.context, transaction.id, account.id, direction, category, amount, balance_after
        )
        AccountRepository.update_balance(self.context, account, balance_after)


def is_same_transaction(previous: Transaction, payload: dict, destination: Optional[Account]) -> bool:
    """O pedido repetido é idêntico ao gravado? Compara o corpo com as colunas da transação.

    Faz o papel do antigo hash do corpo sem guardar nada a mais: o pedido original já está gravado.
    """
    return (
        previous.type == payload["type"]
        and previous.amount == payload["amount"]
        and previous.destination_account_id == (destination.id if destination else None)
        and previous.description == payload.get("description")
    )


def parse_idempotency_key(idempotency_key: Optional[str]) -> str:
    """A chave em formato canônico. Ausente, vazia ou fora do formato UUID: 400.

    Quem gera a chave é quem chama a API, um UUID novo por pedido; reenviar o mesmo pedido
    com a mesma chave é o que faz o banco devolver a resposta original em vez de repetir.
    """
    try:
        return str(uuid.UUID(idempotency_key))
    except (TypeError, ValueError):
        raise MissingIdempotencyKey()
