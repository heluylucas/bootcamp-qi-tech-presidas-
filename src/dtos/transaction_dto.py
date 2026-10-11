from typing import Optional

from models import Account, LedgerEntry, Transaction
from utils.dates import to_utc_text


INCOMING_TYPES = ("DEPOSIT", "INVESTMENT_REDEEM")


def transaction_to_dict(transaction: Transaction, balance: int) -> dict:
    return {
        "transaction_key": transaction.transaction_key,
        "type": transaction.type,
        "amount": transaction.amount,
        "fee_amount": transaction.fee_amount,
        "description": transaction.description,
        "balance": balance,
        "created_at": to_utc_text(transaction.created_at),
    }


def entry_to_dict(entry: LedgerEntry) -> dict:
    transaction = entry.transaction
    return {
        "transaction_key": transaction.transaction_key,
        "type": transaction.type,
        "direction": entry.direction,
        "category": entry.category,
        "amount": entry.amount,
        "balance_after": entry.balance_after,
        "description": transaction.description,
        "counterparty_account_key": counterparty_key(transaction, entry.account_id),
        "business_date": transaction.business_date.isoformat(),
        "created_at": to_utc_text(entry.created_at),
    }


def receipt_to_dict(transaction: Transaction) -> dict:
    if transaction.type in INCOMING_TYPES:
        origin, destination = None, transaction.owner_account
    else:
        origin, destination = transaction.owner_account, transaction.destination_account

    return {
        "transaction_key": transaction.transaction_key,
        "type": transaction.type,
        "amount": transaction.amount,
        "fee_amount": transaction.fee_amount,
        "description": transaction.description,
        "origin_account_key": account_key_or_none(origin),
        "destination_account_key": account_key_or_none(destination),
        "business_date": transaction.business_date.isoformat(),
        "created_at": to_utc_text(transaction.created_at),
    }


def counterparty_key(transaction: Transaction, account_id: int) -> Optional[str]:
    if transaction.owner_account_id == account_id:
        return account_key_or_none(transaction.destination_account)

    return account_key_or_none(transaction.owner_account)


def account_key_or_none(account: Optional[Account]) -> Optional[str]:
    return account.account_key if account is not None else None
