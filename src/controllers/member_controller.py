from controllers.base_controller import BaseController
from dtos import MemberDTO
from errors import DuplicatedDocumentNumber, DuplicatedMemberEmail, InvalidDocumentNumber, NotFoundMember
from repositories import MemberRepository
from utils.document_number import is_valid_cpf


class MemberController(BaseController):
    """As regras de negócio do leitor.

    Duas regras: o e-mail não se repete, e o CPF, obrigatório, precisa
    existir e não pode se repetir. Cada uma é conferida antes de gravar
    (veja o `create`).
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.member_repository = MemberRepository(self.context)

    def create(self, member_data: dict) -> dict:
        """Recusa e-mail ou CPF repetido.

        As perguntas `get_by_email` e `get_by_document_number` resolvem o
        caso comum: o valor já está no banco, e a API responde 409 sem
        tentar gravar. Antes delas, o CPF passa pela conta dos dígitos
        verificadores (422), que não depende do banco.

        O CPF é único DENTRO desta tabela, e só nela. O mesmo CPF pode
        estar num autor e num leitor, porque a mesma pessoa pode escrever
        um livro e pegar outro emprestado — por isso a pergunta vai ao
        MemberRepository, e não à tabela `author`.
        """
        self.logger.debug("Cadastrando um novo leitor")

        document_number = member_data["document_number"]
        email = member_data["email"]

        if not is_valid_cpf(document_number):
            raise InvalidDocumentNumber()

        if self.member_repository.get_by_email(email) is not None:
            raise DuplicatedMemberEmail()

        if self.member_repository.get_by_document_number(document_number) is not None:
            raise DuplicatedDocumentNumber()

        member = self.member_repository.create(member_data)

        member_dto = MemberDTO.only_obj_key(member)

        self.session.commit()

        return member_dto

    def get_by_key(self, member_key: str) -> dict:
        member = self.member_repository.get_by_key(member_key)

        if member is None:
            raise NotFoundMember(member_key)

        return MemberDTO.obj_to_dict(member)

    def get_list(self, limit: int, offset: int) -> dict:
        members_list = self.member_repository.list_page(limit, offset)

        is_last_page = True
        if len(members_list) > limit:
            is_last_page = False
            members_list = members_list[:-1]

        return {
            "members_list_dto": MemberDTO.list_obj_to_list_dict(members_list),
            "is_last_page": is_last_page,
        }
