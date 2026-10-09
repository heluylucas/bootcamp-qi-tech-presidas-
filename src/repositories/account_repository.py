import uuid
from typing import List, Optional

from sqlalchemy import func

from database import Context
from models import Account, AccountStatusEvent


class AccountRepository:
    @staticmethod
    def create(context: Context, customer_id: int, status: str) -> Account:
        account = Account(account_key=str(uuid.uuid4()), customer_id=customer_id, status=status)
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
            .filter(Account.customer_id == customer_id, Account.status != "CLOSED")
            .count()
        )

    @staticmethod
    def update_status(context: Context, account: Account, status: str) -> Account:
        account.status = status
        account.updated_at = func.now()
        context.db_session.flush()

        return account

    @staticmethod
    def create_status_event(
        context: Context,
        account_id: int,
        from_status: Optional[str],
        to_status: str,
        reason: Optional[str],
        actor: str,
    ) -> AccountStatusEvent:
        event = AccountStatusEvent(
            account_id=account_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            actor=actor,
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

    @staticmethod
    def get_by_key_any_owner(context: Context, account_key: str) -> Optional[Account]:
        # Sem filtro de dono: só para o DESTINO de uma transferência, que pode
        # ser de outro cliente (RN-MOV-05). Nunca use para a conta do caminho.
        # A conta do banco (sem cliente) fica de fora: ela só recebe tarifa.
        return (
            context.db_session.query(Account)
            .filter(Account.account_key == account_key, Account.customer_id.isnot(None))
            .first()
        )

    @staticmethod
    def get_by_key_any_owner_for_update(context: Context, account_key: str) -> Optional[Account]:
        # Sem filtro de dono: só para a rota do banco (RN-CON-11), que não é
        # aninhada em cliente. Travada, porque o status e o saldo lidos decidem a mudança.
        # A conta do banco (sem cliente) fica de fora: ninguém a bloqueia nem encerra.
        return (
            context.db_session.query(Account)
            .filter(Account.account_key == account_key, Account.customer_id.isnot(None))
            .populate_existing()
            .with_for_update()
            .first()
        )

    @staticmethod
    def get_by_id_for_update(context: Context, account_id: int) -> Optional[Account]:
        # populate_existing: se a conta já foi lida antes nesta sessão, o
        # SQLAlchemy devolveria o objeto com o saldo ANTIGO, lido antes da
        # trava. Com ele, os valores são relidos depois que a trava é concedida.
        return (
            context.db_session.query(Account)
            .filter(Account.id == account_id)
            .populate_existing()
            .with_for_update()
            .first()
        )

    @staticmethod
    def get_bank(context: Context) -> Account:
        """A conta do próprio banco, a única sem cliente (seed do database.sql)."""
        return context.db_session.query(Account).filter(Account.customer_id.is_(None)).one()

    @staticmethod
    def sum_customer_balances(context: Context) -> int:
        """Soma dos saldos das contas de cliente, sem a conta do banco. Conta encerrada tem saldo 0."""
        total = context.db_session.query(func.sum(Account.balance)).filter(Account.customer_id.isnot(None)).scalar()
        return int(total or 0)

    @staticmethod
    def update_balance(context: Context, account: Account, balance: int) -> Account:
        account.balance = balance
        account.updated_at = func.now()
        context.db_session.flush()

        return account
