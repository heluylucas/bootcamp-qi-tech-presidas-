from datetime import timezone

from models import Customer


def customer_to_dict(customer: Customer) -> dict:
    return {
        "customer_key": customer.customer_key,
        "name": customer.name,
        # '123.456.789-09' sai como '***.456.789-**' (RN-GER-10).
        "document_number": f"***{customer.document_number[3:11]}-**",
        "birth_date": customer.birth_date.isoformat(),
        "created_at": customer.created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
