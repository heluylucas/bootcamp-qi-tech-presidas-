from typing import List, Tuple

from models import ModelPortfolioItem


def suggestion_to_dict(profile: str, amount: int, allocations: List[Tuple[ModelPortfolioItem, int]]) -> dict:
    return {
        "profile": profile,
        "amount": amount,
        "items": [
            {
                "product_key": item.product.product_key,
                "name": item.product.name,
                "weight_bps": item.weight_bps,
                "amount": item_amount,
            }
            for item, item_amount in allocations
        ],
    }
