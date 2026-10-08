import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import aliased

from database import Context
from models import Account, InvestmentOrder, Position, Transaction


class InvestmentOrderRepository:
    @staticmethod
    def create(context: Context, **fields) -> InvestmentOrder:
        order = InvestmentOrder(order_key=str(uuid.uuid4()), **fields)
        context.db_session.add(order)
        context.db_session.flush()

        return order

    @staticmethod
    def of_customer(context: Context, customer_id: int):
        """As ordens das contas do cliente: o dono da ordem é a conta da transação dela."""
        return (
            context.db_session.query(InvestmentOrder)
            .join(Transaction, InvestmentOrder.transaction_id == Transaction.id)
            .join(Account, Transaction.account_id == Account.id)
            .filter(Account.customer_id == customer_id)
        )

    @staticmethod
    def get_by_key(context: Context, customer_id: int, order_key: str) -> Optional[InvestmentOrder]:
        # Filtrar pelo dono na própria query: a ordem de outro cliente volta None (R8).
        return (
            InvestmentOrderRepository.of_customer(context, customer_id)
            .filter(InvestmentOrder.order_key == order_key)
            .first()
        )

    @staticmethod
    def get_by_transaction(context: Context, transaction_id: int) -> Optional[InvestmentOrder]:
        return (
            context.db_session.query(InvestmentOrder).filter(InvestmentOrder.transaction_id == transaction_id).first()
        )

    @staticmethod
    def list_by_customer(
        context: Context, customer_id: int, product_id: Optional[int], page: int, limit: int
    ) -> Tuple[List[InvestmentOrder], int]:
        query = InvestmentOrderRepository.of_customer(context, customer_id)

        if product_id is not None:
            query = query.filter(InvestmentOrder.product_id == product_id)

        total = query.count()
        orders = query.order_by(InvestmentOrder.id.desc()).offset((page - 1) * limit).limit(limit).all()
        return orders, total

    @staticmethod
    def list_due_applications(context: Context, day: date) -> List[InvestmentOrder]:
        """Aplicações com vencimento até o dia e que nenhuma liquidação devolveu ainda (RN-FEC-09).

        Só a aplicação em produto com prazo tem maturity_date, então o filtro de data já basta.
        """
        settlement = aliased(InvestmentOrder)
        already_settled = context.db_session.query(settlement.id).filter(
            settlement.settled_order_id == InvestmentOrder.id
        )
        return (
            context.db_session.query(InvestmentOrder)
            .join(Transaction, InvestmentOrder.transaction_id == Transaction.id)
            .filter(InvestmentOrder.maturity_date <= day, ~already_settled.exists())
            .order_by(Transaction.account_id, InvestmentOrder.id)
            .all()
        )

    @staticmethod
    def latest_open_maturity(context: Context, account_id: int, product_id: int) -> Optional[date]:
        """O vencimento mais distante entre as aplicações deste produto ainda não liquidadas."""
        settlement = aliased(InvestmentOrder)
        already_settled = context.db_session.query(settlement.id).filter(
            settlement.settled_order_id == InvestmentOrder.id
        )
        return (
            context.db_session.query(func.max(InvestmentOrder.maturity_date))
            .join(Transaction, InvestmentOrder.transaction_id == Transaction.id)
            .filter(
                Transaction.account_id == account_id,
                InvestmentOrder.product_id == product_id,
                ~already_settled.exists(),
            )
            .scalar()
        )


class PositionRepository:
    @staticmethod
    def get_for_update(context: Context, account_id: int, product_id: int) -> Optional[Position]:
        # populate_existing: relê quantidade e custo depois que a trava é concedida.
        return (
            context.db_session.query(Position)
            .filter(Position.account_id == account_id, Position.product_id == product_id)
            .populate_existing()
            .with_for_update()
            .first()
        )

    @staticmethod
    def create(context: Context, account_id: int, product_id: int) -> Position:
        position = Position(account_id=account_id, product_id=product_id, quantity=Decimal(0), invested_amount=0)
        context.db_session.add(position)
        context.db_session.flush()

        return position

    @staticmethod
    def update(context: Context, position: Position, quantity: Decimal, invested_amount: int) -> Position:
        position.quantity = quantity
        position.invested_amount = invested_amount
        position.updated_at = func.now()
        context.db_session.flush()

        return position

    @staticmethod
    def list_by_customer(context: Context, customer_id: int, include_closed: bool) -> List[Position]:
        query = (
            context.db_session.query(Position)
            .join(Account, Position.account_id == Account.id)
            .filter(Account.customer_id == customer_id)
        )

        if not include_closed:
            query = query.filter(Position.quantity > 0)

        return query.order_by(Position.product_id).all()

    @staticmethod
    def has_open_position(context: Context, account_id: int) -> bool:
        return (
            context.db_session.query(Position.id)
            .filter(Position.account_id == account_id, Position.quantity > 0)
            .first()
            is not None
        )
