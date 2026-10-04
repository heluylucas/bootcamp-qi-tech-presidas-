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
    def post_product_price(product_key: str, payload: dict):
        endpoint = f"/product/{product_key}/price"
        response = ClientRequisition.send("POST", endpoint, payload=payload, headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def get_account_status_events(customer_key: str, account_key: str):
        endpoint = f"/customer/{customer_key}/account/{account_key}/status_events"
        response = ClientRequisition.send("GET", endpoint, headers=HEADERS)
        return response.response_status, response.response_json
