from datetime import date
from typing import Optional
from urllib.parse import urlencode

import requests

from connectors.rest_connector import BaseConnectorResponse, RestConnector
from constants import CENTRAL_BANK_API_URL, FUND_ADMIN_API_URL, PRICE_SOURCE_TIMEOUT, TREASURY_API_URL


class PriceSourceConnector(RestConnector):
    def __init__(self, class_name: str, base_url: str) -> None:
        super().__init__(class_name, base_url, PRICE_SOURCE_TIMEOUT, "")

    def get(self, endpoint: str, query_params: dict) -> Optional[BaseConnectorResponse]:
        try:
            return self.send(f"{endpoint}?{urlencode(query_params)}", "GET")
        except requests.RequestException as error:
            self.logger.warning(f"NO RESPONSE GET {self.base_url}{endpoint}: {error}")
            return None


class FundAdminConnector(PriceSourceConnector):
    def __init__(self) -> None:
        super().__init__(__name__, FUND_ADMIN_API_URL)

    def get_quote(self, cnpj_digits: str, day: date) -> Optional[BaseConnectorResponse]:
        return self.get(f"/funds/{cnpj_digits}/quotes", {"date": day.isoformat()})


class TreasuryConnector(PriceSourceConnector):
    def __init__(self) -> None:
        super().__init__(__name__, TREASURY_API_URL)

    def get_prices(self, day: date) -> Optional[BaseConnectorResponse]:
        return self.get("/prices", {"date": day.isoformat()})


class CentralBankConnector(PriceSourceConnector):
    def __init__(self) -> None:
        super().__init__(__name__, CENTRAL_BANK_API_URL)

    def get_rate(self, series: int, day: date) -> Optional[BaseConnectorResponse]:
        text = day.strftime("%d/%m/%Y")
        query_params = {"formato": "json", "dataInicial": text, "dataFinal": text}
        return self.get(f"/dados/serie/bcdata.sgs.{series}/dados", query_params)
