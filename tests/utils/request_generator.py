from os import environ

from tests.utils.requisition import ClientRequisition


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")

HEADERS = {"INTERNAL-TOKEN": INTERNAL_TOKEN}


class RequestGenerator:
    """Uma chamada por rota da API, cada uma devolvendo (status, json)."""

    @staticmethod
    def get_business_date():
        response = ClientRequisition.send("GET", "/internal/business_date", headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def post_day_close(payload: dict):
        response = ClientRequisition.send("POST", "/internal/day_close", payload=payload, headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def post_customer(payload: dict):
        response = ClientRequisition.send("POST", "/customer", payload=payload, headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def get_customer(customer_key: str):
        response = ClientRequisition.send("GET", f"/customer/{customer_key}", headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def post_account(customer_key: str):
        response = ClientRequisition.send("POST", f"/customer/{customer_key}/account", headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def get_account(customer_key: str, account_key: str):
        endpoint = f"/customer/{customer_key}/account/{account_key}"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def patch_account(customer_key: str, account_key: str, payload: dict):
        endpoint = f"/customer/{customer_key}/account/{account_key}"
        response = ClientRequisition.send("PATCH", endpoint, payload=payload, headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def get_products(query_params: dict = None):
        response = ClientRequisition.send("GET", "/products", headers=HEADERS, query_params=query_params)
        return response.response_status, response.response_json

    @staticmethod
    def get_product(product_key: str):
        response = ClientRequisition.send("GET", f"/product/{product_key}", headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def get_product_prices(product_key: str, query_params: dict = None):
        endpoint = f"/product/{product_key}/prices"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS, query_params=query_params)
        return response.response_status, response.response_json

    @staticmethod
    def get_account_status_events(customer_key: str, account_key: str):
        endpoint = f"/customer/{customer_key}/account/{account_key}/status_events"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def get_suitability_questions():
        response = ClientRequisition.send("GET", "/suitability_questions", headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def post_suitability(customer_key: str, payload: dict):
        endpoint = f"/customer/{customer_key}/suitability"
        response = ClientRequisition.send("POST", endpoint, payload=payload, headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def get_suitability(customer_key: str):
        endpoint = f"/customer/{customer_key}/suitability"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def get_suitabilities(customer_key: str):
        endpoint = f"/customer/{customer_key}/suitabilities"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def post_transaction(customer_key: str, account_key: str, payload: dict, idempotency_key):
        """idempotency_key=None não manda o cabeçalho: é assim que se testa a falta dele."""
        endpoint = f"/customer/{customer_key}/account/{account_key}/transaction"
        headers = dict(HEADERS)
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        response = ClientRequisition.send("POST", endpoint, payload=payload, headers=headers)
        return response.response_status, response.response_json

    @staticmethod
    def get_transactions(customer_key: str, account_key: str, query_params: dict = None):
        endpoint = f"/customer/{customer_key}/account/{account_key}/transactions"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS, query_params=query_params)
        return response.response_status, response.response_json

    @staticmethod
    def get_transaction(customer_key: str, account_key: str, transaction_key: str):
        endpoint = f"/customer/{customer_key}/account/{account_key}/transaction/{transaction_key}"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS)
        return response.response_status, response.response_json
    
    @staticmethod
    def post_investment_order(customer_key: str, payload: dict, idempotency_key):
        """idempotency_key=None não manda o cabeçalho: é assim que se testa a falta dele."""
        endpoint = f"/customer/{customer_key}/investment_order"
        headers = dict(HEADERS)
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        response = ClientRequisition.send("POST", endpoint, payload=payload, headers=headers)
        return response.response_status, response.response_json

    @staticmethod
    def get_investment_order(customer_key: str, order_key: str):
        endpoint = f"/customer/{customer_key}/investment_order/{order_key}"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def get_investment_orders(customer_key: str, query_params: dict = None):
        endpoint = f"/customer/{customer_key}/investment_orders"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS, query_params=query_params)
        return response.response_status, response.response_json

    @staticmethod
    def get_positions(customer_key: str, query_params: dict = None):
        endpoint = f"/customer/{customer_key}/positions"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS, query_params=query_params)
        return response.response_status, response.response_json

    @staticmethod
    def get_portfolio_suggestion(customer_key: str, query_params: dict = None):
        endpoint = f"/customer/{customer_key}/portfolio_suggestion"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS, query_params=query_params)
        return response.response_status, response.response_json
