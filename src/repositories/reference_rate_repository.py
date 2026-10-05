from datetime import date

from database import Context
from models import ReferenceRate


class ReferenceRateRepository:
    @staticmethod
    def create(context: Context, code: str, reference_date: date, annual_rate_bps: int) -> ReferenceRate:
        rate = ReferenceRate(code=code, reference_date=reference_date, annual_rate_bps=annual_rate_bps)
        context.db_session.add(rate)
        context.db_session.flush()

        return rate
