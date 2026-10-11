from sqlalchemy import (
    BigInteger,
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


ProductType = Enum("PUBLIC_BOND", "PRIVATE_BOND", "FUND", name="product_type")
ProductIndexer = Enum("SELIC", "CDI", "PREFIXED", "IPCA", "QUOTA", name="product_indexer")


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
    term_months = Column(SmallInteger)
    minimum_application_amount = Column(BigInteger, nullable=False)
    cdi_percentage_bps = Column(SmallInteger)
    administration_fee_bps = Column(SmallInteger)
    price_source_code = Column(String(50))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProductPrice(Base):
    __tablename__ = "product_price"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    price_date = Column(Date, nullable=False)
    unit_price = Column(Numeric(20, 8), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
