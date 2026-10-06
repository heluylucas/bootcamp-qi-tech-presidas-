from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Dict, Optional, Tuple
from uuid import NAMESPACE_URL, uuid5

from controllers.base_controller import BaseController
from controllers.suitability_controller import SuitabilityController
from controllers.transaction_controller import TransactionController, hash_request
from dtos.investment_order_dto import order_to_dict, position_to_dict, total_to_dict
from errors import (
    AccountNotActive,
    BelowMinimumApplication,
    CustomerNotFound,
    IdempotencyKeyReused,
    InsufficientBalance,
    InsufficientPosition,
    InvalidAmount,
    MissingIdempotencyKey,
    NoActiveAccount,
    OrderNotFound,
    ProductNotFound,
    ProductNotSuitable,
    RedemptionNotAllowed,
)
from models import Account, Customer, InvestmentOrder, Position, Product
from repositories import (
    AccountRepository,
    BusinessDayRepository,
    CustomerRepository,
    InvestmentOrderRepository,
    PositionRepository,
    ProductRepository,
    TransactionRepository,
)
from utils.dates import add_months


EIGHT_PLACES = Decimal("0.00000001")


class InvestmentOrderController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def create(self, customer_key: str, payload: dict, idempotency_key: Optional[str]) -> Tuple[dict, bool]:
        """Devolve (ordem, criada). criada=False é a repetição idempotente: o resource responde 200."""
        if idempotency_key is None:
            raise MissingIdempotencyKey()

        if payload["side"] == "REDEEM":
            return self.redeem_order(customer_key, payload, idempotency_key)

        return self.apply(customer_key, payload, idempotency_key)

    def apply(self, customer_key: str, payload: dict, idempotency_key: str) -> Tuple[dict, bool]:
        """Aplicação: toda recusa antes de qualquer escrita (RN-ORD-01 a 08 e 17)."""
        amount = payload["amount"]

        if amount <= 0:
            raise InvalidAmount()

        customer = self.get_customer(customer_key)
        account = self.get_open_account(customer)
        assessment = SuitabilityController().get_valid_assessment(customer.id)
        product = self.get_product(payload["product_key"])
        business_date = BusinessDayRepository.get_current(self.context).reference_date

        if product.risk_level > assessment.profile.max_risk_level:
            raise ProductNotSuitable()

        if amount < product.min_application:
            raise BelowMinimumApplication()

        # Sempre existe: o seed grava o preço do primeiro dia e o fechamento só abre
        # um dia novo depois de gravar o preço de todos os produtos (RN-FEC-06).
        price = ProductRepository.get_price_on(self.context, product.id, business_date)

        # Daqui em diante, saldo e posição são lidos travados: conta, depois posição (RN-GER-12).
        account = AccountRepository.get_by_id_for_update(self.context, account.id)
        position = PositionRepository.get_for_update(self.context, customer.id, product.id)

        # Idempotência depois das travas: um reenvio simultâneo espera o original
        # e recebe a resposta dele, e não um falso "saldo insuficiente" (RN-GER-08).
        request_hash = hash_request(payload)
        original = InvestmentOrderRepository.get_by_idempotency_key(self.context, customer.id, idempotency_key)

        if original is not None:
            if original.request_hash != request_hash:
                raise IdempotencyKeyReused()
            return order_to_dict(original), False

        if account.status.enumerator != "ACTIVE":
            raise AccountNotActive()

        if account.balance < amount:
            raise InsufficientBalance()

        if position is None:
            position = PositionRepository.create(self.context, customer.id, product.id)

        # RN-ORD-06: valor em reais / preço, truncado em 8 casas. O débito é o valor pedido.
        quantity = (Decimal(amount) / 100 / price.unit_price).quantize(EIGHT_PLACES, ROUND_DOWN)
        maturity_date = add_months(business_date, product.term_months) if product.term_months else None

        transaction = self.money_transaction("INVESTMENT_APPLY", account, amount, idempotency_key, request_hash)
        TransactionController().add_entry(transaction, account, "DEBIT", "PRINCIPAL", amount, account.balance - amount)
        order = InvestmentOrderRepository.create(
            self.context,
            customer_id=customer.id,
            account_id=account.id,
            product_id=product.id,
            side="APPLY",
            amount=amount,
            quantity=quantity,
            unit_price=price.unit_price,
            cost_amount=amount,
            maturity_date=maturity_date,
            transaction_id=transaction.id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        PositionRepository.update(
            self.context, position, position.quantity + quantity, position.invested_amount + amount
        )

        response = order_to_dict(order)
        self.session.commit()
        return response, True

    def redeem_order(self, customer_key: str, payload: dict, idempotency_key: str) -> Tuple[dict, bool]:
        """Resgate pedido pelo cliente: igual à aplicação, sem olhar o perfil (RN-ORD-09 a 16)."""
        amount = payload.get("amount")

        if amount is not None and amount <= 0:
            raise InvalidAmount()

        customer = self.get_customer(customer_key)
        account = self.get_open_account(customer)
        product = self.get_product(payload["product_key"])
        business_date = BusinessDayRepository.get_current(self.context).reference_date
        price = ProductRepository.get_price_on(self.context, product.id, business_date)

        # Mesma ordem de travas da aplicação: conta, depois posição (RN-GER-12).
        account = AccountRepository.get_by_id_for_update(self.context, account.id)
        position = PositionRepository.get_for_update(self.context, customer.id, product.id)

        request_hash = hash_request(payload)
        original = InvestmentOrderRepository.get_by_idempotency_key(self.context, customer.id, idempotency_key)

        if original is not None:
            if original.request_hash != request_hash:
                raise IdempotencyKeyReused()
            return order_to_dict(original), False

        if account.status.enumerator != "ACTIVE":
            raise AccountNotActive()

        held = position.quantity if position is not None else Decimal(0)

        # RN-ORD-12: por valor, valor / preço truncado; total, toda a posição a floor(qtd × preço).
        if amount is None:
            quantity = held
            amount = int(quantity * price.unit_price * 100)
        else:
            quantity = (Decimal(amount) / 100 / price.unit_price).quantize(EIGHT_PLACES, ROUND_DOWN)

        if quantity <= 0 or quantity > held:
            raise InsufficientPosition()

        if product.liquidity == "AT_MATURITY" and not self.has_matured(customer.id, product, business_date):
            raise RedemptionNotAllowed()

        order = self.redeem(account, position, price.unit_price, quantity, amount, idempotency_key, request_hash)

        response = order_to_dict(order)
        self.session.commit()
        return response, True

    def redeem(
        self,
        account: Account,
        position: Position,
        unit_price: Decimal,
        quantity: Decimal,
        amount: int,
        idempotency_key: str,
        request_hash: str,
        source: str = "CUSTOMER",
        settled_order_id: Optional[int] = None,
    ) -> InvestmentOrder:
        """As escritas do resgate, com conta e posição já travadas. Não decide nada: só grava."""
        # RN-ORD-13: custo médio. Sai a fração do custo igual à fração das cotas; no total, tudo.
        if quantity == position.quantity:
            cost_amount = position.invested_amount
        else:
            cost_amount = int(position.invested_amount * quantity // position.quantity)

        transaction = self.money_transaction("INVESTMENT_REDEEM", account, amount, idempotency_key, request_hash)
        TransactionController().add_entry(transaction, account, "CREDIT", "PRINCIPAL", amount, account.balance + amount)
        order = InvestmentOrderRepository.create(
            self.context,
            customer_id=position.customer_id,
            account_id=account.id,
            product_id=position.product_id,
            side="REDEEM",
            amount=amount,
            quantity=quantity,
            unit_price=unit_price,
            cost_amount=cost_amount,
            source=source,
            settled_order_id=settled_order_id,
            transaction_id=transaction.id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        # RN-ORD-14: a posição zerada fica com quantidade 0, não é apagada.
        PositionRepository.update(
            self.context, position, position.quantity - quantity, position.invested_amount - cost_amount
        )
        return order

    def settle_maturities(self, day: date, prices: Dict[int, Decimal]) -> None:
        """RN-FEC-09: devolve à conta cada aplicação vencida até o dia, ao preço do dia.

        Roda dentro do fechamento, que faz o commit: ou o dia abre com tudo pago, ou nada muda.
        """
        # Em ordem crescente de conta, e em cada uma conta depois posição: a mesma
        # ordem de travas das ordens do cliente, então ninguém espera ninguém em círculo.
        for application in InvestmentOrderRepository.list_due_applications(self.context, day):
            account = AccountRepository.get_by_id_for_update(self.context, application.account_id)
            position = PositionRepository.get_for_update(self.context, application.customer_id, application.product_id)
            unit_price = prices[application.product_id]
            quantity = application.quantity

            # Sem chave do cliente: uma fixa por aplicação cumpre os UNIQUE de
            # transaction e investment_order, e repetir a liquidação dá erro em vez de pagar duas vezes.
            reference = {"settled_order_key": application.order_key}
            idempotency_key = str(uuid5(NAMESPACE_URL, f"maturity:{application.order_key}"))

            # O crédito vale mesmo com a conta bloqueada: o banco devolver não é o cliente movimentar.
            self.redeem(
                account,
                position,
                unit_price,
                quantity,
                int(quantity * unit_price * 100),
                idempotency_key,
                hash_request(reference),
                source="MATURITY",
                settled_order_id=application.id,
            )

    def has_matured(self, customer_id: int, product: Product, business_date: date) -> bool:
        """RN-ORD-11: com prazo, vale o vencimento da aplicação mais recente ainda não liquidada."""
        if product.term_months:
            maturity = InvestmentOrderRepository.latest_open_maturity(self.context, customer_id, product.id)
        else:
            maturity = product.maturity_date

        return maturity is not None and maturity <= business_date

    def get(self, customer_key: str, order_key: str) -> dict:
        customer = self.get_customer(customer_key)
        # A busca já filtra pelo dono: ordem de outro cliente dá o mesmo 404 (R8).
        order = InvestmentOrderRepository.get_by_key(self.context, customer.id, order_key)

        if order is None:
            raise OrderNotFound()

        return order_to_dict(order)

    def list_orders(self, customer_key: str, page: int, limit: int, product_key: Optional[str]) -> dict:
        """RN-GER-11: a mais nova primeiro, em páginas."""
        customer = self.get_customer(customer_key)
        empty = {"items": [], "page": page, "limit": limit, "total": 0}
        product_id = None

        if product_key is not None:
            product = ProductRepository.get_by_key(self.context, product_key)
            # O filtro só restringe a busca: produto que não existe não tem ordem nenhuma.
            if product is None:
                return empty
            product_id = product.id

        orders, total = InvestmentOrderRepository.list_by_customer(self.context, customer.id, product_id, page, limit)
        return {**empty, "items": [order_to_dict(order) for order in orders], "total": total}

    def positions(self, customer_key: str, include_closed: bool) -> dict:
        """RN-POS-01 a 03: cada posição ao preço do dia, e o total consolidado."""
        customer = self.get_customer(customer_key)
        business_date = BusinessDayRepository.get_current(self.context).reference_date
        items = [
            position_to_dict(
                position, ProductRepository.get_price_on(self.context, position.product_id, business_date).unit_price
            )
            for position in PositionRepository.list_by_customer(self.context, customer.id, include_closed)
        ]
        return {"items": items, "total": total_to_dict(items)}

    def money_transaction(self, type_enumerator: str, account: Account, amount: int, idempotency_key: str, request_hash: str):
        """A transação na conta: a aplicação "sai para fora" (só origem), o resgate "vem de fora" (só destino)."""
        is_apply = type_enumerator == "INVESTMENT_APPLY"
        type_row = TransactionRepository.get_type(self.context, type_enumerator)
        return TransactionRepository.create(
            self.context,
            type_id=type_row.id,
            requester_account_id=account.id,
            origin_account_id=account.id if is_apply else None,
            destination_account_id=None if is_apply else account.id,
            amount=amount,
            fee_amount=0,
            description=None,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )

    def get_customer(self, customer_key: str) -> Customer:
        customer = CustomerRepository.get_by_key(self.context, customer_key)

        if customer is None:
            raise CustomerNotFound()

        return customer

    def get_open_account(self, customer: Customer) -> Account:
        """A conta que paga e recebe: a não encerrada do cliente (RN-ORD-01)."""
        account = AccountRepository.get_not_closed_by_customer(self.context, customer.id)

        if account is None:
            raise NoActiveAccount()

        if account.status.enumerator != "ACTIVE":
            raise AccountNotActive()

        return account

    def get_product(self, product_key: str) -> Product:
        product = ProductRepository.get_by_key(self.context, product_key)

        if product is None:
            raise ProductNotFound()

        return product
