from sqlalchemy import Column, Date, DateTime, Integer, String, func

from models.base import Base


class ReferenceRate(Base):
    """CDI ou Selic de um dia, em pontos-base ao ano (RN-REC-08). Nunca alterada."""

    __tablename__ = "reference_rate"

    id = Column(Integer, primary_key=True)
    code = Column(String(5), nullable=False)
    reference_date = Column(Date, nullable=False)
    annual_rate_bps = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
