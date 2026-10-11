from typing import List

from sqlalchemy.orm import selectinload

from database import Context
from models import ModelPortfolioItem


class PortfolioRepository:
    @staticmethod
    def list_items(context: Context, investor_profile: str) -> List[ModelPortfolioItem]:
        return (
            context.db_session.query(ModelPortfolioItem)
            .options(selectinload(ModelPortfolioItem.product))
            .filter(ModelPortfolioItem.investor_profile == investor_profile)
            .order_by(ModelPortfolioItem.weight_bps.desc(), ModelPortfolioItem.id)
            .all()
        )
