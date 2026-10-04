from datetime import date

from tests.utils import RequestGenerator
from tests.utils.requisition import ClientRequisition


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
        assert response.response_json["code"] == "BNK000002"
