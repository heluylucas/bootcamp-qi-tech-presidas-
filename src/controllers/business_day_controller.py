from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError

from connectors.price_source_connector import CentralBankConnector, FundAdminConnector, TreasuryConnector
from connectors.rest_connector import BaseConnectorResponse
from controllers.base_controller import BaseController
from controllers.investment_order_controller import InvestmentOrderController
from controllers.revenue_controller import RevenueController
from errors import BusinessDateMismatch, InvalidPriceSourceResponse, PriceSourceUnavailable
from models import Product
from repositories import BusinessDayRepository, ProductRepository, ReferenceRateRepository
from utils.dates import next_business_day, parse_date
from utils.money import EIGHT_PLACES


CDI_SERIES = 4389
SELIC_SERIES = 1178
MAX_PRICE = Decimal(10) ** 12


class BusinessDayController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def get(self) -> dict:
        business_day = BusinessDayRepository.get_current(self.context)
        return {"business_date": business_day.business_date.isoformat()}

    def close(self, payload: dict) -> dict:
        close_date = parse_date(payload["close_date"], "close_date")

        BusinessDayRepository.get_current_for_update(self.context)
        # Relida depois da trava: o segundo clique vê o dia já fechado.
        if BusinessDayRepository.get_current(self.context).business_date != close_date:
            raise BusinessDateMismatch()

        new_day = next_business_day(close_date)
        products = ProductRepository.list(self.context, None, None)

        prices = self.fetch_fund_quotes(products, new_day)
        prices.update(self.fetch_treasury_prices(products, new_day))
        cdi_bps = self.fetch_rate(CDI_SERIES, new_day)
        selic_bps = self.fetch_rate(SELIC_SERIES, new_day)
        prices.update(self.own_issue_prices(products, close_date))

        try:
            for product in products:
                ProductRepository.create_price(self.context, product.id, new_day, prices[product.id])
            ReferenceRateRepository.create(self.context, "CDI", new_day, cdi_bps)
            ReferenceRateRepository.create(self.context, "SELIC", new_day, selic_bps)
            # Provisão antes da liquidação (foto do dia que fecha); o dia novo antes das transações dele.
            RevenueController().accrue(close_date, new_day)
            BusinessDayRepository.create(self.context, new_day)
            InvestmentOrderController().settle_maturities(new_day, prices)
        except IntegrityError:
            raise BusinessDateMismatch()

        response = {
            "business_date": new_day.isoformat(),
            "prices": [
                {"product_key": product.product_key, "name": product.name, "unit_price": f"{prices[product.id]:.8f}"}
                for product in products
            ],
            "rates": [{"code": "CDI", "annual_rate_bps": cdi_bps}, {"code": "SELIC", "annual_rate_bps": selic_bps}],
        }
        self.session.commit()
        return response

    def fetch_fund_quotes(self, products: List[Product], day: date) -> Dict[int, Decimal]:
        quotes = {}
        for product in products:
            if product.type != "FUND":
                continue

            cnpj_digits = "".join(character for character in product.price_source_code if character.isdigit())
            body = answer_of(FundAdminConnector().get_quote(cnpj_digits, day))

            if field(body, "CNPJ_FUNDO") != product.price_source_code or field(body, "DT_COMPTC") != day.isoformat():
                raise InvalidPriceSourceResponse()

            quotes[product.id] = positive_price(field(body, "VL_QUOTA"))

        return quotes

    def fetch_treasury_prices(self, products: List[Product], day: date) -> Dict[int, Decimal]:
        body = answer_of(TreasuryConnector().get_prices(day))

        if field(body, "date") != day.isoformat() or not isinstance(field(body, "bonds"), list):
            raise InvalidPriceSourceResponse()

        published = {field(bond, "name"): field(bond, "unit_price") for bond in body["bonds"]}
        prices = {}
        for product in products:
            if product.type != "PUBLIC_BOND":
                continue
            if product.price_source_code not in published:
                raise InvalidPriceSourceResponse()

            prices[product.id] = positive_price(published[product.price_source_code])

        return prices

    def fetch_rate(self, series: int, day: date) -> int:
        body = answer_of(CentralBankConnector().get_rate(series, day))

        if not isinstance(body, list) or len(body) != 1 or field(body[0], "data") != day.strftime("%d/%m/%Y"):
            raise InvalidPriceSourceResponse()

        annual_rate_bps = int((positive_price(field(body[0], "valor")) * 100).to_integral_value(ROUND_HALF_UP))
        if annual_rate_bps <= 0:
            raise InvalidPriceSourceResponse()

        return annual_rate_bps

    def own_issue_prices(self, products: List[Product], close_date: date) -> Dict[int, Decimal]:
        cdi_bps = ReferenceRateRepository.get_on(self.context, "CDI", close_date).annual_rate_bps
        daily_cdi = (1 + Decimal(cdi_bps) / 10000) ** (Decimal(1) / 252) - 1
        prices = {}
        for product in products:
            if product.price_source_code is not None:
                continue

            previous = ProductRepository.get_price_on(self.context, product.id, close_date).unit_price
            growth = 1 + daily_cdi * product.cdi_percentage_bps / 10000
            prices[product.id] = (previous * growth).quantize(EIGHT_PLACES, ROUND_HALF_UP)

        return prices


def answer_of(response: Optional[BaseConnectorResponse]):
    if response is None or response.status != 200:
        raise PriceSourceUnavailable()
    return response.json


def field(body, name: str):
    if not isinstance(body, dict) or name not in body:
        raise InvalidPriceSourceResponse()
    return body[name]


def positive_price(text) -> Decimal:
    if not isinstance(text, str):
        raise InvalidPriceSourceResponse()

    try:
        value = Decimal(text)
    except InvalidOperation:
        raise InvalidPriceSourceResponse()

    if not value.is_finite() or value <= 0 or value >= MAX_PRICE:
        raise InvalidPriceSourceResponse()

    return value.quantize(EIGHT_PLACES, ROUND_HALF_UP)
