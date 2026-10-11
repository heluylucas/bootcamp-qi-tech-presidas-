import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import aliased

from database import Context
from models import InvestmentOrder, Position, Transaction


class InvestmentOrderRepository:
    @staticmethod
    def create(context: Context, **fields) -> InvestmentOrder:
        order = InvestmentOrder(investment_order_key=str(uuid.uuid4()), **fields)
        context.db_session.add(order)
        context.db_session.flush()

        return order

    @staticmethod
    def of_account(context: Context, account_id: int):
        return (
            context.db_session.query(InvestmentOrder)
            .join(Transaction, InvestmentOrder.transaction_id == Transaction.id)
            .filter(Transaction.owner_account_id == account_id)
        )

    @staticmethod
    def get_by_key(context: Context, account_id: int, investment_order_key: str) -> Optional[InvestmentOrder]:
        return (
            InvestmentOrderRepository.of_account(context, account_id)
            .filter(InvestmentOrder.investment_order_key == investment_order_key)
            .first()
        )

    @staticmethod
    def get_by_transaction(context: Context, transaction_id: int) -> Optional[InvestmentOrder]:
        return (
            context.db_session.query(InvestmentOrder).filter(InvestmentOrder.transaction_id == transaction_id).first()
        )

    @staticmethod
    def list_by_account(
        context: Context, account_id: int, product_id: Optional[int], page: int, limit: int
    ) -> Tuple[List[InvestmentOrder], int]:
        query = InvestmentOrderRepository.of_account(context, account_id)

        if product_id is not None:
            query = query.filter(InvestmentOrder.product_id == product_id)

        total = query.count()
        orders = query.order_by(InvestmentOrder.id.desc()).offset((page - 1) * limit).limit(limit).all()
        return orders, total

    @staticmethod
    def list_due_applications(context: Context, day: date) -> List[InvestmentOrder]:
        return (
            context.db_session.query(InvestmentOrder)
            .join(Transaction, InvestmentOrder.transaction_id == Transaction.id)
            .filter(InvestmentOrder.maturity_date <= day, InvestmentOrderRepository.not_settled(context))
            .order_by(Transaction.owner_account_id, InvestmentOrder.id)
            .all()
        )

    @staticmethod
    def latest_open_maturity(context: Context, account_id: int, product_id: int) -> Optional[date]:
        return (
            context.db_session.query(func.max(InvestmentOrder.maturity_date))
            .join(Transaction, InvestmentOrder.transaction_id == Transaction.id)
            .filter(
                Transaction.owner_account_id == account_id,
                InvestmentOrder.product_id == product_id,
                InvestmentOrderRepository.not_settled(context),
            )
            .scalar()
        )

    @staticmethod
    def not_settled(context: Context):
        settlement = aliased(InvestmentOrder)
        already_settled = context.db_session.query(settlement.id).filter(
            settlement.matured_investment_order_id == InvestmentOrder.id
        )
        return ~already_settled.exists()


class PositionRepository:
    @staticmethod
    def get_for_update(context: Context, account_id: int, product_id: int) -> Optional[Position]:
        return (
            context.db_session.query(Position)
            .filter(Position.account_id == account_id, Position.product_id == product_id)
            .populate_existing()
            .with_for_update()
            .first()
        )

    @staticmethod
    def create(context: Context, account_id: int, product_id: int) -> Position:
        position = Position(account_id=account_id, product_id=product_id, quantity=Decimal(0), acquisition_cost_amount=0)
        context.db_session.add(position)
        context.db_session.flush()

        return position

    @staticmethod
    def update(context: Context, position: Position, quantity: Decimal, acquisition_cost_amount: int) -> Position:
        position.quantity = quantity
        position.acquisition_cost_amount = acquisition_cost_amount
        position.updated_at = func.now()
        context.db_session.flush()

        return position

    @staticmethod
    def list_by_account(context: Context, account_id: int, include_closed: bool = False) -> List[Position]:
        query = context.db_session.query(Position).filter(Position.account_id == account_id)

        if not include_closed:
            query = query.filter(Position.quantity > 0)

        return query.order_by(Position.product_id).all()

    @staticmethod
    def sum_by_product(context: Context) -> List[Tuple[int, Decimal, int]]:
        rows = (
            context.db_session.query(
                Position.product_id, func.sum(Position.quantity), func.sum(Position.acquisition_cost_amount)
            )
            .group_by(Position.product_id)
            .all()
        )
        return [(product_id, quantity, int(cost)) for product_id, quantity, cost in rows]

    @staticmethod
    def has_open_position(context: Context, account_id: int) -> bool:
        return (
            context.db_session.query(Position.id)
            .filter(Position.account_id == account_id, Position.quantity > 0)
            .first()
            is not None
        )
