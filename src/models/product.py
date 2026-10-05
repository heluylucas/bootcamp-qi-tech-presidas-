from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import relationship

from models.base import Base


class ProductType(Base):
    __tablename__ = "product_type"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Product(Base):
    __tablename__ = "product"

    id = Column(Integer, primary_key=True)
    product_key = Column(CHAR(36), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    type_id = Column(Integer, ForeignKey("product_type.id"), nullable=False)
    issuer = Column(String(100), nullable=False)
    indexer = Column(String(8), nullable=False)
    rate_description = Column(String(100), nullable=False)
    risk_level = Column(SmallInteger, nullable=False)
    liquidity = Column(String(11), nullable=False)
    maturity_date = Column(Date)
    term_months = Column(SmallInteger)
    tax_exempt = Column(Boolean, nullable=False, server_default="false")
    min_application = Column(BigInteger, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    own_issue = Column(Boolean, nullable=False, server_default="false")
    cdi_percentage_bps = Column(SmallInteger)
    admin_fee_bps = Column(SmallInteger)
    external_code = Column(String(50))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    type = relationship(ProductType)


class ProductPrice(Base):
    __tablename__ = "product_price"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    reference_date = Column(Date, nullable=False)
    # NUMERIC volta como Decimal, nunca float (R6).
    unit_price = Column(Numeric(20, 8), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
