import os


SERVICE_ROOT = os.path.abspath(os.path.dirname(__file__))

SCHEMA_PATH = os.path.join(SERVICE_ROOT, "schemas")

APP_ENV = os.environ.get("APP_ENV", "local")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "triple-p-bank-api")

DATABASE_URL = os.environ.get("DATABASE_URL")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN")

OPERATOR_TOKEN = os.environ.get("OPERATOR_TOKEN")
INTERNAL_PREFIX = "/internal/"

DATABASE_ECHO = os.environ.get("DATABASE_ECHO", "false").lower() == "true"

BYPASS_ENDPOINTS = [
    "/",
    "/health_check",
]

FUND_ADMIN_API_URL = os.environ.get("FUND_ADMIN_API_URL")
TREASURY_API_URL = os.environ.get("TREASURY_API_URL")
CENTRAL_BANK_API_URL = os.environ.get("CENTRAL_BANK_API_URL")

PRICE_SOURCE_TIMEOUT = 5

REQUIRED_VARIABLES = [
    "DATABASE_URL",
    "INTERNAL_TOKEN",
    "OPERATOR_TOKEN",
    "FUND_ADMIN_API_URL",
    "TREASURY_API_URL",
    "CENTRAL_BANK_API_URL",
]


def check_variables():
    missing = []
    for name in REQUIRED_VARIABLES:
        if not globals().get(name):
            missing.append(name)

    if missing:
        raise EnvironmentError(
            f"Faltam variáveis de ambiente: {', '.join(missing)}. "
            "Rodando com 'docker compose up' elas já vêm preenchidas. "
            "Fora do Docker, copie o .env.example para .env."
        )
