from typing import List, Tuple

from controllers.base_controller import BaseController
from controllers.suitability_controller import SuitabilityController
from dtos.portfolio_dto import suggestion_to_dict
from errors import CustomerNotFound, SuggestionAmountTooLow
from models import ModelPortfolioItem
from repositories import CustomerRepository, PortfolioRepository


# RN-CAR-02: R$ 1.000,00. Garante que cada fatia respeite a aplicação mínima do produto.
MINIMUM_SUGGESTION_AMOUNT = 100000

# A carteira-modelo soma 10.000 pontos-base (100%).
FULL_WEIGHT_BPS = 10000


class PortfolioController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def suggest(self, customer_key: str, amount: int) -> dict:
        """Divide o valor entre os produtos da carteira do perfil (RN-CAR-01 a 05).

        É só simulação: não olha saldo nem conta e não grava nada, por isso não há commit.
        """
        customer = CustomerRepository.get_by_key(self.context, customer_key)

        if customer is None:
            raise CustomerNotFound()

        # A mesma regra de perfil válido que as ordens usam (sem perfil / vencido → 409).
        assessment = SuitabilityController().get_valid_assessment(customer.id)

        if amount < MINIMUM_SUGGESTION_AMOUNT:
            raise SuggestionAmountTooLow()

        # O seed grava uma carteira para cada perfil, então ela sempre tem itens.
        items = PortfolioRepository.list_items(self.context, assessment.investor_profile)

        allocations = split_amount(amount, items)
        return suggestion_to_dict(assessment.investor_profile, amount, allocations)


def split_amount(amount: int, items: List[ModelPortfolioItem]) -> List[Tuple[ModelPortfolioItem, int]]:
    """RN-CAR-03: floor(valor × peso / 10.000) por item; os centavos que sobram vão para o maior peso.

    Só inteiros (centavos), nunca float. Os itens chegam do maior peso para o menor,
    então o maior peso é o primeiro. A soma dos itens é exatamente o valor pedido.
    """
    shares = [amount * item.weight_bps // FULL_WEIGHT_BPS for item in items]
    shares[0] += amount - sum(shares)
    return list(zip(items, shares))
