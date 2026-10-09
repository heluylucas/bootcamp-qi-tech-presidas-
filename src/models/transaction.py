from sqlalchemy import BigInteger, CHAR, Column, DateTime, Enum, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import relationship

from models.base import Base


# Espelho dos tipos ENUM do database.sql: o banco recusa qualquer valor fora da lista.
TransactionType = Enum(
    "DEPOSIT", "WITHDRAWAL", "TRANSFER", "INVESTMENT_APPLY", "INVESTMENT_REDEEM", name="transaction_type"
)
EntryDirection = Enum("DEBIT", "CREDIT", name="entry_direction")
EntryCategory = Enum("PRINCIPAL", "FEE", name="entry_category")


class Transaction(Base):
    """O pedido: o que o cliente pediu. Os efeitos em cada conta ficam no LedgerEntry."""

    __tablename__ = "transaction"

    id = Column(Integer, primary_key=True)
    transaction_key = Column(CHAR(36), nullable=False, unique=True)
    type = Column(TransactionType, nullable=False)
    # A dona do pedido: a conta que pediu (no depósito e no resgate, a que recebe).
    owner_account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    # Só na transferência, e nela sempre: a conta que recebe.
    destination_account_id = Column(Integer, ForeignKey("account.id"))
    amount = Column(BigInteger, nullable=False)
    fee_amount = Column(BigInteger, nullable=False, server_default="0")
    description = Column(String(140))
    # Única no banco inteiro; nula quando o próprio banco cria a transação.
    idempotency_key = Column(Uuid(as_uuid=False), unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    owner_account = relationship("Account", foreign_keys=[owner_account_id])
    destination_account = relationship("Account", foreign_keys=[destination_account_id])


class LedgerEntry(Base):
    """O lançamento: o que aconteceu em UMA conta. Uma transferência gera quatro."""

    __tablename__ = "ledger_entry"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transaction.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    direction = Column(EntryDirection, nullable=False)
    category = Column(EntryCategory, nullable=False)
    amount = Column(BigInteger, nullable=False)
    balance_after = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    transaction = relationship(Transaction)
