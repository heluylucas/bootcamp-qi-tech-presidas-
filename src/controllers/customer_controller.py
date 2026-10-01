from datetime import date

from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos.customer_dto import customer_to_dict
from errors import (
    CustomerNotFound,
    DocumentAlreadyRegistered,
    InvalidDocumentNumber,
    InvalidSchema,
    UnderageCustomer,
)
from repositories import CustomerRepository
from utils.document_number import is_valid_cpf


MINIMUM_AGE = 18


class CustomerController(BaseController):
    def __init__(self) -> None:
        super().__init__(__name__)

    def create(self, payload: dict) -> dict:
        # O schema só confere a cara AAAA-MM-DD; "2000-02-30" passa por lá
        # e só aqui se descobre que o dia não existe.
        try:
            birth_date = date.fromisoformat(payload["birth_date"])
        except ValueError:
            raise InvalidSchema("birth_date is not a valid date")

        document_number = normalize_cpf(payload["document_number"])

        if not is_valid_cpf(document_number):
            raise InvalidDocumentNumber()

        if age_on(date.today(), birth_date) < MINIMUM_AGE:
            raise UnderageCustomer()

        if CustomerRepository.get_by_document_number(self.context, document_number) is not None:
            raise DocumentAlreadyRegistered()

        # Dois cadastros do mesmo CPF ao mesmo tempo passam os dois pela
        # busca acima; o UNIQUE do banco recusa o segundo no flush.
        try:
            customer = CustomerRepository.create(self.context, payload["name"], document_number, birth_date)
        except IntegrityError:
            raise DocumentAlreadyRegistered()

        self.session.commit()
        return customer_to_dict(customer)

    def get(self, customer_key: str) -> dict:
        customer = CustomerRepository.get_by_key(self.context, customer_key)

        if customer is None:
            raise CustomerNotFound()

        return customer_to_dict(customer)


def normalize_cpf(document_number: str) -> str:
    """'12345678909' e '123.456.789-09' viram '123.456.789-09' (RN-CLI-04)."""
    digits = "".join(character for character in document_number if character.isdigit())
    return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"


def age_on(today: date, birth_date: date) -> int:
    """Anos completos. Nascimento no futuro dá idade negativa, e cai na mesma recusa."""
    birthday_not_reached = (today.month, today.day) < (birth_date.month, birth_date.day)
    return today.year - birth_date.year - birthday_not_reached
