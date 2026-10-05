import os

import requests


class BaseExpectation:
    """Monta uma "expectativa" do MockServer: quando chegar esta requisição, responda isto."""

    @staticmethod
    def generate_expectation(
        method: str,
        endpoint: str,
        response_json,
        status_code: int,
        query_params: dict = None,
        number_of_calls: int = None,
        priority: int = None,
    ) -> dict:
        expectation = BaseExpectation.general_configs(method, endpoint, query_params, number_of_calls, priority)
        expectation["httpResponse"] = {
            "headers": {"Content-Type": ["application/json", "charset=utf-8"]},
            "body": {"type": "JSON", "json": response_json},
            "statusCode": status_code,
        }
        return expectation

    @staticmethod
    def generate_error(
        method: str,
        endpoint: str,
        error_json: dict,
        query_params: dict = None,
        number_of_calls: int = None,
        priority: int = None,
    ) -> dict:
        """Sem resposta nenhuma: por exemplo {"dropConnection": True} derruba a conexão."""
        expectation = BaseExpectation.general_configs(method, endpoint, query_params, number_of_calls, priority)
        expectation["httpError"] = error_json
        return expectation

    @staticmethod
    def general_configs(method, endpoint, query_params, number_of_calls, priority) -> dict:
        expectation = {"httpRequest": {"method": method.upper(), "path": endpoint}}

        if query_params is not None:
            expectation["httpRequest"]["queryStringParameters"] = query_params
        if number_of_calls is not None:
            expectation["times"] = {"remainingTimes": number_of_calls, "unlimited": False}
        if priority is not None:
            expectation["priority"] = priority

        return expectation


class Mock:
    """Fala com o MockServer pela porta que o compose abriu na sua máquina.

    De propósito, não existe `clear()` do mock inteiro: apagaria também o
    cenário da demonstração que o mock-init ensinou. Os testes ensinam as
    próprias respostas com prioridade maior, e elas ganham; uma resposta
    ensinada com o mesmo `id` substitui a anterior em vez de empilhar.
    """

    def __init__(self) -> None:
        host = os.environ.get("MOCK_HOST", os.environ.get("SERVER_LOCALHOST", "localhost"))
        port = os.environ.get("MOCK_PORT", "1080")
        self.base_url = f"http://{host}:{port}"
        self.url = f"{self.base_url}/mockserver"

    def add_expectations(self, expectations) -> None:
        response = requests.put(f"{self.url}/expectation", json=expectations)
        if response.status_code not in (200, 201):
            raise Exception(f"O mock em {self.url} recusou a expectativa: {response.text}")

    def get(self, endpoint: str, query_params: dict = None) -> requests.Response:
        """Chama o mock como a API vai chamar: serve para conferir o que ele responde."""
        return requests.get(f"{self.base_url}{endpoint}", params=query_params)
