from datetime import date
from decimal import Decimal
from typing import List, Optional

from database import Context
from models import Product, ProductPrice


class ProductRepository:
    @staticmethod
    def list(context: Context, product_type: Optional[str], maximum_risk_level: Optional[int]) -> List[Product]:
        query = context.db_session.query(Product)

        if product_type is not None:
            query = query.filter(Product.type == product_type)
        if maximum_risk_level is not None:
            query = query.filter(Product.risk_level <= maximum_risk_level)

        return query.order_by(Product.id).all()

    @staticmethod
    def get_by_key(context: Context, product_key: str) -> Optional[Product]:
        return context.db_session.query(Product).filter(Product.product_key == product_key).first()

    @staticmethod
    def get_price_on(context: Context, product_id: int, day: date) -> Optional[ProductPrice]:
        return (
            context.db_session.query(ProductPrice)
            .filter(ProductPrice.product_id == product_id, ProductPrice.price_date <= day)
            .order_by(ProductPrice.price_date.desc())
            .first()
        )

    @staticmethod
    def list_prices(
        context: Context, product_id: int, from_date: Optional[date], to_date: Optional[date]
    ) -> List[ProductPrice]:
        query = context.db_session.query(ProductPrice).filter(ProductPrice.product_id == product_id)

        if from_date is not None:
            query = query.filter(ProductPrice.price_date >= from_date)
        if to_date is not None:
            query = query.filter(ProductPrice.price_date <= to_date)

        return query.order_by(ProductPrice.price_date).all()

    @staticmethod
    def create_price(context: Context, product_id: int, day: date, unit_price: Decimal) -> ProductPrice:
        price = ProductPrice(product_id=product_id, price_date=day, unit_price=unit_price)
        context.db_session.add(price)
        context.db_session.flush()

        return price
