from datetime import date
from typing import Optional

from database import Context
from models import BusinessDay


class BusinessDayRepository:
    @staticmethod
    def get_current(context: Context) -> Optional[BusinessDay]:
        return context.db_session.query(BusinessDay).order_by(BusinessDay.business_date.desc()).first()

    @staticmethod
    def get_current_for_update(context: Context) -> Optional[BusinessDay]:
        return (
            context.db_session.query(BusinessDay)
            .order_by(BusinessDay.business_date.desc())
            .with_for_update()
            .first()
        )

    @staticmethod
    def create(context: Context, business_date: date) -> BusinessDay:
        business_day = BusinessDay(business_date=business_date)
        context.db_session.add(business_day)
        context.db_session.flush()

        return business_day
