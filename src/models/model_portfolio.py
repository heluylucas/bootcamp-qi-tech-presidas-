from sqlalchemy import Column, DateTime, ForeignKey, Integer, SmallInteger, func
from sqlalchemy.orm import relationship

from models.base import Base
from models.product import Product


class ModelPortfolioItem(Base):
    """Um produto da carteira-modelo de um perfil e o peso dele, em pontos-base (a carteira soma 10.000)."""

    __tablename__ = "model_portfolio_item"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("investor_profile.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    weight_bps = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    product = relationship(Product)
