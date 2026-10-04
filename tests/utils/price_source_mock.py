from datetime import date
from typing import Dict

from tests.utils.mock_utils import BaseExpectation, Mock


FUND_CNPJ = "12345678000195"
TREASURY_BONDS = {
    "TESOURO SELIC 2031": "2031-03-01",
    "TESOURO PREFIXADO 2029": "2029-01-01",
    "TESOURO IPCA+ 2035": "2035-05-15",
}
CDI_SERIES = 4389
SELIC_SERIES = 1178

# Ganha do cenário da demonstração, que o mock-init ensina sem prioridade.
TEST_PRIORITY = 10


class PriceSourceMock:

    @staticmethod
    def fund_quote(day: date, unit_price: str) -> None:
        """Administradora: a cota do FGV Quant Capital naquele dia."""
        Mock().add_expectations(
            BaseExpectation.generate_expectation(
                "GET",
                f"/fund-admin/funds/{FUND_CNPJ}/quotes",
                query_params={"date": [day.isoformat()]},
                status_code=200,
                response_json=fund_quote_body(day, unit_price),
                number_of_calls=1,
                priority=TEST_PRIORITY,
            )
        )

    @staticmethod
    def treasury_prices(day: date, unit_prices: Dict[str, str]) -> None:
        """Tesouro: o preço de cada título, pelo nome (o external_code do produto)."""
        Mock().add_expectations(
            BaseExpectation.generate_expectation(
                "GET",
                "/treasury/prices",
                query_params={"date": [day.isoformat()]},
                status_code=200,
                response_json=treasury_body(day, unit_prices),
                number_of_calls=1,
                priority=TEST_PRIORITY,
            )
        )

    @staticmethod
    def rate(day: date, series: int, annual_rate: str) -> None:
        """Banco Central: a taxa anual de uma série (CDI_SERIES ou SELIC_SERIES), em % ao ano."""
        Mock().add_expectations(
            BaseExpectation.generate_expectation(
                "GET",
                f"/bcb/dados/serie/bcdata.sgs.{series}/dados",
                query_params=bcb_query(day),
                status_code=200,
                response_json=[{"data": day.strftime("%d/%m/%Y"), "valor": annual_rate}],
                number_of_calls=1,
                priority=TEST_PRIORITY,
            )
        )


def fund_quote_body(day: date, unit_price: str) -> dict:
    # Campos do Informe Diário da CVM.
    return {
        "CNPJ_FUNDO": "12.345.678/0001-95",
        "DT_COMPTC": day.isoformat(),
        "VL_QUOTA": unit_price,
        "VL_PATRIM_LIQ": "150000000.00",
        "NR_COTST": 1200,
    }


def treasury_body(day: date, unit_prices: Dict[str, str]) -> dict:
    bonds = [
        {"name": name, "maturity_date": TREASURY_BONDS[name], "unit_price": unit_price}
        for name, unit_price in unit_prices.items()
    ]
    return {"date": day.isoformat(), "bonds": bonds}


def bcb_query(day: date) -> dict:
    text = day.strftime("%d/%m/%Y")
    return {"formato": ["json"], "dataInicial": [text], "dataFinal": [text]}
