from sqlalchemy import Column, DateTime, ForeignKey, Integer, SmallInteger, String, func
from sqlalchemy.orm import relationship

from models.base import Base
from models.product import Product


class ModelPortfolioItem(Base):
    """Um produto da carteira-modelo e o peso dele, em pontos-base (a carteira soma 10.000)."""

    __tablename__ = "model_portfolio_item"

    id = Column(Integer, primary_key=True)
    model_portfolio_id = Column(Integer, ForeignKey("model_portfolio.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    weight_bps = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    product = relationship(Product)


class ModelPortfolio(Base):
    """A carteira sugerida de um perfil de investidor: uma por perfil."""

    __tablename__ = "model_portfolio"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("investor_profile.id"), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Do maior peso para o menor; no empate, na ordem do seed (é a ordem do exemplo da RFC).
    items = relationship(
        ModelPortfolioItem,
        order_by=(ModelPortfolioItem.weight_bps.desc(), ModelPortfolioItem.id),
    )
