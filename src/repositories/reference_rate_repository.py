from datetime import date
from typing import Optional

from database import Context
from models import ReferenceRate


class ReferenceRateRepository:
    @staticmethod
    def get_on(context: Context, code: str, day: date) -> Optional[ReferenceRate]:
        # A última taxa publicada até o dia pedido, como o preço (RN-REC-08).
        return (
            context.db_session.query(ReferenceRate)
            .filter(ReferenceRate.code == code, ReferenceRate.rate_date <= day)
            .order_by(ReferenceRate.rate_date.desc())
            .first()
        )

    @staticmethod
    def create(context: Context, code: str, rate_date: date, annual_rate_bps: int) -> ReferenceRate:
        rate = ReferenceRate(code=code, rate_date=rate_date, annual_rate_bps=annual_rate_bps)
        context.db_session.add(rate)
        context.db_session.flush()

        return rate
