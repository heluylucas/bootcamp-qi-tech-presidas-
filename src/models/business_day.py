from sqlalchemy import Column, Date, DateTime, Integer, func

from models.base import Base


class BusinessDay(Base):
    __tablename__ = "business_day"

    id = Column(Integer, primary_key=True)
    reference_date = Column(Date, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
