from datetime import date
from typing import List

from database import Context
from models import RevenueAccrual


class RevenueAccrualRepository:
    @staticmethod
    def create(context: Context, **fields) -> RevenueAccrual:
        accrual = RevenueAccrual(**fields)
        context.db_session.add(accrual)
        context.db_session.flush()

        return accrual

    @staticmethod
    def list_between(context: Context, from_date: date, to_date: date) -> List[RevenueAccrual]:
        """As provisões dos dias fechados no período, do mais antigo para o mais novo."""
        return (
            context.db_session.query(RevenueAccrual)
            .filter(RevenueAccrual.business_date >= from_date, RevenueAccrual.business_date <= to_date)
            .order_by(RevenueAccrual.business_date)
            .all()
        )
