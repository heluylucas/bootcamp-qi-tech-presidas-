from os import environ

from tests.utils.requisition import ClientRequisition


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")

HEADERS = {"INTERNAL-TOKEN": INTERNAL_TOKEN}


class RequestGenerator:
    """Uma chamada por rota da API, cada uma devolvendo (status, json)."""

    @staticmethod
    def post_customer(payload: dict):
        response = ClientRequisition.send("POST", "/customer", payload=payload, headers=HEADERS)
        return response.response_status, response.response_json

    @staticmethod
    def get_customer(customer_key: str):
        response = ClientRequisition.send("GET", f"/customer/{customer_key}", headers=HEADERS)
        return response.response_status, response.response_json
