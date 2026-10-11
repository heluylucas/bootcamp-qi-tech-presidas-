import uuid
from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from database import Context
from models import LedgerEntry, Transaction


class TransactionRepository:
    @staticmethod
    def get_by_idempotency_key(context: Context, idempotency_key: str) -> Optional[Transaction]:
        # A chave é única no banco inteiro: a busca não filtra por dono, quem confere é o controller.
        return context.db_session.query(Transaction).filter(Transaction.idempotency_key == idempotency_key).first()

    @staticmethod
    def get_balance_after(context: Context, transaction_id: int, account_id: int) -> Optional[int]:
        """O saldo da conta logo depois desta transação: o do último lançamento dela ali."""
        entry = (
            context.db_session.query(LedgerEntry)
            .filter(LedgerEntry.transaction_id == transaction_id, LedgerEntry.account_id == account_id)
            .order_by(LedgerEntry.id.desc())
            .first()
        )

        return entry.balance_after if entry else None

    @staticmethod
    def list_entries(
        context: Context,
        account_id: int,
        transaction_type: Optional[str],
        from_date: Optional[date],
        to_date: Optional[date],
        offset: int,
        limit: int,
    ) -> Tuple[List[LedgerEntry], int]:
        """Uma página do extrato e o total de lançamentos que passam pelos filtros.

        As datas são do calendário do banco (o business_date da transação), com as duas pontas inclusas.
        """
        query = (
            context.db_session.query(LedgerEntry)
            .join(Transaction, LedgerEntry.transaction_id == Transaction.id)
            .filter(LedgerEntry.account_id == account_id)
        )

        if transaction_type is not None:
            query = query.filter(Transaction.type == transaction_type)

        if from_date is not None:
            query = query.filter(Transaction.business_date >= from_date)

        if to_date is not None:
            query = query.filter(Transaction.business_date <= to_date)

        total = query.count()
        # Os lançamentos de uma transação nascem com o mesmo NOW(); o id desempata.
        entries = (
            query.options(joinedload(LedgerEntry.transaction))
            .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return entries, total

    @staticmethod
    def sum_credits(context: Context, account_id: int, category: str, from_date: date, to_date: date) -> int:
        """Soma dos créditos da categoria na conta, nos dias de movimento do período (as duas pontas)."""
        total = (
            context.db_session.query(func.sum(LedgerEntry.amount))
            .join(Transaction, LedgerEntry.transaction_id == Transaction.id)
            .filter(
                LedgerEntry.account_id == account_id,
                LedgerEntry.direction == "CREDIT",
                LedgerEntry.category == category,
                Transaction.business_date >= from_date,
                Transaction.business_date <= to_date,
            )
            .scalar()
        )

        return int(total or 0)

    @staticmethod
    def get_by_key_for_account(context: Context, transaction_key: str, account_id: int) -> Optional[Transaction]:
        # Só se a conta participou (dona ou destino): a de fora volta None, igual à inexistente (R8).
        return (
            context.db_session.query(Transaction)
            .filter(
                Transaction.transaction_key == transaction_key,
                or_(Transaction.owner_account_id == account_id, Transaction.destination_account_id == account_id),
            )
            .first()
        )

    @staticmethod
    def create(
        context: Context,
        transaction_type: str,
        owner_account_id: int,
        destination_account_id: Optional[int],
        amount: int,
        fee_amount: int,
        description: Optional[str],
        idempotency_key: Optional[str],
        business_date: date,
    ) -> Transaction:
        transaction = Transaction(
            transaction_key=str(uuid.uuid4()),
            type=transaction_type,
            owner_account_id=owner_account_id,
            destination_account_id=destination_account_id,
            amount=amount,
            fee_amount=fee_amount,
            description=description,
            idempotency_key=idempotency_key,
            business_date=business_date,
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
