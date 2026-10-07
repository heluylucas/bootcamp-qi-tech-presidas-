import os


SERVICE_ROOT = os.path.abspath(os.path.dirname(__file__))

# Onde moram os arquivos de schema — os .json que descrevem o formato
# que cada requisicao precisa ter. Quem le essa pasta e o
# src/utils/schema_handler.py.
SCHEMA_PATH = os.path.join(SERVICE_ROOT, "schemas")

APP_ENV = os.environ.get("APP_ENV", "local")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "triple-p-bank-api")

DATABASE_URL = os.environ.get("DATABASE_URL")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN")

# A senha da operação do banco (RN-GER-14). As rotas que começam com
# INTERNAL_PREFIX (fechamento do dia, status de conta pelo banco...) pedem
# este token além do INTERNAL_TOKEN: o cliente tem o segundo, nunca o primeiro.
OPERATOR_TOKEN = os.environ.get("OPERATOR_TOKEN")
INTERNAL_PREFIX = "/internal/"

# Liga a impressao de TODO SQL que o SQLAlchemy emite. Serve pra
# responder "que consulta esse repository virou, afinal?" sem abrir o
# banco do lado. Quem lê isto é o src/utils/logger.py, e o porquê de
# nao ser o `echo=True` do create_engine esta explicado la.
#
# Padrao desligado: em producao isso escreveria uma linha de log por
# comando, incluindo os valores enviados.
DATABASE_ECHO = os.environ.get("DATABASE_ECHO", "false").lower() == "true"

# Rotas públicas: não exigem o header INTERNAL-TOKEN. São as duas que
# precisam responder pra quem ainda não tem token nenhum: a raiz, que
# diz quem é este serviço, e o health check, que o Docker consulta pra
# saber se a API já está de pé.
BYPASS_ENDPOINTS = [
    "/",
    "/health_check",
]

# As fontes de preço que o fechamento do dia consulta (RN-FEC-04). No
# compose, as três apontam para o mock; em produção, para os serviços
# reais. O código dos connectors é o mesmo nos dois casos.
FUND_ADMIN_API_URL = os.environ.get("FUND_ADMIN_API_URL")
TREASURY_API_URL = os.environ.get("TREASURY_API_URL")
CENTRAL_BANK_API_URL = os.environ.get("CENTRAL_BANK_API_URL")

# Segundos que o fechamento espera cada fonte antes de desistir (RN-FEC-06).
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
