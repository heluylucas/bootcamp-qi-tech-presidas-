from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from controllers.base_controller import BaseController
from controllers.suitability_controller import SuitabilityController
from controllers.transaction_controller import DEFAULT_LIMIT, DEFAULT_PAGE, TransactionController, parse_idempotency_key
from dtos.investment_order_dto import order_to_dict, position_to_dict, total_to_dict
from errors import (
    AccountNotActive,
    BelowMinimumApplication,
    IdempotencyKeyReused,
    InsufficientBalance,
    InsufficientPosition,
    InvalidAmount,
    OrderNotFound,
    ProductNotSuitable,
    RedemptionNotAllowed,
)
from models import Account, InvestmentOrder, Position, Product, Transaction
from repositories import (
    AccountRepository,
    BusinessDayRepository,
    InvestmentOrderRepository,
    PositionRepository,
    ProductRepository,
)
from utils.dates import add_months
from utils.money import amount_for, quantity_for


SIDE_TRANSACTION_TYPES = {"APPLY": "INVESTMENT_APPLY", "REDEEM": "INVESTMENT_REDEEM"}


class InvestmentOrderController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def create(
        self, customer_key: str, account_key: str, payload: dict, idempotency_key: Optional[str]
    ) -> Tuple[dict, bool]:
        idempotency_key = parse_idempotency_key(idempotency_key)

        if payload["side"] == "REDEEM":
            return self.redeem(customer_key, account_key, payload, idempotency_key)

        return self.apply(customer_key, account_key, payload, idempotency_key)

    def apply(self, customer_key: str, account_key: str, payload: dict, idempotency_key: str) -> Tuple[dict, bool]:
        amount = payload["amount"]

        if amount <= 0:
            raise InvalidAmount()

        account = self.get_active_account(customer_key, account_key)
        assessment = SuitabilityController().get_valid_assessment(account.customer_id)
        product = self.get_product(payload["product_key"])
        business_date = BusinessDayRepository.get_current(self.context).business_date

        if product.risk_level > assessment.maximum_risk_level:
            raise ProductNotSuitable()

        if amount < product.minimum_application_amount:
            raise BelowMinimumApplication()

        price = ProductRepository.get_price_on(self.context, product.id, business_date)

        account = AccountRepository.get_by_id_for_update(self.context, account.id)
        position = PositionRepository.get_for_update(self.context, account.id, product.id)

        original = self.find_original(idempotency_key, account)

        if original is not None:
            if not is_same_order(original, payload, product):
                raise IdempotencyKeyReused()
            return order_to_dict(original), False

        if account.status != "ACTIVE":
            raise AccountNotActive()

        if account.balance < amount:
            raise InsufficientBalance()

        if position is None:
            position = PositionRepository.create(self.context, account.id, product.id)

        quantity = quantity_for(amount, price.unit_price)
        maturity_date = add_months(business_date, product.term_months) if product.term_months else None

        transaction = self.money_transaction("INVESTMENT_APPLY", account, amount, idempotency_key)
        TransactionController().add_entry(transaction, account, "DEBIT", "PRINCIPAL", amount, account.balance - amount)
        order = InvestmentOrderRepository.create(
            self.context,
            transaction_id=transaction.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=price.unit_price,
            acquisition_cost_amount=amount,
            maturity_date=maturity_date,
        )
        PositionRepository.update(
            self.context, position, position.quantity + quantity, position.acquisition_cost_amount + amount
        )

        response = order_to_dict(order)
        self.session.commit()
        return response, True

    def redeem(
        self, customer_key: str, account_key: str, payload: dict, idempotency_key: str
    ) -> Tuple[dict, bool]:
        amount = payload.get("amount")

        if amount is not None and amount <= 0:
            raise InvalidAmount()

        account = self.get_active_account(customer_key, account_key)
        product = self.get_product(payload["product_key"])
        business_date = BusinessDayRepository.get_current(self.context).business_date
        price = ProductRepository.get_price_on(self.context, product.id, business_date)

        account = AccountRepository.get_by_id_for_update(self.context, account.id)
        position = PositionRepository.get_for_update(self.context, account.id, product.id)

        original = self.find_original(idempotency_key, account)

        if original is not None:
            if not is_same_order(original, payload, product):
                raise IdempotencyKeyReused()
            return order_to_dict(original), False

        if account.status != "ACTIVE":
            raise AccountNotActive()

        held = position.quantity if position is not None else Decimal(0)

        if amount is None:
            quantity = held
            amount = amount_for(quantity, price.unit_price)
        else:
            quantity = quantity_for(amount, price.unit_price)

        if quantity <= 0 or quantity > held:
            raise InsufficientPosition()

        if product.term_months and not self.has_matured(account.id, product, business_date):
            raise RedemptionNotAllowed()

        order = self.record_redemption(
            account,
            position,
            price.unit_price,
            quantity,
            amount,
            idempotency_key,
            redeem_all=payload.get("redeem_all", False),
        )

        response = order_to_dict(order)
        self.session.commit()
        return response, True

    def record_redemption(
        self,
        account: Account,
        position: Position,
        unit_price: Decimal,
        quantity: Decimal,
        amount: int,
        idempotency_key: Optional[str],
        redeem_all: bool = False,
        matured_investment_order_id: Optional[int] = None,
        business_date: Optional[date] = None,
    ) -> InvestmentOrder:
        if quantity == position.quantity:
            acquisition_cost_amount = position.acquisition_cost_amount
        else:
            acquisition_cost_amount = int(position.acquisition_cost_amount * quantity // position.quantity)

        transaction = self.money_transaction("INVESTMENT_REDEEM", account, amount, idempotency_key, business_date)
        TransactionController().add_entry(transaction, account, "CREDIT", "PRINCIPAL", amount, account.balance + amount)
        order = InvestmentOrderRepository.create(
            self.context,
            transaction_id=transaction.id,
            product_id=position.product_id,
            quantity=quantity,
            unit_price=unit_price,
            acquisition_cost_amount=acquisition_cost_amount,
            redeem_all=redeem_all,
            matured_investment_order_id=matured_investment_order_id,
        )
        PositionRepository.update(
            self.context, position, position.quantity - quantity, position.acquisition_cost_amount - acquisition_cost_amount
        )
        return order

    def settle_maturities(self, day: date, prices: Dict[int, Decimal]) -> None:
        for application in InvestmentOrderRepository.list_due_applications(self.context, day):
            account = AccountRepository.get_by_id_for_update(self.context, application.transaction.owner_account_id)
            position = PositionRepository.get_for_update(self.context, account.id, application.product_id)
            unit_price = prices[application.product_id]
            quantity = application.quantity

            # Sem Idempotency-Key: o UNIQUE de matured_investment_order_id impede pagar duas vezes.
            # Conta bloqueada recebe mesmo assim: é o banco devolvendo, não o cliente movimentando.
            self.record_redemption(
                account,
                position,
                unit_price,
                quantity,
                amount_for(quantity, unit_price),
                None,
                matured_investment_order_id=application.id,
                business_date=day,
            )

    def has_matured(self, account_id: int, product: Product, business_date: date) -> bool:
        maturity = InvestmentOrderRepository.latest_open_maturity(self.context, account_id, product.id)
        return maturity is not None and maturity <= business_date

    def get(self, customer_key: str, account_key: str, order_key: str) -> dict:
        account = self.get_owned_account(customer_key, account_key)
        order = InvestmentOrderRepository.get_by_key(self.context, account.id, order_key)

        if order is None:
            raise OrderNotFound()

        return order_to_dict(order)

    def list_orders(self, customer_key: str, account_key: str, query_params: dict) -> dict:
        page = int(query_params.get("page", DEFAULT_PAGE))
        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        product_key = query_params.get("product_key")
        account = self.get_owned_account(customer_key, account_key)
        empty = {"items": [], "page": page, "limit": limit, "total": 0}
        product_id = None

        if product_key is not None:
            product = ProductRepository.get_by_key(self.context, product_key)
            if product is None:
                return empty
            product_id = product.id

        orders, total = InvestmentOrderRepository.list_by_account(self.context, account.id, product_id, page, limit)
        return {**empty, "items": [order_to_dict(order) for order in orders], "total": total}

    def list_positions(self, customer_key: str, account_key: str, include_closed: bool) -> dict:
        account = self.get_owned_account(customer_key, account_key)
        positions = PositionRepository.list_by_account(self.context, account.id, include_closed)
        items = [position_to_dict(position, unit_price) for position, unit_price in self.priced_positions(positions)]
        return {"items": items, "total": total_to_dict(items, account.balance)}

    def priced_positions(self, positions: List[Position]) -> List[Tuple[Position, Decimal]]:
        if not positions:
            return []
        business_date = BusinessDayRepository.get_current(self.context).business_date
        return [
            (position, ProductRepository.get_price_on(self.context, position.product_id, business_date).unit_price)
            for position in positions
        ]

    def find_original(self, idempotency_key: str, account: Account) -> Optional[InvestmentOrder]:
        previous = TransactionController().find_repetition(idempotency_key, account)

        if previous is None:
            return None

        order = InvestmentOrderRepository.get_by_transaction(self.context, previous.id)

        if order is None:
            raise IdempotencyKeyReused()

        return order

    def money_transaction(
        self,
        transaction_type: str,
        account: Account,
        amount: int,
        idempotency_key: Optional[str],
        business_date: Optional[date] = None,
    ) -> Transaction:
        return TransactionController().create_transaction(
            transaction_type, account, None, amount, 0, None, idempotency_key, business_date
        )

    def get_active_account(self, customer_key: str, account_key: str) -> Account:
        account = self.get_owned_account(customer_key, account_key)

        if account.status != "ACTIVE":
            raise AccountNotActive()

        return account


def is_same_order(original: InvestmentOrder, payload: dict, product: Product) -> bool:
    redeem_all = payload.get("redeem_all", False)
    return (
        original.transaction.type == SIDE_TRANSACTION_TYPES[payload["side"]]
        and original.product_id == product.id
        and original.redeem_all == redeem_all
        and (redeem_all or original.transaction.amount == payload["amount"])
    )
