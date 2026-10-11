import json
import math
import os
import time
import urllib.request
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, getcontext

getcontext().prec = 40

MOCK_URL = os.environ.get("MOCK_URL", "http://mock:1080")
# Pouco mais de um ano: a LCI de 12 meses vence ~262 dias úteis depois de aplicada.
BUSINESS_DAYS = 300
DAYS_PER_REQUEST = 25
ANCHOR = date(2026, 1, 1)

FUND_CNPJ = "12.345.678/0001-95"
# No caminho vai só com dígitos: a "/" do CNPJ quebraria o endereço.
FUND_CNPJ_DIGITS = "12345678000195"
# Taxa anual de cada título público (RN-PRO-06) e o vencimento que o Tesouro informa.
TREASURY_BONDS = {
    "TESOURO SELIC 2031": (Decimal("1.15"), "2031-03-01"),
    "TESOURO PREFIXADO 2029": (Decimal("1.13"), "2029-01-01"),
    "TESOURO IPCA+ 2035": (Decimal("1.045") * Decimal("1.06"), "2035-05-15"),
}
CDI_SERIES, CDI_RATE = 4389, "14.90"
SELIC_SERIES, SELIC_RATE = 1178, "15.00"


def business_days_since_anchor(day: date) -> int:
    """d: dias úteis (segunda a sexta) depois de 01/01/2026, até o dia, inclusive."""
    return sum(1 for offset in range(1, (day - ANCHOR).days + 1) if (ANCHOR + timedelta(offset)).weekday() < 5)


def to_text(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))


def fund_quote(d: int) -> str:
    # O Postgres converte o seno (double) para numeric com 15 dígitos; aqui igual.
    wave = Decimal(f"{math.sin((d + 15) / 7):.15g}")
    trend = (Decimal("1.10") * Decimal("0.99")) ** (Decimal(d) / 252)
    return to_text(100 * trend * (1 + Decimal("0.03") * wave))


def treasury_price(annual_factor: Decimal, d: int) -> str:
    return to_text(100 * annual_factor ** (Decimal(d) / 252))


def json_response(path: str, query: dict, body) -> dict:
    return {
        "httpRequest": {"method": "GET", "path": path, "queryStringParameters": query},
        "httpResponse": {
            "statusCode": 200,
            "headers": {"Content-Type": ["application/json", "charset=utf-8"]},
            "body": {"type": "JSON", "json": body},
        },
    }


def expectations_for(day: date) -> list:
    d = business_days_since_anchor(day)
    iso, br = day.isoformat(), day.strftime("%d/%m/%Y")
    bcb_query = {"formato": ["json"], "dataInicial": [br], "dataFinal": [br]}

    fund = {
        "CNPJ_FUNDO": FUND_CNPJ,
        "DT_COMPTC": iso,
        "VL_QUOTA": fund_quote(d),
        "VL_PATRIM_LIQ": "150000000.00",
        "NR_COTST": 1200,
    }
    bonds = [
        {"name": name, "maturity_date": maturity, "unit_price": treasury_price(factor, d)}
        for name, (factor, maturity) in TREASURY_BONDS.items()
    ]

    return [
        json_response(f"/fund-admin/funds/{FUND_CNPJ_DIGITS}/quotes", {"date": [iso]}, fund),
        json_response("/treasury/prices", {"date": [iso]}, {"date": iso, "bonds": bonds}),
        json_response(f"/bcb/dados/serie/bcdata.sgs.{CDI_SERIES}/dados", bcb_query,
                      [{"data": br, "valor": CDI_RATE}]),
        json_response(f"/bcb/dados/serie/bcdata.sgs.{SELIC_SERIES}/dados", bcb_query,
                      [{"data": br, "valor": SELIC_RATE}]),
    ]


def next_business_days(start: date, count: int) -> list:
    """Começa no próprio dia (se for útil): a data de movimento nasce com a data de hoje."""
    days, day = [], start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


def put(path: str, payload, attempts: int = 5) -> None:
    # Recém-ligado, o mock às vezes demora a responder os primeiros pedidos:
    # tenta de novo em vez de deixar a demonstração sem preços.
    request = urllib.request.Request(
        f"{MOCK_URL}/mockserver/{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="PUT",
    )
    for attempt in range(1, attempts + 1):
        try:
            urllib.request.urlopen(request, timeout=30)
            return
        except OSError:
            if attempt == attempts:
                raise
            time.sleep(2)


def wait_for_mock() -> None:
    for _ in range(60):
        try:
            put("status", {}, attempts=1)
            return
        except OSError:
            time.sleep(1)
    raise SystemExit(f"O mock em {MOCK_URL} não respondeu em 60 s.")


if __name__ == "__main__":
    wait_for_mock()
    days = next_business_days(date.today(), BUSINESS_DAYS)
    # Em lotes: os 300 dias num pedido só passam do timeout do mock, e um pedido
    # por dia deixa o mock-init ensinando por meio minuto depois de a API subir.
    for start in range(0, len(days), DAYS_PER_REQUEST):
        batch = days[start:start + DAYS_PER_REQUEST]
        try:
            put("expectation", [expectation for day in batch for expectation in expectations_for(day)])
        except OSError as error:
            raise SystemExit(f"mock-init: o mock não aceitou os preços a partir de {batch[0]}: {error!r}")
    print(f"mock-init: {len(days)} dias úteis ensinados, de {days[0]} a {days[-1]}.")
