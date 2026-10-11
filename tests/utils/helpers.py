import uuid
from datetime import date, timedelta

from tests.utils.price_source_mock import PriceSourceMock
from tests.utils.random_generator import RandomGenerator
from tests.utils.request_generator import RequestGenerator


TRANSFER_FEE = 200

CONSERVATIVE, MODERATE, AGGRESSIVE = 1, 2, 4

SELIC = "Tesouro Selic 2031"
PREFIXED = "Tesouro Prefixado 2029"
IPCA = "Tesouro IPCA+ 2035"
CDB = "CDB Triple P Bank Liquidez"
LCI = "LCI Triple P Bank 12 meses"
FUND = "FGV Quant Capital FIM"


def create_customer() -> str:
    payload = {"name": "Ana Silva", "document_number": RandomGenerator.generate_cpf(), "birth_date": "1990-05-17"}
    _, body = RequestGenerator.post_customer(payload)
    return body["customer_key"]


def open_account() -> tuple:
    customer_key = create_customer()
    _, account = RequestGenerator.post_account(customer_key)
    return customer_key, account["account_key"]


def send(customer_key: str, account_key: str, payload: dict):
    return RequestGenerator.post_transaction(customer_key, account_key, payload, str(uuid.uuid4()))


def deposit(customer_key: str, account_key: str, amount: int):
    return send(customer_key, account_key, {"type": "DEPOSIT", "amount": amount})


def balance_of(customer_key: str, account_key: str) -> int:
    _, account = RequestGenerator.get_account(customer_key, account_key)
    return account["balance"]


def answer_profile(customer_key: str, option: int) -> dict:
    answers = [{"question_code": f"Q{number}", "option_code": option} for number in range(1, 8)]
    _, assessment = RequestGenerator.post_suitability(customer_key, {"answers": answers})
    return assessment


def investor(option: int = MODERATE, balance: int = 1_000_000) -> tuple:
    customer_key, account_key = open_account()
    answer_profile(customer_key, option)
    deposit(customer_key, account_key, balance)
    return customer_key, account_key


def product_key(name: str) -> str:
    _, body = RequestGenerator.get_products()
    return next(product["product_key"] for product in body["items"] if product["name"] == name)


def product(name: str) -> dict:
    _, body = RequestGenerator.get_product(product_key(name))
    return body


def apply(customer_key: str, account_key: str, name: str, amount: int, idempotency_key: str = None):
    payload = {"product_key": product_key(name), "side": "APPLY", "amount": amount}
    return RequestGenerator.post_investment_order(customer_key, account_key, payload, idempotency_key or str(uuid.uuid4()))


def business_date() -> date:
    _, body = RequestGenerator.get_business_date()
    return date.fromisoformat(body["business_date"])


def next_business_day(day: date) -> date:
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def close_day(**teach) -> tuple:
    today = business_date()
    PriceSourceMock.teach_day(next_business_day(today), **teach)
    return RequestGenerator.post_day_close({"close_date": today.isoformat()})
