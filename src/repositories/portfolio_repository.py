from typing import Optional

from sqlalchemy.orm import selectinload

from database import Context
from models import ModelPortfolio, ModelPortfolioItem


class PortfolioRepository:
    @staticmethod
    def get_by_profile(context: Context, profile_id: int) -> Optional[ModelPortfolio]:
        # Sem trava: a sugestão só lê o seed e não grava nada (RN-CAR-04).
        # selectinload: os itens e os produtos deles vêm em poucas consultas, não uma por item.
        return (
            context.db_session.query(ModelPortfolio)
            .options(selectinload(ModelPortfolio.items).selectinload(ModelPortfolioItem.product))
            .filter(ModelPortfolio.profile_id == profile_id)
            .first()
        )
