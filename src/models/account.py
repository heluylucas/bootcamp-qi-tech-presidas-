from sqlalchemy import BigInteger, CHAR, Column, DateTime, Enum, ForeignKey, Integer, String, func

from models.base import Base


# Espelho dos tipos ENUM do database.sql: o banco recusa qualquer valor fora da lista.
AccountStatus = Enum("ACTIVE", "BLOCKED", "CLOSED", name="account_status")
StatusActor = Enum("CUSTOMER", "BANK", name="status_actor")


class Account(Base):
    __tablename__ = "account"

    id = Column(Integer, primary_key=True)
    account_key = Column(CHAR(36), nullable=False, unique=True)
    # Nulo só na conta do próprio banco, que recebe as tarifas.
    customer_id = Column(Integer, ForeignKey("customer.id"))
    status = Column(AccountStatus, nullable=False)
    balance = Column(BigInteger, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AccountStatusEvent(Base):
    __tablename__ = "account_status_event"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    # Nulo no nascimento da conta (RN-CON-03).
    from_status = Column(AccountStatus)
    to_status = Column(AccountStatus, nullable=False)
    reason = Column(String(255))
    # CUSTOMER ou BANK: quem fez a mudança (RN-CON-05).
    actor = Column(StatusActor, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
