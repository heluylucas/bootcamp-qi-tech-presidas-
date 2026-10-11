from sqlalchemy import BigInteger, CHAR, Column, Date, DateTime, Enum, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import relationship

from models.base import Base


TransactionType = Enum(
    "DEPOSIT", "WITHDRAWAL", "TRANSFER", "INVESTMENT_APPLY", "INVESTMENT_REDEEM", name="transaction_type"
)
EntryDirection = Enum("DEBIT", "CREDIT", name="entry_direction")
EntryCategory = Enum("PRINCIPAL", "FEE", name="entry_category")


class Transaction(Base):
    __tablename__ = "transaction"

    id = Column(Integer, primary_key=True)
    transaction_key = Column(CHAR(36), nullable=False, unique=True)
    type = Column(TransactionType, nullable=False)
    owner_account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    destination_account_id = Column(Integer, ForeignKey("account.id"))
    amount = Column(BigInteger, nullable=False)
    fee_amount = Column(BigInteger, nullable=False, server_default="0")
    description = Column(String(140))
    idempotency_key = Column(Uuid(as_uuid=False), unique=True)
    business_date = Column(Date, ForeignKey("business_day.business_date"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    owner_account = relationship("Account", foreign_keys=[owner_account_id])
    destination_account = relationship("Account", foreign_keys=[destination_account_id])


class LedgerEntry(Base):
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
