from typing import List

from models import Book


class BookDTO:
    """O JSON do livro — e a travessia das chaves estrangeiras.

    Na TABELA, o livro aponta pro autor e pra estante pelo `id`
    numérico. Na RESPOSTA, ele aponta pela `_key`, que é o único
    identificador que o cliente conhece. Quem faz essa troca é o DTO,
    lendo `book.author.author_key` em vez de `book.author_id`.

    O `shelf_key` pode sair `null`: livro cadastrado sem lugar ainda. O
    `member_key` também: livro disponível não está com ninguém.
    """

    @staticmethod
    def obj_to_dict(book: Book) -> dict:
        """O livro INTEIRO, com a trilha de status do cadastro em diante.

        Cada linha de `book_status_event` vira um item de
        `status_events`, na ordem em que aconteceu, no formato da base:
        `status` e `event_datetime`.
        """
        dto = BookDTO.obj_to_simplified_dict(book)
        dto["status_events"] = []

        for status_event in book.status_events:
            status_event_dto = dict()
            status_event_dto["status"] = status_event.status.enumerator
            status_event_dto["event_datetime"] = status_event.event_datetime.isoformat()

            dto["status_events"].append(status_event_dto)

        return dto

    @staticmethod
    def obj_to_simplified_dict(book: Book) -> dict:
        """O livro sem a trilha — o resumo que a listagem devolve.

        A trilha mora em outra tabela, e montá-la para cada livro da
        página custaria uma consulta por livro. Como na base, quem lista
        recebe o resumo; quem abre um livro recebe a trilha junto.
        """
        dto = dict()
        dto["book_key"] = book.book_key
        dto["title"] = book.title
        dto["isbn"] = book.isbn
        dto["year"] = book.year
        dto["pages"] = book.pages
        dto["author_key"] = book.author.author_key

        if book.shelf is None:
            dto["shelf_key"] = None
        else:
            dto["shelf_key"] = book.shelf.shelf_key

        dto["status"] = book.status.enumerator

        if book.member is None:
            dto["member_key"] = None
        else:
            dto["member_key"] = book.member.member_key

        return dto

    @staticmethod
    def list_obj_to_list_dict(books_list: List[Book]) -> List[dict]:
        books_dict_list = []

        for book in books_list:
            books_dict_list.append(BookDTO.obj_to_simplified_dict(book))

        return books_dict_list

    @staticmethod
    def only_obj_key(book: Book) -> dict:
        dto = dict()
        dto["book_key"] = book.book_key
        dto["status"] = book.status.enumerator

        return dto
