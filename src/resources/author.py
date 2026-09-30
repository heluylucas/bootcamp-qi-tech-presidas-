from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import AuthorController
from utils.schema_handler import SchemaHandler

DEFAULT_LIMIT = 10
DEFAULT_PAGE = 0


class AuthorResource:
    """A porta de entrada HTTP do autor.

    ────────────────────────────────────────────────────────────────
    O QUE UM RESOURCE FAZ — E O QUE ELE NÃO FAZ
    ────────────────────────────────────────────────────────────────
    Ele faz três coisas, nesta ordem, e nada além disso:

      1. confere o corpo da requisição (o decorator do schema);
      2. chama o controller;
      3. devolve o que o controller respondeu.

    Repare no que NÃO está aqui: nenhuma regra de negócio, nenhum `if`
    sobre o estado de um livro, nenhuma linha de SQL. Um método daqui
    cabe em três linhas, e quando não couber é sinal de que uma regra
    vazou da camada de baixo pra cá. Os três resources do projeto
    (autor, estante, livro) seguem este desenho, e é por isso que só
    este arquivo conta a história.

    ────────────────────────────────────────────────────────────────
    POR QUE OS MÉTODOS SE CHAMAM `on_post`, `on_get_by_key`...
    ────────────────────────────────────────────────────────────────
    Há frameworks web que DESCOBREM o método pelo nome — chegou um POST,
    o framework procura sozinho um `on_post`. O FastAPI não faz isso;
    quem liga o endereço ao método é o `src/app.py`, uma linha por rota,
    à vista. Aqui o nome não tem efeito nenhum sozinho: é uma convenção
    de leitura, e ela é a mesma nos três arquivos.

    ────────────────────────────────────────────────────────────────
    UMA REGRA QUE O CÓDIGO NÃO CONSEGUE COBRAR SOZINHO
    ────────────────────────────────────────────────────────────────
    O `src/app.py` cria UM resource e ele vive enquanto a API estiver no
    ar — não nasce um por requisição. Repare que não existe `__init__`
    aqui, e que nenhum método escreve `self.alguma_coisa`: isso é de
    propósito.

    No dia em que um método guardar algo no `self`, esse algo passa a
    ser compartilhado por TODAS as requisições ao mesmo tempo — e o
    sintoma é uma resposta levando o dado de outra pessoa, sob carga,
    sem erro nenhum no log. O que é de uma requisição fica no contexto
    dela (veja o `get_context` em src/database.py); o que fica aqui é de
    todo mundo.

    ────────────────────────────────────────────────────────────────
    O STATUS DA RESPOSTA É DECIDIDO AQUI
    ────────────────────────────────────────────────────────────────
    201 pra criação, 200 pro resto. Os dois saem destes métodos, e é por
    isso que eles devolvem um `JSONResponse` em vez de um dicionário
    solto: o dicionário sozinho não sabe dizer com que status ele quer
    sair.

    ────────────────────────────────────────────────────────────────
    POR QUE O `jsonable_encoder`
    ────────────────────────────────────────────────────────────────
    Quando a rota devolve um dicionário, o FastAPI passa esse dicionário
    por um tradutor antes de virar JSON — é ele que sabe transformar uma
    data, um Decimal ou um UUID em texto. Devolvendo o `JSONResponse` na
    mão, esse passo não acontece sozinho: sem a chamada, o dia em que
    alguém acrescentar uma data no DTO a resposta estoura em runtime, e
    só naquele endpoint.
    """

    @SchemaHandler.validate("post_author.json")
    def on_post(self, payload: dict) -> JSONResponse:
        controller = AuthorController()
        author = controller.create(payload)

        return JSONResponse(
            content=jsonable_encoder(author),
            status_code=http_status.HTTP_201_CREATED,
        )

    def on_get_by_key(self, author_key: str) -> JSONResponse:
        controller = AuthorController()
        author = controller.get_by_key(author_key)

        return JSONResponse(
            content=jsonable_encoder(author),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate_query_params("get_authors.json")
    def on_get_list(self, request: Request) -> JSONResponse:
        controller = AuthorController()

        query_params = request.query_params

        # O schema já garantiu que só chega dígito, e por isso os `int()`
        # não têm try.
        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        page = int(query_params.get("page", DEFAULT_PAGE))

        offset = page * limit
        authors_page = controller.get_list(limit, offset)

        # A paginação é assunto do endereço (?limit=&page=), não do
        # autor: por isso quem monta o envelope da página é o resource, e
        # não o DTO. Empurrá-lo pro controller obrigaria a regra de
        # negócio a saber o que é uma página.
        page_envelope = {
            "data": authors_page["authors_list_dto"],
            "limit": limit,
            "page": page,
            "is_last_page": authors_page["is_last_page"],
        }

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
            status_code=http_status.HTTP_200_OK,
        )
