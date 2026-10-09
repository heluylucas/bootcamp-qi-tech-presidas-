from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Dict, List, Optional, Tuple

from controllers.base_controller import BaseController
from controllers.suitability_controller import SuitabilityController
from controllers.transaction_controller import TransactionController, parse_idempotency_key
from dtos.investment_order_dto import order_to_dict, position_to_dict, total_to_dict
from errors import (
    AccountNotActive,
    BelowMinimumApplication,
    IdempotencyKeyReused,
    InsufficientBalance,
    InsufficientPosition,
    InvalidAmount,
    OrderNotFound,
    ProductNotFound,
    ProductNotSuitable,
    RedemptionNotAllowed,
)
from models import Account, InvestmentOrder, Position, Product
from repositories import (
    AccountRepository,
    BusinessDayRepository,
    InvestmentOrderRepository,
    PositionRepository,
    ProductRepository,
)
from utils.dates import add_months


EIGHT_PLACES = Decimal("0.00000001")

# O tipo da transação de cada lado da ordem.
SIDE_TRANSACTION_TYPES = {"APPLY": "INVESTMENT_APPLY", "REDEEM": "INVESTMENT_REDEEM"}


class InvestmentOrderController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def create(
        self, customer_key: str, account_key: str, payload: dict, idempotency_key: Optional[str]
    ) -> Tuple[dict, bool]:
        """Devolve (ordem, criada). criada=False é a repetição idempotente: o resource responde 200."""
        idempotency_key = parse_idempotency_key(idempotency_key)

        if payload["side"] == "REDEEM":
            return self.redeem_order(customer_key, account_key, payload, idempotency_key)

        return self.apply(customer_key, account_key, payload, idempotency_key)

    def apply(self, customer_key: str, account_key: str, payload: dict, idempotency_key: str) -> Tuple[dict, bool]:
        """Aplicação: toda recusa antes de qualquer escrita (RN-ORD-01 a 08 e 17)."""
        amount = payload["amount"]

        if amount <= 0:
            raise InvalidAmount()

        account = self.get_active_account(customer_key, account_key)
        assessment = SuitabilityController().get_valid_assessment(account.customer_id)
        product = self.get_product(payload["product_key"])
        business_date = BusinessDayRepository.get_current(self.context).business_date

        if product.risk_level > assessment.investor_profile.maximum_risk_level:
            raise ProductNotSuitable()

        if amount < product.minimum_application_amount:
            raise BelowMinimumApplication()

        # Sempre existe: o seed grava o preço do primeiro dia e o fechamento só abre
        # um dia novo depois de gravar o preço de todos os produtos (RN-FEC-06).
        price = ProductRepository.get_price_on(self.context, product.id, business_date)

        # Daqui em diante, saldo e posição são lidos travados: conta, depois posição (RN-GER-12).
        account = AccountRepository.get_by_id_for_update(self.context, account.id)
        position = PositionRepository.get_for_update(self.context, account.id, product.id)

        # Idempotência depois das travas: um reenvio simultâneo espera o original
        # e recebe a resposta dele, e não um falso "saldo insuficiente" (RN-GER-08).
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

        # RN-ORD-06: valor em reais / preço, truncado em 8 casas. O débito é o valor pedido.
        quantity = (Decimal(amount) / 100 / price.unit_price).quantize(EIGHT_PLACES, ROUND_DOWN)
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

    def redeem_order(
        self, customer_key: str, account_key: str, payload: dict, idempotency_key: str
    ) -> Tuple[dict, bool]:
        """Resgate pedido pelo cliente: igual à aplicação, sem olhar o perfil (RN-ORD-09 a 16)."""
        amount = payload.get("amount")

        if amount is not None and amount <= 0:
            raise InvalidAmount()

        account = self.get_active_account(customer_key, account_key)
        product = self.get_product(payload["product_key"])
        business_date = BusinessDayRepository.get_current(self.context).business_date
        price = ProductRepository.get_price_on(self.context, product.id, business_date)

        # Mesma ordem de travas da aplicação: conta, depois posição (RN-GER-12).
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

        # RN-ORD-12: por valor, valor / preço truncado; total, toda a posição a floor(qtd × preço).
        if amount is None:
            quantity = held
            amount = int(quantity * price.unit_price * 100)
        else:
            quantity = (Decimal(amount) / 100 / price.unit_price).quantize(EIGHT_PLACES, ROUND_DOWN)

        if quantity <= 0 or quantity > held:
            raise InsufficientPosition()

        # Produto com prazo só é resgatado no vencimento da aplicação (RN-ORD-11).
        if product.term_months and not self.has_matured(account.id, product, business_date):
            raise RedemptionNotAllowed()

        order = self.redeem(
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

    def redeem(
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
        """As escritas do resgate, com conta e posição já travadas. Não decide nada: só grava."""
        # RN-ORD-13: custo médio. Sai a fração do custo igual à fração das cotas; no total, tudo.
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
        # RN-ORD-14: a posição zerada fica com quantidade 0, não é apagada.
        PositionRepository.update(
            self.context, position, position.quantity - quantity, position.acquisition_cost_amount - acquisition_cost_amount
        )
        return order

    def settle_maturities(self, day: date, prices: Dict[int, Decimal]) -> None:
        """RN-FEC-09: devolve à conta cada aplicação vencida até o dia, ao preço do dia.

        Roda dentro do fechamento, que faz o commit: ou o dia abre com tudo pago, ou nada muda.
        """
        # Em ordem crescente de conta, e em cada uma conta depois posição: a mesma
        # ordem de travas das ordens do cliente, então ninguém espera ninguém em círculo.
        for application in InvestmentOrderRepository.list_due_applications(self.context, day):
            account = AccountRepository.get_by_id_for_update(self.context, application.transaction.owner_account_id)
            position = PositionRepository.get_for_update(self.context, account.id, application.product_id)
            unit_price = prices[application.product_id]
            quantity = application.quantity

            # Sem chave de idempotência: não há pedido de cliente para repetir. O que impede
            # pagar duas vezes é o UNIQUE de matured_investment_order_id.
            # O crédito vale mesmo com a conta bloqueada: o banco devolver não é o cliente movimentar.
            self.redeem(
                account,
                position,
                unit_price,
                quantity,
                int(quantity * unit_price * 100),
                None,
                matured_investment_order_id=application.id,
                # O dinheiro volta antes de o novo dia abrir: a transação é do dia novo.
                business_date=day,
            )

    def has_matured(self, account_id: int, product: Product, business_date: date) -> bool:
        """RN-ORD-11: vale o vencimento da aplicação mais recente ainda não liquidada."""
        maturity = InvestmentOrderRepository.latest_open_maturity(self.context, account_id, product.id)
        return maturity is not None and maturity <= business_date

    def get(self, customer_key: str, account_key: str, order_key: str) -> dict:
        account = TransactionController().get_owned_account(customer_key, account_key)
        # A busca já filtra pelo dono: ordem de outra conta dá o mesmo 404 (R8).
        order = InvestmentOrderRepository.get_by_key(self.context, account.id, order_key)

        if order is None:
            raise OrderNotFound()

        return order_to_dict(order)

    def list_orders(
        self, customer_key: str, account_key: str, page: int, limit: int, product_key: Optional[str]
    ) -> dict:
        """RN-GER-11: a mais nova primeiro, em páginas."""
        account = TransactionController().get_owned_account(customer_key, account_key)
        empty = {"items": [], "page": page, "limit": limit, "total": 0}
        product_id = None

        if product_key is not None:
            product = ProductRepository.get_by_key(self.context, product_key)
            # O filtro só restringe a busca: produto que não existe não tem ordem nenhuma.
            if product is None:
                return empty
            product_id = product.id

        orders, total = InvestmentOrderRepository.list_by_account(self.context, account.id, product_id, page, limit)
        return {**empty, "items": [order_to_dict(order) for order in orders], "total": total}

    def positions(self, customer_key: str, account_key: str, include_closed: bool) -> dict:
        """RN-POS-01 a 03: cada posição da conta ao preço do dia, e o total com o caixa (o saldo dela).

        Calculado na leitura, não gravado: o valor dos investimentos muda a cada fechamento do dia.
        """
        account = TransactionController().get_owned_account(customer_key, account_key)
        positions = PositionRepository.list_by_account(self.context, account.id, include_closed)
        items = [position_to_dict(position, unit_price) for position, unit_price in self.priced_positions(positions)]
        return {"items": items, "total": total_to_dict(items, account.balance)}

    def priced_positions(self, positions: List[Position]) -> List[Tuple[Position, Decimal]]:
        """Cada posição com o preço do dia (o último publicado até a data de movimento).

        A rota de posições e a consulta da conta usam este mesmo cálculo, para nunca divergirem.
        """
        if not positions:
            return []
        business_date = BusinessDayRepository.get_current(self.context).business_date
        return [
            (position, ProductRepository.get_price_on(self.context, position.product_id, business_date).unit_price)
            for position in positions
        ]

    def find_original(self, idempotency_key: str, account: Account) -> Optional[InvestmentOrder]:
        """A ordem já feita com esta chave nesta conta; None se a chave é nova."""
        previous = TransactionController().find_repetition(idempotency_key, account)

        if previous is None:
            return None

        # A chave mora na transação. Se ela não tem ordem (um depósito, por exemplo),
        # a chave foi usada em outro pedido.
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
    ):
        """O pedido de dinheiro da ordem: o dono é a conta, o tipo diz se é aplicação ou resgate."""
        return TransactionController().create_transaction(
            transaction_type, account, None, amount, 0, None, idempotency_key, business_date
        )

    def get_active_account(self, customer_key: str, account_key: str) -> Account:
        """A conta que paga e recebe (RN-ORD-01): do cliente (senão 404, R8) e ativa."""
        account = TransactionController().get_owned_account(customer_key, account_key)

        if account.status != "ACTIVE":
            raise AccountNotActive()

        return account

    def get_product(self, product_key: str) -> Product:
        product = ProductRepository.get_by_key(self.context, product_key)

        if product is None:
            raise ProductNotFound()

        return product


def is_same_order(original: InvestmentOrder, payload: dict, product: Product) -> bool:
    """O pedido repetido é idêntico ao gravado? Compara o corpo com as colunas da ordem e da transação.

    O resgate total não traz valor (é calculado na hora): nele, compara-se o redeem_all gravado.
    """
    redeem_all = payload.get("redeem_all", False)
    return (
        original.transaction.type == SIDE_TRANSACTION_TYPES[payload["side"]]
        and original.product_id == product.id
        and original.redeem_all == redeem_all
        and (redeem_all or original.transaction.amount == payload["amount"])
    )
