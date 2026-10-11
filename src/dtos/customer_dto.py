from models import Customer
from utils.dates import to_utc_text


def customer_to_dict(customer: Customer) -> dict:
    return {
        "customer_key": customer.customer_key,
        "name": customer.name,
        "document_number": f"***{customer.document_number[3:11]}-**",
        "birth_date": customer.birth_date.isoformat(),
        "created_at": to_utc_text(customer.created_at),
    }
