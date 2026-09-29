from os import environ

from tests.utils.requisition import ClientRequisition, BaseConnectorResponse


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")


class RequestGenerator:
    @staticmethod
    def POST_author(author_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/author",
            payload=author_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_author(author_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET",
            f"/author/{author_key}",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_authors(params: dict = None) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET", "/authors", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}, query_params=params
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_shelf(shelf_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/shelf",
            payload=shelf_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_shelf(shelf_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET",
            f"/shelf/{shelf_key}",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_shelves(params: dict = None) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET", "/shelves", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}, query_params=params
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_member(member_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/member",
            payload=member_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_member(member_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET",
            f"/member/{member_key}",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_members(params: dict = None) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET", "/members", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}, query_params=params
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_book(book_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/book",
            payload=book_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_book(book_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET",
            f"/book/{book_key}",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_books(params: dict = None) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET", "/books", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}, query_params=params
        )
        return response.response_status, response.response_json

    @staticmethod
    def PUT_book_shelf(book_key: str, shelf_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PUT",
            f"/book/{book_key}/shelf",
            payload=shelf_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def PUT_book_borrow(book_key: str, borrow_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PUT",
            f"/book/{book_key}/borrow",
            payload=borrow_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def PUT_book_return(book_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PUT",
            f"/book/{book_key}/return",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json
