from dtos.account_dto import to_utc_text
from models import LedgerEntry, Transaction


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


def entry_to_dict(entry: LedgerEntry) -> dict:
    """Uma linha do extrato, do ponto de vista da conta do lançamento (RN-MOV-12)."""
    transaction = entry.transaction
    return {
        "transaction_key": transaction.transaction_key,
        "type": transaction.type.enumerator,
        "direction": entry.direction,
        "category": entry.category,
        "amount": entry.amount,
        "balance_after": entry.balance_after,
        "description": transaction.description,
        "counterparty_account_key": counterparty_key(transaction, entry.account_id),
        "created_at": to_utc_text(entry.created_at),
    }


def receipt_to_dict(transaction: Transaction) -> dict:
    """O comprovante (RN-MOV-13). Sem saldo: o destino não pode ver o saldo da origem."""
    return {
        "transaction_key": transaction.transaction_key,
        "type": transaction.type.enumerator,
        "amount": transaction.amount,
        "fee_amount": transaction.fee_amount,
        "description": transaction.description,
        "origin_account_key": account_key_or_none(transaction.origin_account),
        "destination_account_key": account_key_or_none(transaction.destination_account),
        "created_at": to_utc_text(transaction.created_at),
    }


def counterparty_key(transaction: Transaction, account_id: int):
    """A OUTRA conta da transação; None quando o dinheiro veio ou foi para fora (depósito, saque)."""
    if transaction.origin_account_id == account_id:
        return account_key_or_none(transaction.destination_account)

    return account_key_or_none(transaction.origin_account)


def account_key_or_none(account):
    return account.account_key if account is not None else None
