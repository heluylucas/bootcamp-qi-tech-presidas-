from fastapi import FastAPI, Request

from constants import BYPASS_ENDPOINTS, INTERNAL_PREFIX, INTERNAL_TOKEN, OPERATOR_TOKEN
from errors.base_error import ForbiddenNotInternal, OperatorOnly
from errors.handlers import qi_exception_to_response


def register_internal_token_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def check_internal_token(request: Request, call_next):
        is_public = request.url.path in BYPASS_ENDPOINTS

        if request.method == "OPTIONS" or is_public:
            return await call_next(request)

        if request.headers.get("INTERNAL-TOKEN") != INTERNAL_TOKEN:
            return qi_exception_to_response(ForbiddenNotInternal())

        is_operator_route = request.url.path.startswith(INTERNAL_PREFIX)
        if is_operator_route and request.headers.get("OPERATOR-TOKEN") != OPERATOR_TOKEN:
            return qi_exception_to_response(OperatorOnly())

        return await call_next(request)
