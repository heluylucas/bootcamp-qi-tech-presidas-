from requests.exceptions import RequestException

from connectors import CatalogConnector
from controllers.base_controller import BaseController
from dtos import BookDTO
from errors import (
    BookAlreadyOnShelf,
    CatalogUnavailable,
    DuplicatedIsbn,
    InvalidBookStatus,
    NotFoundAuthor,
    NotFoundBook,
    NotFoundIsbnInCatalog,
    NotFoundMember,
    NotFoundShelf,
    ShelfFull,
)
from models import Book, BookStatus, Member, Shelf
from repositories import AuthorRepository, BookRepository, MemberRepository, ShelfRepository


class BookController(BaseController):
    """As regras de negócio do livro — o controller mais cheio do projeto.

    São três regras, e cada uma ensina uma coisa diferente:

      • o CADASTRO atravessa a fronteira: o título, o ano e as páginas
        vêm do catálogo de ISBN (`create`);
      • a ESTANTE tem capacidade, e a conta de lotação precisa ser feita
        dentro da mesma transação que põe o livro lá (`_check_capacity`);
      • o STATUS só anda em duas direções: AVAILABLE → BORROWED →
        AVAILABLE, e o LEITOR anda junto com ele (`_change_status`, com o
        livro travado por `_get_locked_book`).
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.book_repository = BookRepository(self.context)
        self.author_repository = AuthorRepository(self.context)
        self.shelf_repository = ShelfRepository(self.context)
        self.member_repository = MemberRepository(self.context)
        self.catalog_connector = CatalogConnector()

    def create(self, book_data: dict) -> dict:
        """Confere o que dá pra conferir aqui, e só então pergunta ao catálogo.

        A ordem é a regra. Tudo que se responde olhando o NOSSO banco vem
        primeiro — o ISBN já existe? o autor existe? a estante existe? —,
        porque é barato e porque não faz sentido incomodar o serviço de
        fora por um pedido que vai ser recusado de qualquer jeito. O ISBN
        repetido, em especial, sai com 409 sem o catálogo receber nada.

        Só depois vem a travessia (`_fetch_from_catalog`), e só depois
        dela a conta de lotação. A trava da estante é a ÚLTIMA coisa
        antes de gravar: segurar uma linha travada enquanto se espera um
        serviço de fora (até 5 segundos, o timeout do connector) faria
        toda outra requisição daquela estante esperar junto.
        """
        self.logger.debug("Cadastrando um novo livro")

        isbn = book_data["isbn"]
        author_key = book_data["author_key"]
        shelf_key = book_data.get("shelf_key")

        if self.book_repository.get_by_isbn(isbn) is not None:
            raise DuplicatedIsbn(isbn)

        author = self.author_repository.get_by_key(author_key)

        if author is None:
            raise NotFoundAuthor(author_key)

        shelf = None

        if shelf_key is not None:
            shelf = self._get_shelf(shelf_key)

        catalog_data = self._fetch_from_catalog(isbn)

        if shelf is not None:
            self._check_capacity(shelf)

        book = self.book_repository.create(isbn, catalog_data, author, shelf)

        book_dto = BookDTO.only_obj_key(book)

        self.session.commit()

        return book_dto

    def get_by_key(self, book_key: str) -> dict:
        book = self._get_book(book_key)

        return BookDTO.obj_to_dict(book)

    def get_list(self, limit: int, offset: int, shelf_key: str = None) -> dict:
        """A página pedida, com o filtro de estante se ele vier.

        Filtrar por uma estante que não existe responde 404, e não uma
        lista vazia. Lista vazia diria "essa estante não tem livros" — e a
        verdade é que a pergunta não tinha resposta possível.
        """
        shelf = None

        if shelf_key is not None:
            shelf = self._get_shelf(shelf_key)

        books_list = self.book_repository.list_page(limit, offset, shelf)

        is_last_page = True
        if len(books_list) > limit:
            is_last_page = False
            books_list = books_list[:-1]

        return {
            "books_list_dto": BookDTO.list_obj_to_list_dict(books_list),
            "is_last_page": is_last_page,
        }

    def move_to_shelf(self, book_key: str, shelf_key: str) -> dict:
        """Move o livro para outra estante, se ela tiver vaga.

        Pedir a estante onde o livro já está responde 409 com o
        QIT001025: o pedido não move nada, e quem chamou precisa saber
        disso. A conferência vem ANTES do `_check_capacity` por dois
        motivos: não faz sentido travar e contar uma estante para não
        mover nada, e, numa estante cheia, o próprio livro entraria na
        conta e a resposta sairia como "lotada" — o motivo errado.
        """
        book = self._get_book(book_key)
        shelf = self._get_shelf(shelf_key)

        if book.shelf_id == shelf.id:
            raise BookAlreadyOnShelf(book.book_key, shelf.code)

        self._check_capacity(shelf)

        self.book_repository.update_shelf(book, shelf)

        book_dto = BookDTO.only_obj_key(book)
        self.session.commit()

        return book_dto

    def borrow(self, book_key: str, member_key: str) -> dict:
        """Empresta o livro para o leitor do corpo.

        O leitor é conferido ANTES da trava: se ele não existe, a
        resposta é 404 sem a linha do livro ter sido segurada por ninguém.
        """
        member = self.member_repository.get_by_key(member_key)

        if member is None:
            raise NotFoundMember(member_key)

        book = self._get_locked_book(book_key)

        return self._change_status(book, BookStatus.AVAILABLE, BookStatus.BORROWED, member)

    def return_book(self, book_key: str) -> dict:
        book = self._get_locked_book(book_key)

        return self._change_status(book, BookStatus.BORROWED, BookStatus.AVAILABLE, None)

    def _change_status(self, book: Book, from_status: str, to_status: str, member: Member) -> dict:
        """Uma transição só é aceita partindo do status certo.

        Emprestar e devolver são a MESMA regra lida em sentidos opostos,
        e por isso moram num método só: o que muda entre as duas é de
        onde se parte, aonde se chega e quem fica com o livro — o leitor
        no empréstimo, ninguém na devolução.

        O livro emprestado continua na estante dele, e continua contando
        na lotação: a vaga fica reservada pra quando ele voltar.

        ────────────────────────────────────────────────────────────────
        "EMPRESTADO TEM LEITOR; DISPONÍVEL NÃO TEM" — QUEM GARANTE É ESTE MÉTODO
        ────────────────────────────────────────────────────────────────
        Com o status numa coluna de texto do `book`, um CHECK cobrava a
        regra no banco. Com o status em `book_status`, um CHECK não
        alcança o `enumerator`: ele só enxerga a própria linha, e a
        linha do livro tem só o `status_id`. Sobraram duas saídas no
        banco, e as duas foram recusadas:

          • CHECK sobre o número (`(status_id = 2) = ...`) — amarra a
            regra a um id que o banco sorteou no `INSERT`;
          • FK composta com uma coluna `requires_member` em `book_status`
            e uma cópia dela no `book` — duas colunas que a base não tem,
            só pra carregar a regra até o CHECK.

        A garantia fica aqui: o livro chega travado pelo
        `_get_locked_book`, a origem é conferida, e status, leitor e
        evento são gravados juntos pelo `update_loan` e salvos num único
        `commit`. `to_status` e `member` andam aos pares nos dois únicos
        chamadores: BORROWED com leitor, AVAILABLE com `None`.
        """
        if book.status.enumerator != from_status:
            raise InvalidBookStatus(book.book_key, book.status.enumerator, to_status)

        self.book_repository.update_loan(book, to_status, member)

        book_dto = BookDTO.only_obj_key(book)
        self.session.commit()

        return book_dto

    def _get_locked_book(self, book_key: str) -> Book:
        """O livro, travado até o `commit` — pra que dois empréstimos não passem juntos.

        ────────────────────────────────────────────────────────────────
        POR QUE EMPRESTAR PRECISA DE TRAVA
        ────────────────────────────────────────────────────────────────
        A regra "só empresta o que está AVAILABLE" é uma pergunta seguida
        de uma gravação, e o perigo mora entre as duas — o mesmo da
        lotação da estante (veja o `_check_capacity`). Dois leitores
        pedindo o mesmo livro ao mesmo tempo:

            requisição A (Capitu): lê → AVAILABLE. Pode.
            requisição B (Bento):  lê → AVAILABLE. Pode.
            requisição A: grava BORROWED, leitor Capitu. 200.
            requisição B: grava BORROWED, leitor Bento.  200.

        Sem trava, os dois recebem 200 e o livro fica no nome de Bento —
        mas quem saiu com ele foi Capitu. O CHECK do banco não pega isso:
        BORROWED com leitor é um estado válido; o que está errado é QUAL
        leitor.

        O `get_by_key_for_update` vira `SELECT ... FOR UPDATE`. Quando B
        chega, fica parada na trava até A dar `commit`; aí lê BORROWED e
        leva 409. A devolução usa a mesma trava, pelo mesmo motivo: uma
        devolução e um empréstimo cruzados não podem ler o mesmo estado.

        Por isso quem chama este método não dá `commit` antes de gravar:
        a trava vale enquanto a transação estiver aberta.
        """
        book = self.book_repository.get_by_key_for_update(book_key)

        if book is None:
            raise NotFoundBook(book_key)

        return book

    def _check_capacity(self, shelf: Shelf) -> None:
        """Recusa com 409 se a estante já está cheia — sem deixar brecha.

        ────────────────────────────────────────────────────────────────
        POR QUE A CONTAGEM E A GRAVAÇÃO FICAM NA MESMA TRANSAÇÃO
        ────────────────────────────────────────────────────────────────
        A regra parece uma linha: "se a estante tem menos livros que a
        capacidade, põe mais um". O perigo está no que acontece ENTRE a
        pergunta e a gravação.

        Imagine uma estante com capacidade 10 e 9 livros, e duas
        requisições chegando juntas, cada uma querendo pôr um livro lá:

            requisição A: conta → 9. Tem vaga.
            requisição B: conta → 9. Tem vaga.
            requisição A: grava. Agora são 10.
            requisição B: grava. Agora são 11.

        As duas perguntaram certo e as duas gravaram — e a estante ficou
        com 11. Nenhuma das duas errou sozinha; o erro está no intervalo.

        A saída é travar a estante ANTES de contar. O
        `get_by_key_for_update` vira um `SELECT ... FOR UPDATE`: a linha
        da estante fica reservada pra esta transação até o `commit`.
        Quando B chega, ela fica parada na trava até A terminar — e aí
        conta 10, e recusa.

        É por isso que este método não dá `commit`. A trava vale enquanto
        a transação estiver aberta, e quem fecha é o método que chamou
        este, depois de gravar o livro. Se este método desse `commit`
        logo depois de contar, a trava sumiria antes da gravação, e o
        intervalo voltaria.
        """
        locked_shelf = self.shelf_repository.get_by_key_for_update(shelf.shelf_key)

        occupancy = self.book_repository.count_by_shelf(locked_shelf)

        if occupancy >= locked_shelf.capacity:
            raise ShelfFull(locked_shelf.code, locked_shelf.capacity)

    def _fetch_from_catalog(self, isbn: str) -> dict:
        """Pergunta ao catálogo o que ele sabe deste ISBN.

        O connector devolve a resposta como veio; quem decide o que cada
        status significa é este método:

          200            os dados seguem pro cadastro;
          404            o catálogo não conhece o ISBN: 404 com o
                         QIT001018, pra não confundir com o QIT001015;
          qualquer outro não dá pra usar: 502 com o QIT001019.

        E há o caso em que não chega resposta nenhuma — conexão caída ou
        timeout. Aí o `requests` levanta, e a exceção vira o mesmo 502.
        Sem este `except`, ela subiria até o handler genérico e sairia
        como 500: a API assumindo a culpa por um problema do outro lado.
        """
        try:
            response = self.catalog_connector.get_by_isbn(isbn)
        except RequestException as exception:
            self.logger.error(f"Catálogo sem resposta para o ISBN {isbn}: {exception}")
            raise CatalogUnavailable("no response")

        if response.status == 404:
            raise NotFoundIsbnInCatalog(isbn)

        if response.status != 200:
            self.logger.error(f"Catálogo respondeu {response.status} para o ISBN {isbn}")
            raise CatalogUnavailable(f"unexpected status {response.status}")

        if response.json is None:
            raise CatalogUnavailable("response without a JSON body")

        return response.json

    def _get_book(self, book_key: str) -> Book:
        book = self.book_repository.get_by_key(book_key)

        if book is None:
            raise NotFoundBook(book_key)

        return book

    def _get_shelf(self, shelf_key: str) -> Shelf:
        shelf = self.shelf_repository.get_by_key(shelf_key)

        if shelf is None:
            raise NotFoundShelf(shelf_key)

        return shelf
