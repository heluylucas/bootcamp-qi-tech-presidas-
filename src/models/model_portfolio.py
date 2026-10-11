from sqlalchemy import Column, DateTime, ForeignKey, Integer, SmallInteger, func
from sqlalchemy.orm import relationship

from models.base import Base
from models.product import Product
from models.suitability import InvestorProfile


class ModelPortfolioItem(Base):
    __tablename__ = "model_portfolio_item"

    id = Column(Integer, primary_key=True)
    investor_profile = Column(InvestorProfile, nullable=False)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    weight_bps = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    product = relationship(Product)
