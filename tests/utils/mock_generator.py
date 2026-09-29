from tests.utils.mock_utils import BaseExpectation, Mock


class CatalogMock:
    """As respostas do catálogo de ISBN que o CatalogConnector chama.

    O mock server sobe vazio. Cada método aqui ensina a ele UMA resposta:
    "quando chegar esta requisição, devolva isto". O teste chama o
    método antes de chamar a API, e a API encontra o mock já ensinado.

    O ritual de um teste que passa pelo catálogo é sempre o mesmo, nesta
    ordem:

        Mock().clear()                          # esquece o teste anterior
        CatalogMock.GET_isbn(isbn=isbn)         # ensina o que este precisa
        RequestGenerator.POST_book(payload)     # chama a API
        Mock().retrieve_requests("GET", f"/catalog/isbn/{isbn}")

    O último passo é opcional: ele devolve as requisições que o mock
    recebeu, e serve pra conferir que a API chamou quem devia — ou que
    NÃO chamou, quando a regra manda parar antes da fronteira.

    Todo endereço começa com "/catalog": é o prefixo deste serviço
    dentro do mock, o mesmo que termina o CATALOG_API_URL do
    docker-compose.yml.

    Onde o método recebe um ISBN, o padrão "[0-9]+" quer dizer "qualquer
    ISBN". Passe um ISBN de verdade quando o teste precisar que só ele
    seja atendido.
    """

    @staticmethod
    def GET_isbn(isbn: str = "[0-9]+"):
        """GET /isbn/{isbn}: 200 e os dados de uma edição."""
        mock = Mock()

        mock.add_expectations(
            BaseExpectation.generate_expectation(
                "GET",
                f"/catalog/isbn/{isbn}",
                status_code=200,
                response_json={
                    "title": "Dom Casmurro",
                    "authors": ["Machado de Assis"],
                    "year": 1899,
                    "pages": 256,
                },
            )
        )

    @staticmethod
    def GET_isbn_not_found(isbn: str = "0000000000000"):
        """GET /isbn/{isbn}: 404 com code e description no corpo.

        É como um serviço de verdade costuma dizer "não achei". Compare
        com uma requisição que o mock não foi ensinado a atender: ele
        também responde 404, mas SEM corpo. Se o json da resposta chegou
        None, a requisição não bateu com nada que o teste ensinou —
        confira endereço e método antes de desconfiar do connector.
        """
        mock = Mock()

        mock.add_expectations(
            BaseExpectation.generate_expectation(
                "GET",
                f"/catalog/isbn/{isbn}",
                status_code=404,
                response_json={
                    "code": "ISBN_NOT_FOUND",
                    "description": "No edition with this ISBN.",
                },
                priority=1,
            )
        )

    @staticmethod
    def GET_isbn_server_error(isbn: str = "[0-9]+"):
        """GET /isbn/{isbn}: 500 — o catálogo respondeu, e respondeu que quebrou."""
        mock = Mock()

        mock.add_expectations(
            BaseExpectation.generate_expectation(
                "GET",
                f"/catalog/isbn/{isbn}",
                status_code=500,
                response_json={
                    "code": "INTERNAL_ERROR",
                    "description": "Unexpected error in the catalog.",
                },
                priority=1,
            )
        )

    @staticmethod
    def GET_isbn_connection_dropped(isbn: str = "[0-9]+"):
        """GET /isbn/{isbn}: a conexão cai, e não volta resposta nenhuma.

        Não é um status de erro: é a ausência de status. O mock aceita a
        conexão e a derruba sem escrever nada, e do lado da API o
        `requests` levanta — é o mesmo caminho de um serviço fora do ar
        ou de um timeout, só que sem esperar os segundos do timeout.
        """
        mock = Mock()

        mock.add_expectations(
            BaseExpectation.generate_error(
                "GET",
                f"/catalog/isbn/{isbn}",
                error_json={"dropConnection": True},
                priority=1,
            )
        )
