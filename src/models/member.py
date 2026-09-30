from sqlalchemy import CHAR, Column, DateTime, Integer, String, UniqueConstraint, func
from models.base import Base


class Member(Base):
    """A tabela `member`, descrita em Python: o leitor da biblioteca.

    Mesmo desenho do Author — `id` pra dentro, `member_key` pra fora. A
    regra própria dele é o `email`, que não se repete: é o que separa
    dois leitores com o mesmo nome. O UNIQUE mora no banco e é repetido
    aqui pra quem lê este arquivo saber sem abrir o SQL.

    O leitor não sabe quais livros estão com ele. Quem guarda isso é o
    livro, na coluna `member_id` (veja o Book).
    """

    __tablename__ = "member"

    id = Column(Integer, primary_key=True)
    member_key = Column(CHAR(36), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    # O CPF do leitor, com a máscara 000.000.000-00: obrigatório e único
    # dentro desta tabela, o mesmo desenho do Author.document_number.
    document_number = Column(CHAR(14), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("member_key"),
        UniqueConstraint("email"),
        UniqueConstraint("document_number"),
    )
