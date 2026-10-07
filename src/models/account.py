from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from models.base import Base


class AccountStatus(Base):
    __tablename__ = "account_status"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Account(Base):
    __tablename__ = "account"

    id = Column(Integer, primary_key=True)
    account_key = Column(CHAR(36), nullable=False, unique=True)
    customer_id = Column(Integer, ForeignKey("customer.id"), nullable=False)
    status_id = Column(Integer, ForeignKey("account_status.id"), nullable=False)
    balance = Column(BigInteger, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Carregado só quando alguém lê `account.status` (padrão do SQLAlchemy).
    # Não troque por lazy="joined": o JOIN quebraria o SELECT ... FOR UPDATE.
    status = relationship(AccountStatus)


class AccountStatusEvent(Base):
    __tablename__ = "account_status_event"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("account.id"), nullable=False)
    from_status_id = Column(Integer, ForeignKey("account_status.id"))
    to_status_id = Column(Integer, ForeignKey("account_status.id"), nullable=False)
    reason = Column(String(255))
    # CUSTOMER ou BANK: quem fez a mudança (RN-CON-05).
    actor = Column(String(8), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    from_status = relationship(AccountStatus, foreign_keys=[from_status_id])
    to_status = relationship(AccountStatus, foreign_keys=[to_status_id])
