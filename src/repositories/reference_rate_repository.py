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
            .filter(ReferenceRate.code == code, ReferenceRate.reference_date <= day)
            .order_by(ReferenceRate.reference_date.desc())
            .first()
        )

    @staticmethod
    def create(context: Context, code: str, reference_date: date, annual_rate_bps: int) -> ReferenceRate:
        rate = ReferenceRate(code=code, reference_date=reference_date, annual_rate_bps=annual_rate_bps)
        context.db_session.add(rate)
        context.db_session.flush()

        return rate
