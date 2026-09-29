from sqlalchemy import CHAR, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from models.base import Base
from models import Author, BookStatus, Member, Shelf


class Book(Base):
    """A tabela `book`, descrita em Python.

    ────────────────────────────────────────────────────────────────
    AS TRÊS CHAVES ESTRANGEIRAS NÃO SÃO IGUAIS
    ────────────────────────────────────────────────────────────────
    `author_id` é obrigatório: livro sem autor não existe. `shelf_id`
    aceita vazio: o livro pode estar cadastrado e ainda não ter lugar.
    `member_id` também aceita vazio, e o vazio quer dizer "ninguém está
    com ele". A diferença está no `nullable=` de cada uma, e o banco
    cobra as três.

    As três apontam pro `id` numérico, não para a `_key`. O cliente
    manda `author_key` (ou `member_key`) no corpo; quem traduz a chave
    no número é o controller, que busca o autor (ou o leitor) antes de
    gravar o livro.

    ────────────────────────────────────────────────────────────────
    O STATUS MORA EM OUTRA TABELA — E A HISTÓRIA, EM UMA TERCEIRA
    ────────────────────────────────────────────────────────────────
    É o desenho de três tabelas do repositório-base:

      • `book_status` — a lista fechada (`AVAILABLE`, `BORROWED`), com os
        `INSERT` no database/database.sql;
      • `book.status_id` — onde o livro está AGORA;
      • `book_status_event` — uma linha por cadastro e por transição,
        com o status e o instante. É o histórico que a coluna de texto
        de antes não guardava.

    Quem decide QUANDO o status muda é o controller; quem grava o status
    e o evento juntos é o `BookRepository.update_status`.

    ────────────────────────────────────────────────────────────────
    O STATUS E O LEITOR ANDAM JUNTOS — E QUEM COBRA É O CONTROLLER
    ────────────────────────────────────────────────────────────────
    Livro emprestado tem leitor; livro disponível não tem. Enquanto o
    status era texto nesta tabela, um CHECK cobrava isso. Com o status
    em outra tabela, a garantia foi pro controller — o porquê está no
    `BookController._change_status`.

    O evento não guarda o leitor: a tabela de evento da base só tem o
    status e o instante, e o `member_id` aqui continua dizendo só "com
    quem está agora".

    ────────────────────────────────────────────────────────────────
    O `lazy=` DAS ÚLTIMAS LINHAS
    ────────────────────────────────────────────────────────────────
    O DTO do livro devolve o status, `author_key`, `shelf_key` e
    `member_key`, que moram em outras tabelas. Numa listagem de 100
    livros, buscar o autor de cada um sob demanda seriam 100 consultas a
    mais (o problema N+1). Com `selectin`, o SQLAlchemy faz UMA consulta
    a mais por relação e traz todos de uma vez.

    O `status_events` fica no padrão de propósito, como na base: só o
    DTO de UM livro toca nele (o GET por chave e as respostas das
    rotas que mudam o livro). A listagem usa o resumo, sem a trilha.
    """

    __tablename__ = "book"

    id = Column(Integer, primary_key=True)
    book_key = Column(CHAR(36), nullable=False)
    status_id = Column(Integer, ForeignKey(BookStatus.id), nullable=False)
    author_id = Column(Integer, ForeignKey(Author.id), nullable=False)
    shelf_id = Column(Integer, ForeignKey(Shelf.id), nullable=True)
    member_id = Column(Integer, ForeignKey(Member.id), nullable=True)
    title = Column(String(255), nullable=False)
    isbn = Column(CHAR(13), nullable=False)
    year = Column(Integer, nullable=False)
    pages = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("book_key"),
        UniqueConstraint("isbn"),
    )

    status = relationship("BookStatus", foreign_keys=[status_id], lazy="selectin")
    author = relationship("Author", foreign_keys=[author_id], lazy="selectin")
    shelf = relationship("Shelf", foreign_keys=[shelf_id], lazy="selectin")
    member = relationship("Member", foreign_keys=[member_id], lazy="selectin")

    status_events = relationship(
        "BookStatusEvent",
        back_populates="book",
        order_by="asc(BookStatusEvent.event_datetime)",
    )
