from sqlalchemy import BigInteger, Boolean, CHAR, Column, Date, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import relationship

from models.base import Base


class InvestmentOrder(Base):
    __tablename__ = "investment_order"

    id = Column(Integer, primary_key=True)
    investment_order_key = Column(CHAR(36), nullable=False, unique=True)
    transaction_id = Column(Integer, ForeignKey("transaction.id"), nullable=False, unique=True)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False)
    unit_price = Column(Numeric(20, 8), nullable=False)
    acquisition_cost_amount = Column(BigInteger, nullable=False)
    redeem_all = Column(Boolean, nullable=False, server_default="false")
    maturity_date = Column(Date)
    matured_investment_order_id = Column(Integer, ForeignKey("investment_order.id"), unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    product = relationship("Product")
    transaction = relationship("Transaction")


class Position(Base):
    __tablename__ = "position"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False, server_default="0")
    acquisition_cost_amount = Column(BigInteger, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    product = relationship("Product")
