from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import relationship

from models.base import Base


class TransactionType(Base):
    __tablename__ = "transaction_type"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Transaction(Base):
    """O pedido: o que o cliente pediu. Os efeitos em cada conta ficam no LedgerEntry."""

    __tablename__ = "transaction"

    id = Column(Integer, primary_key=True)
    transaction_key = Column(CHAR(36), nullable=False, unique=True)
    type_id = Column(Integer, ForeignKey("transaction_type.id"), nullable=False)
    # A dona do pedido: a conta que pediu (no depósito e no resgate, a que recebe).
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    # Só na transferência: a conta que recebe.
    destination_account_id = Column(Integer, ForeignKey("account.id"))
    amount = Column(BigInteger, nullable=False)
    fee_amount = Column(BigInteger, nullable=False, server_default="0")
    description = Column(String(140))
    # Única no banco inteiro; nula quando o próprio banco cria a transação.
    idempotency_key = Column(Uuid(as_uuid=False), unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    type = relationship(TransactionType)
    account = relationship("Account", foreign_keys=[account_id])
    destination_account = relationship("Account", foreign_keys=[destination_account_id])


class LedgerEntry(Base):
    """O lançamento: o que aconteceu em UMA conta. Uma transferência gera três."""

    __tablename__ = "ledger_entry"

    id = Column(Integer, primary_key=True)
    entry_key = Column(CHAR(36), nullable=False, unique=True)
    transaction_id = Column(Integer, ForeignKey("transaction.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    direction = Column(String(6), nullable=False)
    category = Column(String(9), nullable=False)
    amount = Column(BigInteger, nullable=False)
    balance_after = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    transaction = relationship(Transaction)
