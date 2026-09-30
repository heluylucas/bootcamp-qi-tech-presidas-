from uuid import uuid4

from database import Context
from models import Shelf


class ShelfRepository:
    """As consultas da estante. Mesma forma do AuthorRepository, mais uma.

    A consulta a mais é o `get_by_key_for_update`, e ela é a peça que o
    BookController usa pra contar a lotação sem ser atropelado por
    outra requisição. A explicação está na docstring dela.
    """

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, shelf_data: dict) -> Shelf:
        shelf = Shelf()

        shelf.shelf_key = str(uuid4())
        shelf.code = shelf_data["code"]
        shelf.location = shelf_data["location"]
        shelf.capacity = shelf_data["capacity"]

        self.session.add(shelf)
        return shelf

    def get_by_key(self, shelf_key: str) -> Shelf:
        return self.session.query(Shelf).filter(Shelf.shelf_key == shelf_key).first()

    def get_by_code(self, shelf_code: str) -> Shelf:
        return self.session.query(Shelf).filter(Shelf.code == shelf_code).first()

    def get_by_key_for_update(self, shelf_key: str) -> Shelf:
        """A estante, TRAVADA até o fim da transação.

        O `with_for_update()` vira `SELECT ... FOR UPDATE` no banco: a
        linha desta estante fica reservada pra esta transação. Outra
        requisição que peça a MESMA estante do mesmo jeito fica parada
        no Postgres até o `commit` (ou o `rollback`) desta.

        Só quem trava é quem vai pôr livro na estante. Um GET comum não
        espera nada — a trava só segura quem também pede a trava.
        """
        return self.session.query(Shelf).filter(Shelf.shelf_key == shelf_key).with_for_update().first()

    def list_page(self, limit: int, offset: int) -> list:
        query = self.session.query(Shelf).order_by(Shelf.created_at.desc(), Shelf.id.desc())

        return query.limit(limit + 1).offset(offset).all()
