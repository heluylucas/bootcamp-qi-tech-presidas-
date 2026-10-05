from dtos.account_dto import to_utc_text
from models import Transaction


def transaction_to_dict(transaction: Transaction, balance: int) -> dict:
    """`balance` é o saldo da conta do caminho logo depois desta transação."""
    return {
        "transaction_key": transaction.transaction_key,
        "type": transaction.type.enumerator,
        "amount": transaction.amount,
        "fee_amount": transaction.fee_amount,
        "description": transaction.description,
        "balance": balance,
        "created_at": to_utc_text(transaction.created_at),
    }
