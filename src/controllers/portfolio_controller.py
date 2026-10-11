from typing import List, Tuple

from controllers.base_controller import BaseController
from controllers.suitability_controller import SuitabilityController
from dtos.portfolio_dto import suggestion_to_dict
from errors import SuggestionAmountTooLow
from models import ModelPortfolioItem
from repositories import PortfolioRepository


MINIMUM_SUGGESTION_AMOUNT = 100000

FULL_WEIGHT_BPS = 10000


class PortfolioController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def suggest(self, customer_key: str, amount: int) -> dict:
        customer = self.get_customer(customer_key)

        assessment = SuitabilityController().get_valid_assessment(customer.id)

        if amount < MINIMUM_SUGGESTION_AMOUNT:
            raise SuggestionAmountTooLow()

        items = PortfolioRepository.list_items(self.context, assessment.investor_profile)

        allocations = split_amount(amount, items)
        return suggestion_to_dict(assessment.investor_profile, amount, allocations)


def split_amount(amount: int, items: List[ModelPortfolioItem]) -> List[Tuple[ModelPortfolioItem, int]]:
    shares = [amount * item.weight_bps // FULL_WEIGHT_BPS for item in items]
    shares[0] += amount - sum(shares)
    return list(zip(items, shares))
