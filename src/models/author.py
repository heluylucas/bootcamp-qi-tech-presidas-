from sqlalchemy import CHAR, Column, DateTime, Integer, String, UniqueConstraint, func
from models.base import Base


class Author(Base):
    """A tabela `author`, descrita em Python.

    Model é a tradução da tabela pra dentro do código: uma classe por
    tabela, um atributo por coluna. Ele não tem regra de negócio, não
    busca nada e não sabe virar JSON — quem busca é o repository, quem
    vira JSON é o DTO. A única coisa que ele sabe é a forma da tabela.

    ────────────────────────────────────────────────────────────────
    DOIS IDENTIFICADORES, E CADA UM TEM UM DONO
    ────────────────────────────────────────────────────────────────
    O `id` é um número que o banco gera sozinho. É ele que aparece na
    chave estrangeira do `book`, e ele NUNCA sai na resposta da API —
    repare que o DTO não o exporta.

    O `author_key` é o UUID que o cliente recebe e usa pra voltar. Dois
    identificadores porque eles respondem a perguntas diferentes: o
    número é barato pro banco juntar tabelas; a chave é segura pro mundo
    de fora, porque não revela quantos autores existem nem deixa
    ninguém adivinhar o próximo somando um.

    As quatro tabelas deste projeto seguem o mesmo desenho, e é por isso
    que só este arquivo conta a história.
    """

    __tablename__ = "author"

    id = Column(Integer, primary_key=True)
    author_key = Column(CHAR(36), nullable=False)
    name = Column(String(255), nullable=False)
    nationality = Column(String(100), nullable=False)
    # O CPF do autor, com a máscara 000.000.000-00. É obrigatório e único
    # dentro desta tabela; a mesma pessoa pode ser autora e leitora.
    document_number = Column(CHAR(14), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("author_key"),
        UniqueConstraint("document_number"),
    )
