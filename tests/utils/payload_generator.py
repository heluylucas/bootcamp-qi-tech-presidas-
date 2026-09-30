from uuid import uuid4

from tests.utils.random_generator import RandomGenerator


class PayloadGenerator:
    @staticmethod
    def create_author_payload(name: str = None, nationality: str = None, document_number: str = None) -> dict:
        """Um autor válido. Sem `document_number`, sai um CPF válido aleatório — ele é único no banco."""
        if name is None:
            name = "Machado de Assis"

        if nationality is None:
            nationality = "Brazilian"

        if document_number is None:
            document_number = RandomGenerator.generate_cpf()

        payload = {
            "name": name,
            "nationality": nationality,
            "document_number": document_number,
        }
        return payload

    @staticmethod
    def create_shelf_payload(code: str = None, location: str = None, capacity: int = None) -> dict:
        """Uma estante válida, com qualquer campo trocado a pedido.

        Sem argumento, o `code` sai aleatório: ele é único no banco, e
        duas estantes seguidas com o mesmo código bateriam na regra de
        duplicidade.
        """
        if code is None:
            code = f"S-{uuid4().hex[:8]}"

        if location is None:
            location = "Reading room, aisle 1"

        if capacity is None:
            capacity = 10

        payload = {
            "code": code,
            "location": location,
            "capacity": capacity,
        }
        return payload

    @staticmethod
    def create_member_payload(name: str = None, email: str = None, document_number: str = None) -> dict:
        """Um leitor válido. Sem `email` ou `document_number`, sai um aleatório — os dois são únicos no banco."""
        if name is None:
            name = "Capitu Pádua"

        if email is None:
            email = f"reader-{uuid4().hex[:12]}@example.com"

        if document_number is None:
            document_number = RandomGenerator.generate_cpf()

        payload = {
            "name": name,
            "email": email,
            "document_number": document_number,
        }
        return payload

    @staticmethod
    def create_book_payload(author_key: str, isbn: str = None, shelf_key: str = None) -> dict:
        """O corpo do POST /book: ISBN e autor, e a estante se vier.

        Sem `isbn`, sai um aleatório — o ISBN é único no banco. O
        `shelf_key` só entra no corpo quando foi pedido: é opcional no
        schema, e mandar `null` seria outra coisa (o schema recusa).
        """
        if isbn is None:
            isbn = RandomGenerator.generate_isbn()

        payload = {
            "isbn": isbn,
            "author_key": author_key,
        }

        if shelf_key is not None:
            payload["shelf_key"] = shelf_key

        return payload
