import uuid

import pytest

from tests.utils import RandomGenerator, RequestGenerator


# Todas as respostas iguais: 1 dá Conservador, 2 dá Moderado, 4 dá Arrojado.
CONSERVATIVE, MODERATE, AGGRESSIVE = 1, 2, 4

SELIC = "Tesouro Selic 2031"
CDB = "CDB Triple P Bank Liquidez"
LCI = "LCI Triple P Bank 12 meses"
PREFIXED = "Tesouro Prefixado 2029"
IPCA = "Tesouro IPCA+ 2035"
FUND = "FGV Quant Capital FIM"


def create_customer() -> str:
    payload = {"name": "Ana Silva", "document_number": RandomGenerator.generate_cpf(), "birth_date": "1990-05-17"}
    _, body = RequestGenerator.post_customer(payload)
    return body["customer_key"]


def customer_with_profile(option: int) -> tuple:
    """Cliente que respondeu o questionário inteiro com a mesma opção. Devolve a key e a avaliação."""
    customer_key = create_customer()
    answers = [{"question_code": f"Q{number}", "option_code": option} for number in range(1, 8)]
    _, assessment = RequestGenerator.post_suitability(customer_key, {"answers": answers})
    return customer_key, assessment


def suggest(customer_key: str, amount: int):
    # Na query string tudo é texto: o 1000000 viaja como "1000000".
    return RequestGenerator.get_portfolio_suggestion(customer_key, {"amount": str(amount)})


def amounts_by_name(body: dict) -> dict:
    return {item["name"]: item["amount"] for item in body["items"]}


class TestPortfolioSuggestion:
    @pytest.mark.parametrize(
        "option, profile, amount",
        [(CONSERVATIVE, "CONSERVATIVE", 100000), (MODERATE, "MODERATE", 123457), (AGGRESSIVE, "AGGRESSIVE", 999999)],
    )
    def test_weights_and_amounts_add_up(self, option, profile, amount):
        """A carteira-modelo soma 10.000 pb, e os valores somam exatamente o pedido (RN-CAR-03)."""
        customer_key, _ = customer_with_profile(option)

        status, body = suggest(customer_key, amount)

        assert status == 200
        assert body["profile"] == profile
        assert body["amount"] == amount
        assert sum(item["weight_bps"] for item in body["items"]) == 10000
        assert sum(item["amount"] for item in body["items"]) == amount

    def test_rfc_example_1(self):
        """Moderado, R$ 10.000,00: a divisão sai redonda."""
        customer_key, _ = customer_with_profile(MODERATE)

        _, body = suggest(customer_key, 1000000)

        assert amounts_by_name(body) == {
            SELIC: 250000,
            CDB: 200000,
            PREFIXED: 200000,
            IPCA: 200000,
            FUND: 150000,
        }

    def test_rfc_example_2_leftover_cent(self):
        """Moderado, R$ 1.000,01: sobra 1 centavo do arredondamento, que vai para o maior peso (Selic)."""
        customer_key, _ = customer_with_profile(MODERATE)

        _, body = suggest(customer_key, 100001)

        assert amounts_by_name(body) == {
            SELIC: 25001,
            CDB: 20000,
            PREFIXED: 20000,
            IPCA: 20000,
            FUND: 15000,
        }

    def test_conservative_portfolio(self):
        customer_key, _ = customer_with_profile(CONSERVATIVE)

        _, body = suggest(customer_key, 1000000)

        assert amounts_by_name(body) == {SELIC: 500000, CDB: 300000, LCI: 200000}

    def test_aggressive_leftover_goes_to_largest_weight(self):
        # 100.003 centavos: os pisos somam 100.001 e os 2 que sobram vão para o fundo (40%, o maior peso).
        customer_key, _ = customer_with_profile(AGGRESSIVE)

        _, body = suggest(customer_key, 100003)

        assert amounts_by_name(body) == {SELIC: 10000, PREFIXED: 20000, IPCA: 30000, FUND: 40003}

    def test_items_from_largest_weight(self):
        customer_key, _ = customer_with_profile(MODERATE)

        _, body = suggest(customer_key, 1000000)

        weights = [item["weight_bps"] for item in body["items"]]
        assert weights == sorted(weights, reverse=True)

    @pytest.mark.parametrize("option", [CONSERVATIVE, MODERATE, AGGRESSIVE])
    def test_every_product_fits_the_profile(self, option):
        """Nenhuma sugestão tem produto com risco acima do que o perfil aceita (CVM 30)."""
        customer_key, assessment = customer_with_profile(option)

        _, body = suggest(customer_key, 1000000)

        for item in body["items"]:
            _, product = RequestGenerator.get_product(item["product_key"])
            assert product["risk_level"] <= assessment["max_risk_level"]

    def test_response_format(self):
        customer_key, _ = customer_with_profile(MODERATE)

        _, body = suggest(customer_key, 1000000)

        assert set(body) == {"profile", "amount", "items"}
        for item in body["items"]:
            assert set(item) == {"product_key", "name", "weight_bps", "amount"}
            assert len(item["product_key"]) == 36

    def test_works_without_account_or_balance(self):
        """RN-CAR-05: é simulação; quem barra falta de saldo é a ordem. Este cliente nem tem conta."""
        customer_key, _ = customer_with_profile(AGGRESSIVE)

        status, _ = suggest(customer_key, 100000000)

        assert status == 200

    def test_suggestion_is_not_recorded(self):
        """RN-CAR-04: pedir de novo dá a mesma resposta; nada foi gravado entre uma e outra."""
        customer_key, _ = customer_with_profile(MODERATE)

        first_status, first = suggest(customer_key, 1000000)
        second_status, second = suggest(customer_key, 1000000)

        # Sem conferir o 200, dois erros iguais também passariam aqui.
        assert first_status == second_status == 200
        assert first == second

    def test_minimum_amount_is_accepted(self):
        customer_key, _ = customer_with_profile(MODERATE)

        status, _ = suggest(customer_key, 100000)

        assert status == 200


class TestPortfolioSuggestionRefusals:
    def test_without_profile(self):
        customer_key = create_customer()

        status, body = suggest(customer_key, 1000000)

        assert status == 409
        assert body["code"] == "PPP004005"

    def test_below_minimum_amount(self):
        """RN-CAR-02: R$ 999,99, um centavo abaixo do mínimo."""
        customer_key, _ = customer_with_profile(MODERATE)

        status, body = suggest(customer_key, 99999)

        assert status == 422
        assert body["code"] == "PPP006001"

    def test_profile_is_checked_before_amount(self):
        """Sem perfil e com valor baixo: a falta de perfil vem primeiro (RN-CAR-01 antes da RN-CAR-02)."""
        customer_key = create_customer()

        status, body = suggest(customer_key, 99999)

        assert status == 409
        assert body["code"] == "PPP004005"

    def test_customer_not_found(self):
        status, body = suggest(str(uuid.uuid4()), 1000000)

        assert status == 404
        assert body["code"] == "PPP001001"

    @pytest.mark.parametrize(
        "query_params",
        [
            None,
            {"amount": "abc"},
            {"amount": "10.5"},
            {"amount": "-100"},
            {"amount": ""},
            {"amount": "1000000", "page": "1"},
        ],
        ids=["missing", "text", "decimal", "negative", "empty", "unknown_param"],
    )
    def test_invalid_amount(self, query_params):
        customer_key, _ = customer_with_profile(MODERATE)

        status, body = RequestGenerator.get_portfolio_suggestion(customer_key, query_params)

        assert status == 400
        assert body["code"] == "PPP000001"
