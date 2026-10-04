from typing import Optional

from database import Context
from models import BusinessDay


class BusinessDayRepository:
    @staticmethod
    def get_current(context: Context) -> Optional[BusinessDay]:
        # A data de movimento é a maior reference_date (RN-GER-13).
        return context.db_session.query(BusinessDay).order_by(BusinessDay.reference_date.desc()).first()
