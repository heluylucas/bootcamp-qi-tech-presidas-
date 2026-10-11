from abc import ABCMeta

from database import get_context
from errors import AccountNotFound, CustomerNotFound, ProductNotFound
from models import Account, Customer, Product
from repositories import AccountRepository, CustomerRepository, ProductRepository
from utils.logger import get_logger


class BaseController(metaclass=ABCMeta):
    def __init__(self, class_name: str) -> None:
        self.context = get_context()
        self.session = self.context.get_or_create_session()
        self.logger = get_logger(class_name)

    def get_customer(self, customer_key: str) -> Customer:
        customer = CustomerRepository.get_by_key(self.context, customer_key)

        if customer is None:
            raise CustomerNotFound()

        return customer

    def get_owned_account(self, customer_key: str, account_key: str, for_update: bool = False) -> Account:
        customer = self.get_customer(customer_key)

        if for_update:
            account = AccountRepository.get_by_key_for_update(self.context, customer.id, account_key)
        else:
            account = AccountRepository.get_by_key(self.context, customer.id, account_key)

        if account is None:
            raise AccountNotFound()

        return account

    def get_product(self, product_key: str) -> Product:
        product = ProductRepository.get_by_key(self.context, product_key)

        if product is None:
            raise ProductNotFound()

        return product
