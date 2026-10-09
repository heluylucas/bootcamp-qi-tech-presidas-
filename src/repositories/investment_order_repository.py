import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import Date, case, cast, func
from sqlalchemy.orm import aliased

from database import Context
from models import InvestmentOrder, Position, Transaction


class InvestmentOrderRepository:
    @staticmethod
    def create(context: Context, **fields) -> InvestmentOrder:
        order = InvestmentOrder(order_key=str(uuid.uuid4()), **fields)
        context.db_session.add(order)
        context.db_session.flush()

        return order

    @staticmethod
    def of_account(context: Context, account_id: int):
        """As ordens da conta: o dono da ordem é a conta da transação dela."""
        return (
            context.db_session.query(InvestmentOrder)
            .join(Transaction, InvestmentOrder.transaction_id == Transaction.id)
            .filter(Transaction.owner_account_id == account_id)
        )

    @staticmethod
    def get_by_key(context: Context, account_id: int, order_key: str) -> Optional[InvestmentOrder]:
        # Filtrar pelo dono na própria query: a ordem de outra conta volta None (R8).
        return (
            InvestmentOrderRepository.of_account(context, account_id)
            .filter(InvestmentOrder.order_key == order_key)
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
        """Aplicações com vencimento até o dia e que nenhuma liquidação devolveu ainda (RN-FEC-09).

        Só a aplicação em produto com prazo tem maturity_date, então o filtro de data já basta.
        """
        settlement = aliased(InvestmentOrder)
        already_settled = context.db_session.query(settlement.id).filter(
            settlement.matured_investment_order_id == InvestmentOrder.id
        )
        return (
            context.db_session.query(InvestmentOrder)
            .join(Transaction, InvestmentOrder.transaction_id == Transaction.id)
            .filter(InvestmentOrder.maturity_date <= day, ~already_settled.exists())
            .order_by(Transaction.owner_account_id, InvestmentOrder.id)
            .all()
        )

    @staticmethod
    def latest_open_maturity(context: Context, account_id: int, product_id: int) -> Optional[date]:
        """O vencimento mais distante entre as aplicações deste produto ainda não liquidadas."""
        settlement = aliased(InvestmentOrder)
        already_settled = context.db_session.query(settlement.id).filter(
            settlement.matured_investment_order_id == InvestmentOrder.id
        )
        return (
            context.db_session.query(func.max(InvestmentOrder.maturity_date))
            .join(Transaction, InvestmentOrder.transaction_id == Transaction.id)
            .filter(
                Transaction.owner_account_id == account_id,
                InvestmentOrder.product_id == product_id,
                ~already_settled.exists(),
            )
            .scalar()
        )

    @staticmethod
    def daily_position_changes(context: Context, end: datetime) -> List[Tuple[int, date, Decimal, int]]:
        """Por produto e por dia (UTC), a variação de cotas e de custo de todas as contas antes de `end`.

        Aplicação soma, resgate subtrai (no resgate o custo gravado é o que saiu da posição).
        """
        day = cast(func.timezone("UTC", InvestmentOrder.created_at), Date)
        applied = Transaction.type == "INVESTMENT_APPLY"
        rows = (
            context.db_session.query(
                InvestmentOrder.product_id,
                day,
                func.sum(case((applied, InvestmentOrder.quantity), else_=-InvestmentOrder.quantity)),
                func.sum(
                    case((applied, InvestmentOrder.acquisition_cost_amount), else_=-InvestmentOrder.acquisition_cost_amount)
                ),
            )
            .join(Transaction, InvestmentOrder.transaction_id == Transaction.id)
            .filter(InvestmentOrder.created_at < end)
            .group_by(InvestmentOrder.product_id, day)
            .order_by(day)
            .all()
        )
        return [(product_id, row_day, quantity, int(cost)) for product_id, row_day, quantity, cost in rows]


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
        """As posições da conta; as zeradas só com include_closed."""
        query = context.db_session.query(Position).filter(Position.account_id == account_id)

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
