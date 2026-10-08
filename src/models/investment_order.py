from sqlalchemy import BigInteger, Boolean, CHAR, Column, Date, DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import relationship

from models.base import Base


class InvestmentOrder(Base):
    """O anexo do pedido de investimento. Nunca editada: é o histórico de investimentos.

    Dono (conta), lado (tipo da transação), valor e chave de idempotência ficam na transação.
    """

    __tablename__ = "investment_order"

    id = Column(Integer, primary_key=True)
    order_key = Column(CHAR(36), nullable=False, unique=True)
    transaction_id = Column(Integer, ForeignKey("transaction.id"), nullable=False, unique=True)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    # NUMERIC volta como Decimal, nunca float (R6).
    quantity = Column(Numeric(24, 8), nullable=False)
    unit_price = Column(Numeric(20, 8), nullable=False)
    cost_amount = Column(BigInteger, nullable=False)
    # O cliente pediu resgate total: o pedido não traz valor para comparar na repetição.
    redeem_all = Column(Boolean, nullable=False, server_default="false")
    maturity_date = Column(Date)
    # Só na liquidação do vencimento: a aplicação que ela devolveu.
    settled_order_id = Column(Integer, ForeignKey("investment_order.id"), unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    product = relationship("Product")
    transaction = relationship("Transaction")


class Position(Base):
    """Quanto a conta tem de cada produto agora. Zerada não é apagada (RN-ORD-14)."""

    __tablename__ = "position"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    quantity = Column(Numeric(24, 8), nullable=False, server_default="0")
    invested_amount = Column(BigInteger, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    product = relationship("Product")
