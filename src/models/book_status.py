from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func
from models.base import Base


class BookStatus(Base):
    """A tabela de referência dos status do livro.

    São duas linhas, e elas nascem com o banco: os `INSERT` estão no
    database/database.sql, logo depois do `CREATE TABLE`. Ninguém cria
    status pela API — o livro só aponta pra uma destas linhas.

    O código nunca procura um status pelo `id`, e sim pelo `enumerator`:
    o número é do banco e pode mudar de uma instalação pra outra; o
    texto é o contrato. As duas constantes abaixo são os únicos valores
    que o `enumerator` pode ter.
    """

    __tablename__ = "book_status"

    id = Column(Integer, primary_key=True)
    enumerator = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("enumerator"),)

    AVAILABLE = "AVAILABLE"
    BORROWED = "BORROWED"
