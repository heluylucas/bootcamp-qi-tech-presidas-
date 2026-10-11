from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Integer, SmallInteger, func

from models.base import Base


class RevenueAccrual(Base):
    """A provisão diária: as bases do fim do dia e o que o banco ganharia com elas (RN-REC-05 a 07)."""

    __tablename__ = "revenue_accrual"

    id = Column(Integer, primary_key=True)
    business_date = Column(Date, ForeignKey("business_day.business_date"), nullable=False, unique=True)
    # Dias corridos até o próximo dia de movimento: a de sexta vale o fim de semana.
    calendar_days = Column(SmallInteger, nullable=False)
    customer_balance_amount = Column(BigInteger, nullable=False)
    fund_equity_amount = Column(BigInteger, nullable=False)
    own_issue_cost_amount = Column(BigInteger, nullable=False)
    float_amount = Column(BigInteger, nullable=False)
    fund_administration_fee_amount = Column(BigInteger, nullable=False)
    own_issue_spread_amount = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
