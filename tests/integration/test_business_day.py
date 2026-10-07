from datetime import date

from tests.utils import INTERNAL_TOKEN, RequestGenerator
from tests.utils.requisition import ClientRequisition


# Só o INTERNAL-TOKEN, sem o OPERATOR-TOKEN: é o que o cliente teria (RN-GER-14).
WITHOUT_OPERATOR_TOKEN = {"INTERNAL-TOKEN": INTERNAL_TOKEN}


class TestBusinessDate:
    def test_get_business_date(self):
        status, body = RequestGenerator.get_business_date()

        assert status == 200
        assert list(body) == ["business_date"]
        # Nunca conferir uma data fixa: ela só anda para frente (RN-GER-13).
        # Basta ser uma data de verdade no formato AAAA-MM-DD.
        date.fromisoformat(body["business_date"])

    def test_business_date_without_token(self):
        response = ClientRequisition.send("GET", "/internal/business_date")

        assert response.response_status == 403
        assert response.response_json["code"] == "PPP000002"

    def test_business_date_without_operator_token(self):
        response = ClientRequisition.send("GET", "/internal/business_date", headers=WITHOUT_OPERATOR_TOKEN)

        assert response.response_status == 403
        assert response.response_json["code"] == "PPP000007"

    def test_day_close_without_operator_token(self):
        # Data antiga de propósito: se o pedido passasse do porteiro, daria 409 e nada mudaria.
        _, before = RequestGenerator.get_business_date()

        response = ClientRequisition.send(
            "POST", "/internal/day_close", payload={"close_date": "2000-01-01"}, headers=WITHOUT_OPERATOR_TOKEN
        )

        assert response.response_status == 403
        assert response.response_json["code"] == "PPP000007"
        _, after = RequestGenerator.get_business_date()
        assert after == before
