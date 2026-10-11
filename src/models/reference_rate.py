from sqlalchemy import Column, Date, DateTime, Enum, Integer, func

from models.base import Base


ReferenceRateCode = Enum("CDI", "SELIC", name="reference_rate_code")


class ReferenceRate(Base):
    __tablename__ = "reference_rate"

    id = Column(Integer, primary_key=True)
    code = Column(ReferenceRateCode, nullable=False)
    rate_date = Column(Date, nullable=False)
    annual_rate_bps = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
