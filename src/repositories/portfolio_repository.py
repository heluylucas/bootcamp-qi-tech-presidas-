from typing import List

from sqlalchemy.orm import selectinload

from database import Context
from models import ModelPortfolioItem


class PortfolioRepository:
    @staticmethod
    def list_items(context: Context, investor_profile_id: int) -> List[ModelPortfolioItem]:
        """Os itens da carteira-modelo do perfil, do maior peso para o menor; no empate, na ordem do seed."""
        # Sem trava: a sugestão só lê o seed e não grava nada (RN-CAR-04).
        # selectinload: os produtos dos itens vêm numa consulta só, não uma por item.
        return (
            context.db_session.query(ModelPortfolioItem)
            .options(selectinload(ModelPortfolioItem.product))
            .filter(ModelPortfolioItem.investor_profile_id == investor_profile_id)
            .order_by(ModelPortfolioItem.weight_bps.desc(), ModelPortfolioItem.id)
            .all()
        )
