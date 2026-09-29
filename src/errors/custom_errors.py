from errors import QIException


class NotFoundAuthor(QIException):
    code = "QIT001012"

    def __init__(self, author_key) -> None:
        title = "Author not Found"
        http_status = 404
        description = f"Author with key {author_key} was not found."
        translation = f"O autor com chave {author_key} não foi encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class NotFoundShelf(QIException):
    code = "QIT001013"

    def __init__(self, shelf_key) -> None:
        title = "Shelf not Found"
        http_status = 404
        description = f"Shelf with key {shelf_key} was not found."
        translation = f"A estante com chave {shelf_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedShelfCode(QIException):
    """Já existe uma estante com este código.

    409 Conflict: o pedido está correto em si, e o que impede é o que já
    está no banco — conflito com o que já existe, não erro de quem pediu.
    """

    code = "QIT001014"

    def __init__(self, shelf_code) -> None:
        title = "Shelf code already registered"
        http_status = 409
        description = f"There is already a shelf with the code {shelf_code}."
        translation = f"Já existe uma estante com o código {shelf_code}."
        super().__init__(title, self.code, http_status, description, translation)


class NotFoundBook(QIException):
    code = "QIT001015"

    def __init__(self, book_key) -> None:
        title = "Book not Found"
        http_status = 404
        description = f"Book with key {book_key} was not found."
        translation = f"O livro com chave {book_key} não foi encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedIsbn(QIException):
    """Este ISBN já está cadastrado.

    Mesma família do DuplicatedShelfCode: 409, conflito com o que já
    existe. A diferença é onde a recusa acontece — ANTES de a API
    consultar o catálogo. Não faz sentido perguntar ao serviço de fora
    sobre um livro que já temos (veja o BookController.create).
    """

    code = "QIT001016"

    def __init__(self, isbn) -> None:
        title = "ISBN already registered"
        http_status = 409
        description = f"There is already a book with the ISBN {isbn}."
        translation = "Já existe um livro cadastrado com este ISBN."
        super().__init__(title, self.code, http_status, description, translation)


class ShelfFull(QIException):
    """A estante já tem tantos livros quanto a capacidade dela.

    409, e não 422: o pedido seria aceito numa estante com vaga. O que
    impede é o estado do banco agora — os livros que já estão lá.
    """

    code = "QIT001017"

    def __init__(self, shelf_code, capacity) -> None:
        title = "Shelf is full"
        http_status = 409
        description = f"The shelf {shelf_code} is full (capacity: {capacity})."
        translation = f"A estante {shelf_code} está lotada (capacidade: {capacity})."
        super().__init__(title, self.code, http_status, description, translation)


class NotFoundIsbnInCatalog(QIException):
    """O catálogo de ISBN respondeu que não conhece este ISBN.

    404, como o NotFoundBook lá em cima, e com outro código de
    propósito. Os dois dizem "não achei", mas em lugares diferentes: o
    QIT001015 quer dizer que o livro não existe NESTA API; este quer
    dizer que o serviço de fora não tem registro do ISBN. Quem integra
    precisa separar os dois casos, e só o `code` separa — o status HTTP
    é o mesmo.
    """

    code = "QIT001018"

    def __init__(self, isbn) -> None:
        title = "ISBN not found in catalog"
        http_status = 404
        description = f"The ISBN catalog has no record of {isbn}."
        translation = "O catálogo de ISBN não conhece este ISBN."
        super().__init__(title, self.code, http_status, description, translation)


class CatalogUnavailable(QIException):
    """O catálogo de ISBN não deu uma resposta que desse pra usar.

    502 Bad Gateway, e não 500: 500 diz "EU quebrei"; 502 diz "quem eu
    chamei não me respondeu direito". Caem aqui dois casos: a conexão
    caiu ou estourou o timeout, ou o catálogo respondeu um status que
    esta API não sabe tratar (um 500 dele, por exemplo). Com 502, quem
    olha o alerta sabe que a investigação começa do outro lado da
    fronteira.
    """

    code = "QIT001019"

    def __init__(self, reason) -> None:
        title = "ISBN catalog unavailable"
        http_status = 502
        description = f"The ISBN catalog did not give a usable answer: {reason}."
        translation = "O catálogo de ISBN não respondeu. Tente novamente em instantes."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidBookStatus(QIException):
    """O livro não está no status de onde esta transição parte.

    Emprestar só parte de AVAILABLE; devolver só parte de BORROWED.
    Emprestar duas vezes seguidas não é erro de digitação — é um pedido
    que o estado atual do livro não permite, e por isso é 409.
    """

    code = "QIT001020"

    def __init__(self, book_key, current_status, target_status) -> None:
        title = "Invalid book status transition"
        http_status = 409
        description = f"Book {book_key} is {current_status} and cannot change to {target_status}."
        translation = f"O livro está {current_status} e não pode passar para {target_status}."
        super().__init__(title, self.code, http_status, description, translation)


class NotFoundMember(QIException):
    code = "QIT001021"

    def __init__(self, member_key) -> None:
        title = "Member not Found"
        http_status = 404
        description = f"Member with key {member_key} was not found."
        translation = f"O leitor com chave {member_key} não foi encontrado."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedMemberEmail(QIException):
    """Já existe um leitor com este e-mail.

    Mesma família do DuplicatedShelfCode: 409, conflito com o que já
    existe. A mensagem não repete o e-mail de propósito: é dado pessoal,
    e a resposta de erro acaba em log.
    """

    code = "QIT001022"

    def __init__(self) -> None:
        title = "Member email already registered"
        http_status = 409
        description = "There is already a member with this email."
        translation = "Já existe um leitor cadastrado com este e-mail."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidDocumentNumber(QIException):
    """O CPF tem o formato certo e não existe.

    422, e não 400, de propósito: 400 quer dizer "não consegui ler o seu
    pedido" — e o formato já é cobrado pelo schema, que responde 400.
    Aqui a API leu, entendeu, e o valor é que não pode existir: os dois
    últimos dígitos não batem com a conta. A diferença está explicada em
    src/utils/document_number.py.

    A mensagem não repete o número: CPF é dado pessoal, e a resposta de
    erro acaba em log.
    """

    code = "QIT001023"

    def __init__(self) -> None:
        title = "Invalid Document Number"
        http_status = 422
        description = "The document number is not a valid CPF."
        translation = "O CPF informado não é válido."
        super().__init__(title, self.code, http_status, description, translation)


class DuplicatedDocumentNumber(QIException):
    """Este CPF já está cadastrado na tabela onde se tentou gravá-lo.

    Mesma família do DuplicatedMemberEmail: 409, conflito com o que já
    existe, e a mensagem sem o número, porque é dado pessoal.

    Serve ao autor e ao leitor, e por isso a mensagem não diz qual dos
    dois: quem chamou sabe em que endpoint bateu. A unicidade é por
    tabela — o mesmo CPF num autor e num leitor não é conflito.
    """

    code = "QIT001024"

    def __init__(self) -> None:
        title = "Document Number already registered"
        http_status = 409
        description = "This document number is already registered."
        translation = "Este CPF já está cadastrado."
        super().__init__(title, self.code, http_status, description, translation)


class BookAlreadyOnShelf(QIException):
    """O livro já está na estante para onde se pediu movê-lo.

    409: o pedido é bem formado, e o que o impede é o estado atual do
    livro — mover para onde ele já está não move nada. Responder 200
    esconderia de quem chamou que o pedido não teve efeito.
    """

    code = "QIT001025"

    def __init__(self, book_key, shelf_code) -> None:
        title = "Book already on shelf"
        http_status = 409
        description = f"Book {book_key} is already on the shelf {shelf_code}."
        translation = f"O livro já está na estante {shelf_code}."
        super().__init__(title, self.code, http_status, description, translation)
