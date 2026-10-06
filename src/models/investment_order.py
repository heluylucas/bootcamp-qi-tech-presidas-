from sqlalchemy import BigInteger, CHAR, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import relationship

from models.base import Base


class InvestmentOrder(Base):
    """Cada aplicação (APPLY) ou resgate (REDEEM). Nunca editada: é o histórico de investimentos."""

    __tablename__ = "investment_order"

    id = Column(Integer, primary_key=True)
    order_key = Column(CHAR(36), nullable=False, unique=True)
    customer_id = Column(Integer, ForeignKey("customer.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    side = Column(String(6), nullable=False)
    amount = Column(BigInteger, nullable=False)
    # NUMERIC volta como Decimal, nunca float (R6).
    quantity = Column(Numeric(24, 8), nullable=False)
    unit_price = Column(Numeric(20, 8), nullable=False)
    cost_amount = Column(BigInteger, nullable=False)
    maturity_date = Column(Date)
    source = Column(String(8), nullable=False, server_default="CUSTOMER")
    settled_order_id = Column(Integer, ForeignKey("investment_order.id"), unique=True)
    transaction_id = Column(Integer, ForeignKey("transaction.id"), nullable=False, unique=True)
    status = Column(String(8), nullable=False, server_default="EXECUTED")
    idempotency_key = Column(CHAR(36), nullable=False)
    request_hash = Column(CHAR(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    product = relationship("Product")
    transaction = relationship("Transaction")


class Position(Base):
    """Quanto o cliente tem de cada produto agora. Zerada não é apagada (RN-ORD-14)."""

    __tablename__ = "position"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customer.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False, server_default="0")
    invested_amount = Column(BigInteger, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    product = relationship("Product")
