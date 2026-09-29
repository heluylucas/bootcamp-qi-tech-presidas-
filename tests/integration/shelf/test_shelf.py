from tests.utils import PayloadGenerator, RequestGenerator


class TestShelf:
    def test_creates_shelf(self):
        payload = PayloadGenerator.create_shelf_payload(capacity=3)

        status, response = RequestGenerator.POST_shelf(payload)
        assert status == 201

        _key = response["shelf_key"]

        status, response = RequestGenerator.GET_shelf(_key)
        assert status == 200
        assert response == {
            "shelf_key": _key,
            "code": payload["code"],
            "location": "Reading room, aisle 1",
            "capacity": 3,
        }

    def test_not_found(self):
        status, response = RequestGenerator.GET_shelf("00000000-0000-0000-0000-000000000000")
        assert status == 404
        assert response["code"] == "QIT001013"

    def test_schema_refuses_capacity_below_one(self):
        """Estante de capacidade zero não guarda livro nenhum, e por isso não existe.

        Quem recusa é o "minimum": 1 do src/schemas/post_shelf.json,
        antes de o controller rodar. O CHECK do banco diz a mesma coisa,
        como última linha de defesa.
        """
        for capacity in [0, -1]:
            payload = PayloadGenerator.create_shelf_payload(capacity=capacity)

            status, response = RequestGenerator.POST_shelf(payload)
            assert status == 400, f"capacity {capacity} was accepted"
            assert response["code"] == "QIT000001"

    def test_refuses_duplicated_code(self):
        first_payload = PayloadGenerator.create_shelf_payload()
        status, _response = RequestGenerator.POST_shelf(first_payload)
        assert status == 201

        second_payload = PayloadGenerator.create_shelf_payload(code=first_payload["code"])

        status, response = RequestGenerator.POST_shelf(second_payload)
        assert status == 409
        assert response["code"] == "QIT001014"
