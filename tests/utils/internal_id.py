"""A R5 conferida em toda resposta: o id inteiro é interno e nunca sai na API.

Toda chamada dos testes passa pelo ClientRequisition.send, que chama a conferência
abaixo. Assim, cada teste confere a R5 na resposta que recebeu, inclusive em rotas
novas, sem ninguém precisar lembrar de escrever o assert.
"""

# Rotas cujo "id" não é do banco. GET / (repositório-base) mostra o número do processo da API.
ENDPOINTS_WITH_PROCESS_ID = {"/"}


def internal_ids(data, path: str = "resposta") -> list:
    """Chaves 'id' ou '..._id' em todo o JSON, inclusive dentro de listas e objetos.

    Olha só o nome da chave, nunca o valor. 'valid_until', 'liquidity' e
    'idempotency_key' passam: nenhuma é 'id' nem termina em '_id'.
    """
    found = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "id" or key.endswith("_id"):
                found.append(f"{path}.{key}")
            found += internal_ids(value, f"{path}.{key}")
    elif isinstance(data, list):
        for index, item in enumerate(data):
            found += internal_ids(item, f"{path}[{index}]")
    return found


def assert_no_internal_id(data, endpoint: str) -> None:
    if endpoint in ENDPOINTS_WITH_PROCESS_ID:
        return

    leaked = internal_ids(data)
    assert not leaked, f"R5: id interno na resposta de {endpoint}: {leaked}"
