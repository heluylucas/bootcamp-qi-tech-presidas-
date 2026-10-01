from os import environ


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")


class RequestGenerator:
    """Uma chamada por rota da API, cada uma devolvendo (status, json).

    Vazio até a primeira rota do Quant Bank existir.
    """
