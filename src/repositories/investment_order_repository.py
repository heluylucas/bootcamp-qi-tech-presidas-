import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import aliased

from database import Context
from models import InvestmentOrder, Position


class InvestmentOrderRepository:
    @staticmethod
    def create(context: Context, **fields) -> InvestmentOrder:
        order = InvestmentOrder(order_key=str(uuid.uuid4()), **fields)
        context.db_session.add(order)
        context.db_session.flush()

        return order

    @staticmethod
    def get_by_key(context: Context, customer_id: int, order_key: str) -> Optional[InvestmentOrder]:
        # Filtrar pelo dono na própria query: a ordem de outro cliente volta None (R8).
        return (
            context.db_session.query(InvestmentOrder)
            .filter(InvestmentOrder.order_key == order_key, InvestmentOrder.customer_id == customer_id)
            .first()
        )

    @staticmethod
    def get_by_idempotency_key(context: Context, customer_id: int, idempotency_key: str) -> Optional[InvestmentOrder]:
        return (
            context.db_session.query(InvestmentOrder)
            .filter(InvestmentOrder.customer_id == customer_id, InvestmentOrder.idempotency_key == idempotency_key)
            .first()
        )

    @staticmethod
    def list_by_customer(
        context: Context, customer_id: int, product_id: Optional[int], page: int, limit: int
    ) -> Tuple[List[InvestmentOrder], int]:
        query = context.db_session.query(InvestmentOrder).filter(InvestmentOrder.customer_id == customer_id)

        if product_id is not None:
            query = query.filter(InvestmentOrder.product_id == product_id)

        total = query.count()
        orders = query.order_by(InvestmentOrder.id.desc()).offset((page - 1) * limit).limit(limit).all()
        return orders, total

    @staticmethod
    def list_due_applications(context: Context, day: date) -> List[InvestmentOrder]:
        """Aplicações com vencimento até o dia e que nenhuma liquidação devolveu ainda (RN-FEC-09)."""
        settlement = aliased(InvestmentOrder)
        already_settled = context.db_session.query(settlement.id).filter(
            settlement.settled_order_id == InvestmentOrder.id
        )
        return (
            context.db_session.query(InvestmentOrder)
            .filter(
                InvestmentOrder.side == "APPLY",
                InvestmentOrder.maturity_date <= day,
                ~already_settled.exists(),
            )
            .order_by(InvestmentOrder.account_id, InvestmentOrder.id)
            .all()
        )

    @staticmethod
    def latest_open_maturity(context: Context, customer_id: int, product_id: int) -> Optional[date]:
        """O vencimento mais distante entre as aplicações deste produto ainda não liquidadas."""
        settlement = aliased(InvestmentOrder)
        already_settled = context.db_session.query(settlement.id).filter(
            settlement.settled_order_id == InvestmentOrder.id
        )
        return (
            context.db_session.query(func.max(InvestmentOrder.maturity_date))
            .filter(
                InvestmentOrder.customer_id == customer_id,
                InvestmentOrder.product_id == product_id,
                InvestmentOrder.side == "APPLY",
                ~already_settled.exists(),
            )
            .scalar()
        )


class PositionRepository:
    @staticmethod
    def get_for_update(context: Context, customer_id: int, product_id: int) -> Optional[Position]:
        # populate_existing: relê quantidade e custo depois que a trava é concedida.
        return (
            context.db_session.query(Position)
            .filter(Position.customer_id == customer_id, Position.product_id == product_id)
            .populate_existing()
            .with_for_update()
            .first()
        )

    @staticmethod
    def create(context: Context, customer_id: int, product_id: int) -> Position:
        position = Position(customer_id=customer_id, product_id=product_id, quantity=Decimal(0), invested_amount=0)
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
        query = context.db_session.query(Position).filter(Position.customer_id == customer_id)

        if not include_closed:
            query = query.filter(Position.quantity > 0)

        return query.order_by(Position.product_id).all()

    @staticmethod
    def has_open_position(context: Context, customer_id: int) -> bool:
        return (
            context.db_session.query(Position.id)
            .filter(Position.customer_id == customer_id, Position.quantity > 0)
            .first()
            is not None
        )
