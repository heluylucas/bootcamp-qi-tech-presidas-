import uuid
from typing import List, Optional

from sqlalchemy import func

from database import Context
from models import Account, AccountStatus, AccountStatusEvent


class AccountRepository:
    @staticmethod
    def create(context: Context, customer_id: int, status_id: int) -> Account:
        account = Account(account_key=str(uuid.uuid4()), customer_id=customer_id, status_id=status_id)
        context.db_session.add(account)
        context.db_session.flush()

        return account

    @staticmethod
    def get_by_key(context: Context, customer_id: int, account_key: str) -> Optional[Account]:
        # Filtrar pelo dono na própria query: a conta de outro cliente
        # volta None, igual à inexistente (R8).
        return (
            context.db_session.query(Account)
            .filter(Account.account_key == account_key, Account.customer_id == customer_id)
            .first()
        )

    @staticmethod
    def get_by_key_for_update(context: Context, customer_id: int, account_key: str) -> Optional[Account]:
        return (
            context.db_session.query(Account)
            .filter(Account.account_key == account_key, Account.customer_id == customer_id)
            .with_for_update()
            .first()
        )

    @staticmethod
    def count_not_closed(context: Context, customer_id: int) -> int:
        return (
            context.db_session.query(Account)
            .join(AccountStatus, Account.status_id == AccountStatus.id)
            .filter(Account.customer_id == customer_id, AccountStatus.enumerator != "CLOSED")
            .count()
        )

    @staticmethod
    def update_status(context: Context, account: Account, status_id: int) -> Account:
        account.status_id = status_id
        account.updated_at = func.now()
        context.db_session.flush()

        return account

    @staticmethod
    def get_status(context: Context, enumerator: str) -> Optional[AccountStatus]:
        return context.db_session.query(AccountStatus).filter(AccountStatus.enumerator == enumerator).first()

    @staticmethod
    def create_status_event(
        context: Context,
        account_id: int,
        from_status_id: Optional[int],
        to_status_id: int,
        reason: Optional[str],
    ) -> AccountStatusEvent:
        event = AccountStatusEvent(
            account_id=account_id,
            from_status_id=from_status_id,
            to_status_id=to_status_id,
            reason=reason,
        )
        context.db_session.add(event)
        context.db_session.flush()

        return event

    @staticmethod
    def list_status_events(context: Context, account_id: int) -> List[AccountStatusEvent]:
        return (
            context.db_session.query(AccountStatusEvent)
            .filter(AccountStatusEvent.account_id == account_id)
            .order_by(AccountStatusEvent.id)
            .all()
        )
