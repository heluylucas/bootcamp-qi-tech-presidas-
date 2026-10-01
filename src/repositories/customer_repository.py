import uuid
from datetime import date
from typing import Optional

from database import Context
from models import Customer


class CustomerRepository:
    @staticmethod
    def create(context: Context, name: str, document_number: str, birth_date: date) -> Customer:
        customer = Customer(
            customer_key=str(uuid.uuid4()),
            name=name,
            document_number=document_number,
            birth_date=birth_date,
        )
        context.db_session.add(customer)
        
        context.db_session.flush()

        return customer

    @staticmethod
    def get_by_key(context: Context, customer_key: str) -> Optional[Customer]:
        return context.db_session.query(Customer).filter(Customer.customer_key == customer_key).first()

    @staticmethod
    def get_by_document_number(context: Context, document_number: str) -> Optional[Customer]:
        return context.db_session.query(Customer).filter(Customer.document_number == document_number).first()
