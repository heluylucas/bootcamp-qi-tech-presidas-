ENDPOINTS_WITH_PROCESS_ID = {"/"}


def internal_ids(data, path: str = "resposta") -> list:
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
