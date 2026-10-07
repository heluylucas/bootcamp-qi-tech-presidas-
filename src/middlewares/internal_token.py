from fastapi import FastAPI, Request

from constants import BYPASS_ENDPOINTS, INTERNAL_PREFIX, INTERNAL_TOKEN, OPERATOR_TOKEN
from errors.base_error import ForbiddenNotInternal, OperatorOnly
from errors.handlers import qi_exception_to_response


def register_internal_token_middleware(application: FastAPI) -> None:
    """Deixa passar só quem manda o header INTERNAL-TOKEN com o valor certo.

    O valor certo vem da variável de ambiente INTERNAL_TOKEN, nunca do
    código. As rotas de BYPASS_ENDPOINTS (raiz e health check) são públicas.

    Repare que aqui a gente DEVOLVE a resposta de erro em vez de levantar
    a exceção: dentro de um middleware, ninguém está escutando pra traduzir
    o erro — quem traduz são os exception handlers, que rodam mais pra
    dentro. Levantar aqui viraria um 500.
    """

    @application.middleware("http")
    async def check_internal_token(request: Request, call_next):
        is_public = request.url.path in BYPASS_ENDPOINTS

        if request.method == "OPTIONS" or is_public:
            return await call_next(request)

        if request.headers.get("INTERNAL-TOKEN") != INTERNAL_TOKEN:
            return qi_exception_to_response(ForbiddenNotInternal())

        # As rotas da operação do banco pedem também o token de operador
        # (RN-GER-14). Conferido aqui, na porta, nenhuma rota precisa lembrar.
        is_operator_route = request.url.path.startswith(INTERNAL_PREFIX)
        if is_operator_route and request.headers.get("OPERATOR-TOKEN") != OPERATOR_TOKEN:
            return qi_exception_to_response(OperatorOnly())

        return await call_next(request)
