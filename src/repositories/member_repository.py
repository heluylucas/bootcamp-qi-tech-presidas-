from uuid import uuid4

from database import Context
from models import Member


class MemberRepository:
    """As consultas do leitor. Mesma forma do AuthorRepository, mais duas.

    As consultas a mais são o `get_by_email` e o `get_by_document_number`,
    que o MemberController usa pra recusar um e-mail ou um CPF repetido
    antes de tentar gravar.
    """

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, member_data: dict) -> Member:
        member = Member()

        member.member_key = str(uuid4())
        member.name = member_data["name"]
        member.email = member_data["email"]
        member.document_number = member_data["document_number"]

        self.session.add(member)
        return member

    def get_by_key(self, member_key: str) -> Member:
        return self.session.query(Member).filter(Member.member_key == member_key).first()

    def get_by_email(self, email: str) -> Member:
        return self.session.query(Member).filter(Member.email == email).first()

    def get_by_document_number(self, document_number: str) -> Member:
        return self.session.query(Member).filter(Member.document_number == document_number).first()

    def list_page(self, limit: int, offset: int) -> list:
        query = self.session.query(Member).order_by(Member.created_at.desc(), Member.id.desc())

        return query.limit(limit + 1).offset(offset).all()
