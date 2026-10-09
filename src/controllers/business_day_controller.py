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


CDI_SERIES = 4389
SELIC_SERIES = 1178
EIGHT_PLACES = Decimal("0.00000001")
# NUMERIC(20,8): no máximo 12 dígitos antes da vírgula.
MAX_PRICE = Decimal(10) ** 12


class BusinessDayController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def get(self) -> dict:
        # O seed sempre grava a primeira linha (R2), então nunca vem None.
        business_day = BusinessDayRepository.get_current(self.context)
        return {"business_date": business_day.business_date.isoformat()}

    def close(self, payload: dict) -> dict:
        """Fecha a data de movimento e abre o próximo dia útil (RN-FEC-01 a 08)."""
        close_date = parse_date(payload["close_date"], "close_date")

        # A trava faz dois fechamentos simultâneos virarem fila. Quem esperou
        # a trava ainda tem nas mãos a linha antiga (ela continua existindo),
        # então a data atual é relida DEPOIS da trava: é aí que o segundo
        # clique descobre que o dia já foi fechado (RN-FEC-02).
        BusinessDayRepository.get_current_for_update(self.context)
        if BusinessDayRepository.get_current(self.context).business_date != close_date:
            raise BusinessDateMismatch()

        new_day = next_business_day(close_date)
        products = ProductRepository.list(self.context, None, None)

        # Daqui até as escritas só se pergunta e se confere: qualquer recusa
        # acontece antes de gravar a primeira linha (tudo ou nada, RN-FEC-06).
        prices = self._fetch_fund_quotes(products, new_day)
        prices.update(self._fetch_treasury_prices(products, new_day))
        cdi_bps = self._fetch_rate(CDI_SERIES, new_day)
        selic_bps = self._fetch_rate(SELIC_SERIES, new_day)
        prices.update(self._own_issue_prices(products, close_date))

        # O UNIQUE de product_price, reference_rate e business_day é a rede
        # de segurança: se outro fechamento gravou o mesmo dia, recusa aqui.
        try:
            for product in products:
                ProductRepository.create_price(self.context, product.id, new_day, prices[product.id])
            ReferenceRateRepository.create(self.context, "CDI", new_day, cdi_bps)
            ReferenceRateRepository.create(self.context, "SELIC", new_day, selic_bps)
            # RN-REC-05 a 07: a provisão do dia que fecha, com a foto do fim dele. Vem antes da
            # liquidação, que já mexe nos saldos do dia novo.
            RevenueController().accrue(close_date, new_day)
            # O dia novo existe antes da liquidação: as transações dela são desse dia.
            BusinessDayRepository.create(self.context, new_day)
            # RN-FEC-09: o dinheiro das aplicações que vencem no novo dia volta antes de ele abrir.
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

    def _fetch_fund_quotes(self, products: List[Product], day: date) -> Dict[int, Decimal]:
        """Administradora: a cota de cada fundo, já líquida da taxa de administração (RN-REC-04)."""
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

    def _fetch_treasury_prices(self, products: List[Product], day: date) -> Dict[int, Decimal]:
        """Tesouro: uma chamada traz todos os títulos; cada produto acha o seu pelo price_source_code."""
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

    def _fetch_rate(self, series: int, day: date) -> int:
        """Banco Central: a taxa anual em % (texto "14.90"), que vira pontos-base (1490)."""
        body = answer_of(CentralBankConnector().get_rate(series, day))

        if not isinstance(body, list) or len(body) != 1 or field(body[0], "data") != day.strftime("%d/%m/%Y"):
            raise InvalidPriceSourceResponse()

        annual_rate_bps = int((positive_price(field(body[0], "valor")) * 100).to_integral_value(ROUND_HALF_UP))
        if annual_rate_bps <= 0:
            raise InvalidPriceSourceResponse()

        return annual_rate_bps

    def _own_issue_prices(self, products: List[Product], close_date: date) -> Dict[int, Decimal]:
        """CDB e LCI: preço anterior × (1 + c × percentual do CDI), c = CDI do dia que fecha (RN-FEC-05)."""
        # Sempre existe: o seed grava a do primeiro dia e cada fechamento grava a do dia que abre.
        cdi_bps = ReferenceRateRepository.get_on(self.context, "CDI", close_date).annual_rate_bps
        daily_cdi = (1 + Decimal(cdi_bps) / 10000) ** (Decimal(1) / 252) - 1
        prices = {}
        for product in products:
            # Emissão própria é o produto que nenhuma fonte externa publica: sem price_source_code.
            if product.price_source_code is not None:
                continue

            # Sempre existe: o seed grava o preço do dia em que o banco nasce.
            previous = ProductRepository.get_price_on(self.context, product.id, close_date).unit_price
            growth = 1 + daily_cdi * product.cdi_percentage_bps / 10000
            prices[product.id] = (previous * growth).quantize(EIGHT_PLACES, ROUND_HALF_UP)

        return prices


def answer_of(response: Optional[BaseConnectorResponse]):
    """Sem resposta (None) ou status diferente de 200: a fonte está fora do ar (PPP005006)."""
    if response is None or response.status != 200:
        raise PriceSourceUnavailable()
    return response.json


def field(body, name: str):
    """Um campo da resposta de fora. Faltou, ou o corpo nem é um objeto: resposta sem sentido."""
    if not isinstance(body, dict) or name not in body:
        raise InvalidPriceSourceResponse()
    return body[name]


def positive_price(text) -> Decimal:
    """Texto com um número > 0, que caiba em NUMERIC(20,8). Número em JSON (float) é recusado (R6)."""
    if not isinstance(text, str):
        raise InvalidPriceSourceResponse()

    try:
        value = Decimal(text)
    except InvalidOperation:
        raise InvalidPriceSourceResponse()

    if not value.is_finite() or value <= 0 or value >= MAX_PRICE:
        raise InvalidPriceSourceResponse()

    return value.quantize(EIGHT_PLACES, ROUND_HALF_UP)
