from sqlalchemy import CHAR, CheckConstraint, Column, DateTime, Integer, String, UniqueConstraint, func
from models.base import Base


class Shelf(Base):
    """A tabela `shelf`, descrita em Python.

    ────────────────────────────────────────────────────────────────
    O `__table_args__` NÃO É DECORAÇÃO
    ────────────────────────────────────────────────────────────────
    As restrições existem no banco, escritas no database/database.sql.
    Repeti-las aqui serve pra que quem lê este arquivo saiba o que é
    proibido sem abrir o SQL: duas estantes não dividem o mesmo
    `code`, e `capacity` é sempre maior que zero. Se as duas
    descrições discordarem, quem manda é o banco — e a discordância é
    um bug esperando acontecer.

    Repare que a estante não sabe QUANTOS livros tem. Essa conta não é
    uma coluna: é uma consulta à tabela `book`, feita na hora em que
    alguém tenta pôr um livro aqui (veja o BookController). Guardar a
    lotação numa coluna daria dois lugares pra mesma verdade, e um dia
    eles discordariam.
    """

    __tablename__ = "shelf"

    id = Column(Integer, primary_key=True)
    shelf_key = Column(CHAR(36), nullable=False)
    code = Column(String(20), nullable=False)
    location = Column(String(255), nullable=False)
    capacity = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("shelf_key"),
        UniqueConstraint("code"),
        CheckConstraint("capacity > 0"),
    )
