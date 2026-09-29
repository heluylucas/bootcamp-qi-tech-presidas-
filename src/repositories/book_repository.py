from datetime import datetime
from uuid import uuid4

from sqlalchemy import func

from database import Context
from models import Author, Book, BookStatus, BookStatusEvent, Member, Shelf


class BookRepository:
    """As consultas do livro. Só aqui existe query.

    Repare que `create` recebe os OBJETOS do autor e da estante, e não as
    chaves: quem traduziu `author_key` em autor foi o controller, que
    precisava saber se ele existia antes de chegar aqui.
    """

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, isbn: str, catalog_data: dict, author: Author, shelf: Shelf) -> Book:
        book = Book()

        book.book_key = str(uuid4())
        book.isbn = isbn
        book.title = catalog_data["title"]
        book.year = catalog_data["year"]
        book.pages = catalog_data["pages"]
        book.author = author
        book.shelf = shelf
        self.update_status(book, BookStatus.AVAILABLE)

        self.session.add(book)
        return book

    def update_shelf(self, book: Book, shelf: Shelf) -> None:
        book.shelf = shelf

    def update_loan(self, book: Book, new_status_enumerator: str, member: Member) -> None:
        """Grava o status, o evento e o leitor juntos, na transação de quem chamou."""
        self.update_status(book, new_status_enumerator)
        book.member = member

    def update_status(self, book: Book, new_status_enumerator: str) -> None:
        """Muda o status do livro e acrescenta a linha do histórico.

        É o `update_status` do repositório-base, com uma diferença: lá o
        cadastro gravava o status inicial direto na entidade e a trilha
        começava sem ele. Aqui o `create` também passa por este método,
        e por isso o primeiro evento de todo livro é o AVAILABLE do
        cadastro.

        Nada é salvo aqui: o evento entra na sessão junto com o livro, e
        os dois vão pro banco no mesmo `commit` do controller.
        """
        new_status = self.get_status(new_status_enumerator)
        book.status = new_status

        new_status_event = BookStatusEvent()
        new_status_event.status = new_status
        new_status_event.event_datetime = datetime.now()

        book.status_events.append(new_status_event)

    def get_status(self, enumerator: str) -> BookStatus:
        return self.session.query(BookStatus).filter(BookStatus.enumerator == enumerator).one()

    def get_by_key(self, book_key: str) -> Book:
        return self.session.query(Book).filter(Book.book_key == book_key).first()

    def get_by_key_for_update(self, book_key: str) -> Book:
        """O livro, TRAVADO até o fim da transação.

        Mesmo mecanismo do `ShelfRepository.get_by_key_for_update`: o
        `with_for_update()` vira `SELECT ... FOR UPDATE`, e outra
        requisição que peça a MESMA linha do mesmo jeito espera o
        `commit` (ou o `rollback`) desta. Quem precisa dela, e por quê,
        está no BookController._get_locked_book.
        """
        return self.session.query(Book).filter(Book.book_key == book_key).with_for_update().first()

    def get_by_isbn(self, isbn: str) -> Book:
        return self.session.query(Book).filter(Book.isbn == isbn).first()

    def count_by_shelf(self, shelf: Shelf) -> int:
        """Quantos livros esta estante tem agora.

        `func.count` vira um `SELECT count(book.id)`: o banco conta e
        devolve UM número, em vez de mandar todas as linhas pra API
        contar com `len()`.
        """
        return self.session.query(func.count(Book.id)).filter(Book.shelf_id == shelf.id).scalar()

    def list_page(self, limit: int, offset: int, shelf: Shelf = None) -> list:
        query = self.session.query(Book)

        if shelf is not None:
            query = query.filter(Book.shelf_id == shelf.id)

        query = query.order_by(Book.created_at.desc(), Book.id.desc())

        return query.limit(limit + 1).offset(offset).all()
