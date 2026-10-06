from datetime import date
from typing import Optional
from urllib.parse import urlencode

import requests

from connectors.rest_connector import BaseConnectorResponse, RestConnector
from constants import CENTRAL_BANK_API_URL, FUND_ADMIN_API_URL, PRICE_SOURCE_TIMEOUT, TREASURY_API_URL


class PriceSourceConnector(RestConnector):
    """O que as três fontes de preço têm em comum (RN-FEC-04).

    Devolve a resposta como veio, ou None quando não houve resposta
    nenhuma (fora do ar, timeout, conexão derrubada). Quem decide que
    isso vira 502 é o controller.
    """

    def __init__(self, class_name: str, base_url: str) -> None:
        # Token vazio: o INTERNAL-TOKEN é desta API e não sai para serviço de fora.
        super().__init__(class_name, base_url, PRICE_SOURCE_TIMEOUT, "")

    def get(self, endpoint: str, query_params: dict) -> Optional[BaseConnectorResponse]:
        try:
            return self.send(f"{endpoint}?{urlencode(query_params)}", "GET")
        except requests.RequestException as error:
            self.logger.warning(f"NO RESPONSE GET {self.base_url}{endpoint}: {error}")
            return None


class FundAdminConnector(PriceSourceConnector):
    """Administradora do fundo: a cota do dia, no formato do Informe Diário da CVM."""

    def __init__(self) -> None:
        super().__init__(__name__, FUND_ADMIN_API_URL)

    def get_quote(self, cnpj_digits: str, day: date) -> Optional[BaseConnectorResponse]:
        return self.get(f"/funds/{cnpj_digits}/quotes", {"date": day.isoformat()})


class TreasuryConnector(PriceSourceConnector):
    """Tesouro: o preço de todos os títulos públicos de um dia."""

    def __init__(self) -> None:
        super().__init__(__name__, TREASURY_API_URL)

    def get_prices(self, day: date) -> Optional[BaseConnectorResponse]:
        return self.get("/prices", {"date": day.isoformat()})


class CentralBankConnector(PriceSourceConnector):
    """Banco Central: uma série do SGS (4389 = CDI, 1178 = Selic), mesmo formato da API pública."""

    def __init__(self) -> None:
        super().__init__(__name__, CENTRAL_BANK_API_URL)

    def get_rate(self, series: int, day: date) -> Optional[BaseConnectorResponse]:
        text = day.strftime("%d/%m/%Y")
        query_params = {"formato": "json", "dataInicial": text, "dataFinal": text}
        return self.get(f"/dados/serie/bcdata.sgs.{series}/dados", query_params)
