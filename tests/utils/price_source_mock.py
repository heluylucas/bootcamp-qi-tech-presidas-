from datetime import date
from typing import Dict, Optional

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

# Os números redondos que o teste usa quando não pede outro.
DEFAULT_FUND_QUOTE = "102.00"
DEFAULT_TREASURY_PRICES = {name: "120.00" for name in TREASURY_BONDS}
DEFAULT_CDI = "14.90"
DEFAULT_SELIC = "15.00"

SERVICES = ("fund", "treasury", "cdi", "selic")


class PriceSourceMock:
    # Toda resposta daqui vale para UMA chamada: depois que a API a consome,
    # o mock volta ao cenário da demonstração.

    @staticmethod
    def teach_day(
        day: date,
        fund: str = DEFAULT_FUND_QUOTE,
        treasury: Optional[Dict[str, str]] = None,
        cdi: str = DEFAULT_CDI,
        selic: str = DEFAULT_SELIC,
        skip: Optional[str] = None,
    ) -> None:
        # Não apaga nada: cada resposta de teste tem um id fixo por fonte e dia
        # (expectation_id_for), e ensinar de novo SUBSTITUI a anterior. Assim a
        # sobra de um teste que falhou no meio some, e o cenário da demonstração
        # que o mock-init ensinou continua lá para as próximas rodadas da suíte.
        if skip != "fund":
            PriceSourceMock.fund_quote(day, fund)
        if skip != "treasury":
            PriceSourceMock.treasury_prices(day, treasury or DEFAULT_TREASURY_PRICES)
        if skip != "cdi":
            PriceSourceMock.answer("cdi", day, rate_body(day, cdi))
        if skip != "selic":
            PriceSourceMock.answer("selic", day, rate_body(day, selic))

    @staticmethod
    def fund_quote(day: date, unit_price: str, quote_date: Optional[date] = None) -> None:
        """Administradora: a cota do FGV Quant Capital. `quote_date` diferente simula data errada."""
        PriceSourceMock.answer("fund", day, fund_quote_body(quote_date or day, unit_price))

    @staticmethod
    def treasury_prices(day: date, unit_prices: Dict[str, str]) -> None:
        """Tesouro: o preço de cada título, pelo nome (o external_code do produto)."""
        PriceSourceMock.answer("treasury", day, treasury_body(day, unit_prices))

    @staticmethod
    def answer(service: str, day: date, body, status_code: int = 200) -> None:
        """Qualquer corpo, inclusive um sem sentido, para um dos SERVICES."""
        path, query_params = request_of(service, day)
        expectation = BaseExpectation.generate_expectation(
            "GET",
            path,
            query_params=query_params,
            status_code=status_code,
            response_json=body,
            number_of_calls=1,
            priority=TEST_PRIORITY,
        )
        expectation["id"] = expectation_id_for(service, day)
        Mock().add_expectations(expectation)

    @staticmethod
    def server_error(service: str, day: date) -> None:
        """A fonte respondeu, e respondeu que quebrou (500)."""
        PriceSourceMock.answer(service, day, {"message": "internal error"}, status_code=500)

    @staticmethod
    def connection_dropped(service: str, day: date) -> None:
        """A conexão cai sem resposta nenhuma: o mesmo caminho de fora do ar ou timeout."""
        path, query_params = request_of(service, day)
        expectation = BaseExpectation.generate_error(
            "GET",
            path,
            error_json={"dropConnection": True},
            query_params=query_params,
            number_of_calls=1,
            priority=TEST_PRIORITY,
        )
        expectation["id"] = expectation_id_for(service, day)
        Mock().add_expectations(expectation)


def expectation_id_for(service: str, day: date) -> str:
    """Um id por fonte e dia: o MockServer troca a expectativa de mesmo id em vez de empilhar."""
    return f"test-{service}-{day.isoformat()}"


def request_of(service: str, day: date):
    """Caminho e query que a API usa para perguntar a cada fonte (contratos na RFC)."""
    if service == "fund":
        return f"/fund-admin/funds/{FUND_CNPJ}/quotes", {"date": [day.isoformat()]}
    if service == "treasury":
        return "/treasury/prices", {"date": [day.isoformat()]}

    series = {"cdi": CDI_SERIES, "selic": SELIC_SERIES}[service]
    return f"/bcb/dados/serie/bcdata.sgs.{series}/dados", bcb_query(day)


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


def rate_body(day: date, annual_rate: str) -> list:
    return [{"data": day.strftime("%d/%m/%Y"), "valor": annual_rate}]


def bcb_query(day: date) -> dict:
    text = day.strftime("%d/%m/%Y")
    return {"formato": ["json"], "dataInicial": [text], "dataFinal": [text]}
