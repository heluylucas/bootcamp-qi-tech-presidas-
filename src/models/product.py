from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
)

from models.base import Base


# Espelho dos tipos ENUM do database.sql: o banco recusa qualquer valor fora da lista.
ProductType = Enum("PUBLIC_BOND", "PRIVATE_BOND", "FUND", name="product_type")
ProductIndexer = Enum("SELIC", "CDI", "PREFIXED", "IPCA", "QUOTA", name="product_indexer")
ProductLiquidity = Enum("DAILY", "AT_MATURITY", name="product_liquidity")


class Product(Base):
    __tablename__ = "product"

    id = Column(Integer, primary_key=True)
    product_key = Column(CHAR(36), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    type = Column(ProductType, nullable=False)
    issuer = Column(String(100), nullable=False)
    indexer = Column(ProductIndexer, nullable=False)
    rate_description = Column(String(100), nullable=False)
    risk_level = Column(SmallInteger, nullable=False)
    liquidity = Column(ProductLiquidity, nullable=False)
    maturity_date = Column(Date)
    term_months = Column(SmallInteger)
    tax_exempt = Column(Boolean, nullable=False, server_default="false")
    min_application = Column(BigInteger, nullable=False)
    cdi_percentage_bps = Column(SmallInteger)
    admin_fee_bps = Column(SmallInteger)
    external_code = Column(String(50))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProductPrice(Base):
    __tablename__ = "product_price"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    reference_date = Column(Date, nullable=False)
    # NUMERIC volta como Decimal, nunca float (R6).
    unit_price = Column(Numeric(20, 8), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
