from sqlalchemy import BigInteger, CHAR, Column, DateTime, Enum, ForeignKey, Integer, String, func

from models.base import Base


AccountStatus = Enum("ACTIVE", "BLOCKED", "CLOSED", name="account_status")
StatusActor = Enum("CUSTOMER", "BANK", name="status_actor")


class Account(Base):
    __tablename__ = "account"

    id = Column(Integer, primary_key=True)
    account_key = Column(CHAR(36), nullable=False, unique=True)
    customer_id = Column(Integer, ForeignKey("customer.id"))
    status = Column(AccountStatus, nullable=False)
    balance = Column(BigInteger, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AccountStatusEvent(Base):
    __tablename__ = "account_status_event"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    from_status = Column(AccountStatus)
    to_status = Column(AccountStatus, nullable=False)
    reason = Column(String(255))
    actor = Column(StatusActor, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
