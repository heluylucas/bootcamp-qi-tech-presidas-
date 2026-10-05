import uuid
from typing import Optional

from database import Context
from models import LedgerEntry, Transaction, TransactionType


class TransactionRepository:
    @staticmethod
    def get_type(context: Context, enumerator: str) -> Optional[TransactionType]:
        return context.db_session.query(TransactionType).filter(TransactionType.enumerator == enumerator).first()

    @staticmethod
    def create(
        context: Context,
        type_id: int,
        requester_account_id: int,
        origin_account_id: Optional[int],
        destination_account_id: Optional[int],
        amount: int,
        fee_amount: int,
        description: Optional[str],
        idempotency_key: str,
        request_hash: str,
    ) -> Transaction:
        transaction = Transaction(
            transaction_key=str(uuid.uuid4()),
            type_id=type_id,
            requester_account_id=requester_account_id,
            origin_account_id=origin_account_id,
            destination_account_id=destination_account_id,
            amount=amount,
            fee_amount=fee_amount,
            description=description,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        context.db_session.add(transaction)
        context.db_session.flush()

        return transaction

    @staticmethod
    def create_ledger_entry(
        context: Context,
        transaction_id: int,
        account_id: int,
        direction: str,
        category: str,
        amount: int,
        balance_after: int,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            entry_key=str(uuid.uuid4()),
            transaction_id=transaction_id,
            account_id=account_id,
            direction=direction,
            category=category,
            amount=amount,
            balance_after=balance_after,
        )
        context.db_session.add(entry)
        context.db_session.flush()

        return entry
