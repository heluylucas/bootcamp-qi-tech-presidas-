from connectors.rest_connector import BaseConnectorResponse, RestConnector
from constants import CATALOG_API_INTERNAL_TOKEN, CATALOG_API_URL


class CatalogConnector(RestConnector):
    """Fala com o catálogo de ISBN — o serviço de fora desta biblioteca.

    ────────────────────────────────────────────────────────────────
    POR QUE PERGUNTAR A UM CATÁLOGO, EM VEZ DE PEDIR TUDO AO CLIENTE
    ────────────────────────────────────────────────────────────────
    Quem cadastra um livro manda só o ISBN (e o autor). Título, ano e
    número de páginas vêm do catálogo, e o motivo é quem é a FONTE de
    cada dado:

      • o ISBN identifica uma edição no mundo inteiro. Título, ano e
        páginas daquela edição já estão escritos em algum lugar, e
        digitá-los de novo é abrir espaço pra erro de digitação — dois
        cadastros do mesmo livro com títulos ligeiramente diferentes;
      • um ISBN que o catálogo não conhece é um sinal de que o número
        está errado. Pedir tudo ao cliente aceitaria o número torto em
        silêncio;
      • o cliente fica mais simples: ele sabe o ISBN, que está impresso
        no livro, e não precisa saber o resto.

    O preço é depender de outro serviço estar de pé. Quando ele não
    responde, a API recusa com 502 em vez de cadastrar pela metade —
    a decisão está no BookController.create.

    ────────────────────────────────────────────────────────────────
    O QUE MORA AQUI, E O QUE NÃO MORA
    ────────────────────────────────────────────────────────────────
    Nenhum `requests`, nenhuma URL escrita no código, nenhum timeout
    repetido: isso mora no RestConnector, uma vez só. O que mora aqui é
    o que é específico DESTE serviço — qual endpoint existe e o que ele
    devolve.

    O método devolve a resposta como veio (status e corpo). Quem decide
    o que fazer com um 404 ou um 500 é a regra de negócio, no
    controller. Siga o caminho inteiro pra ver a fronteira de ponta a
    ponta:

        grep -rn -e get_by_isbn -e CatalogMock src/ tests/
    """

    def __init__(self) -> None:
        super().__init__(
            class_name=__name__,
            base_url=CATALOG_API_URL,
            # 5 segundos de prazo: se o catálogo parar de responder, a
            # chamada desiste em vez de deixar o pedido pendurado.
            timeout=5,
            internal_token=CATALOG_API_INTERNAL_TOKEN,
        )

    def get_by_isbn(self, isbn: str) -> BaseConnectorResponse:
        """Busca uma edição pelo ISBN.

        O ISBN viaja NO ENDEREÇO, não no corpo: ele diz QUAL edição, e
        isso é parte do endereço dela. Quando o catálogo conhece o ISBN,
        responde 200 com este corpo:

            {"title": "...", "authors": ["..."], "year": 1899, "pages": 256}

        Um 404 aqui é resposta válida ("não conheço esse ISBN"), não
        erro — quem decide o que fazer com ele é o controller.
        """
        return self.send(endpoint=f"/isbn/{isbn}", method="GET")
