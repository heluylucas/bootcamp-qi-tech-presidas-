from fastapi import FastAPI

from constants import check_variables
from errors import register_error_handlers
from errors.base_error import error_verification
from middlewares import (
    register_internal_token_middleware,
    register_request_context_middleware,
    register_request_logger_middleware,
    register_session_manager_middleware,
)
from resources import (
    AccountResource,
    BusinessDayResource,
    CustomerResource,
    HealthCheckResource,
    InvestmentOrderResource,
    PortfolioResource,
    ProductResource,
    RevenueResource,
    SuitabilityResource,
    TransactionResource,
)
from utils.logger import setup_logging


def create_app() -> FastAPI:
    application = FastAPI(
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    register_session_manager_middleware(application)
    register_internal_token_middleware(application)
    register_request_logger_middleware(application)
    register_request_context_middleware(application)

    health_check_resource = HealthCheckResource()

    application.add_api_route("/", health_check_resource.on_get_home, methods=["GET"])
    application.add_api_route(
        "/health_check",
        health_check_resource.on_get_health_check,
        methods=["GET"]
    )

    business_day_resource = BusinessDayResource()

    application.add_api_route("/internal/business_date", business_day_resource.on_get, methods=["GET"])
    application.add_api_route("/internal/day_close", business_day_resource.on_post_close, methods=["POST"])

    revenue_resource = RevenueResource()

    application.add_api_route("/internal/revenue", revenue_resource.on_get, methods=["GET"])

    customer_resource = CustomerResource()

    application.add_api_route("/customer", customer_resource.on_post, methods=["POST"])
    application.add_api_route("/customer/{customer_key}", customer_resource.on_get, methods=["GET"])

    account_resource = AccountResource()
    account_path = "/customer/{customer_key}/account/{account_key}"

    application.add_api_route("/customer/{customer_key}/account", account_resource.on_post, methods=["POST"])
    application.add_api_route(account_path, account_resource.on_get, methods=["GET"])
    application.add_api_route(account_path, account_resource.on_patch, methods=["PATCH"])
    application.add_api_route(
        f"{account_path}/status_events",
        account_resource.on_get_status_events,
        methods=["GET"]
    )
    application.add_api_route(
        "/internal/account/{account_key}/status",
        account_resource.on_patch_internal,
        methods=["PATCH"]
    )

    suitability_resource = SuitabilityResource()
    suitability_path = "/customer/{customer_key}/suitability"

    application.add_api_route("/suitability_questions", suitability_resource.on_get_questions, methods=["GET"])
    application.add_api_route(suitability_path, suitability_resource.on_post, methods=["POST"])
    application.add_api_route(suitability_path, suitability_resource.on_get, methods=["GET"])
    application.add_api_route(
        "/customer/{customer_key}/suitabilities",
        suitability_resource.on_get_history,
        methods=["GET"]
    )

    product_resource = ProductResource()
    product_path = "/product/{product_key}"

    application.add_api_route("/products", product_resource.on_get_list, methods=["GET"])
    application.add_api_route(product_path, product_resource.on_get, methods=["GET"])
    application.add_api_route(f"{product_path}/prices", product_resource.on_get_prices, methods=["GET"])

    transaction_resource = TransactionResource()

    application.add_api_route(f"{account_path}/transaction", transaction_resource.on_post, methods=["POST"])
    application.add_api_route(f"{account_path}/transactions", transaction_resource.on_get_list, methods=["GET"])
    application.add_api_route(
        f"{account_path}/transaction/{{transaction_key}}",
        transaction_resource.on_get,
        methods=["GET"]
    )

    portfolio_resource = PortfolioResource()

    application.add_api_route(
        "/customer/{customer_key}/portfolio_suggestion",
        portfolio_resource.on_get_suggestion,
        methods=["GET"]
    )

    investment_order_resource = InvestmentOrderResource()

    investment_order_path = f"{account_path}/investment_order"

    application.add_api_route(investment_order_path, investment_order_resource.on_post, methods=["POST"])
    application.add_api_route(f"{investment_order_path}/{{order_key}}", investment_order_resource.on_get, methods=["GET"])
    application.add_api_route(
        f"{account_path}/investment_orders",
        investment_order_resource.on_get_list,
        methods=["GET"]
    )
    application.add_api_route(
        f"{account_path}/positions",
        investment_order_resource.on_get_positions,
        methods=["GET"]
    )

    register_error_handlers(application)

    return application


def main() -> FastAPI:
    check_variables()
    error_verification()
    setup_logging()

    return create_app()


app = main()
