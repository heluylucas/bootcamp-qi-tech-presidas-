from sqlalchemy import CHAR, Column, Date, DateTime, Integer, Text, func

from models.base import Base


class Customer(Base):
    __tablename__ = "customer"

    id = Column(Integer, primary_key=True)
    customer_key = Column(CHAR(36), nullable=False, unique=True)
    name = Column(Text, nullable=False)
    document_number = Column(CHAR(14), nullable=False, unique=True)
    birth_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
